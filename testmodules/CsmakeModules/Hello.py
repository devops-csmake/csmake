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
from Csmake.CsmakeModuleAllPhase import CsmakeModuleAllPhase

class Hello(CsmakeModuleAllPhase):
    """Purpose: To test csmake, that is all"""

    def default(self, options):
        print("Hello, csmake")
        print(("Arguments are: %s" % str(options)))
        print(("Environment is: %s" % str(self.env)))
        self.log.passed()

    def build(self, options):
        print("Hello, build phase for csmake")
        self.log.passed()
