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
"""Tests for MirrorSync -- mirroring a generation's pinned packages into a
static-index source directory.

mirror_sync() is a plain function (the CsmakeModule wrapper around it is
thin glue, tested separately/indirectly), so most of this drives it
directly against file:// fixture artifacts. The round-trip test proves
the mirrored output is directly consumable as a static-index source by
pointing a real SourceLayers-configured ModuleRegistry at it.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from CsmakeModules import MirrorSync
from CsmakeCore import ModuleRegistry as ModuleRegistryModule
from CsmakeCore import SourceLayers as SourceLayersModule
from CsmakeCore.ModuleRegistry import ModuleRegistry


def _make_source_artifact(directory, pkgname, version, files):
    os.makedirs(directory, exist_ok=True)
    csm_path = os.path.join(directory, '%s-%s.csm' % (pkgname, version))
    manifest = {'name': pkgname, 'version': version, 'dependencies': {},
                'files': {}}
    with zipfile.ZipFile(csm_path, 'w') as zf:
        zf.writestr('csmake-manifest.json', json.dumps(manifest))
        for archive_path, data in files.items():
            zf.writestr(archive_path, data)
    with open(csm_path, 'rb') as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    return csm_path, sha256


class MirrorSyncTestBase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.scratch, 'source-artifacts')
        self.target_dir = os.path.join(self.scratch, 'garden')

    def tearDown(self):
        shutil.rmtree(self.scratch, ignore_errors=True)

    def _combined_index(self, pkgname, version, sha256, csm_path,
                         provides_modules=None):
        return {
            'packages': {
                pkgname: {
                    'name': pkgname,
                    'provides_modules': provides_modules or [],
                    'versions': {
                        version: {
                            'url': 'file://' + csm_path,
                            'sha256': sha256,
                            'dependencies': {},
                        }
                    },
                    'latest': version,
                }
            }
        }


class TestMirrorSyncBasics(MirrorSyncTestBase):
    def test_mirrors_pinned_package(self):
        csm_path, sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        combined = self._combined_index(
            'fakepkg', '1.0.0', sha256, csm_path, provides_modules=['Widget'])
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}

        mirrored = MirrorSync.mirror_sync(generation, combined, self.target_dir)

        self.assertEqual(mirrored, [('fakepkg', '1.0.0')])
        self.assertTrue(os.path.isfile(
            os.path.join(self.target_dir, 'artifacts', 'fakepkg-1.0.0.csm')))
        self.assertTrue(os.path.isfile(
            os.path.join(self.target_dir, 'index', 'fakepkg.json')))
        with open(os.path.join(self.target_dir, 'index.json')) as f:
            self.assertEqual(json.load(f), ['fakepkg'])

    def test_mirrored_index_entry_content(self):
        csm_path, sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        combined = self._combined_index(
            'fakepkg', '1.0.0', sha256, csm_path, provides_modules=['Widget'])
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}

        MirrorSync.mirror_sync(generation, combined, self.target_dir)

        with open(os.path.join(self.target_dir, 'index', 'fakepkg.json')) as f:
            entry = json.load(f)
        self.assertEqual(entry['provides_modules'], ['Widget'])
        self.assertEqual(entry['latest'], '1.0.0')
        self.assertEqual(entry['versions']['1.0.0']['sha256'], sha256)
        # Local (no base_url given): points straight at the mirrored file.
        self.assertTrue(entry['versions']['1.0.0']['url'].startswith('file://'))
        self.assertIn('fakepkg-1.0.0.csm', entry['versions']['1.0.0']['url'])

    def test_base_url_used_when_given(self):
        csm_path, sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        combined = self._combined_index('fakepkg', '1.0.0', sha256, csm_path)
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}

        MirrorSync.mirror_sync(
            generation, combined, self.target_dir,
            base_url='https://garden.internal/csmake')

        with open(os.path.join(self.target_dir, 'index', 'fakepkg.json')) as f:
            entry = json.load(f)
        self.assertEqual(
            entry['versions']['1.0.0']['url'],
            'https://garden.internal/csmake/artifacts/fakepkg-1.0.0.csm')

    def test_hash_mismatch_raises_and_does_not_leave_partial_file(self):
        csm_path, _real_sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        wrong_sha256 = 'deadbeef' * 8
        combined = self._combined_index(
            'fakepkg', '1.0.0', wrong_sha256, csm_path)
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}

        with self.assertRaises(MirrorSync.MirrorSyncError):
            MirrorSync.mirror_sync(generation, combined, self.target_dir)
        self.assertFalse(os.path.isfile(
            os.path.join(self.target_dir, 'artifacts', 'fakepkg-1.0.0.csm')))

    def test_package_not_in_index_is_skipped_not_fatal(self):
        generation = {'packages': {'unknown-pkg': '1.0.0'}, 'parent': None}
        mirrored = MirrorSync.mirror_sync(
            generation, {'packages': {}}, self.target_dir)
        self.assertEqual(mirrored, [])

    def test_rerun_skips_already_mirrored_matching_hash(self):
        csm_path, sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        combined = self._combined_index('fakepkg', '1.0.0', sha256, csm_path)
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}

        MirrorSync.mirror_sync(generation, combined, self.target_dir)
        artifact = os.path.join(self.target_dir, 'artifacts', 'fakepkg-1.0.0.csm')
        first_mtime = os.path.getmtime(artifact)

        # Break the source artifact's URL -- if mirror_sync tried to
        # re-download, this would fail loudly.
        broken_combined = self._combined_index(
            'fakepkg', '1.0.0', sha256, '/nonexistent/path.csm')
        mirrored = MirrorSync.mirror_sync(generation, broken_combined, self.target_dir)
        self.assertEqual(mirrored, [('fakepkg', '1.0.0')])
        self.assertEqual(os.path.getmtime(artifact), first_mtime)

    def test_multiple_packages_all_mirrored(self):
        csm_a, sha_a = _make_source_artifact(
            self.source_dir, 'pkg-a', '1.0.0', {'x.py': b'a'})
        csm_b, sha_b = _make_source_artifact(
            self.source_dir, 'pkg-b', '2.0.0', {'x.py': b'b'})
        combined = {'packages': {
            'pkg-a': {'name': 'pkg-a', 'provides_modules': [],
                      'versions': {'1.0.0': {'url': 'file://' + csm_a,
                                              'sha256': sha_a, 'dependencies': {}}},
                      'latest': '1.0.0'},
            'pkg-b': {'name': 'pkg-b', 'provides_modules': [],
                      'versions': {'2.0.0': {'url': 'file://' + csm_b,
                                              'sha256': sha_b, 'dependencies': {}}},
                      'latest': '2.0.0'},
        }}
        generation = {
            'packages': {'pkg-a': '1.0.0', 'pkg-b': '2.0.0'}, 'parent': None}

        mirrored = MirrorSync.mirror_sync(generation, combined, self.target_dir)
        self.assertEqual(
            sorted(mirrored), [('pkg-a', '1.0.0'), ('pkg-b', '2.0.0')])
        with open(os.path.join(self.target_dir, 'index.json')) as f:
            self.assertEqual(json.load(f), ['pkg-a', 'pkg-b'])


class TestMirrorSyncRoundTrip(MirrorSyncTestBase):
    """The mirrored output must be directly usable as a static-index
    source -- verified end to end through the real SourceLayers +
    ModuleRegistry resolution path, not just by inspecting files."""

    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.scratch, 'home')
        os.makedirs(self.home)
        self._saved_cache_root = ModuleRegistryModule._CACHE_ROOT
        self._saved_registry_cache = ModuleRegistryModule._REGISTRY_CACHE
        ModuleRegistryModule._CACHE_ROOT = os.path.join(self.home, 'modules')
        ModuleRegistryModule._REGISTRY_CACHE = os.path.join(self.home, 'registry')
        self._saved_user_path = SourceLayersModule.USER_CONFIG_PATH
        SourceLayersModule.USER_CONFIG_PATH = os.path.join(
            self.home, 'config.json')
        self.cwd = os.path.join(self.scratch, 'work')
        os.makedirs(self.cwd)

    def tearDown(self):
        ModuleRegistryModule._CACHE_ROOT = self._saved_cache_root
        ModuleRegistryModule._REGISTRY_CACHE = self._saved_registry_cache
        SourceLayersModule.USER_CONFIG_PATH = self._saved_user_path
        super().tearDown()

    def test_mirrored_garden_resolves_via_real_module_registry(self):
        csm_path, sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        combined = self._combined_index(
            'fakepkg', '1.0.0', sha256, csm_path, provides_modules=['Widget'])
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}

        MirrorSync.mirror_sync(generation, combined, self.target_dir)

        with open(SourceLayersModule.USER_CONFIG_PATH, 'w') as f:
            json.dump({'sources': [{
                'ecosystem': 'csmake-module',
                'url': 'file://' + self.target_dir,
                'type': 'static-index',
            }]}, f)

        registry = ModuleRegistry(cwd=self.cwd)
        dest = registry.find('Widget')
        self.assertIsNotNone(dest)
        self.assertTrue(os.path.isfile(
            os.path.join(dest, 'CsmakeModules', 'Widget.py')))

    def test_frozen_build_resolves_entirely_from_mirrored_garden(self):
        csm_path, sha256 = _make_source_artifact(
            self.source_dir, 'fakepkg', '1.0.0',
            {'CsmakeModules/Widget.py': b'# widget\n'})
        combined = self._combined_index(
            'fakepkg', '1.0.0', sha256, csm_path, provides_modules=['Widget'])
        generation = {'packages': {'fakepkg': '1.0.0'}, 'parent': None}
        MirrorSync.mirror_sync(generation, combined, self.target_dir)

        with open(SourceLayersModule.USER_CONFIG_PATH, 'w') as f:
            json.dump({'sources': [{
                'ecosystem': 'csmake-module',
                'url': 'file://' + self.target_dir,
                'type': 'static-index',
            }]}, f)

        # Warm the cache once (unfrozen), then resolve again frozen --
        # must succeed purely from what's now cached, no network.
        warm = ModuleRegistry(cwd=self.cwd)
        self.assertIsNotNone(warm.find('Widget'))

        frozen = ModuleRegistry(cwd=self.cwd, frozen=True)
        dest = frozen.find('Widget')
        self.assertIsNotNone(dest)


if __name__ == "__main__":
    unittest.main()
