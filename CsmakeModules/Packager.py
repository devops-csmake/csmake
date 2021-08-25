# <copyright>
# (c) Copyright 2018 Cardinal Peak Technologies, LLC
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
import tarfile
import copy
import os.path
import shutil
import sys
import time
import datetime

class Packager(CsmakeModule):
    """Purpose: Implements the packaging framework
                This module will produce a "tarball" archive
                Other kinds of packagers should subclass this
                implementation.
       Type: Module   Library: csmake (core)
       Package Name Format: tarball
       Phases:
           package - Will build the package
           clean, package_clean - will delete the package
       Options:
           format - bzip2 or gzip (OPTIONAL)
                    (specific packagers may define other formats)
                    Default will be gzip
           package-version - the version for the package
           maps - points to installmap based sections that
                  define how files should be mapped into the package
           default_<path> - Define a default path for an install map path
                            definition.  Other paths may be referred
                            to using curly braces '{' '}', such as:
                              {root}
                            (for anything to make sense, paths must start
                             with at least {root}, or something that makes
                             sense to the Packager)
                            It is important to realize that references
                            are not the installmap definitions.
                            For example, an install map might define:
                               path_root=INSTALL_ROOT
                            INSTALL_ROOT is specific to the *installmap*
                            root from path_root is what Packagers understand.
                            (See "Install Map Definitions" ::path:: below)
                  If a Packager doesn't have a built-in mapping/understanding
                    of a <path> and there is no default, the <path> and any
                    mappings that use it will be ignored.
           result - directory to put the results
                    The package will be called
                         <name>-<version>-<package-version>.tar.<ext>
                    Where <ext> == bz2 for bzip2 and gz for gzip

       Joinpoints introduced:
           begin_map - Advised on any file index matching
                                the aspect's specified file-types
                                before it is mapped into the package.
              extra parameters: from: the index of the source file
                                tos: the indicies of the targets installed
                                mapping: the mapping dictionary
              (the extra parameters may be manipulated to change
               the default mapping behavior)
           end_map - Advised on any file index matching
                              the aspect's specified file-types
                              after it is mapped into the package.
              extra parameters: from: the index of the source file
                                tos: the indicies of the targets installed
                                mapping: the mapping dictionary
           archive_file - Advised on any file index matching
                         the aspect's specified file-types
                         before a single file is archived
                         (if a directory is the source, this will advise on
                          every file and every directory in the source)
              extra parameters: from: the path of the source file
                                to: the path of the target installed
                                mapping: the mapping dictionary
                                info: tarinfo object for file
                                      (can be manipulated
                                       to affect the behavior of the file)
           mapping_complete - Advised when all the mappings have been
                              executed.
                                This is a good place to add any files,
                                or links, etc.  It is unfiltered, so
                                all aspects that define handlers for this advice
                                will be advised.
                                NOTE: Other data may be added to
                                      the data archive as necessary
                                      to fully support the format and
                                      platform.  This addition of files
                                      should be managed through the use
                                      of the package controls.
            control - Advised before writing a 'control' defined entry
               extra parameters: control: Name of the control being processed

       Flowcontrol Advice introduced:
            doNotMapFile - Avoid archiving the given file.
                               Can be recommended on begin_map or map_file.
            ignoreControl - Do not process the control.
                               Can be recommended on the control advice.

       Install Map Definitions:
           :: path ::
               root - The root file system of the install target
               python-lib - Specifies that the path is a python lib path.
           :: user ::
               root - The root user ('root', 0)
               someone - The someone user ('someone', 64)
           :: group ::
               root - The root group ('root', 0)
               someone - The someone group ('someone', 64)

       Package controls:
           Controls are broadly defined dictionaries that should make
           some sense to the packager.  For example, a Debian 'control'
           file the dictionary of stanzas intended to be written should be
           the in the package control entry.  For a postinst, a shell script
           string under 'script'.

           TODO: Define the structure for common package controls.

           Use debian control file names to correspond to the control
           as they tend to be the most extensive set and most complex
           - if the debian control file doesn't align with the package
             control need, then add it with a different name.
           (RPM spec file sections, for example, tend to somewhat align
              with the debian control file names)
           See:
               https://www.debian.org/doc/manuals/maint-guide/dreq.en.html
               https://www.debian.org/doc/manuals/maint-guide/dother.en.html

        Classifier Meanings:
            Classifiers can be used by packagers to determine metadata and other
            package attributes.  By default, Programming Language is used
            (currently for Java and Python) and License to determine the
            shorthand name for a license
    """

    REQUIRED_OPTIONS = ['maps', 'result', 'package-version']
    PACKAGER_NAME_FORMAT = "tarball"

    #These mapper classes are here to allow individual metadata attributes
    #   to be mapped declaratively using these class names.
    #
    # The way this works is the mapper calls mapdict passing itself in
    # Then mapmethod is called - and returns a method that will perform
    # the mapping
    #   The contract is that what is passed to the mapper class method
    #   will have the standard components referenced - for example
    #   everything referenced as packager.* below is guaranteed to be defined
    #   in Packager (but may be overridden by a subclass of Packager)
    #
    # Below you can see the METAMAP_METHODS (which use these classes)
    # these are the mappings to the required or desired names the packager cares
    # about and how the values should be constructed via the given Mapper class.
    #
    # The idea generally is that there are a handful of generic ways to map
    # most metadata from a generic declaration to a specific instance that
    # a specific package format requires - and that package formats generally
    # require the same kinds of information - just with differing keys.
    #
    class MetadataMapper:
        """Basic mapper: Translates a metadata key to a packager specific key"""
        @staticmethod
        def mapdict(packager):
            return packager.productMetadata

        @staticmethod
        def mapmethod(packager):
            return packager._mapMetadata

    class PackageNameMapper:
        """Package name mapper: Attempts to translate given package names
               to the names of the format desired by the Packager.
            NOTE: Override PACKAGER_NAME_FORMAT to dictate the naming scheme"""
        @staticmethod
        def mapdict(packager):
            return packager.productMetadata

        @staticmethod
        def mapmethod(packager):
            return packager._mapPackageNameMetadata

    class ClassifierMapper:
        """Classifier interpreter: Translates trove declarations to
                                   packager specific information.
              This picks the *best* information to deliver based on
              prioritization of the matches"""
        @staticmethod
        def mapdict(packager):
            return packager._parseClassifiers()

        @staticmethod
        def mapmethod(packager):
            return packager._mapClassifiers

    class AppendingClassifierMapper:
        """Classifier interpreter: Translates trove declarations to
                                   packager specific information.
              This picks all the matching information to deliver"""
        @staticmethod
        def mapdict(packager):
            return packager._parseClassifiers()

        @staticmethod
        def mapmethod(packager):
            return packager._mapAndAppendClassifiers

    #Structure is:
    # <Metadata tag for format> : <mapped value class> (above)
    METAMAP_METHODS = {
        'Package' : PackageNameMapper,
        '**python-lib' : AppendingClassifierMapper,
        'License' : ClassifierMapper
    }

    #Structure is:
    # <item> : <metadata key>
    # For use with MetadataMapper
    METAMAP = {
        'Package' : 'name'
    }

    #Format is 'item' : {
    #    '<classifier>' :
    #            (<priority lower is more specific>, <value of classifer>)}
    # Default is <classifier> == '' (use sys.maxint for priority)
    # For use with ClassifierMapper
    CLASSIFIER_MAPS = {
        '**python-lib' : {
            '' : (sys.maxsize, None),
            'Programming Language :: Python' : (9, 'python'),
            'Programming Language :: Python :: 2' : (8, 'python2.7'),
            'Programming Language :: Python :: 2.3' : (5, 'python2.3'),
            'Programming Language :: Python :: 2.4' : (5, 'python2.4'),
            'Programming Language :: Python :: 2.5' : (5, 'python2.5'),
            'Programming Language :: Python :: 2.6' : (5, 'python2.6'),
            'Programming Language :: Python :: 2.7' : (5, 'python2.7'),
            'Programming Language :: Python :: 2 :: Only' : (1, 'python2'),
            'Programming Language :: Python :: 3' : (9, 'python3.4'),
            'Programming Language :: Python :: 3.0' : (5, 'python3.0'),
            'Programming Language :: Python :: 3.1' : (5, 'python3.1'),
            'Programming Language :: Python :: 3.2' : (5, 'python3.2'),
            'Programming Language :: Python :: 3.3' : (5, 'python3.3'),
            'Programming Language :: Python :: 3.4' : (5, 'python3.4'),
            'Programming Language :: Python :: 3 :: Only' : (1, 'python3')
         },
         #TODO: Check acronyms with Debian pool
         #       http://spdx.org is the authority now.  See CLDSYS-16651
         'License' : {
             '' : (sys.maxsize,"non-free"),
             'License :: OSI Approved :: Academic Free License (AFL)' : (1, "AFL"),
             'License :: OSI Approved :: Apache Software License' : (1, "Apache"),
             'License :: OSI Approved :: Apple Public Source License' : (1, "APL"),
             'License :: OSI Approved :: Artistic License' : (1, "Artistic"),
             'License :: OSI Approved :: Attribution Assurance License' : (1, "AAL"),
             'License :: OSI Approved :: BSD License' : (1, "BSD"),
             'License :: OSI Approved :: CEA CNRS Inria Logiciel Libre License, version 2.1 (CeCILL-2.1)' : (1, "CeCILL-2.1"),
             'License :: OSI Approved :: Common Public License' : (1, "CPL"),
             'License :: OSI Approved :: Eiffel Forum License' : (1, "Eiffel"),
             'License :: OSI Approved :: European Union Public Licence 1.0 (EUPL 1.0)' : (1, "EUPL1"),
             'License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)' : (1, "EUPL1.1"),
             'License :: OSI Approved :: GNU Affero General Public License v3' : (1, "AGPLv3"),
             'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)' : (1, "AGPLv3+"),
             'License :: OSI Approved :: GNU Free Documentation License (FDL)' : (1, "FDL"),
             'License :: OSI Approved :: GNU General Public License (GPL)' : (1, "GPL"),
             'License :: OSI Approved :: GNU General Public License v2 (GPLv2)' : (1, "GPLv2"),
             'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)' : (1, "GPLv2+"),
             'License :: OSI Approved :: GNU General Public License v3 (GPLv3)' : (1, "GPLv3"),
             'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)' : (1, "GPLv3+"),
             'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)' : (1, "LGPLv2"),
             'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)' : (1, "LGPLv2+"),
             'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)' : (1, "LGPLv3"),
             'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)' : (1, "LGPLv3+"),
             'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)' : (1, "LGPL"),
             'License :: OSI Approved :: IBM Public License' : (1, "IBMPL"),
             'License :: OSI Approved :: Intel Open Source License' : (1, "Intel"),
             'License :: OSI Approved :: ISC License (ISCL)' : (1, "ISC"),
             'License :: OSI Approved :: Jabber Open Source License' : (1, "Jabber"),
             'License :: OSI Approved :: MIT License' : (1, "MIT"),
             'License :: OSI Approved :: MITRE Collaborative Virtual Workspace License (CVW)' : (1, "CVW"),
             'License :: OSI Approved :: Motosoto License' : (1, "Motosoto"),
             'License :: OSI Approved :: Mozilla Public License 1.0 (MPL)' : (1, "MPL1"),
             'License :: OSI Approved :: Mozilla Public License 1.1 (MPL 1.1)' : (1, "MPL1.1"),
             'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)' : (1, "MPL2"),
             'License :: OSI Approved :: Nethack General Public License' : (1, "NGPL"),
             'License :: OSI Approved :: Nokia Open Source License' : (1, "Nokia"),
             'License :: OSI Approved :: Open Group Test Suite License' : (1, "OGTSL"),
             'License :: OSI Approved :: Python License (CNRI Python License)' : (1, "CNRI"),
             'License :: OSI Approved :: Python Software Foundation License' : (1, "python"),
             'License :: OSI Approved :: Qt Public License (QPL)' : (1, "QPL"),
             'License :: OSI Approved :: Ricoh Source Code Public License' : (1, "RSC-PL"),
             'License :: OSI Approved :: Sleepycat License' : (1, "Sleepycat"),
             'License :: OSI Approved :: Sun Industry Standards Source License (SISSL)' : (1, "SISSL"),
             'License :: OSI Approved :: Sun Public License' : (1, "SPL"),
             'License :: OSI Approved :: University of Illinois/NCSA Open Source License' : (1, "NCSA"),
             'License :: OSI Approved :: Vovida Software License 1.0' : (1, "VSD"),
             'License :: OSI Approved :: W3C License' : (1, "W3C"),
             'License :: OSI Approved :: X.Net License' : (1, "X.Net"),
             'License :: OSI Approved :: zlib/libpng License' : (1, "zlib"),
             'License :: OSI Approved :: Zope Public License' : (1, "Zope"),
             'License :: Other/Proprietary License' : (1, "non-free"),
             'License :: Public Domain' : (1, "Public Domain"),
             'License :: Repoze Public License' : (1, "Repose")
        }
    }

    def __init__(self, env, log):
        """Create the minimum state data for a package"""
        CsmakeModule.__init__(self, env, log)
        self.classifiers = None
        self.controls = {}

    @staticmethod
    def _getCurrentPOSIXTime():
        return time.mktime(datetime.datetime.now().timetuple())

    def _packageControl(self, controlName, replace=False):
        """Manages the lifecycle and retrieval of control metadata parts"""
        if controlName in self.controls:
            if replace:
                self.controls[controlName] = {}
        else:
            self.controls[controlName] = {}
        return self.controls[controlName]

    def _createArchiveFileInfo(self, fullArchivePath):
        result = tarfile.TarInfo("%s/%s" % (
            self.archiveRoot,
            fullArchivePath ) )
        result.mtime = self._getCurrentPOSIXTime()
        return result

    def _parseClassifiers(self):
        """Distills the classifier input from the product metadata"""
        if self.classifiers is None:
            if 'classifiers' in self.productMetadata:
                result = ','.join(self.productMetadata['classifiers'].split('\n')).split(',')
                self.classifiers = [ item.strip() for item in result ]
            else:
                self.classifiers = []
        return self.classifiers

    def _mapMetadata(self, key, dictionary):
        """This method is the basic implementation for mapping metadata
           this mapper maps metadata straight across one package tag
           to one package metadata tag"""
        metamap = self.__class__.METAMAP
        if key in metamap and metamap[key] in dictionary:
            return dictionary[metamap[key]]
        else:
            return None

    #Creates an ast of boolean expressions where
    # '' is translated to None
    # 'a' is translated to ('id', 'a', '')
    # 'a (> 2.0), b' is translated to ['and' ('id', 'a'`, "> 2.0"), ('id', 'b', "")]
    # 'a | b | c, d' is translated to:
    #    ['and' ['or' ('id', "a", ""), ('id', "b", ""), ('id', "c", "")], ('id', "d", "")]
    def _parsePackageDependencyEntry(self, entries):
        packages = self._parseCommaAndNewlineList(entries)
        packageList = []
        for package in packages:
            packageParts = package.split('|')
            partList = []
            for part in packageParts:
                part = part.strip()
                nameParts = part.split('(')
                packageName = []
                versionQual = ""
                current = 0
                for namePart in nameParts:
                    namePart = namePart.strip()
                    if namePart[0] in '<=>~' or namePart == '{version})':
                        versionQual = namePart.strip().strip(')')
                        current += 1
                        break
                    packageName.append(namePart)
                    current += 1
                if current != len(nameParts):
                    self.log.warning("Invalid dependency specification found: %s", part)
                    self.log.warning("   Parts ignored: %s", str(nameParts[current:]))
                packageName = '('.join(packageName)
                partList.append(('id', packageName, versionQual))
            if len(partList) > 1:
                packageList.append(['or'] + partList)
            else:
                packageList.append(partList[0])
        if len(packageList) > 1:
            return ['and'] + packageList
        elif len(packageList) == 0:
            return None
        else:
            return packageList[0]

    def _translatedPackageVersionHelper(self, item, version):
        if item is None:
            return None
        if item[0] == 'id':
            if item[2] == '{version}':
                return ('id', item[1], version)
            else:
                return item
        result = [item[0]]
        for current in item[1:]:
            currentResult = self._translatedPackageVersionHelper(current, version)
            if currentResult is None:
                continue
            result.append(currentResult)
        if len(result) == 1:
            return None
        else:
            return result

    def _translatePackageNameHelper(self, current):
        if current is None:
            return None
        if current[0] == 'id':
            resultAst = current
            packageName = current[1]
            #See if there's a translation....
            sectionLookup = "translatePackageName@~~%s~~" % packageName
            if self.engine.lookupSection(sectionLookup) is not None:
                phase = self.engine.getPhase()
                step = self.engine.launchStep(
                    sectionLookup,
                    phase,
                    extraOptions={'~~format~~' : self.__class__.PACKAGER_NAME_FORMAT})
                if step is not None:
                    #There is a translation defined...
                    result = step._getResult()
                    if result is not None:
                        #There is a result
                        transItems = result.getReturnValue(
                            phase )
                        if transItems is None:
                            return None
                        #The result isn't "None" it could be empty....
                        transAst = self._parsePackageDependencyEntry(transItems)
                        if transAst is None:
                            return None
                        if transAst[0] == 'id':
                            if len(transAst[2]) == 0 \
                               or transAst[2] == '{version}':
                                return ('id', transAst[1], current[2])
                            else:
                                return transAst
                        self.log.debug("Sending to version helper: %s", transAst)
                        resultAst = self._translatedPackageVersionHelper(transAst, current[2])
            return resultAst
        result = [current[0]]
        for part in current[1:]:
            partResult = self._translatePackageNameHelper(part)
            if partResult is None:
                continue
            result.append(partResult)
        if len(result) == 1:
            return None
        if len(result) == 2:
            return result[1]
        else:
            return result

    def _translatePackageNames(self, packagesOption):
        fullList = []
        self.log.debug("Input: %s", str(packagesOption))
        phase = self.engine.getPhase()
        ast = self._parsePackageDependencyEntry(packagesOption)
        self.log.debug("Dep AST: %s", str(ast))
        result = self._translatePackageNameHelper(ast)
        self.log.debug("Post trans: %s", str(result))
        return result

    def _unrollAstToDebianStyleDependency(self, ast):
        #Debian doesn't support nested booleans
        #   so the semantics of the AST won't be fully preserved
        #   when it's a complex nested structure.
        #   - there is a way to preserve the meaning by generating
        #     every combination of each term between the ors and ands
        #     ....just don't do that, it's confusing and probably wrong
        if ast is None:
            return ''
        if ast[0] == 'id':
            if len(ast[2]) > 0:
                return "%s (%s)" % (ast[1], ast[2])
            else:
                return ast[1]
        else:
            result = []
            for item in ast[1:]:
                result.append(self._unrollAstToDebianStyleDependency(item))
            if ast[0] == 'and':
                return ', '.join(result)
            elif ast[0] == 'or':
                return ' | '.join(result)
            else:
                self.log.warning("Invalid parse of package occurred: %s", str(ast))

    def _mapPackageNameMetadata(self, key, dictionary):
        """This method handles the translation of the package names given
           to the packager's format, defined in PACKAGER_NAME_FORMAT"""
        metamap = self.__class__.METAMAP
        if key in metamap and metamap[key] in dictionary:
            result = self._unrollAstToDebianStyleDependency(
                self._translatePackageNames(dictionary[metamap[key]]) )
            self.log.debug("Unrolled AST: %s", result)
            return result
        else:
            return None

    def _mapClassifiers(self, key, dictionary):
        """This method handles creating metadata values from classifiers
           The method utilizes the Packager's implementation specific version
           of CLASSIFIER_MAPS."""
        maps = self.__class__.CLASSIFIER_MAPS[key]
        if '' in maps:
            currentpriority, currentresult = maps['']
        else:
            currentpriority, currentresult = (sys.maxsize, 'default')

        for classifier in dictionary:
            if classifier in maps:
                priority, result = maps[classifier]
                if priority < currentpriority:
                    currentresult = result
                    currentpriority = priority
        return currentresult

    def _mapAndAppendClassifiers(self, key, dictionary):
        """Similar to _mapClassifiers, this will map to a list of
           results based on the information contained within the
           classifiers.  This will also utilize the Packager's
           implementation specific version of CLASSIFIER_MAPS."""
        maps = self.__class__.CLASSIFIER_MAPS[key]
        result = []
        for classifier in dictionary:
            if classifier in maps:
                result.append(maps[classifier])
        if len(result) == 0:
            return None
        else:
            return result

    def _doMetadataMappings(self):
        """This method will consume the list of Package metadata tags provided
           in the Packager's implementation specific version of
           METAMAP_METHODS and perform each of the methods given
           in order to construct the package's metadata from the
           csmake metadata provided (and possibly other input as
           the Packager implementation might dictate).  A 'method'
           is really class with static methods (see METAMAP_METHODS above)

           Defines a package metadata dictionary self.packageMetadata"""
        self.packageMetadata = {}
        self.productMetadata = self.metadata._getMetadataDefinitions()
        classifiers = self._parseClassifiers()
        if 'copyrights' in self.productMetadata:
            copyrights = self._packageControl('copyright')
            copyrights['default'] = self.productMetadata['copyrights']
        for key, value in self.__class__.METAMAP_METHODS.items():
            try:
                callresult = value.mapmethod(self)(key, value.mapdict(self))
                if callresult is not None:
                    self.packageMetadata[key] = callresult
            except:
                self.log.exception("Attempt to map '%s' failed", key)
                self.packageMetadata[key] = None
        self.packageName = self.productMetadata['name']
        self._calculateFileNameAndVersioning()
        return self.packageMetadata

    def _calculateFileNameAndVersioning(self):
        """This provides the package implementation a chance to
           define the file name and versioning that meets the package
           standard requirements and customs.

           The members defined by this package are:
           - self.packageVersion
           - self.fullVersion
           - self.fullPackageName

           It expects to have defined:
           - self.packageName
           - self.packageMetadata
           - self.productMetadata

           The environment it makes use of is the product metadata
           from the metadata section in the csmakefile and
           the package-version option"""
        #Determines version style/format and archive filename (not extension)
        self.resultdir = self.options['result']
        self.version=self.metadata._getDefaultDefinedVersion('+')
        version = self.version
        self.packageVersion=self.options['package-version']
        self.fullVersion = '%s-%s' % (
            version,
            self.packageVersion )
        self.fullPackageName = '%s-%s' % (
            self.packageName,
            self.fullVersion )
        result = self.resultdir
        if 'format' in self.options:
            self.format = self.options['format']
        else:
            self.format = 'gzip'
        if self.format == 'gzip':
            self.filetype = 'gz'
            ext = 'tar.gz'
        elif self.format == 'bzip2':
            self.filetype = 'bz'
            ext = 'tar.bz2'
        else:
            self.log.warning("'format' '%s' is not understood defaulting to gzip")
            self.format = 'gzip'
            self.filetype = 'gz'
            ext = 'tar.gz'
        self.archiveFileName = "%s.%s" % (
            self.fullPackageName,
            ext )
        self.fullPathToArchive = os.path.join(
            self.resultdir,
            self.archiveFileName )

    def _modeInt(self, permission):
        """Unstringifies an octal string mode"""
        if type(permission) == str:
            permission = int(permission, 8)
        return permission

    def _setupArchive(self):
        """Specialize setup archive to create the data archive, self.archive
           self.archive should respond to:
           add(<path to source>, <path in archive>, <filter method: TarInfo>)
           or _placeFileInArchive should also be overridden

           Apart from self.archive this method also establishes:
           self.archiveFileName - the name of the archive file
           self.fullPathToArchive - which is the full path to the archive file
           """
        self._ensureDirectoryExists(self.fullPathToArchive)
        self.archive = tarfile.open(self.fullPathToArchive, 'w:%s' % self.filetype)

    def _setupPackage(self):
        """Override this for packages that require more than just
           the data archive.  The base implementation simply calls
           setupArchive. More elaborate packaging schemes may
           require more here.
           self.resultdir - the path defined by the 'result' option"""
        #TODO: Collect all initialization of packager state into
        #      a single method
        self._setupArchive()

    def _finishArchive(self):
        """Override this to finish building the data archive for the package
           specific implementation"""
        self.archive.close()
        return True

    def _finishPackage(self):
        """Override this to handle more elaborate packaging schemes.
           The base implementation will only finish off the archive.
           When this method completes, the result from this module
           should also be complete and ready for use."""
        return self._finishArchive()

    ##############################
    # Path mapping handlers

    def _map_path_root(self, value, pathmaps, pathkeymaps):
        """The default root of a tarball for a product is the name of
           the product.  Different packaging schemes will vary"""
        pathmaps[value] = [self.fullPackageName]
        self.archiveRoot = self.fullPackageName
        pathkeymaps['root'] = [self.archiveRoot]

    def _map_path_python_lib(self, value, pathmaps, pathkeymaps):
        """The default python library path.  Different packaging schemes and
            different distrobutions will have varying ways to handle the
            location of the python library - whose varying default locations
            tries to be all things to all distros"""
        if '**python-lib' in self.packageMetadata:
            pydists = self.packageMetadata['**python-lib']
            pydists.sort()
            initprio, _ = pydists[0]
            dists = []
            for priority, dist in self.packageMetadata['**python-lib']:
                if priority != initprio:
                    break
                dists.append(dist)
            distpaths = []
            for dist in dists:
                #TODO: This is not correct for py 3 and older py 2's
                distpaths.append(os.path.join(
                    '%(root)s',
                    "usr",
                    "lib",
                    dist ) )
            pathmaps[value] = distpaths
        else:
            self.log.warning("python-dist-packages was specified in the mappings: but the product's metadata does not specify:")
            self.log.warning("  Programming Language :: Python")
            self.log.warning("  (nor anything more specific than that)")
            self.log.warning("  defaulting to python2.7")
            pathmaps[value] = [ os.path.join(
               '%(root)s',
               'usr',
               'lib',
               'python2.7' ) ]
        pathkeymaps['python-lib'] = pathmaps[value]

    ###############################
    # User maps
    def _map_user_root(self, value, ownermaps):
        """Root user definition"""
        ownermaps[value] = ('root', 0)

    def _map_user_someone(self, value, ownermaps):
        """The "someone" user definition"""
        ownermaps[value] = ('someone', 64)

    ###############################
    # Group maps
    def _map_group_root(self, value, groupmaps):
        """Root group definition"""
        groupmaps[value] = ('root', 0)

    def _map_group_someone(self, value, groupmaps):
        """The "someone" user definition"""
        groupmaps[value] = ('someone', 64)

    def _generateSubstitutionDictionaries(self, pathkeymaps):
        lookupCombos = [{}]
        for key, paths in pathkeymaps.items():
            if len(paths) == 0:
                continue
            newCombos = []
            for path in paths:
                for lookup in lookupCombos:
                    newlookup = dict(lookup)
                    newlookup.update({key:path})
                    newCombos.append(newlookup)
            lookupCombos = newCombos
        return lookupCombos

    def _doMappingSubstitutions(self, mapping):
        """Performs the mapping calculations based on
           the mappings given by the installmap sections referred to
           in 'maps'.  This is invoked by _doMaps.
           Contains a list of dictionaries representing the map information"""
        #Defines the virtual mapping to the substitutions to simplify the
        #Handlers
        virtualmaps = {}
        #Defines the replacement for the substitution variable in the installmap
        pathmaps = {}
        #Defines the replacement for the default substitutions in the Packager
        pathkeymaps = {}
        if 'path' in mapping:
            for key, value in mapping['path'].items():
                if key not in pathkeymaps:
                    pathkeymaps[key] = []
                if value not in virtualmaps:
                    virtualmaps[value] = []
                methodName = '_map_path_%s' % key.replace('-', '_')
                if hasattr(self, methodName):
                    #The contract is this updates pathmaps with at least
                    #pathmaps[value] = path stuff
                    getattr(self, methodName)(value, virtualmaps, pathkeymaps)
                else:
                    if key == 'root':
                        self.log.warning("File mapping 'root' unhandled: default is '.'")
                        virtualmaps[value] = ['.']
                        self.archiveRoot = '.'
                        pathkeymaps['root'] = ['.']
                        continue
                    self.log.info(
                        "File mapping '%s' has no handler, using default if defined", key )
                    defaultPathOption = 'default_%s' % key
                    if defaultPathOption in self.options:
                        path = self.options[defaultPathOption]
                        virtualmaps[value] = [path.replace('{',"%(").replace('}',')s')]
                        pathkeymaps[key] = virtualmaps[value]
                    else:
                        self.log.warning(
                            "File mapping '%s' has no implementation for '%s'",
                            key,
                            self.__class__.__name__)
                        self.log.warning(
                            "   NOTE: '%s' in the installmap will be ignored",
                            value)

        self.log.devdebug("'virtualmaps' is: %s", str(virtualmaps))
        self.log.devdebug("'pathkeymaps' is: %s", str(pathkeymaps))

        #Path maps have the option to defer to other path map definitions
        #for part of their definition (in implementation) to ensure
        #consistency.  This has to get untangled before we can proceed.
        #Unless there is a definition loop we should be able to resolve
        #  all references in N passes where N is the number of definitions
        loops = []
        for i in range(0,len(pathkeymaps)):
            repeat = False
            loops = []

            #Generate the lookup table
            lookupCombos = self._generateSubstitutionDictionaries(pathkeymaps)
            self.log.devdebug("lookupCombos are '%s'", lookupCombos)
            for key, paths in pathkeymaps.items():
                newpathkeymap = set()
                try:
                    for combo in lookupCombos:
                        newpathkeymap.update(
                            [path % combo for path in paths])
                except KeyError:
                    repeat = True
                    loops.append(key)
                    self.log.devdebug("key not resolved: '%s'", key)
                pathkeymaps[key] = list(newpathkeymap)
            if not repeat:
                break
        else:
            self.log.error("Path mappings could not be resolved: %s", str(loops))
            raise KeyError(str(loops))

        lookupCombos = self._generateSubstitutionDictionaries(pathkeymaps)
        self.log.devdebug("All final lookup combos are: %s", str(lookupCombos))
        for value, paths in virtualmaps.items():
            realPathmaps = set()
            for combo in lookupCombos:
                realPathmaps.update(
                    [path % combo for path in paths])
            pathmaps[value] = list(realPathmaps)
        self.log.devdebug("All pathmaps are: %s", str(pathmaps))

        ownermaps = {}
        if 'owner' in mapping:
            for key, value in mapping['owner'].items():
                methodName = '_map_user_%s' % key.replace('-', '_')
                if hasattr(self, methodName):
                    getattr(self, methodName)(value, ownermaps)
                else:
                    self.log.warning(
                        "User mapping '%s' has no implementation for '%s'",
                        key,
                        self.__class__.__name__ )
                    self.log.warning(
                        "    Default is: someone(64)")
                    ownermaps[value] = ('someone', 64)

        groupmaps = {}
        if 'group' in mapping:
            for key, value in mapping['group'].items():
                methodName = '_map_group_%s' % key.replace('-', '_')
                if hasattr(self, methodName):
                    getattr(self, methodName)(value, groupmaps)
                else:
                    self.log.warning(
                        "Group mapping '%s' has no implementation for '%s'",
                        key,
                        self.__class__.__name__ )
                    self.log.warning(
                        "    Default is: someone(64)")
                    groupmaps[value] = ('someone', 64)

        if 'path' in mapping and 'root' in mapping['path']:
            self.log.debug("'root' was defined in installmap")
        else:
            self.log.error("'path_root' was not defined in the installmap.")
            self.log.error("   defaulting to '.'")
            self.archiveRoot = '.'
            if 'path' not in mapping:
                mapping['path'] = {}
            mapping['path']['root'] = '.'

        copymaps = {}
        results = []
        lookupCombos = self._generateSubstitutionDictionaries(
                           pathmaps)
        self.log.devdebug("pathmaps substitutions: %s", lookupCombos)
        for key, value in mapping['map'].items():
            installmap = {}
            try:
                for mappart, target in value.items():
                    if mappart == 'map':
                        filemap = list(
                            set([self._parseBrackets(target, combo) for combo in lookupCombos]) )
                        filemap = ' && '.join(filemap)
                        installmap['map'] = filemap
                        self.log.devdebug("Emiting mapping: %s", str(filemap))
                    elif mappart == 'owner':
                        owner = target
                        if owner.startswith('{') and owner.endswith('}'):
                            ownerkey = owner.lstrip('{').rstrip('}')
                            ownervalue = ownermaps[ownerkey]
                        else:
                            #TODO: Check to see if 64 works to call out a specific
                            #      user as a string in the tar file.
                            ownervalue = (owner, 64)
                        installmap['owner'] = ownervalue
                    elif mappart == 'group':
                        group = target
                        if group.startswith('{') and group.endswith('}'):
                            groupkey = group.lstrip('{').rstrip('}')
                            groupvalue = groupmaps[groupkey]
                        else:
                            groupvalue = (group, 64)
                        installmap['group'] = groupvalue
                    elif mappart == 'permissions':
                        permissions = target
                        installmap['permissions'] = permissions
                    elif mappart == 'copyright':
                        copiesright = target.split(',')
                        installmap['copyright'] = []
                        for copyright in copiesright:
                            target = copyright.strip()
                            if target not in copymaps:
                                result = self.engine.launchStep(
                                    target,
                                    'package' )
                                if result is None or not result._didPass():
                                    self.log.error("%s step failed", target)
                                    self.log.failed()
                                    raise ValueError("Mappings for DebianPackage failed")
                                copymaps[target] = result._getReturnValue('package')
                            installmap['copyright'].append(copymaps[target])
                    else:
                        installmap[mappart] = target
                results.append(installmap)
            except:
                self.log.exception("Install mapping 'map_%s' failed and will not be packaged", key)

        return results

    def _lookupControlAspects(self, control):
        """Aspects that have registered for handling control
           generation or manipulation are found by this method."""
        partName = '__PackagerAspect__'
        if partName not in self.controls:
            return []
        if 'control-dispatch' not in self.controls:
            return []
        aspects = []
        dispatch = self.options[partName]['control-dispatch']
        for controls, aspect, aspectOptions in dispatch:
            if control in controls:
                aspects.append((aspect, aspectOptions))
        return aspects

    def _lookupFileTypeAspects(self, sourceIndex):
        """Aspects that have registered for handling file types
           when they are in the process of beming mapped
           are found by this method."""
        partName = '__PackagerAspect__'
        if partName not in self.options:
            return []
        if 'file-type-dispatch' not in self.options[partName]:
            return []
        aspects = []
        dispatch = self.options[partName]['file-type-dispatch']
        self.log.devdebug("file type aspects lookup source (%s) ===== against (%s)", str(sourceIndex), str(dispatch))
        for indexes, aspect, aspectOptions in dispatch:
            if type(indexes) == str:
                if indexes == '*':
                    aspects.append((aspect, aspectOptions))
                    continue
            match = False
            for index in indexes:
                hit = True
                for key, value in index.items():
                    if key not in sourceIndex or sourceIndex[key] != value:
                        hit = False
                        break
                if hit:
                    match = True
                    break
            if match:
                aspects.append((aspect, aspectOptions))
        return aspects

    def _addFileObjToArchive(self, fileobj, info):
        self._ensureArchivePath(self.archive, info)
        info.size = self._filesize(fileobj)
        fileobj.seek(0)
        self._filePlacingInPackage('data', None, info.name, fileobj)
        self.archive.addfile(info, fileobj)

    def _ensureArchivePath(self, archive, info):
        path, filename = os.path.split(info.name)
        dirmode = self._getDirectoryMode(info.mode)

        def pathHelper(curpath):
            if curpath is None or len(curpath) == 0 or curpath == '/':
                return
            try:
                archive.getmember(curpath)
                return
            except KeyError:
                pathHelper(os.path.split(curpath)[0])
                dirinfo = tarfile.TarInfo(curpath)
                dirinfo.mtime = self._getCurrentPOSIXTime()
                dirinfo.uid = info.uid
                dirinfo.uname = info.uname
                dirinfo.gid = info.gid
                dirinfo.gname = info.gname
                dirinfo.type = tarfile.DIRTYPE
                dirinfo.mode = dirmode
                #Don't call _filePlacingInPackage on directories
                archive.addfile(dirinfo)
        pathHelper(path)

    def _addInfoToArchive(self, info):
        self._ensureArchivePath(self.archive, info)
        self._filePlacingInPackage('data',None,info.name,None)
        self.archive.addfile(info)

    @staticmethod
    def _getDirectoryMode(mode):
        mode = mode & 0o777
        return ((mode >> 2) & 0o111) | mode

    def _doArchiveFileAspects(self, mapping, sourcePath, archivePath, aspects, info=None):
        if aspects is not None and len(aspects) > 0:
            self.flowcontrol.initFlowControlIssue(
                "doNotMapFile",
                "Tells packager to avoid archiving a file" )
            self.engine.launchAspects(
                aspects,
                'archive_file',
                self.engine.getPhase(),
                self,
                self.options,
                {'from' : sourcePath,
                 'to' : archivePath,
                 'mapping': mapping,
                 'info': info } )
            if self.flowcontrol.advice("doNotMapFile"):
                self.log.info("Not archiving file '%s' on advice of aspects", str(source) )
                return False
        return True

    def _filePlacingInPackage(self, archive, sourcePath, archivePath, contents=None):
        """Override this to handle individual files placed in an archive
           'archive' - may be used to distinguish which archive when a package
                       format requires multiple archives.
           'contents' - if there is no 'sourcePath' pass None for sourcePath
                        and pass the file contents in here.
                        may be a string or file object.
           The _placeFileInArchive method must call this for every individual
               file placed for the 'data' archive.  Methods that place other
               files should also call this with a different 'archive' label.
           This is called before the file is actually present in the archive"""
        if sourcePath is None:
            self.log.devdebug("Archiving in %s: Archive: %s   contents: %s",
                archive,
                archivePath,
                contents )
        else:
            self.log.devdebug("Archiving in %s: Source:  %s   Archive: %s",
                archive,
                sourcePath,
                archivePath )

    def _placeFileInArchive(self, mapping, sourcePath, archivePath, aspects):
        """Override this method if the data archive is not represented by
           a TarFile object, or an object that doesn't respond in
           a similar fashion to TarFile's 'add' method"""
        def addFilter(info):
            info.mode = self._modeInt(mapping['permissions'])
            #Directories usually need execution rights if they have read rights
            if info.isdir():
                info.mode = self._getDirectoryMode(info.mode)
            info.uid = mapping['owner'][1]
            info.gid = mapping['group'][1]
            info.uname = mapping['owner'][0]
            info.gname = mapping['group'][0]
            subdirPath = os.path.relpath(info.name, archivePath)
            if subdirPath[:2] == './':
                subdirPath = subdirPath[:2]
            elif subdirPath[0] == '.':
                subdirPath = subdirPath[1:]
            if len(subdirPath) == 0:
                actualSourcePath = sourcePath
                actualArchivePath = archivePath
            else:
                actualSourcePath = os.path.join(sourcePath, subdirPath)
                actualArchivePath = os.path.join(archivePath, subdirPath)
            if not self._doArchiveFileAspects(
                mapping,
                actualSourcePath,
                actualArchivePath,
                aspects,
                info ):
                return None
            self.log.devdebug("addFilter info: %s", str(info.__dict__))
            self._ensureArchivePath(self.archive, info)
            self._filePlacingInPackage(
                'data',
                actualSourcePath,
                actualArchivePath )
            return info

        info = self.archive.add(sourcePath, archivePath, filter=addFilter)

    def _executePreppedMapping(self, mapping):
        """This method performs the action of taking files specified
           by the installmap sections given and placing them into
           the package.  This is the method that calls _placeFileInArchive"""
        filemappings = self.filemanager.parseFileMap(mapping['map'])
        copyrightControl = self._packageControl('copyright')
        if 'files' not in copyrightControl:
            copyrightControl['files'] = {}
        for froms, tos in filemappings.iterspecs():
            self.log.devdebug("filemappings: \n  (from) %s\n  (to) %s", froms, tos)
            resultsAreDirectories = len(froms) > 1
            for source in froms:
                fileAspects = self._lookupFileTypeAspects(source)
                #Allow the aspect to alter the mapping without
                #changing the rest of the behavior
                if len(fileAspects) > 0:
                    self.flowcontrol.initFlowControlIssue(
                        "doNotMapFile",
                        "Tells packager to avoid archiving a file" )
                    aspectMapping = copy.deepcopy(mapping)
                    self.engine.launchAspects(
                        fileAspects,
                        'begin_map',
                        self.engine.getPhase(),
                        self,
                        self.options,
                        {'from' : source, 'tos' : tos, 'mapping': aspectMapping} )
                    if self.flowcontrol.advice("doNotMapFile"):
                        self.log.info("Not archiving file '%s' on advice of aspects", str(source) )
                        continue
                else:
                    aspectMapping = mapping
                for result in tos:
                    #Create tarinfo here.
                    if resultsAreDirectories:
                        pathpart = result['relLocation']
                        _, filepart = os.path.split(source['location'])
                    else:
                        pathpart, filepart = os.path.split(result['relLocation'])

                    self._placeFileInArchive(
                        aspectMapping,
                        source['location'],
                        os.path.join(
                            pathpart,
                            filepart ),
                        fileAspects )

                    #TODO: This will only save off the directory for
                    #      in debian, for example, adding a /* to the end
                    #      if a single directory in the archive happens
                    #      to have varying copyrights, this will not be correct.
                    copyrightControl['files'][pathpart] = aspectMapping['copyright']
                if len(fileAspects) > 0:
                    self.engine.launchAspects(
                        fileAspects,
                        'end_map',
                        self.engine.getPhase(),
                        self,
                        self.options,
                        {'from' : source, 'tos' : tos, 'mapping': aspectMapping} )

    def _doMaps(self):
        """This is the high level method that performs the
           actions specified by the installmap sections given in
           'maps'.   This executes all the map sections,
           does _doMappingSubstitutions with them and then
           performs _executePreppedMapping on each section."""
        mappings = self.options['maps']
        self.filemanager = self.metadata._getFileManager()
        mappingParts = mappings.split('\n')
        mappings = ','.join(mappingParts)
        mappingParts = mappings.split(',')
        allmaps = []
        for part in mappingParts:
            result = self.engine.launchStep(
                part.strip(),
                'package' )
            if result is None or not result._didPass():
                self.log.error("%s step failed", part)
                self.log.failed()
                raise ValueError("Mappings for Packager failed")
            mapDefinitions = result._getReturnValue('package')
            allmaps.append(mapDefinitions)
        #Grok the definitions and do substitutions in the map entries
        for mapping in allmaps:
            readymappings = self._doMappingSubstitutions(mapping)
            for ready in readymappings:
                self.log.devdebug("readymapping: %s", str(ready))
                self._executePreppedMapping(ready)
        self.engine.launchAspects(
            self.aspects,
            'mapping_complete',
            self.engine.getPhase(),
            self,
            self.options )

    def _handleControls(self):
        """Handle controls will dispatch _control_<control name>
           methods for each section it finds as well as do any
           setup required (on override) for the control file(s) or other
           package writing that needs to occur to include the
           metadata represented by the controls defined."""
        for key, value in self.controls.items():
            aspects = self._lookupControlAspects(key)
            if len(aspects) > 0:
                self.flowcontrol.initFlowControlIssue(
                    "ignoreControl",
                    "Tells packager to ignore a control definition" )
                self.engine.launchAspects(
                    aspects,
                    'control',
                    self.engine.getPhase(),
                    self,
                    self.options,
                    {'control' : value} )
                if self.flowcontrol.advice('ignoreControl'):
                    self.log.info("---- Control '%s' will not be written on advice of an aspect")
                    continue
            if not hasattr(self, '_control_%s' % key):
                self.log.warning("'%s' control was defined for the package but was not handled or written ", key)
                continue
            getattr(self, '_control_%s' % key)(value)

    def package(self, options):
        self.options = options

        #Figure out how the product metadata corresponds to
        #the package being created.
        self._doMetadataMappings()

        #Set up the package structure and parts for filling out.
        self._setupPackage()

        #Move in mapped files
        self._doMaps()

        #Handle the control metadata
        self._handleControls()

        #produce debian directory and files
        if self._finishPackage():
            self.log.passed()
            return True
        else:
            self.log.failed()
            return False

    def clean(self, options):
        self._cleaningFiles()
        result = options['result']
        try:
            shutil.rmtree(result)
        except (IOError,OSError) as e:
            self.log.info("'result' could not be removed: %s", repr(e))
        except:
            self.log.exception("'result' coult not be removed")
        self.log.passed()
        return True

    def package_clean(self, options):
        return self.clean(options)
