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
"""Layered, ordered source configuration for csmake's acquisition mechanisms.

Any csmake mechanism that fetches bytes from somewhere (the module registry
today; GitHub Actions / terraform-style providers / etc. in other libraries,
eventually) can ask ``SourceLayers`` for the ordered list of places to look
for a given "ecosystem" (``csmake-module`` for the module registry).

Layer precedence, highest priority first:

    org/machine   -- path named by the CSMAKE_SOURCES_CONFIG env var
    project       -- ./.csmake/sources.json (relative to cwd)
    user          -- ~/.csmake/config.json
    built-in      -- the default csmake-registry GitHub repo

A layer file has the shape::

    {
      "sources": [
        {
          "scope": "*",                  // "*" or an ecosystem name
          "ecosystem": "csmake-module",  // "*" matches every ecosystem
          "url": "https://...",
          "type": "github-contents",     // or "static-index"
          "terminal": false              // stop consulting lower layers
        }
      ]
    }

A ``terminal`` entry that matches the requested ecosystem causes every
lower-priority layer to be dropped entirely for that ecosystem -- this is
what makes a walled garden a wall: a project csmakefile cannot add public
fallthrough underneath an org-pinned terminal source.  Entries for other
ecosystems in the same or lower layers are unaffected.

For backward compatibility, a user config file in the older
``{"registries": ["https://...", ...]}`` shape (a flat list of
csmake-module registry base URLs) is still read correctly.
"""

import hashlib
import json
import os

DEFAULT_ECOSYSTEM = 'csmake-module'

_REGISTRY_OWNER  = 'devops-csmake'
_REGISTRY_REPO   = 'csmake-registry'
_REGISTRY_BRANCH = 'main'
_RAW_BASE        = 'https://raw.githubusercontent.com'

# The built-in default layer -- today's single hardcoded registry, now
# expressed as a source entry so it participates in the same merge logic
# as everything else.
_BUILTIN_SOURCES = [
    {
        'scope': '*',
        'ecosystem': DEFAULT_ECOSYSTEM,
        'url': '%s/%s/%s/%s' % (
            _RAW_BASE, _REGISTRY_OWNER, _REGISTRY_REPO, _REGISTRY_BRANCH),
        'type': 'github-contents',
        'terminal': False,
    },
]

ORG_ENV_VAR          = 'CSMAKE_SOURCES_CONFIG'
USER_CONFIG_PATH     = os.path.expanduser('~/.csmake/config.json')
PROJECT_CONFIG_RELPATH = os.path.join('.csmake', 'sources.json')


def source_id(url):
    """Short, stable, filesystem-safe identifier for a source URL.

    Used to namespace per-source cache files so two sources can never
    collide on disk, even if they offer a package of the same name.
    """
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]


def _normalize_entries(raw_entries):
    result = []
    for entry in raw_entries:
        if not isinstance(entry, dict) or 'url' not in entry:
            continue
        result.append({
            'scope': entry.get('scope', '*'),
            'ecosystem': entry.get('ecosystem', DEFAULT_ECOSYSTEM),
            'url': entry['url'],
            'type': entry.get('type', 'github-contents'),
            'terminal': bool(entry.get('terminal', False)),
        })
    return result


def _read_layer_file(path):
    """Return the list of source entries declared in a layer file, or []."""
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict) and 'sources' in data:
        return _normalize_entries(data.get('sources') or [])
    if isinstance(data, dict) and 'registries' in data:
        # Legacy format: {"registries": ["https://...", ...]} -- a flat
        # list of csmake-module registry bases, no scoping/terminal support.
        return [
            {
                'scope': '*',
                'ecosystem': DEFAULT_ECOSYSTEM,
                'url': url,
                'type': 'github-contents',
                'terminal': False,
            }
            for url in (data.get('registries') or [])
            if isinstance(url, str)
        ]
    return []


class SourceLayers(object):
    """Resolves the ordered, terminal-aware list of sources for an ecosystem."""

    def __init__(self, cwd=None):
        self._cwd = cwd or os.getcwd()

    def _org_layer(self):
        path = os.environ.get(ORG_ENV_VAR)
        return _read_layer_file(path) if path else []

    def _project_layer(self):
        return _read_layer_file(
            os.path.join(self._cwd, PROJECT_CONFIG_RELPATH))

    def _user_layer(self):
        return _read_layer_file(USER_CONFIG_PATH)

    def _default_layer(self):
        return [dict(entry) for entry in _BUILTIN_SOURCES]

    def effective_sources(self, ecosystem=DEFAULT_ECOSYSTEM):
        """Ordered (highest priority first) list of sources for *ecosystem*.

        Each returned entry also carries its own ``source_id`` under the
        ``id`` key, ready for cache namespacing.
        """
        layers = [
            self._org_layer(),
            self._project_layer(),
            self._user_layer(),
            self._default_layer(),
        ]

        effective = []
        for layer in layers:
            layer_is_terminal = False
            for entry in layer:
                if entry['ecosystem'] not in ('*', ecosystem):
                    continue
                tagged = dict(entry)
                tagged['id'] = source_id(entry['url'])
                effective.append(tagged)
                if entry.get('terminal'):
                    layer_is_terminal = True
            if layer_is_terminal:
                break
        return effective
