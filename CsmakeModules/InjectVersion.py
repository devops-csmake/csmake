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
from CsmakeCore.CsmakeModule import CsmakeModule
import os
import shutil

class InjectVersion(CsmakeModule):
    """Purpose: Replace version strings with the current calculated version
       Type: Module   Library: csmake (core)
       Phases:
           build, package - Will do the replacement in a build or package step
           clean - Delete the versioned file only if it's not in-place
       Mapping: Expects a 1-1 mapping - may be in-place
                WARNING: Original source files should not be in-place
                         This module will modify files on the right side
                         of the mapping.
       Options:
           match - String to match and replace in files with the current version
                   Take care not to make this something that is easily matched
                   NOTE: csmake '%' environment substitutions
                         will not be performed
           version-marker - (OPTIONAL) String to use to separate the
                                       parts of the version
                            DEFAULT: -
    """

    REQUIRED_OPTIONS = ['match']

    def _replaceMatchInFiles(self, options, mapping):
        matchString = options['match'].strip()
        marker = '-'
        if 'version-marker' in options:
            marker = self.env.doSubstitutions(options['version-marker'].strip())
        versionString = self.metadata._getDefaultDefinedVersion(marker)
        for froms, tos in mapping.iterfiles():
            self.log.debug("Froms: %s", str(froms))
            self.log.debug("Tos: %s", str(tos))
            assert len(froms) == 1 and len(tos) == 1
            with open(froms[0]) as fromfile:
                self._ensureDirectoryExists(tos[0])
                lines = fromfile.readlines()

                with open(tos[0], 'w') as tofile:
                    for line in lines:
                        tofile.write(line.replace(matchString, versionString))
            shutil.copystat(froms[0], tos[0])
        self.log.passed()

    def build(self, options):
        self._replaceMatchInFiles(options, self.mapping)

    def package(self, options):
        self._replaceMatchInFiles(options, self.mapping)

    def clean(self, options):
        self._cleaningFiles()
        for froms, tos in self.mapping.iterfiles():
            if froms[0] != tos[0]:
                try:
                    os.remove(tos[0])
                except:
                    self.log.info("File %s not found to clean", tos[0])
                self._cleanEnsuredDirectory(tos[0])
        self.log.passed()
