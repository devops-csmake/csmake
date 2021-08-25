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
from Csmake.CsmakeModuleAllPhase import CsmakeModuleAllPhase

class ShellEnv(CsmakeModuleAllPhase):
    """Purpose: Adds specified key/value pairs into a shell environment
                (May also be used with other modules that want a private
                 environment)
       Type: Module   Library: csmake (core)
       Phases: *any*
       Options: Adds all flags into the environment for future steps
       Example:
           [ShellEnv@my-command-env]
           THIS_IS_AWESOME = this is/a really/coolpath

           [Shell@do-awesome]
           env=my-command-env
           command=echo $THIS_IS_AWESOME

           When used with a "Shell" section's "env" option, $THIS_IS_AWESOME
           would be available in the scripts defined in that Shell section,
           as in the [Shell@do-awesome] section above.
    """

    def __repr__(self):
        return "<<ShellEnv step definition>>"

    def __str__(self):
        return "<<ShellEnv step definition>>"

    def default(self, options):
        for key in list(options.keys()):
            options[key] = self.env.doSubstitutions(options[key])
            self.log.debug("ShellEnv set: %s=%s", key, options[key])
        self.log.passed()
        return options

    def __getattr__(self, name):
        return self.default
