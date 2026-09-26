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
"""Tests for ModuleRegistry's multi-source resolution.

Exercises the bugs found and fixed in Phase 1 of the module ecosystem
work: every configured source is queried (not just the first reachable
one), a package name is claimed by the first source that offers it
(never merged), and per-source cache files never collide on disk.

Fixture sources are plain directories served over ``file://`` URLs, using
the new ``static-index`` source type -- no network or HTTP server needed.
"""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
import sys
sys.path.insert(0, REPO_ROOT)

from CsmakeCore import ModuleRegistry as ModuleRegistryModule
from CsmakeCore import SourceLayers as SourceLayersModule
from CsmakeCore.ModuleRegistry import ModuleRegistry


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _make_csm(path, name, version, files):
    """Write a minimal valid .csm zip at *path*.

    ``files`` is {archive_path: bytes}.  Embeds a csmake-manifest.json with
    correct per-file sha256 (mirroring CsmakeModulePackager's output).
    """
    file_hashes = {
        archive_path: 'sha256:' + _sha256_bytes(data)
        for archive_path, data in files.items()
    }
    manifest = {
        'name': name,
        'version': version,
        'description': 'fixture',
        'dependencies': {},
        'files': file_hashes,
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('csmake-manifest.json', json.dumps(manifest))
        for archive_path, data in files.items():
            zf.writestr(archive_path, data)
    with open(path, 'rb') as f:
        return _sha256_bytes(f.read())


def _write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path))
    except OSError:
        pass
    with open(path, 'w') as f:
        json.dump(data, f)


class ModuleRegistryTestBase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.home = os.path.join(self.scratch, 'home')
        os.makedirs(self.home)

        # Isolate the module cache and registry cache from the real ~/.csmake.
        self._saved_cache_root = ModuleRegistryModule._CACHE_ROOT
        self._saved_registry_cache = ModuleRegistryModule._REGISTRY_CACHE
        ModuleRegistryModule._CACHE_ROOT = os.path.join(self.home, 'modules')
        ModuleRegistryModule._REGISTRY_CACHE = os.path.join(
            self.home, 'registry')

        self._saved_user_path = SourceLayersModule.USER_CONFIG_PATH
        SourceLayersModule.USER_CONFIG_PATH = os.path.join(
            self.home, 'config.json')

        self.cwd = os.path.join(self.scratch, 'project')
        os.makedirs(self.cwd)

        self._saved_org_env = os.environ.pop(
            SourceLayersModule.ORG_ENV_VAR, None)

        self._saved_sys_path = list(sys.path)

    def tearDown(self):
        shutil.rmtree(self.scratch, ignore_errors=True)
        ModuleRegistryModule._CACHE_ROOT = self._saved_cache_root
        ModuleRegistryModule._REGISTRY_CACHE = self._saved_registry_cache
        SourceLayersModule.USER_CONFIG_PATH = self._saved_user_path
        if self._saved_org_env is not None:
            os.environ[SourceLayersModule.ORG_ENV_VAR] = self._saved_org_env
        else:
            os.environ.pop(SourceLayersModule.ORG_ENV_VAR, None)
        sys.path[:] = self._saved_sys_path

    def _make_static_source(self, dirname, packages):
        """Build a static-index fixture source.

        *packages* is {pkg_name: {"version": v, "provides_modules": [...],
        "files": {archive_path: bytes}}}.  Returns the file:// base URL.
        """
        base = os.path.join(self.scratch, dirname)
        os.makedirs(os.path.join(base, 'index'))
        os.makedirs(os.path.join(base, 'artifacts'))

        _write_json(
            os.path.join(base, 'index.json'), sorted(packages.keys()))

        for pkg_name, spec in packages.items():
            version = spec['version']
            csm_name = '%s-%s.csm' % (pkg_name, version)
            csm_path = os.path.join(base, 'artifacts', csm_name)
            sha256 = _make_csm(csm_path, pkg_name, version, spec['files'])
            _write_json(os.path.join(base, 'index', '%s.json' % pkg_name), {
                'name': pkg_name,
                'provides_modules': spec.get('provides_modules', []),
                'versions': {
                    version: {
                        'url': 'file://%s' % csm_path,
                        'sha256': sha256,
                        'dependencies': {},
                    }
                },
                'latest': version,
            })
        return 'file://%s' % base

    def _configure_sources(self, sources):
        _write_json(SourceLayersModule.USER_CONFIG_PATH, {
            'sources': sources
        })


class TestAllSourcesQueried(ModuleRegistryTestBase):
    """The bug: _refresh_registry_cache used to return after the first
    reachable source, so a second configured source's packages were never
    even fetched."""

    def test_second_source_packages_are_discoverable(self):
        url_a = self._make_static_source('source-a', {
            'pkg-a': {'version': '1.0.0', 'provides_modules': ['ModA'],
                      'files': {'CsmakeModules/ModA.py': b'# a'}},
        })
        url_b = self._make_static_source('source-b', {
            'pkg-b': {'version': '1.0.0', 'provides_modules': ['ModB'],
                      'files': {'CsmakeModules/ModB.py': b'# b'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url_a, 'type': 'static-index'},
            {'ecosystem': 'csmake-module', 'url': url_b, 'type': 'static-index'},
        ])

        registry = ModuleRegistry(cwd=self.cwd)
        combined = registry._get_combined_index()
        self.assertIn('pkg-a', combined['packages'])
        self.assertIn('pkg-b', combined['packages'])
        self.assertEqual(combined['module_index']['ModA'], 'pkg-a')
        self.assertEqual(combined['module_index']['ModB'], 'pkg-b')


class TestFirstClaimWins(ModuleRegistryTestBase):
    """The bug: combining walked files in filename order and last-write
    overwrote, instead of the higher-priority source's claim winning."""

    def test_higher_priority_source_wins_no_merge(self):
        url_a = self._make_static_source('source-a', {
            'conflict': {'version': '9.9.9', 'provides_modules': ['FromA'],
                         'files': {'CsmakeModules/FromA.py': b'# a'}},
        })
        url_b = self._make_static_source('source-b', {
            'conflict': {'version': '1.0.0', 'provides_modules': ['FromB'],
                         'files': {'CsmakeModules/FromB.py': b'# b'}},
        })
        # a is higher priority (listed first / higher layer).
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url_a, 'type': 'static-index'},
            {'ecosystem': 'csmake-module', 'url': url_b, 'type': 'static-index'},
        ])

        registry = ModuleRegistry(cwd=self.cwd)
        combined = registry._get_combined_index()
        self.assertEqual(combined['packages']['conflict']['latest'], '9.9.9')
        self.assertIn('FromA', combined['module_index'])
        self.assertNotIn('FromB', combined['module_index'])

    def test_no_cache_collision_on_disk(self):
        url_a = self._make_static_source('source-a', {
            'conflict': {'version': '9.9.9', 'files': {'x.py': b'a'}},
        })
        url_b = self._make_static_source('source-b', {
            'conflict': {'version': '1.0.0', 'files': {'x.py': b'b'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url_a, 'type': 'static-index'},
            {'ecosystem': 'csmake-module', 'url': url_b, 'type': 'static-index'},
        ])

        registry = ModuleRegistry(cwd=self.cwd)
        registry._get_combined_index()

        # The built-in public default source is also in play (a third,
        # lower-priority source) since this test doesn't wall it off --
        # so check the two known fixture sources specifically rather than
        # asserting a total directory count.
        index_root = os.path.join(ModuleRegistryModule._REGISTRY_CACHE, 'index')
        id_a = SourceLayersModule.source_id(url_a)
        id_b = SourceLayersModule.source_id(url_b)
        self.assertNotEqual(id_a, id_b)

        with open(os.path.join(index_root, id_a, 'conflict.json')) as f:
            data_a = json.load(f)
        with open(os.path.join(index_root, id_b, 'conflict.json')) as f:
            data_b = json.load(f)
        self.assertEqual(set(data_a['versions'].keys()), {'9.9.9'})
        self.assertEqual(set(data_b['versions'].keys()), {'1.0.0'})


class TestStaticIndexInstall(ModuleRegistryTestBase):
    def test_find_and_install_from_static_index(self):
        url = self._make_static_source('source', {
            'pkg-x': {'version': '2.0.0', 'provides_modules': ['ModX'],
                      'files': {'CsmakeModules/ModX.py': b'# x'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url, 'type': 'static-index'},
        ])

        registry = ModuleRegistry(cwd=self.cwd)
        dest = registry.find('ModX')
        self.assertIsNotNone(dest)
        self.assertTrue(os.path.isfile(
            os.path.join(dest, 'CsmakeModules', 'ModX.py')))

    def test_higher_priority_source_installed_on_conflict(self):
        url_a = self._make_static_source('source-a', {
            'conflict': {'version': '9.9.9', 'provides_modules': ['ModC'],
                         'files': {'CsmakeModules/ModC.py': b'# from-a'}},
        })
        url_b = self._make_static_source('source-b', {
            'conflict': {'version': '1.0.0', 'provides_modules': ['ModC'],
                         'files': {'CsmakeModules/ModC.py': b'# from-b'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url_a, 'type': 'static-index'},
            {'ecosystem': 'csmake-module', 'url': url_b, 'type': 'static-index'},
        ])

        registry = ModuleRegistry(cwd=self.cwd)
        dest = registry.find('ModC')
        self.assertIn(os.path.join('conflict', '9.9.9'), dest)
        with open(os.path.join(dest, 'CsmakeModules', 'ModC.py')) as f:
            self.assertIn('from-a', f.read())


class TestFrozenMode(ModuleRegistryTestBase):
    def test_frozen_install_fails_closed_when_not_cached(self):
        url = self._make_static_source('source', {
            'pkg-x': {'version': '2.0.0', 'provides_modules': ['ModX'],
                      'files': {'CsmakeModules/ModX.py': b'# x'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url, 'type': 'static-index'},
        ])

        # Warm the index cache (frozen mode won't refresh it, but it
        # needs to exist already -- mirrors a build that ran once
        # unfrozen, then later runs frozen against the same cache).
        warm = ModuleRegistry(cwd=self.cwd)
        warm._get_combined_index()

        frozen = ModuleRegistry(cwd=self.cwd, frozen=True)
        dest = frozen.install('pkg-x')
        self.assertIsNone(dest)

    def test_frozen_install_succeeds_when_already_cached(self):
        url = self._make_static_source('source', {
            'pkg-x': {'version': '2.0.0', 'provides_modules': ['ModX'],
                      'files': {'CsmakeModules/ModX.py': b'# x'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url, 'type': 'static-index'},
        ])

        # Install once, unfrozen, to populate the cache.
        warm = ModuleRegistry(cwd=self.cwd)
        first_dest = warm.install('pkg-x')
        self.assertIsNotNone(first_dest)

        frozen = ModuleRegistry(cwd=self.cwd, frozen=True)
        dest = frozen.install('pkg-x')
        self.assertEqual(dest, first_dest)

    def test_frozen_never_touches_network(self):
        # Point at a source that would raise if actually contacted --
        # frozen mode must never even try, once the index is warmed.
        url = self._make_static_source('source', {
            'pkg-x': {'version': '2.0.0', 'provides_modules': ['ModX'],
                      'files': {'CsmakeModules/ModX.py': b'# x'}},
        })
        self._configure_sources([
            {'ecosystem': 'csmake-module', 'url': url, 'type': 'static-index'},
        ])
        warm = ModuleRegistry(cwd=self.cwd)
        warm._get_combined_index()

        def _explode(*a, **k):
            raise AssertionError("frozen mode must never touch the network")

        frozen = ModuleRegistry(cwd=self.cwd, frozen=True)
        orig = ModuleRegistryModule._urllib_request.urlopen
        ModuleRegistryModule._urllib_request.urlopen = _explode
        try:
            combined = frozen._get_combined_index()
            self.assertIn('pkg-x', combined['packages'])
        finally:
            ModuleRegistryModule._urllib_request.urlopen = orig


class TestTerminalGarden(ModuleRegistryTestBase):
    def test_terminal_source_hides_public_default(self):
        garden_url = self._make_static_source('garden', {
            'pkg-only-in-garden': {
                'version': '1.0.0', 'provides_modules': ['GardenMod'],
                'files': {'CsmakeModules/GardenMod.py': b'# garden'},
            },
        })
        org_path = os.path.join(self.scratch, 'org-sources.json')
        _write_json(org_path, {
            'sources': [{'ecosystem': 'csmake-module', 'url': garden_url,
                         'type': 'static-index', 'terminal': True}]
        })
        os.environ[SourceLayersModule.ORG_ENV_VAR] = org_path

        registry = ModuleRegistry(cwd=self.cwd)
        # The built-in public default must not be in the effective sources.
        urls = [s['url'] for s in registry._sources]
        self.assertEqual(urls, [garden_url])


if __name__ == "__main__":
    unittest.main()
