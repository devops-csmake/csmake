# <copyright>
# (c) Copyright 2021 Autumn Patterson
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
from Csmake.CsmakeModule import CsmakeModule
import gzip
import shutil
import os

class CompressManPage(CsmakeModule):
    """Purpose: Prepare a man page from source to delivery
       Type: Module   Library: csmake (core)
       Options: (none)
       Phases:
           build - create a man page from specified source
           clean - remove the results
       Mapping:
           Expects a 1-1 mapping of things ready to be delivered as
           man pages and will prep them by compressing them using gzip
    """

    def package(self, options):
        for froms, tos in self.mapping.iterfiles():
            source = froms[0]
            result = tos[0]
            if self._canAvoid(source, result):
                self.log.info("Result exists, continuing")
                continue
            self._ensureDirectoryExists(result)
            shutil.copyfile(source, result)
            sourceman = open(source, 'rb')
            makeman = gzip.GzipFile(result, 'wb', mtime=0)
            self.log.info("Writing manpage to '%s'", result)
            makeman.writelines(sourceman)
            makeman.close()
            sourceman.close()
        self.log.passed()

    def clean(self, options):
        self._cleaningFiles()
        try:
            for froms, tos in self.mapping.iterfiles():
                result = tos[0]
                try:
                   os.remove(result)
                except Exception as e:
                   self.log.info("File could not be removed (%s): %s", result, str(e))
                self._cleanEnsuredDirectory(result)
        except Exception as e:
            self.log.exception("clean failed")
        self.log.passed()
