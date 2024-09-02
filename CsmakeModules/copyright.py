# <copyright>
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
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
from CsmakeCore.CsmakeModuleAllPhase import CsmakeModuleAllPhase

class copyright(CsmakeModuleAllPhase):
    """Purpose: Create a copyright clause for the software described in
                a csmakefile.
       Type: Module   Library: csmake (core)
       Phases: *any*
       Options:
           holder - Holder(s) of the license
           years - The years in which the copyrighted material has bee
                  updated.  E.g., 2014   or   2014-2017    or   2012,2015-2016
           license - (OPTIONAL) Describes a license (e.g., non-free, GPL2+)
                     see https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/index.html#license-field
                     and https://spdx.org/licenses/
           license-text - (OPTIONAL) The text for the full license to include
           disclaimer - (OPTIONAL) A statement about the copyright
             (for example, for Debian, why the copyright is non-free)
           comment - (OPTIONAL) Any apropos comment for the copyright
       Results: A dictionary containing the options provided.
       References:
           The most comprehensive copyright documentation for packaging
           comes from debian and is the inspiration for this module:
           https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"""

    REQUIRED_OPTIONS = ['holder', 'years']

    def __repr__(self):
        return "<<copyright step definition>>"

    def __str__(self):
        return "<<copyright step definition>>"

    def default(self, options):
        result = {}
        for key, value in options.items():
            if key.startswith("**"):
                continue
            result[key] = value

        self.log.passed()
        return result
