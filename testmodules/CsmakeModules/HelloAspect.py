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
from Csmake.CsmakeAspect import CsmakeAspect

class HelloAspect(CsmakeAspect):
    """Purpose: To test csmake aspects, that is all"""

    def start__build(self, phase, options, step, stepoptions):
        self.start(phase, options, step, stepoptions)
        print("This is the aspect, start__build....HELLO!!!!")
        return True

    def start(self, phase, options, step, stepoptions):
        self.repeat = True
        print("The step given is: %s" % str(step))
        print("The step options are: %s" % str(stepoptions))
        self.log.passed()

    def end(self, phase, options, step, stepoptions):
        print("Aspect: General end for all phases")
        self.log.passed()

    def passed(self, phase, options, step, stepoptions):
        print("Aspect: the step succeeded")
        self.log.passed()

    def failed(self, phase, options, step, stepoptions):
        print("Aspect: the step failed")
        if self.repeat:
            self.log.info("Trying the step again")
            self.flowcontrol.vote("tryAgain", True, self)
        self.repeat = False
        self.log.passed()
        
