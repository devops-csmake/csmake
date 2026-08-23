# <copyright>
# (c) Copyright 2025, 2026 Autumn Patterson
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
import glob
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile

from CsmakeCore.CsmakeModule import CsmakeModule
from CsmakeCore import WheelWriter


class CsmakeModulePackager(CsmakeModule):
    """Purpose: Build a .csm package for the csmake module registry.

       A .csm file is a zip archive containing:
           csmake-manifest.json  — embedded per-file SHA256 checksums + metadata
           <name>-<version>.dist-info/  — PEP 427 wheel metadata (METADATA,
                                          WHEEL, RECORD, top_level.txt)
           <files as declared in include>

       Making the archive wheel-compatible means one artifact is hostable in
       any URL-addressable store (S3, nginx, an Artifactory generic repo)
       and openable by standard Python tooling, without adopting PyPI/pip as
       the installer -- csmake keeps its own install path (unzip, two-step
       hash verify, seed sys.path).  See docs/MODULE_ECOSYSTEM_DESIGN.md.

       The manifest enables a two-step integrity check on install:
           1. sha256(downloaded .csm) == SHA256 recorded in the registry index
           2. sha256(each extracted file) == manifest entry

       After building, the SHA256 of the .csm and a ready-to-paste registry
       index entry are printed to the build log.

       Type: Module   Library: csmake (core)
       Phases:
           package - Build the .csm package
           clean, package_clean - Remove the result directory
       Options:
           result     - Directory to write the .csm file
           include    - File glob patterns relative to the build directory,
                        one per line (comma or newline separated).  Example:
                            CsmakeModules/*.py,
                            GHActionsLibrary/*.py
           dependencies - (optional) csmake registry package dependencies,
                        one per line, spec format is pkgname[>=|==|<=]version.
                        Example:
                            csmake-node-runtime>=1.0.0,
                            csmake-docker-runtime>=1.0.0
           tag        - (OPTIONAL) wheel compatibility tag for the embedded
                        dist-info.  Default: py2.py3-none-any (csmake
                        modules are pure Python, cross-version source).
           registry-checkout - (OPTIONAL) path to a local csmake-registry
                        checkout.  When set, the index entry is merged
                        directly into <path>/index/<name>.json on disk
                        (creating it if needed) instead of only being
                        logged.  Opening the PR against the registry
                        remains a separate, explicit step.
    """

    REQUIRED_OPTIONS = ['result', 'include']

    DEFAULT_TAG = 'py2.py3-none-any'

    # ------------------------------------------------------------------ #

    def package(self, options):
        meta     = self.metadata._getMetadataDefinitions()
        name     = meta.get('name', 'unnamed')
        version  = self.metadata._getDefaultDefinedVersion('.')
        desc     = meta.get('description', '')

        # ── Parse dependencies ────────────────────────────────────────
        deps = {}
        for line in re.split(r'[,\n]+', options.get('dependencies', '')):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^([A-Za-z0-9_-]+)(.*)', line)
            if m:
                pkg_dep  = m.group(1)
                spec_dep = m.group(2).strip()
                deps[pkg_dep] = spec_dep if spec_dep else '*'

        # ── Glob include patterns ─────────────────────────────────────
        file_list = []
        for pattern in re.split(r'[,\n]+', options.get('include', '')):
            pattern = pattern.strip()
            if not pattern:
                continue
            matched = sorted(glob.glob(pattern))
            if not matched:
                self.log.warning(
                    "CsmakeModulePackager: no files matched pattern '%s'",
                    pattern)
            for fpath in matched:
                if os.path.isfile(fpath) and fpath not in file_list:
                    file_list.append(fpath)

        if not file_list:
            self.log.error(
                "CsmakeModulePackager: no files to package — "
                "check 'include' patterns")
            self.log.failed()
            return False

        # ── Compute per-file SHA256 and read bytes (shared with dist-info) ──
        file_bytes  = {}
        file_hashes = {}
        for fpath in file_list:
            # Archive path: strip any leading ./ or / so it's always relative
            archive_path = fpath.lstrip('./').lstrip('/')
            with open(fpath, 'rb') as f:
                data = f.read()
            file_bytes[archive_path] = data
            file_hashes[archive_path] = 'sha256:' + hashlib.sha256(data).hexdigest()

        # ── Build csmake-manifest.json ────────────────────────────────
        manifest = {
            'name'        : name,
            'version'     : version,
            'description' : desc,
            'dependencies': deps,
            'files'       : file_hashes,
        }
        manifest_bytes = json.dumps(
            manifest, indent=2, sort_keys=True).encode('utf-8')

        # ── Wheel-compatible dist-info (see WheelWriter / design doc) ──
        authors = []
        packager = meta.get('packager')
        if packager:
            m = re.match(r'^(?P<name>.*?)\s*<(?P<email>[^<>]+)>\s*$', packager)
            if m:
                authors.append((m.group('name').strip(), m.group('email')))
            else:
                authors.append((packager.strip(), None))

        classifiers = [
            line.strip()
            for line in meta.get('classifiers', '').split('\n')
            if line.strip()
        ]

        dist_info_files = WheelWriter.build_dist_info(
            name, version, file_bytes,
            description=desc,
            keywords=meta.get('keywords') or None,
            homepage=meta.get('homepage') or None,
            authors=authors,
            classifiers=classifiers,
            tag=options.get('tag', self.DEFAULT_TAG),
            generator='csmake (CsmakeModulePackager)')

        # ── Write .csm (zip) ──────────────────────────────────────────
        result_dir = options['result']
        try:
            os.makedirs(result_dir)
        except OSError:
            pass

        csm_filename = '%s-%s.csm' % (name, version)
        csm_path     = os.path.join(result_dir, csm_filename)

        # Write to a temp file first for atomicity
        fd, tmp_path = tempfile.mkstemp(
            suffix='.csm', dir=result_dir)
        os.close(fd)
        try:
            def _write_archive(compression):
                with zipfile.ZipFile(tmp_path, 'w', compression) as zf:
                    # Manifest FIRST for fast extraction
                    zf.writestr('csmake-manifest.json', manifest_bytes)
                    for archive_path, data in file_bytes.items():
                        zf.writestr(archive_path, data)
                    for archive_path, data in dist_info_files.items():
                        zf.writestr(archive_path, data)
            try:
                _write_archive(zipfile.ZIP_DEFLATED)
            except RuntimeError:
                # zlib not available — fall back to stored
                _write_archive(zipfile.ZIP_STORED)

            os.replace(tmp_path, csm_path)
        except Exception as e:
            self.log.exception(
                "CsmakeModulePackager: failed to write '%s': %s",
                csm_path, e)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            self.log.failed()
            return False

        # ── Compute zip-level SHA256 ──────────────────────────────────
        zip_sha256 = _sha256_file(csm_path)

        index_entry = {
            version: {
                'url': (
                    'https://github.com/devops-csmake/%s'
                    '/releases/download/v%s/%s'
                ) % (name, version, csm_filename),
                'sha256': zip_sha256,
                'dependencies': deps,
            }
        }

        # ── Report ────────────────────────────────────────────────────
        self.log.info("Built: %s", csm_path)
        self.log.info("File count: %d + manifest + dist-info", len(file_list))
        self.log.info("SHA256: %s", zip_sha256)
        self.log.info(
            "Paste into csmake-registry/index/%s.json versions block:\n%s",
            name, json.dumps(index_entry, indent=2))

        # ── Optionally merge directly into a local registry checkout ───
        checkout = options.get('registry-checkout')
        if checkout:
            self._mergeIntoRegistryCheckout(checkout, name, index_entry)

        self.log.passed()
        return True

    def _mergeIntoRegistryCheckout(self, checkout, name, index_entry):
        """Merge *index_entry* into <checkout>/index/<name>.json on disk.

        Local-only: this never opens a PR or pushes anything.  Preserves
        every field already present in the file (description,
        provides_modules, other versions) and only adds/overwrites the
        version block(s) in *index_entry*.
        """
        index_path = os.path.join(checkout, 'index', '%s.json' % name)
        data = {'name': name, 'provides_modules': [], 'versions': {}}
        if os.path.isfile(index_path):
            try:
                with open(index_path) as f:
                    data = json.load(f)
            except Exception as e:
                self.log.warning(
                    "CsmakeModulePackager: could not parse existing '%s' "
                    "(%s) — starting fresh", index_path, e)
                data = {'name': name, 'provides_modules': [], 'versions': {}}

        data.setdefault('versions', {}).update(index_entry)
        data['latest'] = sorted(
            data['versions'].keys(), key=self._versionSortKey)[-1]

        try:
            os.makedirs(os.path.dirname(index_path))
        except OSError:
            pass
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write('\n')
        self.log.info(
            "CsmakeModulePackager: merged into local registry checkout: %s",
            index_path)

    def _versionSortKey(self, version_str):
        parts = []
        for part in str(version_str).split('.'):
            try:
                parts.append((0, int(part)))
            except ValueError:
                parts.append((1, part))
        return parts

    def clean(self, options):
        result_dir = options['result']
        try:
            shutil.rmtree(result_dir)
        except (IOError, OSError) as e:
            self.log.info(
                "CsmakeModulePackager: 'result' could not be removed: %s",
                repr(e))
        self.log.passed()
        return True

    def package_clean(self, options):
        return self.clean(options)


# ── Helpers ───────────────────────────────────────────────────────────────

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
