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
import threading

class command(CsmakeModuleAllPhase):
    """Purpose: Execute a series of build steps - the initial step is
                a command provided by the command line input (see --command)
       Type: Module    Library: csmake (core)
       Phases: *any*
       Options: The keys are used to order the steps lexicographically
              e.g.: 1, 10, 2, 20, 200, 3, A, a (suggestion use 0000-9999)
              The values are atomic groups of steps
                 , - denotes step follows the next
                 & - denotes steps that can be run in parallel
           description - Provides a description of the command that
                         csmake will use for --list-commands.
       Example:
           [command@build-pond]
           description = "This will build a small pond"
           10 = init
           20 = repo1 & repo2 & repo3, repo4
           30 = createPond
           40 = stockFish

           Execution of the "build-pond" command would proceed as follows:
           The init section would execute
           Then repo1, repo2, and repo3 would execute in parallel
           Then repo4 would execute
           Then createPond would execute
           Finally, stockFish would execute
    """

    RESERVED_FLAGS = ['description']

    def __repr__(self):
        return "<<command step definition>>"

    def __str__(self):
        return "<<command step definition>>"

    def _prepareCommand(self, options):
        self.log.devdebug("command options: %s", str(options))
        steps = list(options.keys())
        steps.sort()
        result = []
        for stanzakey in steps:
            if stanzakey.startswith('**'):
                continue
            if stanzakey in command.RESERVED_FLAGS:
                continue
            stanzaparts = options[stanzakey].split(',');
            for part in stanzaparts:
                step = part.split('&');
                result.append(step)
        self.log.devdebug("The command structure is %s", str(result))
        return result

    def default(self, options):
        class CommandThread(threading.Thread):
            def __init__(innerself, parallelpart):

                threading.Thread.__init__(innerself)
                innerself.parallelpart = parallelpart.strip()
                innerself.failure = True
                innerself._parent = threading.currentThread()

            def run(innerself):
                result = self.engine.launchStep(
                    innerself.parallelpart,
                    self.engine.getPhase())
                innerself.failure = result is None or not result._didPass()

            def failed(innerself):
                return innerself.failure

            def parent(innerself):
                return innerself._parent

        steps = self._prepareCommand(options)
        failure = False
        for step in steps:
            threads = []
            for parallelpart in step:
                if len(step) < 2:
                    result = self.engine.launchStep(
                        parallelpart.strip(),
                        self.engine.getPhase())
                    if result is None or not result._didPass():
                        self.log.error("XXXXXX Step '%s' FAILED XXXXXX" % parallelpart.strip())
                        self.log.failed()
                        failure = True
                        if not self.engine.settings['keep-going']:
                            return None
                else:
                    threads.append(
                        CommandThread(
                            parallelpart ) )
                    threads[-1].start()
            for thread in threads:
                if thread.isAlive():
                    thread.join()
                if thread.failed():
                    self.log.error("XXXXXX Step '%s' FAILED XXXXXX" % thread.parallelpart)
                    self.log.failed()
                    failure = True
            if failure and not self.engine.settings['keep-going']:
                return None

        if not failure:
            self.log.passed()
        return steps

