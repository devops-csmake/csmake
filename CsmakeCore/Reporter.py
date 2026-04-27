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

# ANSI escape sequences — defined unconditionally to avoid NameError in both
# branches of the `if _COLOR` class-body conditionals below.
_R   = '\033[0m'        # reset
_B   = '\033[1m'        # bold
_D   = '\033[2m'        # dim
_G   = '\033[1;32m'     # bold green
_RD  = '\033[1;31m'     # bold red
_C   = '\033[36m'       # cyan
_BC  = '\033[1;36m'     # bold cyan

# Decoration widths
_W  = 67   # standard step width
_PW = 88   # program-level reporter width (long bars for csmakeci)
_AW = 48   # aspect reporter width


class Reporter:

    NESTNOTE = '+'
    OUTPUT_HEADER = "%s  %%s  %s\n" % ('-' * 15, '-' * 15)

    if _COLOR:
        # ------------------------------------------------------------------
        # Color + Unicode mode
        #
        # Pass uses ▓ (dark shade — dense/solid = good)
        # Fail uses ░ (light shade — sparse/translucent = broken)
        # Colorblind-safe: texture difference survives grayscale.
        # ------------------------------------------------------------------

        PASS_BANNER  = _G  + '▓' * 20 + _R
        FAIL_BANNER  = _RD + '░' * 20 + _R
        SKIP_BANNER  = _D  + '╌' * 20 + _R
        UNEX_BANNER  =       ' ' * 20

        # Flat horizontal rules — thin for step boundaries, dashed for
        # internal separators, thick for phase markers.
        OBJECT_HEADER    = '\n  ' + _D + '─' * _W + _R
        OBJECT_FOOTER    = '  ' + _D + '─' * _W + _R + '\n\n\n'
        STATUS_SEPARATOR = '  ' + _D + '╌' * _W + _R + '\n'
        PHASE_BANNER     = '\n  ' + _BC + '━' * _W + _R + '\n'

        # Announce line  ({0}=nesting, {1}=type, {2}=id, {3}=Begin|End)
        ANNOUNCE_FORMAT = (
            '  {0}▸ ' + _C + '{1}' + _R + '@' + _B + '{2}' + _R
            + '  ' + _D + '·' + _R + '  {3}\n'
        )
        ONEXIT_ANNOUNCE_FORMAT = (
            '  /   ' + _D + '{3}' + _R + ' - Exit Handler: {0}@{1}  {2}\n'
        )

        STATUS_FORMAT = ' {1}   {2}: {3}   {1}\n'

        # Exit handler separators — dashed texture marks them as "aside"
        ONEXIT_HEADER          = '\n  ' + _D + '╌' * _W + _R + '\n'
        ONEXIT_FOOTER          = '  '  + _D + '╌' * _W + _R + '\n\n'
        ONEXIT_BEGIN_SEPARATOR = '  '  + _D + '· ' * 33 + '·' + _R + '\n'
        ONEXIT_END_SEPARATOR   = '  '  + _D + '· ' * 33 + '·' + _R + '\n'

        # Aspect joinpoint separators
        ASPECT_JOINPOINT_HEADER = '\n' + _D + '    ╌╌ Begin Joinpoint: %s ' + _R + '\n'
        ASPECT_JOINPOINT_FOOTER = '\n' + _D + '    ╌╌ End Joinpoint: %s '   + _R + '\n'

        # Failure stack-dump separators (red to draw attention)
        DUMP_STACKS_SEPARATOR = _RD + '═' * 77 + _R + '\n'
        DUMP_STACK_SEPARATOR = (
            '\n' + _RD + '─' * 77 + '\n'
            + '═' * 77 + '\n'
            + '=== End of failure output and stacks\n'
            + '═' * 77 + _R + '\n'
        )
        DUMP_STACK_LAST_OUTPUT_SEPARATOR = (
            '\n' + _RD + '─' * 77 + '\n'
            + '── ─ ─ ─ ─ ─ ─ ─ ─ ── Output From Failure ── ─ ─ ─ ─ ─ ─ ─ ─ ──\n'
            + '─' * 77 + _R + '\n'
        )
        DUMP_STACK_STACK_SEPARATOR = (
            '\n' + _RD + '─' * 77 + '\n'
            + '── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ Stack Trace ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ──\n'
            + '─' * 77 + _R + '\n'
        )

    else:
        # ------------------------------------------------------------------
        # Plain ASCII mode  (pipe, dumb terminal, NO_COLOR, CSMAKE_STYLE=plain)
        #
        # Pass uses # (dense, visually heavy = success)
        # Fail uses ~ (wavy, sparse = broken)
        # Colorblind-safe: texture difference requires no color.
        # ------------------------------------------------------------------

        PASS_BANNER  = '#' * 20
        FAIL_BANNER  = ('~ ' * 10).rstrip()
        SKIP_BANNER  = ('. ' * 10).rstrip()
        UNEX_BANNER  = ' ' * 19

        OBJECT_HEADER    = '\n  ' + '-' * _W
        OBJECT_FOOTER    = '  ' + '-' * _W + '\n\n\n'
        STATUS_SEPARATOR = '  ' + '- ' * 33 + '-\n'
        PHASE_BANNER     = '\n  ' + '=' * _W + '\n'

        ANNOUNCE_FORMAT        = '  {0}> {1}@{2}  -  {3}\n'
        ONEXIT_ANNOUNCE_FORMAT = '  /   {3} - Exit Handler: {0}@{1}  {2}\n'

        STATUS_FORMAT = ' {1}   {2}: {3}   {1}\n'

        ONEXIT_HEADER          = '\n  ' + '.' * _W + '\n'
        ONEXIT_FOOTER          = '  '  + '.' * _W + '\n\n'
        ONEXIT_BEGIN_SEPARATOR = '  '  + '. ' * 33 + '.\n'
        ONEXIT_END_SEPARATOR   = '  '  + '. ' * 33 + '.\n'

        ASPECT_JOINPOINT_HEADER = '\n    -- Begin Joinpoint: %s\n'
        ASPECT_JOINPOINT_FOOTER = '\n    -- End Joinpoint: %s\n'

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
    # Long flat rules — csmakeci uses this reporter and benefits from the width.
    if _COLOR:
        OBJECT_HEADER = '\n  ' + _BC + '━' * _PW + _R + '\n'
        OBJECT_FOOTER = '\n  ' + _BC + '━' * _PW + _R + '\n'

        # ▓ (dark/dense) for pass — visually heavy, green, reads as "solid/complete"
        # ░ (light/sparse) for fail — visually hollow, red, reads as "broken/empty"
        # Texture alone (no color) distinguishes them: colorblind-safe.
        PASS_BANNER = (
            _G
            + '\n  ' + '▓' * _PW + '\n'
            + '  ▓  Build Passed' + ' ' * (_PW - 17) + '▓\n'
            + '  ' + '▓' * _PW + '\n'
            + _R
        )
        FAIL_BANNER = (
            _RD
            + '\n  ' + '░' * _PW + '\n'
            + '  ░  Build Failed' + ' ' * (_PW - 17) + '░\n'
            + '  ' + '░' * _PW + '\n'
            + _R
        )
    else:
        OBJECT_HEADER = '\n  ' + '=' * _PW + '\n'
        OBJECT_FOOTER = '\n  ' + '=' * _PW + '\n'

        # # (dense) for pass, ~ (sparse/wavy) for fail — distinguishable without color
        PASS_BANNER = (
            '\n  ' + '#' * _PW + '\n'
            + '  #  Build Passed' + ' ' * (_PW - 17) + '#\n'
            + '  ' + '#' * _PW + '\n'
        )
        FAIL_BANNER = (
            '\n  ' + '~' * _PW + '\n'
            + '  ~  Build Failed' + ' ' * (_PW - 17) + '~\n'
            + '  ' + '~' * _PW + '\n'
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
        PASS_BANNER = _G  + '▓' * 14 + _R
        FAIL_BANNER = _RD + '░' * 14 + _R
        OBJECT_HEADER = (
            '       ' + _D + '─' * _AW + _R + '\n'
            + '       ' + _D + '▸  ' + _R + _B + 'Aspect' + _R + '\n'
        )
        OBJECT_FOOTER = (
            '       ' + _D + '▸  End Aspect' + _R + '\n'
            + '       ' + _D + '─' * _AW + _R + '\n'
        )
        STATUS_SEPARATOR = '       ' + _D + '╌' * _AW + _R + '\n'
        ANNOUNCE_FORMAT  = (
            '        &' + _C + '{1}' + _R + '@' + _B + '{2}' + _R
            + '  ' + _D + '·' + _R + '  {3}\n'
        )
    else:
        PASS_BANNER = '#' * 14
        FAIL_BANNER = ('~ ' * 7).rstrip()
        OBJECT_HEADER = (
            '       ' + '-' * _AW + '\n'
            '       >  Aspect\n'
        )
        OBJECT_FOOTER = (
            '       >  End Aspect\n'
            '       ' + '-' * _AW + '\n'
        )
        STATUS_SEPARATOR = '       ' + '- ' * 24 + '\n'
        ANNOUNCE_FORMAT  = '        &{1}@{2}  -  {3}\n'

    STATUS_FORMAT = '{0}   {1} {2}: {3} {1}\n'
