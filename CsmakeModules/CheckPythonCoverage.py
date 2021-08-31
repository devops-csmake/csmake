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
from Csmake.CsmakeAspect import CsmakeAspect
import unittest
import Csmake._vendor.coverage as coverage

class CheckPythonCoverage(CsmakeAspect):
    """Purpose: Fail testing if coverage does not pass the given threshold
       Type: Aspect   Library: csmake (core)
       JoinPoints/Phases:
           passed__test - Will check the resulting threshold
       Options:
           required-percentage - The coverage threshold required to pass
           every-class - (OPTIONAL) When True every class tested must
                                    clear the given threshold
                         Default: False
       Notes: Built for use with TestPython
    """

    def _fixResultsToFailed(self, results):
        results.failed()
        for result in results.childResults:
            self._fixResultsToFailed(result)

    def passed__test(self, phase, options, step, stepoptions):
        requiredPercent = float(options['required-percentage'])
        if requiredPercent > step.percentCovered:
            self._fixResultsToFailed(step.log)
            self.log.error("Total coverage failed to meet required threshold (%f%%)", requiredPercent)
            self.log.failed()
            return None
        elif 'every-class' in options and options['every-class'] == 'True':
            classesPassed = True
            for classResult in step.olderCoverageResults:
                lineRate = float(classResult['line-rate']) *100.0
                if requiredPercent > lineRate:
                    self.log.error("Class '%s' coverage was not enough (%f%%)", classResult['name'], lineRate)
                    classesPassed = False
            if not classesPassed:
                self.log.error("Some classes failed to meet required threshold (%f%%)", requiredPercent)
                self._fixResultsToFailed(step.log)
                self.log.failed()
                return None
        self.log.passed()
