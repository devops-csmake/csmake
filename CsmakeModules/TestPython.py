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
from CsmakeCore.CsmakeModule import CsmakeModule
import unittest
import CsmakeCore._vendor.coverage as coverage
import os.path
import xml.parsers.expat

class TestPython(CsmakeModule):
    """Purpose: Running python unit testing (using unittest test definitions)
                (assumes python 2.7)
       Type: Module   Library: csmake (core)
       Phases:
           test - Will run python unit tests
       Options:
           test-dir - path to the unittest.TestCase implementations
           test - names of the python files to execute unittests from
                  glob style wildcards may be used.
           source-dir - path to the sources under test
           resource-dir - (OPTIONAL) path to any resources for testing
           ignore-files - (OPTIONAL) Files to ignore coverage for
                          comma or newline delimited
                          (may use glob wildcards)
           xml-report - (OPTIONAL) When specified, will output an xml report
                                   to the file provided
                                   - relative paths will be under %(RESULTS)s
           html-report - (OPTIONAL) When specified, will output an html report
                                    to the file provided
                                    - relative paths will be under %(RESULTS)s
           * - any options you wan to pass through to the tests
       Notes:
          The tests must reside under the implementation under test
            I.e., no '..' is allowed in the path
                  from the code being tested to the tests.
          Every directory in the path to the tests must have __init__.py.
          Every test .py file must have the name of the test class, i.e.,:
                class testMyStuff_stuff(unittest.TestCase):
            Must be in a file called testMyStuff_stuff.py
          The csmake runtime will add a "csmake_test" member to
            the TestCase object which is a pointer back to this module
            the "options" passed to the section are at csmake_test.options.
       Requires:
           coverage (>= 4.0 preferred)
               (apt-get install python-coverage
                or pip install coverage)
    """

    REQUIRED_OPTIONS = ['test', 'test-dir', 'source-dir']

    def _xmlStartElementHandler(self, name, attrs):
        if name == 'class':
            self.classList.append(attrs)
    def _xmlEndElementHandler(self, name):
        pass
    def _xmlCharacterData(self, data):
        pass

    def _giveTestsCsmakeContext(self, tests):
        for test in tests:
            if hasattr(test, "_tests"):
                self._giveTestsCsmakeContext(test._tests)
            else:
                test.csmake_test = self

    def test(self, options):
        ignorefileList = []
        self.classList = []
        if 'ignore-files' in options:
            ignorefileList = ','.join(options['ignore-files'].split('\n')).split(',')
            ignorefileList = [
                x.strip() for x in ignorefileList if len(x.strip()) > 0 ]
        self.percentCovered = 0
        self.coverageResults = None
        self.olderCoverageResults = None
        loader = unittest.TestLoader()
        self.options = options
        cover = coverage.coverage(branch=True)
        cover.start()
        tests = loader.discover(
            self.options['test-dir'],
            self.options['test'],
            self.options['source-dir'] )
        for test in tests:
            self._giveTestsCsmakeContext(test)
        testRunner = unittest.TextTestRunner(self.log.out(), True, 3)
        result = testRunner.run(tests)
        cover.stop()
        omits = [self.options['test-dir']+'/*'] + ignorefileList
        self.percentCovered = cover.report(
            file=self.log.out(),
            omit=omits )
        coverageXMLFile = os.path.join(
            self.env.env['RESULTS'],
            "coverage.out.xml" )
        cover.xml_report(
            outfile=coverageXMLFile,
            omit=omits )
        #TODO: add more comprehensive parsing
        lines = []
        try:
            with open(coverageXMLFile, 'rb') as coverageFile:
                parser = xml.parsers.expat.ParserCreate()
                parser.StartElementHandler = self._xmlStartElementHandler
                parser.EndElementHandler = self._xmlEndElementHandler
                parser.CharacterDataHandler = self._xmlCharacterData
                parser.ParseFile(coverageFile)
        except:
            self.log.exception("Failed to read xml coverage file")
        finally:
            try:
                os.remove(coverageXMLFile)
            except:
                self.log.exception("Failed to remove the xml coverage file")

        if len(self.classList) > 0:
            self.olderCoverageResults = self.classList

        if 'xml-report' in options:
            cover.xml_report(
                outfile=os.path.join(
                    self.env.env['RESULTS'],
                    options['xml-report'] ),
                omit=omits )

        if 'html-report' in options:
            cover.html_report(
                outfile=os.path.join(
                    self.env.env['RESULTS'],
                    options['html-report'] ),
                omit=omits )
        try:
            self.coverageResults = cover.get_data()
        except AttributeError as e:
            self.log.info("coverage >= v4.0 required to get new coverage results - some dependent modules may not work properly")

        cover.erase()
        if result.wasSuccessful():
            self.log.passed()
            return True
        else:
            self.log.error("Testing failed")
            self.log.failed()
            self.log.error(result.errors)
            self.log.error(result.failures)
            return False
