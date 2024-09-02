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

class include(CsmakeModuleAllPhase):
    """Purpose: Include another build specification
       Type: Module   Library: csmake (core)
       Phases: *any*
       Options:
           file - File name of the build specification
           path - (OPTIONAL) Path to the build specification
                  DEFAULT: %(WORKING)s
                  (i.e., the path defined by --working-dir)
           description - (OPTIONAL) A description of what the specification is
       Example:
           [include@defaults]
           description = "All the defaults used in these builds"
           path = %(WORKING)s/makefiles
           file = defaults.csmake
       Notes:
           All ~~phases~~ sections included in other specifications are ignored"""

    REQUIRED_OPTIONS = ['file']

    def __repr__(self):
        return "<<include step definition>>"

    def __str__(self):
        return "<<include step definition>>"

    def default(self, options):
        pathspec = "%(WORKING)s"
        if 'path' in options:
            pathspec = options['path'].strip()
        path = self.env.doSubstitutions(pathspec)
        fileName = options['file'].strip()
        self.log.passed()
        return self.engine.includeBuildspec("%s/%s" % (path, fileName))

    def __getattr__(self, name):
        self.env.debug("include: looking up %s" % name)
        return this.default

