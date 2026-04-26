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

class HelloFailed(CsmakeModuleAllPhase):
    """Purpose: To test csmake tryagain advice"""

    def __init__(self, env, log):
        CsmakeModuleAllPhase.__init__(self, env, log)
        self.attempts = 0

    def default(self, options):
        totalAttempts = int(options['totalAttempts'].strip())
        self.attempts = self.attempts + 1
        if self.attempts >= totalAttempts:
            self.log.info("Passing test this time %d out of %d" % (
                self.attempts,
                totalAttempts) )
            self.log.passed()
            return True
        self.log.error("This run will fail %d out of %d" % (
            self.attempts,
            totalAttempts ) )
        self.log.failed()
        return False
