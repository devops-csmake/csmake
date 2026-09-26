# <copyright>
# (c) Copyright 2026 Autumn Patterson
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
import hashlib
import json
import os
import tempfile

try:
    import urllib.request as _urllib_request
except ImportError:                          # Python 2 fallback (best-effort)
    import urllib as _urllib_request

from CsmakeCore.CsmakeModule import CsmakeModule
from CsmakeCore.Generations import Generations


class MirrorSyncError(Exception):
    pass


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path, data):
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory)
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=directory or '.')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write('\n')
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def mirror_sync(generation_manifest, combined_index, target_dir, base_url=None, log=None):
    """Download every package pinned in *generation_manifest* and re-host
    it as a ``static-index`` source (see ``SourceLayers``) at *target_dir*.

    *combined_index* is a ``ModuleRegistry``-shaped combined index dict
    supplying each pinned package's download URL, sha256, and metadata.
    *base_url*, if given, is used as the mirrored artifacts' own base URL
    (e.g. ``https://garden.internal/csmake``, wherever *target_dir* will
    actually be served from); otherwise mirrored entries point at the
    local files directly (``file://...``), useful for local verification
    before deploying anywhere.

    Re-downloads are skipped when the destination file already exists and
    its sha256 already matches -- safe to call repeatedly, e.g. to add
    newly-promoted generations to an existing garden.

    Returns the list of ``(package_name, version)`` mirrored.  Raises
    MirrorSyncError on a hash mismatch (never silently serves a
    corrupted or substituted artifact).
    """
    index_dir = os.path.join(target_dir, 'index')
    artifacts_dir = os.path.join(target_dir, 'artifacts')
    for d in (index_dir, artifacts_dir):
        try:
            os.makedirs(d)
        except OSError:
            pass

    mirrored = []
    pkg_names = sorted(generation_manifest.get('packages', {}).keys())
    for pkgname in pkg_names:
        version = generation_manifest['packages'][pkgname]
        pkg_data = combined_index.get('packages', {}).get(pkgname)
        if not pkg_data:
            if log:
                log.warning(
                    "MirrorSync: '%s' not found in the index; skipping",
                    pkgname)
            continue
        ver_data = pkg_data.get('versions', {}).get(str(version))
        if not ver_data:
            if log:
                log.warning(
                    "MirrorSync: '%s@%s' not found in the index; skipping",
                    pkgname, version)
            continue

        url = ver_data.get('url')
        expected_sha256 = ver_data.get('sha256', '')
        artifact_name = '%s-%s.csm' % (pkgname, version)
        dest_path = os.path.join(artifacts_dir, artifact_name)

        already_mirrored = (
            os.path.isfile(dest_path) and expected_sha256
            and _sha256_file(dest_path) == expected_sha256)
        if not already_mirrored:
            if not url:
                raise MirrorSyncError(
                    "no download URL for '%s@%s'" % (pkgname, version))
            fd, tmp_path = tempfile.mkstemp(suffix='.csm', dir=artifacts_dir)
            os.close(fd)
            try:
                _urllib_request.urlretrieve(url, tmp_path)
                actual_sha256 = _sha256_file(tmp_path)
                if expected_sha256 and actual_sha256 != expected_sha256:
                    raise MirrorSyncError(
                        "sha256 mismatch mirroring '%s@%s' (index says %s, "
                        "downloaded artifact is %s)" % (
                            pkgname, version, expected_sha256, actual_sha256))
                os.replace(tmp_path, dest_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        if base_url:
            artifact_url = '%s/artifacts/%s' % (base_url.rstrip('/'), artifact_name)
        else:
            artifact_url = 'file://' + os.path.abspath(dest_path)

        entry = {
            'name': pkgname,
            'provides_modules': pkg_data.get('provides_modules', []),
            'versions': {
                str(version): {
                    'url': artifact_url,
                    'sha256': expected_sha256 or _sha256_file(dest_path),
                    'dependencies': ver_data.get('dependencies', {}),
                }
            },
            'latest': str(version),
        }
        _atomic_write_json(
            os.path.join(index_dir, '%s.json' % pkgname), entry)

        mirrored.append((pkgname, version))
        if log:
            log.info("MirrorSync: mirrored '%s@%s'", pkgname, version)

    _atomic_write_json(os.path.join(target_dir, 'index.json'), pkg_names)

    return mirrored


class MirrorSync(CsmakeModule):
    """Purpose: Mirror a cache generation's pinned packages into a local
       static-index source directory -- a walled garden's contents.
       Type: Module   Library: csmake (core)
       Phases:
           package - Download and re-host every pinned package
           clean, package_clean - Remove the result directory
       Options:
           result     - Directory to build the static-index layout in.
                        Point a source's "url" (type: static-index) at
                        this directory (or wherever it ends up served
                        from) to consume it.
           generation - (OPTIONAL) Generation name to mirror.  Default:
                        the active generation (~/.csmake/generations/current).
           base-url   - (OPTIONAL) The base URL the mirrored directory
                        will actually be served from (e.g.
                        https://garden.internal/csmake).  Default: mirrored
                        entries point at the local files directly
                        (file://...), useful for verifying the mirror
                        before deploying it anywhere.
       Notes:
           Re-downloads are skipped when the destination file already
           exists with a matching sha256 -- safe to run repeatedly, e.g.
           after promoting a new generation, to add just what changed.
    """

    REQUIRED_OPTIONS = ['result']

    def package(self, options):
        from CsmakeCore.ModuleRegistry import ModuleRegistry

        generations = Generations()
        generation_name = options.get('generation') or generations.current_name()
        if not generation_name:
            self.log.error(
                "MirrorSync: no generation specified and no active "
                "generation set")
            self.log.failed()
            return False
        manifest = generations.get(generation_name)
        if manifest is None:
            self.log.error(
                "MirrorSync: generation '%s' not found", generation_name)
            self.log.failed()
            return False

        registry = ModuleRegistry(self.settings)
        try:
            combined = registry._get_combined_index()
        except Exception as e:
            self.log.error("MirrorSync: could not load registry index: %s", e)
            self.log.failed()
            return False

        try:
            mirrored = mirror_sync(
                manifest, combined, options['result'],
                base_url=options.get('base-url'), log=self.log)
        except MirrorSyncError as e:
            self.log.error("MirrorSync: %s", e)
            self.log.failed()
            return False

        self.log.info(
            "MirrorSync: mirrored %d package(s) from generation '%s' into %s",
            len(mirrored), generation_name, options['result'])
        self.log.passed()
        return True

    def clean(self, options):
        import shutil
        try:
            shutil.rmtree(options['result'])
        except (IOError, OSError) as e:
            self.log.info(
                "MirrorSync: 'result' could not be removed: %s", repr(e))
        self.log.passed()
        return True

    def package_clean(self, options):
        return self.clean(options)
