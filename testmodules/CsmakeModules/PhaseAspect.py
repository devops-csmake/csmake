# <copyright>
# (c) Copyright 2018 Jeremiah S. Patterson
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

class PhaseAspect(CsmakeAspect):
    """Purpose: To test csmake **phases for aspects"""

    def special(self, options):
        print("phase: special")
        self.log.passed()

    def build(self, options):
        print("phase: build")
        self.log.passed()

    def other(self, options):
        print("phase: other")
        self.log.passed()

    def start__aspect(self, phase, options, step, stepoptions):
        print("phase: aspect, start")
        self.log.passed()

    def start__anotherAspect(self, phase, options, stepoptions):
        print("phase: anotherAspect, start")
        self.log.passed()

    def passed__aspect(self, phase, options, step, stepoptions):
        print("phase: aspect, passed")
        self.log.passed()

    def failed__aspect(self, phase, options, step, stepoptions):
        print("phase: aspect, failed")
        self.log.passed()

    def end__aspect(self, phase, options, step, stepoptions):
        print("phase: aspect, end")
        self.log.passed()

