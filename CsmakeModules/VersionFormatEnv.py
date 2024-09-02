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
import os
import shutil

class VersionFormatEnv(CsmakeModuleAllPhase):
    """Purpose: Generate version strings into the csmake environment
       Type: Module   Library: csmake (core)
       Phases: Any
       Options:
           format - The format of the version string to generate
                    into the environment.  Use version designations
                    in curly braces to bring in parts of the version
                    together.
                    NOTE: 'primary' is the version designation defined in
                                    the metadata
                          'primary-major' is the version designation of just
                                    the major version number
                          'primary-minor' is the version designation of just
                                    the minor version number
                          'primary-patch' is the version designation of just
                                    the patch revision number
           env-name - Environment variable name that will hold the version
                      string specified by 'format'
       Example:
           [VersionFormatEnv@my-version]
           format = {primary-patch}+{build-number}
           env-name = FULL_BUILD_NUMBER

           Assuming that a 'versioning' section (or something else) has
           defined a version designation of 'build-number' (for this example
           let's assume it's defined ad 151512) and the 'metadata' section
           has defined a version of say 5.2.4141.  This section would produce
           a csmake environment variable 'FULL_BUILD_NUMBER' set to the value
           4141+151512.
    """

    REQUIRED_OPTIONS=['format', 'env-name']

    def default(self, options):
        versionString = None
        try:
            versionString = self.metadata._parseVersionFormatString(
                                 options['format'])
        except KeyError as k:
            self.log.error("'%s' was requested for the version, but was not defined", str(k))
            self.log.failed()
            return False
        self.env.env[options['env-name']] = versionString
        self.log.passed()
        return versionString
