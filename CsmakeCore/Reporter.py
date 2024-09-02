# <copyright>
# (c) Copyright 2019, 2021 Autumn Patterson
# (c) Copyright 2019 Cardinal Peak Technologies
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

from .phases import phases

class Reporter:
    PHASE_BANNER="""       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
"""
    NESTNOTE='+'

    OUTPUT_HEADER="%s  %%s  %s\n" % ('-'*15, '-'*15)
    PASS_BANNER= "nununununununununununun"
    FAIL_BANNER= ".:*~*:._.:*~*:._.:*~*:."
    SKIP_BANNER= "- - - - - - - - - - - -"
    UNEX_BANNER= "                       "
    DUMP_STACKS_SEPARATOR="""=============================================================================
"""
    DUMP_STACK_SEPARATOR="""
_____________________________________________________________________________
=============================================================================
=== End of failure output and stacks
=============================================================================
"""

    DUMP_STACK_LAST_OUTPUT_SEPARATOR="""
-----------------------------------------------------------------------------
-- - - - - - - - - - - - --- Output From Failure --- - - - - - - - - - - - --
-----------------------------------------------------------------------------
"""
    DUMP_STACK_STACK_SEPARATOR=      """
_____________________________________________________________________________
-----------------------------------------------------------------------------
-- - - - - - - - - - - - - - --- Stack Trace --- - - - - - - - - - - - - - --
-----------------------------------------------------------------------------
"""
    STATUS_FORMAT=" {1}   {2}: {3}   {1}\n"
    ANNOUNCE_FORMAT="{0} {1}@{2}      ---  {3}\n"
    ONEXIT_ANNOUNCE_FORMAT="  /   {3} - Exit Handler: {0}@{1}  {2}\n"

    OBJECT_HEADER= \
"""
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------"""
    OBJECT_FOOTER= \
"""__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)



"""
    ONEXIT_HEADER= \
"""
   ......................................................................
"""
    ONEXIT_FOOTER= \
""" ````````````````````````````````````````````````````````````````````````

"""

    ASPECT_JOINPOINT_HEADER="""
    ___________________________________________________
    \  Begin Joinpoint: %s    
     ```````````````````````````````````````````````````
"""
    ASPECT_JOINPOINT_FOOTER="""
     __________________________________________________
    /  End Joinpoint: %s
    ``````````````````````````````````````````````````
"""
    STATUS_SEPARATOR="%s\n" % ("-" * 66)
    ONEXIT_BEGIN_SEPARATOR=" %s\n" % ("`" *72)
    ONEXIT_END_SEPARATOR="   %s\n" % ("." * 70)

    def __init__(self, out=None):
        self.set_outstream(out)

    def set_outstream(self, out):
        self.out = out

    def start(self, params, nesting=0):
        if self.out is None:
            self.set_outstream(params['Out'])
        self.out.write(self.OBJECT_HEADER)
        self.out.write('\n')
        self.out.write(self.ANNOUNCE_FORMAT.format(
            self.NESTNOTE * nesting,
            params['Type'],
            params['Id'],
            "Begin" ))
        self.out.write(self.STATUS_SEPARATOR)

    def status(self, params, resultType, nesting):
        self.out.write('\n')
        self.out.write(self.STATUS_SEPARATOR)
        if params['status'] == 'Passed':
            statusBanner=self.PASS_BANNER
        elif params['status'] == 'Failed':
            statusBanner=self.FAIL_BANNER
        elif params['status'] == 'Skipped':
            statusBanner=self.SKIP_BANNER
        else:
            statusBanner=self.UNEX_BANNER
        self.out.write(self.STATUS_FORMAT.format(
            self.NESTNOTE * nesting,
            statusBanner,
            resultType,
            params['status']) )

    def end(self, params, nesting):
        self.out.write(self.STATUS_SEPARATOR)
        self.out.write(self.ANNOUNCE_FORMAT.format(
            self.NESTNOTE * nesting,
            params['Type'],
            params['Id'],
            "End" ))
        self.out.write(self.STATUS_SEPARATOR)
        self.out.write(self.OBJECT_FOOTER)

    def startJoinPoint(self, joinpoint):
        self.out.write(self.ASPECT_JOINPOINT_HEADER % joinpoint)
        self.out.write('\n')

    def endJoinPoint(self, joinpoint):
        self.out.write('\n')
        self.out.write(self.ASPECT_JOINPOINT_FOOTER % joinpoint)
        self.out.write('\n')

    def startOnExitCallback(self, name, params):
        self.out.write(self.ONEXIT_HEADER)
        self.out.write(self.ONEXIT_ANNOUNCE_FORMAT.format(
            params['Type'],
            params['Id'],
            name,
            "Begin" ))
        self.out.write(self.ONEXIT_BEGIN_SEPARATOR)

    def endOnExitCallback(self, name, params):
        self.out.write(self.ONEXIT_END_SEPARATOR)
        self.out.write(self.ONEXIT_ANNOUNCE_FORMAT.format(
            params['Type'],
            params['Id'],
            name,
            "End" ) )
        self.out.write(self.ONEXIT_FOOTER)

    def startStackDumpSection(self):
        self.out.write('\n')
        self.out.write(self.DUMP_STACKS_SEPARATOR)
        self.out.write("=== The following failures have occurred\n")
        self.out.write(self.DUMP_STACKS_SEPARATOR)

    def startLastOutput(self):
        self.out.write(self.DUMP_STACK_LAST_OUTPUT_SEPARATOR)

    def startStackDump(self, phase):
        self.out.write(self.DUMP_STACK_STACK_SEPARATOR)
        self.out.write("--- In Phase: %s\n" % phase)

    def endStackDumpSection(self):
        self.out.write(self.DUMP_STACK_SEPARATOR)

    def startPhase(self, phase, doc=None):
        self.out.write(self.PHASE_BANNER)
        self.out.write("        BEGINNING PHASE: %s\n" % phase)
        if doc is not None:
            self.out.write("            %s\n" % doc)

    def endPhase(self, phase, doc=None):
        self.out.write("\n        ENDING PHASE: %s\n" % phase)
        if doc is not None:
            self.out.write("            %s\n" % doc)

    def endLastPhase(self):
        self.out.write(self.PHASE_BANNER)

    def endSequence(self, sequence, doc=None):
        self.out.write("\n   SEQUENCE EXECUTED: %s\n" % phases.joinSequence(sequence))
        if doc is not None:
            self.out.write("     %s\n" % doc)

class NonChattyReporter(Reporter):
    def start(self, params, nesting=0):
        self.out.write(self.ANNOUNCE_FORMAT.format(
                    self.NESTNOTE * nesting,
                    params['Type'],
                    params['Id'],
                    "Begin" ))

    def end(self, params, nesting=0):
        self.out.write(self.ANNOUNCE_FORMAT.format(
                    self.NESTNOTE * nesting,
                    params['Type'],
                    params['Id'],
                    "End" ))

    def startJoinPoint(self, joinpoint):
        pass

    def endJoinPoint(self, joinpoint):
        pass

    def startOnExitCallback(self, name, params):
        pass

    def endOnExitCallback(self, name, params):
        pass

    def startPhase(self, phase, doc=None):
        pass

    def endLastPhase(self):
        pass

    def status(self, params, resultType, nesting):
        self.out.write('\n%s Step Status: %s\n' % (
                    self.NESTNOTE * nesting,
                    params['status'] ) )

class ProgramReporter(Reporter):
    OBJECT_HEADER="""
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
"""
    OBJECT_FOOTER=OBJECT_HEADER

    PASS_BANNER="""
  .--.      .--.      .--.      .--.      .--.      .--.      .--.      .
:::::.\\::::::::.\\::::::::.\\::::::::.\\::::::::.\\::::::::.\\::::::::.\\::::::
'      `--'      `--'      `--'      `--'      `--'      `--'      `--'
"""
    FAIL_BANNER="""
  __   __   __   __   __   __   __   __   __   __   __   __   __   __   __
 _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_
 \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/
"""
    STATUS_FORMAT="""{1}
     {2}: {3}
"""
    def __init__(self, version, out=None):
        Reporter.__init__(self, out)
        self.ANNOUNCE_FORMAT="""
     {3} csmake - version %s
""" % version

class NonChattyProgramReporter(NonChattyReporter):
    def __init__(self, version, out=None):
        NonChattyReporter.__init__(self, out)
        self.ANNOUNCE_FORMAT="""
     {3} csmake - version %s
""" % version

class AspectReporter(Reporter):
    PASS_BANNER="      ~~~~~~      "
    FAIL_BANNER="      ######      "
    NESTNODE="      &"
    OBJECT_HEADER="""       _________________________________________
      |--               Aspect                --|
       \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
        ``````````````````````````````````````````"""

    STATUS_SEPARATOR="        ------------------------------------------\n"
    OBJECT_FOOTER="""        _________________________________________
       //////////////////////////////////////////
      |--             End Aspect              --|
       ``````````````````````````````````````````
"""
    STATUS_FORMAT="{0}   {1} {2}: {3} {1}\n"
    ANNOUNCE_FORMAT="        &{1}@{2}         ...  {3}\n"

