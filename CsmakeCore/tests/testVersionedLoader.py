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
"""Integration tests for package pins ([~~packages~~] / **uses) and the
versioned-name loader projection (Phase 3 of the module ecosystem design).

Two synthetic versions of a fake package ('fakepkg' 1.0.0 and 2.0.0) are
staged directly into a scratch ~/.csmake/modules/ layout -- the exact shape
ModuleRegistry.install() produces -- so these tests exercise the LOADER's
pin resolution in isolation from the registry download/index logic
(already covered by testModuleRegistry.py). Driven through the real
csmake launcher via subprocess, since CsmakeModule instances need a fully
wired Environment/engine to construct (see testCsmakeModulePackager.py).

The governing invariant for this phase: with zero pins anywhere, behavior
must be unchanged. test_no_pins_regression below is the gate for that.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

WIDGET_SOURCE = textwrap.dedent('''\
    from CsmakeCore.CsmakeModule import CsmakeModule
    from CsmakeModules.Helper import Helper
    import json

    class Widget(CsmakeModule):
        """Purpose: Fixture module for versioned-loader tests"""

        def build(self, options):
            import os as _os
            _os.makedirs(_os.path.dirname(options['result']), exist_ok=True)
            with open(options['result'], 'w') as f:
                json.dump({
                    'widget_version': %(version)r,
                    'helper_marker': Helper.MARKER,
                }, f)
            self.log.passed()
            return True
    ''')

HELPER_SOURCE = textwrap.dedent('''\
    class Helper(object):
        MARKER = %(marker)r
    ''')


def _stage_fake_package(cache_root, version, marker):
    pkg_dir = os.path.join(cache_root, 'fakepkg', version, 'CsmakeModules')
    os.makedirs(pkg_dir)
    with open(os.path.join(pkg_dir, 'Widget.py'), 'w') as f:
        f.write(WIDGET_SOURCE % {'version': version})
    with open(os.path.join(pkg_dir, 'Helper.py'), 'w') as f:
        f.write(HELPER_SOURCE % {'marker': marker})


FIXTURE_CSMAKEFILE = """
[~~phases~~]
build=run widgets
**default=build

[Widget@pinned-old]
**uses=fakepkg@1.0.0
result=out/pinned-old.json

[Widget@pinned-new]
**uses=fakepkg@2.0.0
result=out/pinned-new.json

[Widget@unpinned]
result=out/unpinned.json

[command@run]
description=Run all three widget sections
00=pinned-old, pinned-new, unpinned
"""


class VersionedLoaderTestBase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.home = os.path.join(self.scratch, 'home')
        os.makedirs(self.home)
        self.workdir = os.path.join(self.scratch, 'work')
        os.makedirs(self.workdir)
        with open(os.path.join(self.workdir, 'csmakefile'), 'w') as f:
            f.write(FIXTURE_CSMAKEFILE)

        cache_root = os.path.join(self.home, '.csmake', 'modules')
        os.makedirs(cache_root)
        _stage_fake_package(cache_root, '1.0.0', 'helper-v1')
        _stage_fake_package(cache_root, '2.0.0', 'helper-v2')

    def tearDown(self):
        shutil.rmtree(self.scratch, ignore_errors=True)

    def _run(self, command='run'):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env['HOME'] = self.home       # isolates ~/.csmake/modules
        env['PWD'] = self.workdir     # see testCsmakeModulePackager.py
        return subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, 'csmake'),
             '--command=%s' % command, 'build'],
            cwd=self.workdir, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)

    def _read_result(self, name):
        with open(os.path.join(self.workdir, 'out', name)) as f:
            return json.load(f)


class TestPinResolution(VersionedLoaderTestBase):
    def test_all_three_sections_run(self):
        completed = self._run()
        self.assertEqual(
            completed.returncode, 0,
            "csmake failed:\n%s" % completed.stderr.decode('utf-8', 'replace'))

    def test_pinned_old_gets_pinned_version(self):
        self._run()
        result = self._read_result('pinned-old.json')
        self.assertEqual(result['widget_version'], '1.0.0')

    def test_pinned_new_gets_pinned_version(self):
        self._run()
        result = self._read_result('pinned-new.json')
        self.assertEqual(result['widget_version'], '2.0.0')

    def test_unpinned_gets_greatest_cached_version(self):
        self._run()
        result = self._read_result('unpinned.json')
        self.assertEqual(result['widget_version'], '2.0.0')

    def test_sibling_import_isolated_per_pin(self):
        # The core promise: a pinned package's own internal
        # 'from CsmakeModules.Helper import Helper' resolves within that
        # SAME pinned version, not whichever version owns the bare slot.
        self._run()
        old = self._read_result('pinned-old.json')
        new = self._read_result('pinned-new.json')
        unpinned = self._read_result('unpinned.json')
        self.assertEqual(old['helper_marker'], 'helper-v1')
        self.assertEqual(new['helper_marker'], 'helper-v2')
        # Unpinned resolves via the bare/default slot, which is the
        # greatest cached version (2.0.0) -- same as pinned-new here.
        self.assertEqual(unpinned['helper_marker'], 'helper-v2')


class TestPinTriggersFreshInstall(unittest.TestCase):
    """A **uses pin for a version NOT yet cached triggers a registry
    install; a later unpinned section in the SAME build should see that
    version as the "greatest in play" -- distinct from whatever the
    registry itself calls 'latest' -- because it's the only version this
    build has actually installed/used. Exercises _pinnedPackageRoot's
    seed_sys_path() re-seed after a fresh install.
    """

    def _make_fixture_registry(self, base, versions_and_latest):
        """A minimal static-index registry offering 'fakepkg2' with the
        given {version: is_latest} versions, each providing Widget2 (a
        second, distinct fixture module so this doesn't collide with the
        fakepkg/Widget fixtures used elsewhere in this file)."""
        os.makedirs(os.path.join(base, 'index'))
        os.makedirs(os.path.join(base, 'artifacts'))
        with open(os.path.join(base, 'index.json'), 'w') as f:
            json.dump(['fakepkg2'], f)

        widget2_source = textwrap.dedent('''\
            from CsmakeCore.CsmakeModule import CsmakeModule
            import json, os

            class Widget2(CsmakeModule):
                def build(self, options):
                    os.makedirs(os.path.dirname(options['result']), exist_ok=True)
                    with open(options['result'], 'w') as f:
                        json.dump({'widget_version': %(version)r}, f)
                    self.log.passed()
                    return True
            ''')

        versions_block = {}
        for version in versions_and_latest:
            import hashlib
            import zipfile
            csm_path = os.path.join(base, 'artifacts', 'fakepkg2-%s.csm' % version)
            manifest = {'name': 'fakepkg2', 'version': version,
                        'dependencies': {}, 'files': {}}
            with zipfile.ZipFile(csm_path, 'w') as zf:
                zf.writestr('csmake-manifest.json', json.dumps(manifest))
                zf.writestr('CsmakeModules/Widget2.py',
                            widget2_source % {'version': version})
            with open(csm_path, 'rb') as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()
            versions_block[version] = {
                'url': 'file://' + csm_path, 'sha256': sha256, 'dependencies': {}}

        latest = [v for v, is_latest in versions_and_latest.items() if is_latest][0]
        with open(os.path.join(base, 'index', 'fakepkg2.json'), 'w') as f:
            json.dump({
                'name': 'fakepkg2', 'provides_modules': ['Widget2'],
                'versions': versions_block, 'latest': latest,
            }, f)

    def test_unpinned_section_sees_pin_installed_version_not_registry_latest(self):
        scratch = tempfile.mkdtemp()
        try:
            home = os.path.join(scratch, 'home')
            os.makedirs(home)
            registry_dir = os.path.join(scratch, 'registry')
            os.makedirs(registry_dir)
            # Registry's own 'latest' is 3.0.0, but this build only ever
            # pins 2.0.0 -- 2.0.0 is what "greatest in play" must mean.
            self._make_fixture_registry(
                registry_dir, {'2.0.0': False, '3.0.0': True})
            os.makedirs(os.path.join(home, '.csmake'))
            with open(os.path.join(home, '.csmake', 'config.json'), 'w') as f:
                json.dump({'sources': [{
                    'ecosystem': 'csmake-module',
                    'url': 'file://' + registry_dir,
                    'type': 'static-index',
                }]}, f)

            workdir = os.path.join(scratch, 'work')
            os.makedirs(workdir)
            with open(os.path.join(workdir, 'csmakefile'), 'w') as f:
                f.write(textwrap.dedent("""\
                    [~~phases~~]
                    build=run widgets
                    **default=build

                    [Widget2@pinned]
                    **uses=fakepkg2@2.0.0
                    result=out/pinned.json

                    [Widget2@unpinned]
                    result=out/unpinned.json

                    [command@run]
                    description=pinned then unpinned
                    00=pinned, unpinned
                    """))

            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            env['HOME'] = home
            env['PWD'] = workdir
            completed = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, 'csmake'),
                 '--command=run', 'build'],
                cwd=workdir, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            self.assertEqual(
                completed.returncode, 0,
                "csmake failed:\n%s" % completed.stderr.decode('utf-8', 'replace'))

            with open(os.path.join(workdir, 'out', 'pinned.json')) as f:
                pinned = json.load(f)
            with open(os.path.join(workdir, 'out', 'unpinned.json')) as f:
                unpinned = json.load(f)
            self.assertEqual(pinned['widget_version'], '2.0.0')
            self.assertEqual(unpinned['widget_version'], '2.0.0')
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


class TestNoPinsRegression(unittest.TestCase):
    """With zero pins anywhere, behavior must be byte-identical to today.

    This is the regression gate for the whole phase -- the existing suite
    (run separately via command@test) is the real guarantee, but this
    spot-checks the specific mechanism: a plain build with no
    [~~packages~~] section and no **uses anywhere must not touch any of
    the new pin-resolution code paths in a way that changes behavior.
    """
    def test_plain_build_unaffected(self):
        scratch = tempfile.mkdtemp()
        try:
            workdir = os.path.join(scratch, 'work')
            os.makedirs(workdir)
            os.makedirs(os.path.join(workdir, 'CsmakeModules'))
            with open(os.path.join(workdir, 'csmakefile'), 'w') as f:
                f.write(textwrap.dedent("""\
                    [~~phases~~]
                    build=trivial build
                    **default=build

                    [Shell@hello]
                    command(build)=echo hello-from-plain-build

                    [command@run]
                    description=trivial
                    00=hello
                    """))
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            env['HOME'] = os.path.join(scratch, 'home')
            os.makedirs(env['HOME'])
            env['PWD'] = workdir
            completed = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, 'csmake'),
                 '--command=run', 'build'],
                cwd=workdir, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            self.assertEqual(
                completed.returncode, 0,
                "csmake failed:\n%s" % completed.stderr.decode('utf-8', 'replace'))
            self.assertIn(b'hello-from-plain-build', completed.stdout)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
