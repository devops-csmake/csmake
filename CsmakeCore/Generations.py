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
"""Cache generations: a snapshot of pinned package versions, and nothing
more -- no separate artifact storage.  Package artifacts are already
content-addressed by (package, version) under ``~/.csmake/modules/``
(see ``ModuleRegistry``), so a generation is just a manifest file that
plugs into the SAME pin-resolution machinery ``[~~packages~~]`` already
uses (see ``CliDriver._packagePins`` / ``docs/MODULE_ECOSYSTEM_DESIGN.md``),
at the lowest priority -- an explicit ambient pin still wins.

Layout
------
~/.csmake/generations/
  current                 <- plain text: the active generation's name
  <name>.json             <- {"packages": {pkgname: version, ...},
                               "parent": <previous-name-or-null>}

Remastering (recording a new snapshot) is a pure metadata operation --
it resolves each package's "latest" against the registry's combined
index but does not itself download anything; artifacts are still
fetched lazily the first time a build actually needs one (the existing
mechanism). Actually populating a walled garden with the artifacts a
generation pins is ``MirrorSync``'s job, not this module's.
"""

import json
import os


DEFAULT_ROOT = os.path.expanduser('~/.csmake/generations')


def _atomic_write(path, text):
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory)
        except OSError:
            pass
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(text)
    os.replace(tmp, path)


class GenerationError(Exception):
    pass


class Generations(object):
    def __init__(self, root=None):
        self._root = root or DEFAULT_ROOT

    def _manifest_path(self, name):
        return os.path.join(self._root, '%s.json' % name)

    def _current_path(self):
        return os.path.join(self._root, 'current')

    def current_name(self):
        """Return the active generation's name, or None if none is set."""
        path = self._current_path()
        if not os.path.isfile(path):
            return None
        with open(path) as f:
            name = f.read().strip()
        return name or None

    def current(self):
        """Return the active generation's manifest dict, or None."""
        name = self.current_name()
        if name is None:
            return None
        return self.get(name)

    def get(self, name):
        """Return the manifest dict for *name*, or None if it doesn't exist."""
        path = self._manifest_path(name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None

    def exists(self, name):
        return os.path.isfile(self._manifest_path(name))

    def remaster(self, name, combined_index, packages=None):
        """Create generation *name*, resolving each package's version.

        *combined_index* is a ``ModuleRegistry``-shaped combined index
        dict (``{"packages": {pkgname: {"latest": ..., ...}}}``).
        *packages* is an iterable of package names to pin to their
        current "latest"; if omitted, uses the current generation's own
        package set (or an empty set if there is no current generation --
        the first-ever remaster starts from nothing).

        Does not promote the new generation -- call promote() for that.
        Returns the new manifest dict.  Raises GenerationError if *name*
        already exists (generations are immutable once created, matching
        the registry's own "published versions are immutable" invariant)
        or if a named package isn't in the index.
        """
        if self.exists(name):
            raise GenerationError(
                "generation '%s' already exists (generations are "
                "immutable -- remaster to a new name)" % name)

        if packages is None:
            current = self.current()
            packages = list(current['packages'].keys()) if current else []

        resolved = {}
        for pkgname in packages:
            pkg_data = combined_index.get('packages', {}).get(pkgname)
            if not pkg_data:
                raise GenerationError(
                    "package '%s' not found in the registry index" % pkgname)
            latest = pkg_data.get('latest')
            if not latest:
                raise GenerationError(
                    "package '%s' has no 'latest' version in the index"
                    % pkgname)
            resolved[pkgname] = latest

        manifest = {
            'packages': resolved,
            'parent': self.current_name(),
        }
        _atomic_write(
            self._manifest_path(name),
            json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        return manifest

    def promote(self, name):
        """Make *name* the active generation."""
        if not self.exists(name):
            raise GenerationError("generation '%s' does not exist" % name)
        _atomic_write(self._current_path(), name + '\n')

    def rollback(self):
        """Revert to the active generation's own parent.

        Returns the restored generation's name.  Raises GenerationError
        if there is no active generation, or it has no parent to revert
        to (nothing to roll back to).
        """
        current = self.current()
        if current is None:
            raise GenerationError("no active generation to roll back from")
        parent = current.get('parent')
        if not parent:
            raise GenerationError(
                "generation '%s' has no parent to roll back to"
                % self.current_name())
        self.promote(parent)
        return parent
