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
"""Platform package-name hints for system executables csmake modules may
declare (via a module docstring's ``Requires: exec:`` field, or a
spec-level ``**requires=``).

Data only -- csmake never installs anything (see the preflight check in
CliDriver.py). This table only powers the *hint* in that report ("missing
'gpg': try `apt install gnupg`"). Seeded from what today's core and
csmake-packaging modules already shell out to.

A package or a walled garden can extend/override this at the point they
consume it -- same source-of-truth-by-layer philosophy as everywhere else
in docs/MODULE_ECOSYSTEM_DESIGN.md; this module itself is just the
built-in default layer.
"""

import shutil

HINTS = {
    "gpg":        {"apt": "gnupg",     "dnf": "gnupg2",    "brew": "gnupg"},
    "gpg2":       {"apt": "gnupg2",    "dnf": "gnupg2",    "brew": "gnupg"},
    "rpmbuild":   {"apt": "rpm",       "dnf": "rpm-build", "brew": "rpm"},
    "rpm2cpio":   {"apt": "rpm",       "dnf": "rpm-build", "brew": "rpm"},
    "dpkg-deb":   {"apt": "dpkg-dev",  "dnf": None,        "brew": None},
    "dpkg-buildpackage": {"apt": "dpkg-dev", "dnf": None,  "brew": None},
    "fakeroot":   {"apt": "fakeroot",  "dnf": "fakeroot",  "brew": "fakeroot"},
    "lintian":    {"apt": "lintian",   "dnf": None,        "brew": None},
    "chrpath":    {"apt": "chrpath",   "dnf": "chrpath",   "brew": "chrpath"},
    "docker":     {"apt": "docker.io", "dnf": "docker",    "brew": "docker (cask)"},
    "git":        {"apt": "git",       "dnf": "git",       "brew": "git"},
}


def hint_for(exec_name, platform):
    """Return a platform-specific install-hint package name, or None if
    *exec_name* or *platform* isn't in the table."""
    entry = HINTS.get(exec_name)
    if not entry:
        return None
    return entry.get(platform)


def detect_platform():
    """Best-effort local packaging platform: 'brew', 'apt', 'dnf', or
    None if none of those package managers are on PATH."""
    if shutil.which('brew'):
        return 'brew'
    if shutil.which('apt-get') or shutil.which('apt'):
        return 'apt'
    if shutil.which('dnf') or shutil.which('yum'):
        return 'dnf'
    return None
