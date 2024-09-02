# <copyright>
# (c) Copyright 2018 Cardinal Peak Technologies
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
import os

class ShellToEnvironment(CsmakeModuleAllPhase):
    """Purpose: Puts a shell environment variable into the csmake environment
       Type: Module   Library: csmake (core)
       Description:
                This enables the ability to paramiterize a build
                - should be used with caution as this opens builds
                  up to depend on a specific shell context to work properly
                  which is antithetical to the theory of operation
                  behind csmake
                *Options substitutions, e.g., %(var)s, are NOT allowed*
       Phases: *any*
       Options: <shell variable>[:<default value>]
                Adds all flags into the environment for future steps
                The value is a shell variable that should have been
                defined before csmake was executed.
                A default value may be added using a colon ':' followed
                by the default value
       Example:
           [ShellToEnvironment@pull-parameters]
           csmake-build-number=BUILDNO
           branch-to-pull=BRANCH:master

           The 'pull-parameters' section would pull 'BUILDNO' from the
           shell enivronment that csmake is executing from and place it
           in the csmake environment variable called "csmake-build-number"
           Likewise with 'BRANCH', 'branch-to-pull' would be set to
           whatever ${BRANCH} would evaluate to from the shell that launched
           csmake.  
           If BRANCH isn't defined in the shell environment, the 'master'
              is used in its place.
    """

    def __repr__(self):
        return "<<ShellToEnvironment step definition>>"

    def __str__(self):
        return "<<ShellToEnvironment step definition>>"

    def _doOptionSubstitutions(self, stepdict):
        #Avoid options substitutions for this module
        pass

    def default(self, options):
        for option, shellkey in options.items():
            if option.startswith("**"):
                continue
            default_value = None
            if ':' in shellkey:
                shellkey, default_value = shellkey.split(':',1)
            if shellkey not in os.environ:
                if default_value is None:
                    self.log.error("'%s' was not defined in the shell environment", shellkey)
                    self.log.failed()
                    return False
                else:
                    self.log.info("Default value for %s used: %s", shellkey, default_value)
                    self.env.env[option] = default_value
            else:
                self.env.env[option] = os.environ[shellkey]
        self.log.passed()
        return True

