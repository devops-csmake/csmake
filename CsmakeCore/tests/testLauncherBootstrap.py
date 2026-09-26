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
"""Tests that the csmake launcher self-locates CsmakeCore in installed layouts.

Installed packages relocate CsmakeCore away from the launcher's directory:

    Homebrew keg:  <prefix>/bin/csmake  +  <prefix>/libexec/CsmakeCore
    Apple .pkg:    <prefix>/bin/csmake  +  <prefix>/lib/python3/dist-packages/CsmakeCore

Each test stages one of those layouts in a temp directory from the current
checkout and runs the staged launcher in a scratch working directory (no
checkout on sys.path, no PYTHONPATH), asserting csmake comes up and can list
its module catalog.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# The repo root is two levels up from this file (CsmakeCore/tests/).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _stage_install(prefix, libRelPath):
    """Copy the checkout into an installed layout under ``prefix``.

    ``libRelPath`` is where CsmakeCore lands relative to the prefix.
    Mirrors the installmap: CsmakeModules nests inside CsmakeCore.
    """
    binDir = os.path.join(prefix, 'bin')
    libDir = os.path.join(prefix, *libRelPath.split('/'))
    os.makedirs(binDir)
    launcher = os.path.join(binDir, 'csmake')
    shutil.copy(os.path.join(REPO_ROOT, 'csmake'), launcher)
    os.chmod(launcher, 0o755)
    ignore = shutil.ignore_patterns('__pycache__', 'tests')
    shutil.copytree(
        os.path.join(REPO_ROOT, 'CsmakeCore'),
        os.path.join(libDir, 'CsmakeCore'),
        ignore=ignore)
    shutil.copytree(
        os.path.join(REPO_ROOT, 'CsmakeModules'),
        os.path.join(libDir, 'CsmakeCore', 'CsmakeModules'),
        ignore=ignore)
    return launcher


def _run_staged_csmake(launcher, workdir):
    """Run the staged launcher from a scratch cwd, isolated from the checkout."""
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    # CliDriver reads $PWD (not os.getcwd()) for its notion of cwd; a
    # subprocess's inherited (stale) PWD must be corrected to match cwd=
    # here, or module discovery can silently drop entries whenever the
    # stale PWD happens to equal sys.path[0].  See
    # testCsmakeModulePackager.py's _subprocess_env for how this was found.
    env['PWD'] = workdir
    return subprocess.run(
        [sys.executable, launcher,
         '--list-types', '--list-type-format=json'],
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120)


class TestLauncherBootstrap(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.workdir = os.path.join(self.scratch, 'work')
        os.makedirs(self.workdir)

    def tearDown(self):
        shutil.rmtree(self.scratch, ignore_errors=True)

    def _assert_catalog(self, completed):
        self.assertEqual(
            completed.returncode, 0,
            "launcher failed:\n%s" % completed.stderr.decode(
                'utf-8', 'replace'))
        catalog = json.loads(completed.stdout.decode('utf-8'))
        names = [entry['name'] for entry in catalog]
        self.assertIn('Shell', names)

    def test_homebrew_keg_layout(self):
        prefix = os.path.join(self.scratch, 'Cellar', 'csmake', '3.0.0')
        launcher = _stage_install(prefix, 'libexec')
        self._assert_catalog(_run_staged_csmake(launcher, self.workdir))

    def test_homebrew_symlinked_bin(self):
        # brew links <prefix>/bin/csmake into <brew>/bin; the launcher must
        # resolve the symlink to find its keg's libexec.
        prefix = os.path.join(self.scratch, 'Cellar', 'csmake', '3.0.0')
        launcher = _stage_install(prefix, 'libexec')
        linkbin = os.path.join(self.scratch, 'linkbin')
        os.makedirs(linkbin)
        link = os.path.join(linkbin, 'csmake')
        os.symlink(launcher, link)
        self._assert_catalog(_run_staged_csmake(link, self.workdir))

    def test_apple_pkg_layout(self):
        prefix = os.path.join(self.scratch, 'usr', 'local')
        launcher = _stage_install(prefix, 'lib/python3/dist-packages')
        self._assert_catalog(_run_staged_csmake(launcher, self.workdir))

    def test_checkout_still_works(self):
        # The dev-checkout path must be unaffected by the bootstrap.
        completed = _run_staged_csmake(
            os.path.join(REPO_ROOT, 'csmake'), REPO_ROOT)
        self._assert_catalog(completed)


if __name__ == "__main__":
    unittest.main()
