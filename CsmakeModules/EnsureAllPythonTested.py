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
from CsmakeCore.CsmakeAspect import CsmakeAspect
import os.path
import os
import fnmatch

class EnsureAllPythonTested(CsmakeAspect):
    """Purpose: Fail testing if a python file exists that is not tested.
       Type: Aspect   Library: csmake (core)
       Options:
           filter - (OPTIONAL) specifies the filter for files to ensure
                               are covered in the test.
                               May use glob (unix-style) wildcards
       JoinPoints/Phases:
           passed__test - Will check the resulting threshold
       Notes: For use with TestPython
    """

    def _fixResultsToFailed(self, results):
        results.failed()
        for result in results.childResults:
            self._fixResultsToFailed(result)

    def _generateSourceDirectoryContents(self, path, filterer, exclude):
        result = {}
        fullpath = os.path.normpath(os.path.join(
            self.env.env['WORKING'],
            path ))
        files = os.listdir(
            fullpath)
        for entry in files:
            current = os.path.join(fullpath, entry)
            if os.path.isdir(current):
                result.update(
                    self._generateSourceDirectoryContents(
                        current,
                        filterer,
                        exclude ))
            else:
                skip = False
                for ex in exclude:
                    if fnmatch.fnmatch(current,ex):
                        skip = True
                        break
                if fnmatch.fnmatch(entry,filterer) and not skip:
                    result[current] = False
        return result

    def passed__test(self, phase, options, step, stepoptions):
        filterer = "*.py"
        if 'filter' in options:
            filterer = options['filter']
        exclusions = []
        if 'ignore-files' in stepoptions:
            exclusions = ','.join(stepoptions['ignore-files'].split('\n')).split(',')
            exclusions = [
                x.strip() for x in exclusions if len(x.strip()) > 0]
        exclusions.append(stepoptions['test-dir'] + '/*')
        filesInTest = self._generateSourceDirectoryContents(
            stepoptions['source-dir'],
            filterer,
            exclusions )
        self.log.debug("filesInTest: %s", str(filesInTest))
        for classResult in step.olderCoverageResults:
            fullpath = os.path.normpath(os.path.join(
                self.env.env['WORKING'],
                classResult['filename']))
            if fullpath in filesInTest:
                del filesInTest[fullpath]
        if len(filesInTest) != 0:
            self._fixResultsToFailed(step.log)
            for entry in list(filesInTest.keys()):
                self.log.error("File '%s' not covered in unit testing", entry)
            self.log.failed()
            return None
        self.log.passed()
