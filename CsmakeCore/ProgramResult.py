# <copyright>
# (c) Copyright 2019 Autumn Samantha Jeremiah Patterson
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
from .Result import Result
from .phases import phases
from .Reporter import ProgramReporter, NonChattyProgramReporter

class ProgramResult(Result):

    def __init__(self, env, version, resultInfo={}):
        Result.__init__(self, env, resultInfo)
        if self.chatter:
            self.reporter = ProgramReporter(version, self.params['Out'])
        else:
            self.reporter = NonChattyProgramReporter(version, self.params['Out'])

    def setupTee(self):
        pass

    def log(self, level, output, *params):
        #print "XXX Output: %s" % output
        #print "XXX params: %s" % str(params)
        try:
            self.write("` %s: %s\n" % (
                level,
                output % params ) )
        except:
            self.write("  %s: %s(%s)" % (
                str(level),
                str(output),
                str(params) ) )

    def chatStartPhase(self, phase, doc=None):
        if self.loglevel:
            self.reporter.startPhase(phase, doc)

    def chatEndPhase(self, phase, doc=None):
        if self.loglevel:
            self.reporter.endPhase(phase, doc)

    def chatEndLastPhaseBanner(self):
        if self.loglevel:
            self.reporter.endLastPhase()

    def chatEndSequence(self, sequence, doc=None):
        if self.loglevel:
            if len(sequence) > 0:
                self.reporter.endSequence(sequence, doc)
