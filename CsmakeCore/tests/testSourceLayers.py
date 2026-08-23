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
import json
import os
import shutil
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import SourceLayers  # noqa: E402


class SourceLayersTestBase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.cwd = os.path.join(self.scratch, 'project')
        os.makedirs(self.cwd)
        self._saved_env = os.environ.pop(SourceLayers.ORG_ENV_VAR, None)
        self._saved_user_path = SourceLayers.USER_CONFIG_PATH
        SourceLayers.USER_CONFIG_PATH = os.path.join(
            self.scratch, 'user-config.json')

    def tearDown(self):
        shutil.rmtree(self.scratch, ignore_errors=True)
        if self._saved_env is not None:
            os.environ[SourceLayers.ORG_ENV_VAR] = self._saved_env
        else:
            os.environ.pop(SourceLayers.ORG_ENV_VAR, None)
        SourceLayers.USER_CONFIG_PATH = self._saved_user_path

    def _write_json(self, path, data):
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            pass
        with open(path, 'w') as f:
            json.dump(data, f)


class TestDefaultLayer(SourceLayersTestBase):
    def test_default_only_when_no_config(self):
        layers = SourceLayers.SourceLayers(cwd=self.cwd)
        sources = layers.effective_sources('csmake-module')
        self.assertEqual(len(sources), 1)
        self.assertIn('csmake-registry', sources[0]['url'])
        self.assertEqual(sources[0]['type'], 'github-contents')
        self.assertFalse(sources[0]['terminal'])

    def test_no_sources_for_unconfigured_ecosystem(self):
        layers = SourceLayers.SourceLayers(cwd=self.cwd)
        self.assertEqual(layers.effective_sources('gh-action'), [])


class TestLayerPrecedence(SourceLayersTestBase):
    def test_user_layer_appends_before_default(self):
        self._write_json(SourceLayers.USER_CONFIG_PATH, {
            'sources': [{
                'ecosystem': 'csmake-module',
                'url': 'https://example.com/user-registry',
                'type': 'static-index',
            }]
        })
        sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
            'csmake-module')
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]['url'], 'https://example.com/user-registry')
        self.assertIn('csmake-registry', sources[1]['url'])

    def test_project_layer_beats_user_layer(self):
        self._write_json(SourceLayers.USER_CONFIG_PATH, {
            'sources': [{'ecosystem': 'csmake-module',
                         'url': 'https://example.com/user'}]
        })
        self._write_json(
            os.path.join(self.cwd, SourceLayers.PROJECT_CONFIG_RELPATH),
            {'sources': [{'ecosystem': 'csmake-module',
                          'url': 'https://example.com/project'}]})
        sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
            'csmake-module')
        urls = [s['url'] for s in sources]
        self.assertEqual(
            urls,
            ['https://example.com/project', 'https://example.com/user',
             sources[2]['url']])

    def test_org_env_layer_is_highest_priority(self):
        org_path = os.path.join(self.scratch, 'org-sources.json')
        self._write_json(org_path, {
            'sources': [{'ecosystem': 'csmake-module',
                         'url': 'https://garden.internal/csmake'}]
        })
        os.environ[SourceLayers.ORG_ENV_VAR] = org_path
        self._write_json(SourceLayers.USER_CONFIG_PATH, {
            'sources': [{'ecosystem': 'csmake-module',
                         'url': 'https://example.com/user'}]
        })
        sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
            'csmake-module')
        self.assertEqual(sources[0]['url'], 'https://garden.internal/csmake')


class TestTerminal(SourceLayersTestBase):
    def test_terminal_drops_lower_layers_same_ecosystem(self):
        org_path = os.path.join(self.scratch, 'org-sources.json')
        self._write_json(org_path, {
            'sources': [{'ecosystem': 'csmake-module',
                         'url': 'https://garden.internal/csmake',
                         'terminal': True}]
        })
        os.environ[SourceLayers.ORG_ENV_VAR] = org_path
        self._write_json(SourceLayers.USER_CONFIG_PATH, {
            'sources': [{'ecosystem': 'csmake-module',
                         'url': 'https://example.com/user'}]
        })
        sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
            'csmake-module')
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['url'], 'https://garden.internal/csmake')

    def test_terminal_does_not_affect_other_ecosystems(self):
        org_path = os.path.join(self.scratch, 'org-sources.json')
        self._write_json(org_path, {
            'sources': [{'ecosystem': 'csmake-module',
                         'url': 'https://garden.internal/csmake',
                         'terminal': True}]
        })
        os.environ[SourceLayers.ORG_ENV_VAR] = org_path
        self._write_json(SourceLayers.USER_CONFIG_PATH, {
            'sources': [{'ecosystem': 'gh-action',
                         'url': 'https://example.com/actions'}]
        })
        sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
            'gh-action')
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['url'], 'https://example.com/actions')

    def test_wildcard_terminal_walls_off_everything(self):
        org_path = os.path.join(self.scratch, 'org-sources.json')
        self._write_json(org_path, {
            'sources': [{'ecosystem': '*',
                         'url': 'https://garden.internal/all',
                         'terminal': True}]
        })
        os.environ[SourceLayers.ORG_ENV_VAR] = org_path
        for ecosystem in ('csmake-module', 'gh-action', 'anything'):
            sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
                ecosystem)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]['url'], 'https://garden.internal/all')


class TestLegacyFormat(SourceLayersTestBase):
    def test_legacy_registries_list_still_works(self):
        self._write_json(SourceLayers.USER_CONFIG_PATH, {
            'registries': ['https://example.com/legacy-one',
                            'https://example.com/legacy-two']
        })
        sources = SourceLayers.SourceLayers(cwd=self.cwd).effective_sources(
            'csmake-module')
        urls = [s['url'] for s in sources]
        self.assertIn('https://example.com/legacy-one', urls)
        self.assertIn('https://example.com/legacy-two', urls)
        # Legacy entries are treated as ordinary (non-terminal) sources.
        self.assertFalse(any(s['terminal'] for s in sources))


class TestSourceId(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(
            SourceLayers.source_id('https://example.com/x'),
            SourceLayers.source_id('https://example.com/x'))

    def test_different_urls_differ(self):
        self.assertNotEqual(
            SourceLayers.source_id('https://example.com/x'),
            SourceLayers.source_id('https://example.com/y'))

    def test_path_safe(self):
        sid = SourceLayers.source_id('https://example.com/x?y=z&a=b')
        self.assertRegex(sid, r'^[0-9a-f]+$')


if __name__ == "__main__":
    unittest.main()
