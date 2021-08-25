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
import FileManager
#from FileManager import FileSpec
#from FileManager import FileInstance
import os.path

class testFileInstance_basic(unittest.TestCase):

    def setUp(self):
        self.resources = self.csmake_test.options['resource-dir']
        self.resources = os.path.abspath(self.resources)
        self.working = os.path.join(
            self.resources,
            'fakeworking' )
        self.results = os.path.join(
            self.resources,
            'fakeresults' )
        self.log = self.csmake_test.log

    def _getStockIndex(self, index):
        return {
            'simple': {
                'relLocation':'test_1.ext', 
                'location':os.path.join(self.working,'test_1.ext'),
                'type':'mytype',
                'intent':'myintent',
                'id':'myid'} 
        }[index]
            

    def _createaCUT(self, index):
        cut = FileManager.FileInstance(**index)
        return cut

    def test_saneInitialIndex(self):
        myindex = self._getStockIndex('simple')
        cut = self._createaCUT(myindex)
        for axis in myindex.keys():
            self.assertTrue(axis in cut.index)
            self.assertEqual(
                cut.index[axis],
                myindex[axis])

    def test_axisMatch(self):
        myindex = self._getStockIndex("simple")
        cut = self._createaCUT(myindex)
        spec = FileManager.FileSpec(relLocation='*.ext')
    
        self.assertTrue(
            cut._axisMatch('relLocation', spec, '*.ext', 'test_1.ext') )

    def test_findInstances_basic(self):
        myindex = self._getStockIndex("simple")
        cut = self._createaCUT(myindex)
        spec = FileManager.FileSpec(relLocation='*.ext')
        self.assertTrue(cut is cut.findInstances(spec) )
