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

class environment(CsmakeModuleAllPhase):
    """Purpose: Adds specified option(key)/value pairs into the environment
       Type: Module   Library: csmake (core)
       Phases: *any*
       Options: Adds all options into the environment for future steps
       Example:
           [environment@default]
           mypath = /another/abs/%(dpath)sPath/yeah
           dpath  = this is/a really/coolpath

           mypath would evaluate to:
                 /another/abs/this is/a really/coolpathPath/yeah
           and both "mypath" and "dpath" would be entered into the csmake
           environment.
       Usage:
           csmake environment variables may be accessed using the python
           dictionary "mod" operator notation, %(<variable>)s
           So, with the example above, a later step could access 'mypath'
           by using %(mypath)s in one of its options.
       References:
           https://docs.python.org/2/library/stdtypes.html#string-formatting"""

    def __repr__(self):
        return "<<environment step definition>>"

    def __str__(self):
        return "<<environment step definition>>"

    def _doOptionSubstitutions(self, stepdict):
        #Environment can have options with substitutions
        #defined in the section - we handle our own options
        #substitutions to handle this.
        pass

    def default(self, options):
        try:
            self.env.update(options)
            self.log.passed()
        except Exception as e:
            self.log.exception("Update of environment failed")
            self.log.failed()

    def __getattr__(self, name):
        return self.default
