# <copyright>
# (c) Copyright 2021 Cardinal Peak Technologies, LLC
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
import re
import unittest
import os.path
import FileManager
import importlib
importlib.reload(FileManager)
from FileManager import FileManager, MetadataFileTracker, FileSpec

class testFileManager_basic(unittest.TestCase):

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

    def _createaCUT(self):
        cut = FileManager()
        cut.working = self.working
        cut.results = self.results
        cut.log = self.log
        return cut

    def test_saneInitialIndex(self):
        cut = FileManager()
        for axis in FileManager.AXES:
            self.assertTrue(axis in cut.index)

    def test_basicFileDeclarationSanity(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid(test:testing)> test_1.ext")
        self.assertEqual(len(result), 1)
        self.assertTrue('myid' in cut.index['id'])
        self.assertTrue('myid' in cut.index['id']['myid'][0].index['id'])
        self.assertTrue('myid' in cut.index['id']['myid'][0].index['id']['myid'][0].index['id'])

    def test_genericFileDeclarationSanity(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid(test:testing)> *.ext")
        self.assertEqual(len(result), 8)
        self.assertEqual(len(cut.index['id']['myid']), 8)
        self.assertEqual(len(cut.index['id']['myid'][0].index['id']['myid']), 1)

    def test_basicPrecedenceSettingOnAdd(self):
        cut =self._createaCUT()
        result = cut.parseFileDeclaration('<myid(test:testing)> *.ext')
        records = cut.findRecords(FileSpec(relLocation='*.ext', id='myid'))
        self.assertTrue(len(records) != 0)
        for record in records:
            for i, stuff in enumerate(record.records):
                for thing in stuff:
                    self.assertEqual(thing.getPrecedence(record), i+1)

    def test_basicFileMapSanity(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid(test:testing)> test_1.ext")
        result = cut.parseFileMap("*.ext -(1-1)-> *.test")
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            self.assertEqual(froms[0], os.path.join(
                self.working,
                'test_1.ext'))
            self.assertEqual(tos[0], os.path.join(
                self.results,
                'test_1.test'))

    def test_parseFilesWithResultsForYieldsFilesWithResultsInPath(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclarationForIndexes("<myid(test:testing)> mass.all")
        cut.addFileIndexes(result, self.results)

    def test_genericBasicFileMap(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid(test:testing)> test_*.ext")
        result = cut.parseFileMap("*.ext -(1-1)-> *.test")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            self.assertTrue(os.path.split(froms[0])[1].split('_')[1][0],
                os.path.split(tos[0])[1].split('_')[1][0])

    def test_complexMapWithOnlyOneMatch(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid (test:testing)> test_1.ext")
        result = cut.parseFileMap("<myid (test)> -(*-1)-> <(another)> bin/testit && <another (test)> -(*-1)-> <(another)> bin/testanother")
        self.assertEqual(len(result), 1)

    def test_oneToOneWithPathFile(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid (test:testing)> test_*.ext")
        result = cut.parseFileMap("<myid> -(1-1)-> [~~path~~]/[~~file~~]")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            self.assertEqual(
                os.path.realpath(os.path.abspath(froms[0])),
                os.path.realpath(os.path.abspath(tos[0])))
        cut.absorbMappings(result)

    def test_deadEndFile(self):
        cut = self._createaCUT()
        with open(os.path.join(self.working, "__deadend.deadend"), 'w') as f:
            f.write(" ")
        with open(os.path.join(self.results, "__new_deadend.newdead"), 'w') as f:
            f.write(" ")
        result = cut.parseFileDeclaration("<myid (test:testing)> __deadend.deadend")
        result = cut.parseFileMap("<myid> -(1-1)-> <newid> __new_deadend.newdead")
        os.remove(os.path.join(self.working, "__deadend.deadend"))
        cut.absorbMappings(result, validate=True)
        result = cut.parseFileMap("<(test)> -(1-1)-> [~~path~~]/[~~file~~]")
        goodfileexists = False
        for froms, tos in result.iterfiles():
            for from_entry in froms:
                goodfileexists = goodfileexists or "__new_deadend.newdead" in os.path.abspath(from_entry)
        os.remove(os.path.join(self.results, "__new_deadend.newdead"))
        self.assertTrue(goodfileexists)
        
    def test_specialRECharacters(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid (test:testing)> *.special")
        result = cut.parseFileMap("<myid> -(1-1)-> [~~path~~]/[~~file~~]")
        self.assertEqual(len(result), 2)
        for froms, tos in result.iterfiles():
            self.assertEqual(
                os.path.realpath(os.path.abspath(froms[0])),
                os.path.realpath(os.path.abspath(tos[0])))
        cut.absorbMappings(result)

    def test_specialRECharactersInPath(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid (test:testing)> dir+ectory/*.special")
        result = cut.parseFileMap("<myid> -(1-1)-> [~~path~~]/[~~file~~]")
        self.assertEqual(len(result), 2)
        for froms, tos in result.iterfiles():
            #With a path specified in the directory for a file instance,
            #the ~~path~~ only covers the path specified in the file instance
            #  not the entire path like it does in the relative case above
            self.assertEqual(
                os.path.realpath(os.path.abspath(froms[0])),
                os.path.realpath(os.path.abspath(tos[0])).replace('fakeresults','fakeworking'))
        cut.absorbMappings(result)
       

    def test_absPathWithNoFromSpec(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid (test:testing)> test_*.ext")
        result = cut.parseFileMap("<myid> -(1-1)-> %s" % self.working + "/[~~file~~]")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            self.assertEqual(
                os.path.realpath(os.path.abspath(froms[0])),
                os.path.realpath(os.path.abspath(tos[0])))
        cut.absorbMappings(result)
             
    def test_mapSanityWithFutureSubstitution(self):
        cut = self._createaCUT()
        result = cut.parseFileDeclaration("<myid (test:testing)> test_*.ext")
        result = cut.parseFileMap("<myid> -(1-1)-> {blah}/this/that/[~~file~~]")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterspecs():
            path, filename = os.path.split(froms[0]['location'])
            self.assertEqual("{blah}/this/that/%s" % filename, tos[0]['relLocation'])

    def test_basicManyToOneFileMap(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("*.ext -(*-1)-> output.mine")
        self.assertEqual(len(result), 1)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 8)
            self.assertEqual(len(tos), 1)

    def test_basicManyToOneFileMapWithSubstitution(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("*.ext -(*-1)-> [~~id~~].mine")
        self.assertEqual(len(result), 1)
        for froms, tos in result.iterspecs():
            self.assertEqual(len(froms), 8)
            self.assertEqual(len(tos), 1)
            self.assertEqual(tos[0]['relLocation'], 'myid.mine')

    def test_unresolvableAndResolvableManyToManySubstitution(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid (test:testing)> test_*.ext")
        result = cut.addFileDeclaration("<otherid (other:testing)> other_*.ext")
        with self.assertRaises(ValueError):
            result = cut.parseFileMap("*.ext -(*-*)-> [~~id~~].mine")
        result = cut.parseFileMap("*.ext -(*-*)-> [~~intent~~].mine, a.out")
        for froms, tos in result.iterspecs():
            self.assertEqual(len(froms), 8)
            self.assertEqual(len(tos), 2)
            found = False
            for ato in tos:
                if 'mine' in ato['relLocation']:
                    found = True
                    self.assertEqual(ato['relLocation'], 'testing.mine')
            self.assertTrue(found)
        self.assertEqual(result.getMappingSpecification(), '*-*')
        #Test string rep of FileMapper
        str(cut)

    def test_reFileDeclaration(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid (test:testing)> ~~test_[^.1][.]ext")
        result = cut.parseFileMap("*.ext -(*-1)-> [~~id~~].result")
        for froms, tos in result.iterspecs():
            self.assertEqual(len(froms),4)
            self.assertEqual(len(tos),1)
            for afrom in froms:
                self.assertNotEqual('test_1.ext', afrom['relLocation'])

    def test_idSubstitutionOneToOne(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid (test:testing)> test_*.ext")
        result = cut.addFileDeclaration("<otherid (other:testing)> other_*.ext")
        result = cut.parseFileMap("*.ext -(1-1)-> [~~id~~]_[~~file~~].mine, [~~type~~].type")
        self.assertEqual(len(result), 16)
        for froms, tos in result.iterspecs():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            if froms[0]['relLocation'].startswith('test_'):
                if tos[0]['relLocation'].endswith('.type'):
                    self.assertEqual(tos[0]['relLocation'], 'test.type')
                else:
                    self.assertEqual(tos[0]['relLocation'], 'myid_%s.mine' % froms[0]['relLocation'])
            else:
                if tos[0]['relLocation'].endswith('.type'):
                    self.assertEqual(tos[0]['relLocation'], 'other.type')
                else:
                    self.assertEqual(tos[0]['relLocation'], 'otherid_%s.mine' % froms[0]['relLocation'])

    def test_basicFileAbsorb(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("test_*.ext -(1-1)-> test[~~file~~].out")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            path, tofilename = os.path.split(tos[0])
            self.assertTrue(re.match(r'testtest_[1-5][.]ext[.]out', tofilename))
        cut.absorbMappings(result)
        records = cut.findRecords(FileSpec(id="myid"))
        self.assertEqual(len(records), 8)
        for record in records:
            instances = record.findInstances(FileSpec(id='myid'))
            self.assertEqual(len(instances),1)
            for instance in instances:
                match = re.match(r'(testtest_[1-5][.]ext[.]out)|(other_[1-3][.]ext)', instance.index['relLocation'])
                self.assertTrue(match is not None)

    def test_TwoFileAbsorbsWithSameId(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("<(test)> -(1-1)-> <myid(another:mytest)> test[~~file~~].out")
        self.assertEqual(len(result), 8)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            path, tofilename = os.path.split(tos[0])
            self.assertTrue(re.match(r'(testtest_[1-5][.]ext[.]out)|(testother_[1-3][.]ext[.]out)', tofilename))
        cut.absorbMappings(result)
        records = cut.findRecords(FileSpec(id="myid"))
        self.assertEqual(len(records), 8)
        for record in records:
            instances = record.findInstances(FileSpec(id='myid'))
            self.assertEqual(len(instances),1)
            for instance in instances:
                match = re.match(r'(testtest_[1-5][.]ext[.]out)|(testother_[1-3][.]ext[.]out)', instance.index['relLocation'])
                self.assertTrue(match is not None)
        result = cut.parseFileMap("<(another:mytest)> -(1-1)-> <(final)> [~~filename~~].final")
        self.assertEqual(len(result),8)
        for froms, tos in result.iterfiles():
            path, tofilename = os.path.split(tos[0])
            match = re.match(r'(testtest_[1-5][.]ext[.]final)|(testother_[1-3][.]ext[.]final)', tofilename)
            self.assertTrue(match is not None)
        cut.absorbMappings(result)
        records = cut.findRecords(FileSpec(id="myid"))
        for record in records:
            instances = record.findInstances(FileSpec(id='myid'))
            self.assertEqual(len(instances), 1)
            for instance in instances:
                match = re.match(r'(testtest_[1-5][.]ext[.]final)|(testother_[1-3][.]ext[.]final)', instance.index['relLocation'])

        #This test is sufficiently complex to get good coverage on the printing
        result = cut.__repr__()
        print("Result of FileManager repr, first 1000")
        print(result[:1000], "...")

    def test_basicFileAbsorbDeleting(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("test_*.ext -(1-1)-> test[~~file~~].nex")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            path, tofilename = os.path.split(tos[0])
            self.assertTrue(re.match(r'testtest_[1-5][.]ext[.]nex', tofilename))
        cut.absorbMappings(result, deleting=True)
        records = cut.findRecords(FileSpec(id="myid"))
        self.assertEqual(len(records), 8)
        for record in records:
            instances = record.findInstances(FileSpec(id='myid'))
            self.assertEqual(len(instances),1)
            for instance in instances:
                match = re.match(r'(testtest_[1-5][.]ext[.]nex)|(other_[1-3][.]ext)', instance.index['relLocation'])
                self.assertTrue(match is not None)

    def test_basicFileAbsorbSkipVerification(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("test_*.ext -(1-1)-> test[~~file~~].blah")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 1)
            self.assertEqual(len(tos), 1)
            path, tofilename = os.path.split(tos[0])
            self.assertTrue(re.match(r'testtest_[1-5][.]ext[.]blah', tofilename))
        cut.absorbMappings(result, validate=False)
        records = cut.findRecords(FileSpec(id="myid"))
        self.assertEqual(len(records), 8)
        for record in records:
            instances = record.findInstances(FileSpec(id='myid'))
            self.assertEqual(len(instances),1)
            for instance in instances:
                match = re.match(r'(testtest_[1-5][.]ext[.]blah)|(other_[1-3][.]ext)', instance.index['relLocation'])
                self.assertTrue(match is not None)

    def test_OneToOneWithMissingMappingAndOneNonMatch(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid (content:file)> test_1.ext")
        result = cut.addFileDeclaration("<myid (missing:file)> missing_1.ext")
        result = cut.addFileDeclaration("<myid (content:another)> test_2.ext")
        result = cut.parseFileMap("<(missing:file)> -(1-1)-> [~~file~~]")
        self.assertEqual(len(result),0)

    def test_manyToOneFileAbsorb(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap("<myid> -(*-1)-> <myid(library:lib)> nobarf.lib")
        self.assertEqual(len(result), 1)
        for froms, tos in result.iterfiles():
            self.assertEqual(len(froms), 8)
            self.assertEqual(len(tos), 1)
        cut.absorbMappings(result)
        records = cut.findRecords(FileSpec(id='myid'))
        self.assertEqual(len(records), 8)
        for record in records:
            instances = record.findInstances(FileSpec(id='myid'))
            self.assertEqual(len(instances), 1)
            for instance in instances:
                self.assertEqual(instance.index['relLocation'], 'nobarf.lib')
        instances = cut.findInstances(FileSpec(id='myid'))
        self.assertEqual(len(instances), 1)
        for instance in instances:
            self.assertEqual(instance.index['relLocation'], 'nobarf.lib')
            
    def test_mapWithRegexFiles(self):
        cut = self._createaCUT()
        result = cut.addFileDeclaration("<myid(test:testing)> *.ext")
        result = cut.parseFileMap(
            "~~test_([0-9]+)[.]ext -(1-1)-> ~~\\1_atest.out")
        self.assertEqual(len(result), 5)
        for froms, tos in result.iterfiles():
            match = re.match("test_([1-5]).ext", os.path.split(froms[0])[1])
            self.assertTrue(match is not None)
            num = match.group(1)
            self.assertEqual(os.path.split(tos[0])[1],'%s_atest.out' % num)

    def test_findSingleDiskFilesMatchingStarred(self):
        d = {}
        FileManager.fixupLocationWithBase(
            self.working,
            "test_1.ext",
            d )
        results = FileManager.findDiskFilesMatchingStarred(
            d['location'] )
        self.assertEqual(len(results), 1)
        self.assertEqual(os.path.join(
            self.working,
            "test_1.ext" ),
            results[0])

    def test_findFilesStarredWithQuestionMark(self):
        d = {}
        FileManager.fixupLocationWithBase(
            self.working,
            "test_?.ext",
            d )
        results = FileManager.findDiskFilesMatchingStarred(
            d['location'] )
        self.assertEqual(len(results), 5)
        self.assertTrue(os.path.join(
            self.working,
            "test_1.ext" ) in results)
        self.assertTrue(os.path.join(
            self.working,
            "test_5.ext" ) in results)
        
    def test_findFilesStarredWithStars(self):
        d = {}
        FileManager.fixupLocationWithBase(
            self.working,
            "*.ext",
            d )
        results = FileManager.findDiskFilesMatchingStarred(
            d['location'] )
        self.assertEqual(len(results), 8)
        self.assertTrue(os.path.join(
           self.working,
           "test_2.ext" ) in results)
        self.assertTrue(os.path.join(
           self.working,
           "other_1.ext" ) in results)

    def test_findFilesStarredWithRange(self):
        d = {}
        FileManager.fixupLocationWithBase(
            self.working,
            "other_[23].ext",
            d )
        results = FileManager.findDiskFilesMatchingStarred(
            d['location'] )
        self.assertEqual(len(results), 2)
        self.assertTrue(os.path.join(
            self.working,
            "other_2.ext" ) in results )
        self.assertFalse(os.path.join(
            self.working,
            "other_1.ext" ) in results )

    def test_fileBasicREFilesRE(self):
        d = {}
        FileManager.fixupLocationWithBase(
            self.working,
            ".*[.]ext",
            d )
        results = FileManager.findDiskFilesMatchingRegex(
            d['location'] )
        self.assertEqual(len(results), 8)
        self.assertTrue(os.path.join(
            self.working,
            "other_3.ext") in results )
        self.assertTrue(os.path.join(
            self.working,
            "test_4.ext") in results)

    def test_fileBasicREFilesREWithDash(self):
        d = {}
        FileManager.fixupLocationWithBase(
            os.path.join(
                self.working,
                'other-fakeworking' ),
            '.*[.]other',
            d )
        results = FileManager.findDiskFilesMatchingRegex(
            d['location'] )
        self.assertEqual(len(results), 5)
        self.assertTrue(os.path.join(
            self.working,
            'other-fakeworking/my_1.other') in results)


    def test_countedJoin(self):
        result = FileManager.countedJoin(1, ['blah','myt','mya'], '<<<%d>>>')
        self.assertEqual(result[1], "blah<<<1>>>myt<<<2>>>mya")

    def test_translateStarsToSourceRegex(self):
        result = FileManager.translateStarsToSourceRegex('*.ext')
        self.assertEqual(result, r'(?P<file>(?P<filename>(?P<star1>[^/]*))[.](?P<ext>ext))')

    def test_translateStarsToResultRegex(self):
        result = FileManager.translateStarsToResultRegex('file[~~file~~].mine')
        self.assertEqual(result, r'file\g<file>.mine')
