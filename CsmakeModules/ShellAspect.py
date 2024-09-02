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
from CsmakeModules.Shell import Shell
from CsmakeCore.CsmakeAspect import CsmakeAspect
import os
import subprocess
import sys

class ShellAspect(CsmakeAspect):
    """Purpose: Execute out to a shell command
                on advice of aspect joinpoints
       Type: Aspect   Library: csmake (core)
       Options:
           command(<point>)
              - shell command to execute (semi-colons need to be escaped)
                where <point> is either
                    command(<joinpoint>) or
                    command(<joinpoint>__<phase>)
                    (just as any other aspect)
           advise(<point>[#<time>]) = <advise point>:<vote>
              - Will vote Yes or No on the given advice control point
                (only on commands implemented)
                <time> (optional) represents what it will do on the
                       specified time the
                       the joinpoint specified is executed for the given step
                       If not used the same advice will be given every time
                <advise point> is the flow control point to advise on
                    (e.g., tryAgain)
                <vote> is either True or False
           env - (Optional) Reference to a ShellEnv to use
                 Can be multiple envs, comma or newline separated
                 Default is the csmake execution environment
           exec - (Optional) Shell command to use
                 Default is /bin/bash
       Phase: Any
       Joinpoint: Any
           Defaults are:
               avoided - given when a section will be avoided ~~future~~
               start - given when a section will be started
               passed - given when a section completes successfully
               failed - given when a section fails
               exception - given when a section causes an exception
               end - given when a section completes execution
           Flow control issues for advise are:
               doNotStart - checked after 'start'
               tryAgain - checked after passed, failed, and exception
               doNotAvoid - checked after 'avoided' ~~future~~
       Example:
           [ShellEnv@my-command-env]
           THIS_DIR=mydir

           [Command@my-step]
           stuff=happens

           #This will shell at the start of my-step in the 'build' phase
           [&ShellAspect@my-step doshellstuff]
           command(start__build) =
              mkdir -p ${THIS_DIR} && pushd ${THIS_DIR}
              ifconfig > my.cfg
              ls
              popd
              ls
           env = my-command-env, default-env"""

    def __init__(self, env, log):
        CsmakeAspect.__init__(self, env, log)
        self.pointTracking = {}
        self.sheller = Shell(env, log)

    #TODO: Consider adding __str__ and __repr__ definitions
    #      These will currently go to the "AllPhases" output

    def _findAndTrackAdvice(self, joinpoint, options):
        if joinpoint not in self.pointTracking:
            self.pointTracking[joinpoint] = 0
        currentTime = self.pointTracking[joinpoint] + 1
        self.pointTracking[joinpoint] = currentTime

        #Look for advise in options
        bestMatchValue = None
        for key, value in options.items():
            if key.startswith("advise(%s" % joinpoint):
                keyparts = key.split('#')
                if len(keyparts) == 1:
                    bestMatchValue = value.strip()
                if len(keyparts) == 2:
                    time = keyparts[1].strip().rstrip(')')
                    timeValue = -1
                    try:
                       timeValue = int(time)
                    except:
                       self.log.warning("advise spec had %s for <time> which failed to parse", time)
                       continue
                    if timeValue == currentTime:
                        bestMatchValue = value
                        break

        if bestMatchValue is not None:
            valueparts = bestMatchValue.split(':')
            voteValue = False
            try:
                voteValue = bool(valueparts[1].strip())
            except:
                self.log.warning("advise value had %s for the <vote> which failed to parse", valueparts[1].strip())
                self.log.warning("   valid values are: True, False")
                return
            self.flowcontrol.vote(valueparts[0].strip(), voteValue, self)

    def _lookupSubclassImplementedJoinPoints(self, joinpoint, phase, options):
        #Get any hard implemented aspect
        return CsmakeAspect._joinPointLookup(
            self, joinpoint, phase, options)

    def _joinPointLookup(self, joinpoint, phase, options):
        result = self._lookupSubclassImplementedJoinPoints(joinpoint, phase, options)

        #Now get the command, if any
        dispatchString = self._getDispatchString(joinpoint, phase)
        (commandType, command) = self.sheller._getCommand(options, dispatchString)
        if command is not None:
            self._findAndTrackAdvice(dispatchString, options)
        else:
            (commandType, command) = self.sheller._getCommand(options, joinpoint)
            if command is not None:
                self._findAndTrackAdvice(joinpoint, options)

        if command is None:
            self.log.devdebug("A command definition, command(%s) or command(%s), was not found", dispatchString, joinpoint)
            if result is None:
                self.log.devdebug("No joinpoint implementation was found")
                return None

        execer = self.sheller._getExecer(options)
        newenv = self.sheller._getStartingEnvironment(options)
        env = self.sheller._getEnvironment(options, newenv)
        if command is None and result is None:
            return None
        def handler(phase, aspectdict, execinstance, stepdict):
            ret = None
            if result is not None:
                ret = result(phase, aspectdict, execinstance, stepdict)
            if command is not None:
                if not self.optionSubstitutionsDone:
                    self._doOptionSubstitutions(stepdict)
                ret = self.sheller._executeShell(command, env, execer)
                if ret != 0:
                    self.log.error("Shell execution for joinpoint failed")
                    self.log.failed()
                else:
                    self.log.passed()
            return ret

        self.log.devdebug("Returning handler (%s)", str(handler))
        return handler
