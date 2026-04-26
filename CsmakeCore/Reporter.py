# <copyright>
# (c) Copyright 2019, 2021, 2024 Autumn Patterson
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

import os
import sys

from .phases import phases

# ---------------------------------------------------------------------------
# Color / style detection
#
# The decoration style is chosen once at import time from the environment:
#
#   NO_COLOR=1          disable color and Unicode (https://no-color.org/)
#   FORCE_COLOR=1       force color even when stdout is not a TTY
#   CSMAKE_STYLE=plain  same effect as NO_COLOR for csmake output only
#
# Subclass any Reporter and override the class constants to apply a fully
# custom style without touching this module.
# ---------------------------------------------------------------------------

def _detect_color():
    if os.environ.get('NO_COLOR') or os.environ.get('CSMAKE_STYLE', '').lower() == 'plain':
        return False
    if os.environ.get('FORCE_COLOR'):
        return True
    try:
        return (
            hasattr(sys.stdout, 'isatty')
            and sys.stdout.isatty()
            and os.environ.get('TERM', 'xterm') != 'dumb'
        )
    except Exception:
        return False

_COLOR = _detect_color()

# ANSI escape sequences — only meaningful when _COLOR is True, but defined
# unconditionally so the class bodies below can reference them in both branches
# of the `if _COLOR` conditionals without NameError.
_R   = '\033[0m'        # reset
_B   = '\033[1m'        # bold
_D   = '\033[2m'        # dim
_G   = '\033[1;32m'     # bold green
_RD  = '\033[1;31m'     # bold red
_Y   = '\033[33m'       # yellow
_C   = '\033[36m'       # cyan
_BC  = '\033[1;36m'     # bold cyan
_BR  = '\033[1;31m'     # bold red (alias)


class Reporter:

    NESTNOTE = '+'
    OUTPUT_HEADER = "%s  %%s  %s\n" % ('-' * 15, '-' * 15)

    if _COLOR:
        # ------------------------------------------------------------------
        # Color + Unicode mode  (modern terminal)
        # ------------------------------------------------------------------
        PASS_BANNER  = _G  + ' ✔  ✔  ✔  ✔  ✔  ✔  ✔  ✔  ✔  ✔  ✔ ' + _R
        FAIL_BANNER  = _RD + ' ✘  ✘  ✘  ✘  ✘  ✘  ✘  ✘  ✘  ✘  ✘ ' + _R
        SKIP_BANNER  = _D  + ' ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  · ' + _R
        UNEX_BANNER  =       '                                     '

        # Step block borders
        OBJECT_HEADER      = '\n' + _D + '  ╭' + '─' * 64 + '╮' + _R
        OBJECT_FOOTER      = _D + '  ╰' + '─' * 64 + '╯' + _R + '\n\n\n'
        STATUS_SEPARATOR   = _D + '  ├' + '─' * 64 + '┤' + _R + '\n'

        # Phase banner (printed before "BEGINNING PHASE: ...")
        PHASE_BANNER = '\n' + _BC + '  ╒' + '═' * 64 + '╕' + _R + '\n'

        # Announce line  ({0}=nesting, {1}=type, {2}=id, {3}=Begin|End)
        ANNOUNCE_FORMAT = (
            '  {0}' + _C + '{1}' + _R + '@' + _B + '{2}' + _R
            + '      ' + _D + '···' + _R + '  {3}\n'
        )
        ONEXIT_ANNOUNCE_FORMAT = (
            '  /   ' + _D + '{3}' + _R + ' - Exit Handler: {0}@{1}  {2}\n'
        )

        STATUS_FORMAT = ' {1}   {2}: {3}   {1}\n'

        # Exit handler separators
        ONEXIT_HEADER          = '\n' + _D + '   ' + '· ' * 34 + _R + '\n'
        ONEXIT_FOOTER          = _D + ' ' + '‘ ' * 36 + _R + '\n\n'
        ONEXIT_BEGIN_SEPARATOR = _D + ' ' + '· ' * 36 + _R + '\n'
        ONEXIT_END_SEPARATOR   = _D + '   ' + '· ' * 35 + _R + '\n'

        # Aspect joinpoint separators
        ASPECT_JOINPOINT_HEADER = (
            '\n' + _D + '    ╰─ Begin Joinpoint: %s ' + _R + '\n'
        )
        ASPECT_JOINPOINT_FOOTER = (
            '\n' + _D + '    ╭─ End Joinpoint: %s ' + _R + '\n'
        )

        # Failure stack-dump separators  (red to draw attention)
        DUMP_STACKS_SEPARATOR = _RD + '=' * 77 + _R + '\n'
        DUMP_STACK_SEPARATOR = (
            '\n' + _RD + '_' * 77 + '\n'
            + '=' * 77 + '\n'
            + '=== End of failure output and stacks\n'
            + '=' * 77 + _R + '\n'
        )
        DUMP_STACK_LAST_OUTPUT_SEPARATOR = (
            '\n' + _RD + '-' * 77 + '\n'
            + '-- - - - - - - - - - --- Output From Failure --- - - - - - - - - - --\n'
            + '-' * 77 + _R + '\n'
        )
        DUMP_STACK_STACK_SEPARATOR = (
            '\n' + _RD + '_' * 77 + '\n'
            + '-' * 77 + '\n'
            + '-- - - - - - - - - - - - --- Stack Trace --- - - - - - - - - - - - --\n'
            + '-' * 77 + _R + '\n'
        )

    else:
        # ------------------------------------------------------------------
        # Plain ASCII mode  (pipe, dumb terminal, NO_COLOR)
        # ------------------------------------------------------------------
        PASS_BANNER  = '> > > > > > > > > > > > > > > > > > > > > >'
        FAIL_BANNER  = 'X X X X X X X X X X X X X X X X X X X X X X'
        SKIP_BANNER  = '. . . . . . . . . . . . . . . . . . . . . .'
        UNEX_BANNER  = '                                            '

        OBJECT_HEADER      = '\n  +' + '-' * 64 + '+'
        OBJECT_FOOTER      = '  +' + '-' * 64 + '+\n\n\n'
        STATUS_SEPARATOR   = '  ' + '-' * 66 + '\n'

        PHASE_BANNER = '\n  ' + '=' * 66 + '\n'

        ANNOUNCE_FORMAT        = '  {0}{1}@{2}      ---  {3}\n'
        ONEXIT_ANNOUNCE_FORMAT = '  /   {3} - Exit Handler: {0}@{1}  {2}\n'

        STATUS_FORMAT = ' {1}   {2}: {3}   {1}\n'

        ONEXIT_HEADER          = '\n   ' + '.' * 70 + '\n'
        ONEXIT_FOOTER          = ' ' + '`' * 72 + '\n\n'
        ONEXIT_BEGIN_SEPARATOR = ' ' + '`' * 72 + '\n'
        ONEXIT_END_SEPARATOR   = '   ' + '.' * 70 + '\n'

        ASPECT_JOINPOINT_HEADER = '\n    +-- Begin Joinpoint: %s\n'
        ASPECT_JOINPOINT_FOOTER = '\n    +-- End Joinpoint: %s\n'

        DUMP_STACKS_SEPARATOR = '=' * 77 + '\n'
        DUMP_STACK_SEPARATOR = (
            '\n' + '_' * 77 + '\n'
            + '=' * 77 + '\n'
            + '=== End of failure output and stacks\n'
            + '=' * 77 + '\n'
        )
        DUMP_STACK_LAST_OUTPUT_SEPARATOR = (
            '\n' + '-' * 77 + '\n'
            + '-- - - - - - - - - - --- Output From Failure --- - - - - - - - - - --\n'
            + '-' * 77 + '\n'
        )
        DUMP_STACK_STACK_SEPARATOR = (
            '\n' + '_' * 77 + '\n'
            + '-' * 77 + '\n'
            + '-- - - - - - - - - - - - --- Stack Trace --- - - - - - - - - - - - --\n'
            + '-' * 77 + '\n'
        )

    # ------------------------------------------------------------------
    # Methods — unchanged regardless of style
    # ------------------------------------------------------------------

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
            "Begin"))
        self.out.write(self.STATUS_SEPARATOR)

    def status(self, params, resultType, nesting):
        self.out.write('\n')
        self.out.write(self.STATUS_SEPARATOR)
        if params['status'] == 'Passed':
            statusBanner = self.PASS_BANNER
        elif params['status'] == 'Failed':
            statusBanner = self.FAIL_BANNER
        elif params['status'] == 'Skipped':
            statusBanner = self.SKIP_BANNER
        else:
            statusBanner = self.UNEX_BANNER
        self.out.write(self.STATUS_FORMAT.format(
            self.NESTNOTE * nesting,
            statusBanner,
            resultType,
            params['status']))

    def end(self, params, nesting):
        self.out.write(self.STATUS_SEPARATOR)
        self.out.write(self.ANNOUNCE_FORMAT.format(
            self.NESTNOTE * nesting,
            params['Type'],
            params['Id'],
            "End"))
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
            "Begin"))
        self.out.write(self.ONEXIT_BEGIN_SEPARATOR)

    def endOnExitCallback(self, name, params):
        self.out.write(self.ONEXIT_END_SEPARATOR)
        self.out.write(self.ONEXIT_ANNOUNCE_FORMAT.format(
            params['Type'],
            params['Id'],
            name,
            "End"))
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
            "Begin"))

    def end(self, params, nesting=0):
        self.out.write(self.ANNOUNCE_FORMAT.format(
            self.NESTNOTE * nesting,
            params['Type'],
            params['Id'],
            "End"))

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
            params['status']))


class ProgramReporter(Reporter):
    if _COLOR:
        OBJECT_HEADER = (
            '\n' + _BC
            + '  ╔' + '═' * 71 + '╗\n'
            + '  ║' + ' ' * 71 + '║\n'
            + '  ╚' + '═' * 71 + '╝'
            + _R + '\n'
        )
        OBJECT_FOOTER = OBJECT_HEADER

        PASS_BANNER = (
            _G
            + '\n  ┌' + '─' * 71 + '┐\n'
            + '  │' + ' ' * 71 + '│\n'
            + '  │  ✔  Build Passed' + ' ' * 57 + '│\n'
            + '  │' + ' ' * 71 + '│\n'
            + '  └' + '─' * 71 + '┘\n'
            + _R
        )
        FAIL_BANNER = (
            _RD
            + '\n  ┌' + '─' * 71 + '┐\n'
            + '  │' + ' ' * 71 + '│\n'
            + '  │  ✘  Build Failed' + ' ' * 57 + '│\n'
            + '  │' + ' ' * 71 + '│\n'
            + '  └' + '─' * 71 + '┘\n'
            + _R
        )
    else:
        OBJECT_HEADER = (
            '\n'
            '  +' + '=' * 71 + '+\n'
            '  |' + ' ' * 71 + '|\n'
            '  +' + '=' * 71 + '+\n'
        )
        OBJECT_FOOTER = OBJECT_HEADER

        PASS_BANNER = (
            '\n  +' + '-' * 71 + '+\n'
            '  |' + ' ' * 71 + '|\n'
            '  |  >>  Build Passed' + ' ' * 50 + '|\n'
            '  |' + ' ' * 71 + '|\n'
            '  +' + '-' * 71 + '+\n'
        )
        FAIL_BANNER = (
            '\n  +' + '-' * 71 + '+\n'
            '  |' + ' ' * 71 + '|\n'
            '  |  XX  Build Failed' + ' ' * 50 + '|\n'
            '  |' + ' ' * 71 + '|\n'
            '  +' + '-' * 71 + '+\n'
        )

    STATUS_FORMAT = '{1}\n     {2}: {3}\n'

    def __init__(self, version, out=None):
        Reporter.__init__(self, out)
        if _COLOR:
            self.ANNOUNCE_FORMAT = (
                '\n     ' + _B + '{3}' + _R + ' csmake'
                + _D + ' - version %s' % version + _R + '\n'
            )
        else:
            self.ANNOUNCE_FORMAT = '\n     {3} csmake - version %s\n' % version


class NonChattyProgramReporter(NonChattyReporter):
    def __init__(self, version, out=None):
        NonChattyReporter.__init__(self, out)
        if _COLOR:
            self.ANNOUNCE_FORMAT = (
                '\n     ' + _B + '{3}' + _R + ' csmake'
                + _D + ' - version %s' % version + _R + '\n'
            )
        else:
            self.ANNOUNCE_FORMAT = '\n     {3} csmake - version %s\n' % version


class AspectReporter(Reporter):
    if _COLOR:
        PASS_BANNER = _G  + '  ✔  ✔  ✔  ✔  ✔  ✔  ' + _R
        FAIL_BANNER = _RD + '  ✘  ✘  ✘  ✘  ✘  ✘  ' + _R
        OBJECT_HEADER = (
            _D
            + '       ┌' + '─' * 40 + '┐\n'
            + '       │  ' + _R + _B + 'Aspect' + _R + _D + '  ' + '·' * 32 + '│\n'
            + '       └' + '─' * 40 + '┘' + _R
        )
        OBJECT_FOOTER = (
            _D
            + '       ┌' + '─' * 40 + '┐\n'
            + '       │  ' + _R + _D + 'End Aspect' + '  ' + '·' * 28 + '│\n'
            + '       └' + '─' * 40 + '┘' + _R + '\n'
        )
        STATUS_SEPARATOR = _D + '        ' + '─' * 42 + _R + '\n'
        ANNOUNCE_FORMAT  = '        &' + _C + '{1}' + _R + '@' + _B + '{2}' + _R + '         ' + _D + '...' + _R + '  {3}\n'
    else:
        PASS_BANNER = '      ~~~~~~      '
        FAIL_BANNER = '      ######      '
        OBJECT_HEADER = (
            '       +' + '-' * 40 + '+\n'
            '       |  Aspect' + ' ' * 33 + '|\n'
            '       +' + '-' * 40 + '+'
        )
        OBJECT_FOOTER = (
            '       +' + '-' * 40 + '+\n'
            '       |  End Aspect' + ' ' * 29 + '|\n'
            '       +' + '-' * 40 + '+\n'
        )
        STATUS_SEPARATOR = '        ' + '-' * 42 + '\n'
        ANNOUNCE_FORMAT  = '        &{1}@{2}         ...  {3}\n'

    STATUS_FORMAT = '{0}   {1} {2}: {3} {1}\n'
