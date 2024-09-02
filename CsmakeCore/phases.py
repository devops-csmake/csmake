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
class phases:
    """
    This is an *informational* section in the csmakefile for csmake
    This section may not be executed or referred to in the rest
    of the build specification.
    The declaration of this section in the csmakefile *does not*
    have an id.  I.e., the section is *only*:  [~~phases~~]
Purpose: Declare, document, and validate phases and multicommands.

         csmake will use this special section to verify validity of
         the phases and provide information about
         phases that the end-user of the csmakefile may use
         to build.

         It also allows the makefile to declare valid combinations
         of phases, what the default combination should be, and
         what multicommand combinations are considered useful
Options:
    <phase> - Document and declare a phase
    **sequences
        Document what various combinations of phases accomplish
        The format of **sequences is:
            <phase> -> <phase> -> ... -> <phase>: <doc>
    **default
        Declare a default phase sequence.
        When defined, the sequence will be executed instead of the
        "default" phase when csmake is not given any phases on the command-line.
        The format of **default is a sequence:
            <phase> -> <phase> -> ... -> <phase>
    **multicommands
        Document what combinations of commands/sections do if
        they are executed together.
        (Multicommands are not validated against user input)
        The format of multicommands is:
            <command> (,|&) <command> ... <command>: <doc>
    **requires
        System packages required to build the contents of the csmakefile.
        (requires is currently not validated)

Example:
    [~~phases~~]
    build=build the thing
    clean=clean the thing
    xyzzy=do magic on the thing
    test=test the thing
    **sequences=
        clean -> build -> xyzzy -> test -> clean: Full test build sequence
        clean -> build: No magic phrase inserted to result
    **default= clean -> build -> xyzzy
    **requires=
         csmake-providers
         csmake-swak
         n81
    """
    @staticmethod
    def parseSequence(sequence):
        """Takes a sequence string and creates a sequence list"""
        return [phase.strip() for phase in sequence.split('->')]

    @staticmethod
    def joinSequence(sequence):
        """Takes a sequence list and creates a sequence string"""
        return ' -> '.join(sequence)

    def __init__(self, phaseOptions, log):
        self.log = log
        self.options = phaseOptions
        self.phases = {'phases':{}}
        if self.options is not None:
            self._processPhases()

    def _process_sequences(self, sequences):
        result = []
        sequencelist = sequences.split('\n')
        skew = 0
        for count, sequence in enumerate(sequencelist):
            sequence = sequence.strip()
            if len(sequence) == 0:
                skew = skew + 1
                continue
            if ':' not in sequence:
                self.log.error("~~phases~~: Sequence %d: no ':' found", count-skew)
                self.log.error("   %s" % sequence)
                self.log.error("   Run: csmake --list-type=~~phases~~ for help")
                continue
            sequenceparts = sequence.split(':')
            phaseparts = phases.parseSequence(sequenceparts[0])
            result.append((phaseparts, sequenceparts[1]))
        return result

    def _process_multicommands(self, commands):
        return commands.strip().split('\n')

    def _process_default(self, default):
        return phases.parseSequence(default)

    def _process_requires(self, default):
        #TODO: Put broad testing for requirements here...
        #       Be carefile not to add apt or other dependencies
        return True

    def _processPhases(self):
        for key, value in self.options.items():
            if key.startswith('__'):
                continue
            if key.startswith('**'):
                special = "_process_%s" % key[2:]
                if hasattr(self, special):
                    self.phases[key[2:]] = getattr(self,special)(value)
            else:
                self.phases['phases'][key] = value

    def dumpPhases(self):
        self.log.chat("")
        phaseDict = self.phases['phases']
        self.log.chat("=================== Valid Phases ===================")
        if len(phaseDict) == 0:
            self.log.chat("***  No phases have been declared")
            self.log.chat("***  Declare phases in a [~~phases~~] section")
            self.log.chat("***  csmake --list-type=~~phases~~ for help")
        else:
            for phase in phaseDict.items():
                self.log.chat("%s: %s" % phase)
        if 'sequences' in self.phases:
            self.log.chat("")
            self.log.chat("=============== Valid Phase Sequences ==============")
            for sequence, doc in self.phases['sequences']:
                sequencestring = phases.joinSequence(sequence)
                self.log.chat("%s: %s" % (sequencestring, doc))
        if 'default' in self.phases:
            self.log.chat("")
            self.log.chat("Default sequence: %s" % phases.joinSequence(
                                                  self.phases['default']) )
            self.log.chat("   (Executed when phase(s) not given on command line)")
        self.dumpMulticommands()

    def dumpMulticommands(self):
        if 'multicommands' in self.phases:
            self.log.chat("")
            self.log.chat("============= Suggested Multicommands ==============")
            for multi in self.phases['multicommands']:
                self.log.chat("    %s" %multi)

    def validatePhase(self, phase):
        if phase not in self.phases['phases']:
            self.log.warning("Phase '%s' not declared in ~~phases~~ section", phase)
            self.log.warning("  Run: csmake --list-type=~~phases~~ for help")
            return (None, None)
        return (phase, self.phases['phases'][phase])

    def validateSequence(self, sequence):
        if len(sequence) > 1:
            if 'sequences' not in self.phases:
                self.log.warning("No sequences have been defined in ~~phases~~")
                self.log.warning("  Run: csmake --list-type=~~phases~~ for help")
                return (None, None)
            for decledSequence in self.phases['sequences']:
                if decledSequence[0] == sequence:
                    return decledSequence
            self.log.warning("The sequence of phases was not declared in ~~phases~~")
            self.log.warning("  Sequence: %s", phases.joinSequence(sequence))
            self.log.warning("  Run: csmake --list-type=~~phases~~ for help")
            return (None, None)
        elif len(sequence) == 0:
            return (None, None)
        else:
            return self.validatePhase(sequence[0])

    def getDefaultSequence(self):
        if 'default' in self.phases:
            return self.phases['default']
        else:
            return [ 'default' ]
