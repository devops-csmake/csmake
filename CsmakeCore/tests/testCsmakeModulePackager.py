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
"""Integration tests for CsmakeModulePackager, now promoted to core.

CsmakeModule instances need a fully wired Environment/engine to construct,
which isn't worth hand-mocking, so this drives the real ``csmake`` launcher
against a small fixture buildspec in a temp directory and inspects the
produced .csm -- the same subprocess-driven pattern already used by
testLauncherBootstrap.py.
"""
import glob
import json
import textwrap
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

FIXTURE_CSMAKEFILE = """
[~~phases~~]
package=build the fixture package
clean=clean the fixture package
**default=clean -> package

[metadata@fixture]
name=fixture-package
version=1.2.3
description=A fixture package for CsmakeModulePackager tests
packager=Test Author <test@example.com>
keywords=fixture testing
classifiers=
    Development Status :: 4 - Beta
    Programming Language :: Python :: 3

[CsmakeModulePackager@fixture-packager]
result=out
include=CsmakeModules/*.py

[command@build-fixture]
description=Build the fixture .csm
00=fixture, fixture-packager
"""


class TestCsmakeModulePackagerIntegration(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        with open(os.path.join(self.workdir, 'csmakefile'), 'w') as f:
            f.write(FIXTURE_CSMAKEFILE)
        os.makedirs(os.path.join(self.workdir, 'CsmakeModules'))
        with open(os.path.join(self.workdir, 'CsmakeModules', 'Fake.py'), 'w') as f:
            f.write('# a fake module file for the fixture package\n')

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _subprocess_env(self):
        # CliDriver reads $PWD (not os.getcwd()) for its notion of cwd, so a
        # subprocess's inherited (stale) PWD must be corrected to match the
        # cwd= we're about to pass -- otherwise, when the stale PWD happens
        # to equal sys.path[0] (e.g. running this repo's own ./csmake), it
        # gets swapped out for '' and the repo's CsmakeModules silently
        # drops out of module discovery. See docs/MODULE_ECOSYSTEM_DESIGN.md
        # follow-ups; this is a pre-existing CliDriver quirk, not something
        # introduced here.
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env['PWD'] = self.workdir
        return env

    def _run(self, extra_args=()):
        completed = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, 'csmake'),
             '--command=build-fixture', 'package'] + list(extra_args),
            cwd=self.workdir, env=self._subprocess_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return completed

    def _built_csm(self):
        matches = glob.glob(os.path.join(self.workdir, 'out', '*.csm'))
        self.assertEqual(len(matches), 1, "expected exactly one .csm built")
        return matches[0]

    def test_build_succeeds(self):
        completed = self._run()
        self.assertEqual(
            completed.returncode, 0,
            "csmake failed:\n%s" % completed.stderr.decode('utf-8', 'replace'))

    def test_manifest_and_dist_info_both_present(self):
        self._run()
        csm_path = self._built_csm()
        with zipfile.ZipFile(csm_path) as zf:
            names = zf.namelist()
            self.assertIn('csmake-manifest.json', names)
            self.assertIn('CsmakeModules/Fake.py', names)
            dist_info_names = [n for n in names if '.dist-info/' in n]
            self.assertTrue(
                any(n.endswith('METADATA') for n in dist_info_names))
            self.assertTrue(
                any(n.endswith('WHEEL') for n in dist_info_names))
            self.assertTrue(
                any(n.endswith('RECORD') for n in dist_info_names))
            self.assertTrue(
                any(n.endswith('top_level.txt') for n in dist_info_names))

    def test_manifest_hashes_match_payload(self):
        self._run()
        csm_path = self._built_csm()
        with zipfile.ZipFile(csm_path) as zf:
            manifest = json.loads(zf.read('csmake-manifest.json'))
            self.assertEqual(manifest['name'], 'fixture-package')
            self.assertEqual(manifest['version'], '1.2.3')
            import hashlib
            payload = zf.read('CsmakeModules/Fake.py')
            expected = 'sha256:' + hashlib.sha256(payload).hexdigest()
            self.assertEqual(
                manifest['files']['CsmakeModules/Fake.py'], expected)

    def test_dist_info_metadata_reflects_package_metadata(self):
        self._run()
        csm_path = self._built_csm()
        with zipfile.ZipFile(csm_path) as zf:
            metadata_name = [
                n for n in zf.namelist() if n.endswith('.dist-info/METADATA')
            ][0]
            text = zf.read(metadata_name).decode('utf-8')
            self.assertIn('Name: fixture-package', text)
            self.assertIn('Version: 1.2.3', text)
            self.assertIn('Author: Test Author', text)
            self.assertIn('Author-email: test@example.com', text)
            self.assertIn(
                'Classifier: Development Status :: 4 - Beta', text)

    def test_system_requires_extracted_from_module_docstrings(self):
        with open(os.path.join(
                self.workdir, 'CsmakeModules', 'NeedsTools.py'), 'w') as f:
            f.write(textwrap.dedent('''\
                class NeedsTools(object):
                    """Purpose: fixture module declaring requirements
                       Requires:
                           exec: rpmbuild, gpg
                           caps: docker-daemon
                    """
                '''))
        self._run()
        csm_path = self._built_csm()
        with zipfile.ZipFile(csm_path) as zf:
            manifest = json.loads(zf.read('csmake-manifest.json'))
        self.assertEqual(
            sorted(manifest['system_requires']['exec']), ['gpg', 'rpmbuild'])
        self.assertEqual(
            manifest['system_requires']['caps'], ['docker-daemon'])

    def test_registry_checkout_merge(self):
        registry_dir = os.path.join(self.workdir, 'registry-checkout')
        os.makedirs(os.path.join(registry_dir, 'index'))
        # Pre-existing entry for a different, unrelated package must survive.
        with open(os.path.join(registry_dir, 'index', 'other-package.json'), 'w') as f:
            json.dump({'name': 'other-package', 'versions': {}}, f)

        csmakefile_path = os.path.join(self.workdir, 'csmakefile')
        with open(csmakefile_path) as f:
            content = f.read()
        # Inject into the packager section specifically -- appending at
        # end-of-file would land the option inside [command@build-fixture]
        # instead, since it's the last section.
        content = content.replace(
            'include=CsmakeModules/*.py\n',
            'include=CsmakeModules/*.py\nregistry-checkout=%s\n' % registry_dir)
        with open(csmakefile_path, 'w') as f:
            f.write(content)

        completed = self._run()
        self.assertEqual(completed.returncode, 0)

        entry_path = os.path.join(registry_dir, 'index', 'fixture-package.json')
        self.assertTrue(os.path.isfile(entry_path))
        with open(entry_path) as f:
            entry = json.load(f)
        self.assertEqual(entry['name'], 'fixture-package')
        self.assertIn('1.2.3', entry['versions'])
        self.assertEqual(entry['latest'], '1.2.3')
        self.assertIn('sha256', entry['versions']['1.2.3'])
        self.assertTrue(entry['versions']['1.2.3']['sha256'])

        # The unrelated package's own index file is untouched.
        with open(os.path.join(registry_dir, 'index', 'other-package.json')) as f:
            other = json.load(f)
        self.assertEqual(other['name'], 'other-package')

    def test_clean_removes_result(self):
        self._run()
        self.assertTrue(os.path.isdir(os.path.join(self.workdir, 'out')))
        completed = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, 'csmake'),
             '--command=build-fixture', 'clean'],
            cwd=self.workdir, env=self._subprocess_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(completed.returncode, 0)
        self.assertFalse(os.path.isdir(os.path.join(self.workdir, 'out')))


if __name__ == "__main__":
    unittest.main()
