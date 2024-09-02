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
import unittest
import CsmakeModule
from Environment import Environment
from Result import Result
from OutputTee import OutputTee
#from FileManager import FileSpec
#from FileManager import FileInstance
import os.path

class testCsmakeModule_basic(unittest.TestCase):

    class FakeEngine:
        def __init__(self):
            self.settings = {'dev-output':True, 'debug':False,'verbose':False,'quiet':False, 'no-chatter':False, 'file-tracking':False}
            self.log = None
    
    def _createaCUT(self):
        env = Environment(testCsmakeModule_basic.FakeEngine())
        return CsmakeModule.CsmakeModule(env, Result(env))

    def test_saneBracketSubstitutions(self):
        cut = self._createaCUT()
        p = cut._parseBrackets("{test}{this}", {'test':'a', 'this':'b'})
        self.assertEqual('ab', p)

        p = cut._parseBrackets("{{test}{this}", {'test':'a', 'this':'b'})
        self.assertEqual('{ab',p)

        p = cut._parseBrackets("{{test}}}{this}", {'test':'a', 'this':'b'})
        self.assertEqual('{a}b',p)

        p = cut._parseBrackets("{test}/{this}", {'test':'a', 'this':'b'})
        self.assertEqual("a/b",p)

        p = cut._parseBrackets("{test}%{this}", {'test':'a', 'this':'b'})
        self.assertEqual("a%b",p)

        p = cut._parseBrackets("{test}%%{this}", {'test':'a', 'this':'b'})
        self.assertEqual("a%%b",p)

        p = cut._parseBrackets("{{test}{{this}",{'test':'a', 'this':'b'})
        self.assertEqual("{a{b",p)

        OutputTee.endAll()
