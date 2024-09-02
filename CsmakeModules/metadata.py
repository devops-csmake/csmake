# <copyright>
# (c) Copyright 2018 Cardinal Peak Technologies
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
from CsmakeCore.FileManager import MetadataFileTracker
from CsmakeCore.MetadataManager import MetadataWarning, MetadataCurrent
import re
import copy

class metadata(CsmakeModuleAllPhase):
    """Purpose: Define the metadata of software described in the
                csmakefile.
       Type: Module   Library: csmake (core)
       Description:
                metadata is intended to be generic, encompassing
                some major variables of software metadata generally.
                - modules that package software for a specific purpose
                  will need to map this data to the appropriate fields
                  some suggestions are given below...

                The behavior of this module is if a second metadata
                module is invoked, it will push the results of the
                previous metadata down in a metadata stack (accessible
                by id from the MetadataManager instance)

                ++++FUTURE++++
                A well behaved process should have a final step that
                will "end" its metadata  with an
                endmetadata section in cases where a build needs to
                manage multiple instances of metadata.  Ending metadata
                will have the effect of making the previous metadata
                current again.
       Phases: *any*
       Options:
           **use-parent-filetracking:  Adding this flag to the section
                will ensure that filetracking will not be scoped
                by this metadata section.
                Without this flag, filetracking is scoped for each
                metadata set.
           NOTE: (<lang>) after the option
                 will specify value in a different language
                 en_US is default.
                 E.g., name(jp_JA)=<Japanese>
                 would define the name of the package in Japanese.
           ALSO NOTE: 'Corresponds to: notes below are examples of
                       different metadata sets that correspond to
                       the metadata defined in this section
                       --- the lists are *not* comprehensive'
           name - main name of the package (the actual csmake id)
                  (Corresponds to:  Debian: Package, Python: name)
           version - The version of a product described by the
                      csmakefile.
                     Use of the Semantic Versioning standard
                     X.Y.Z is *strongly* encouraged where:
                        X - major
                        Y - minor
                        Z - patch level
                     (see ::Versioning:: below)
                     NOTE: csmake will give a warning if this format is not
                     used for the version.
                     ALSO NOTE: The following version designations
                                will be introduced from this option:
                        at minimum:
                           'primary': which will contain the entire string
                                      defined for version
                        if Semantic Versioning is conformed to:
                           'primary-major': Which will contain the 'X' part
                                            of the version
                           'primary-minor': Which will contain the 'Y' part
                                            of the version
                           'primary-patch': Which will contain the 'Z' part
                                            of the version
              (Corresponds to:
                  Debian: Version (product part), Python: version,
                  Gem: version, OVF: Product Section/Version)
           description - Description of the package (language: en_US)
           description(<lang>) - Description in another language
           about - Extended description of the package (language: en_US)
           about(<lang>) - Extended description of the package in another language
           packager - The name and e-mail of the current person/org maintaing
                      the backage
                 (Corresponds to:  Debian: Maintainer)
           copyrights - References to all applicable copyright modules
                 (Corresponds to:  Wheel: holders are author)
           manufacturer - The indivdual or company responsible
                  for creating and releasing the software.
                 (Corresponds to:  CSU: created_by)
           classifiers - PyPi styled classifiers
                          May translate to various fields in different package
                          formats.  I.e., Topic could imply "Section" in debian
                                      and/or it could imply "Priority"
                         In other words, the classifiers are interpreted
                          by packagers to fill in some fields and information
                          into the package metadata.
           keywords - words used to describe the package
           contains - metadata for object definitions that the object
                      described by this metadata contains
                      may be used in conjunction with or in-place of
                      the "files" option.
                      <package-metadata-id>[(filetype fileintent, filetype fileintent, ...)]

         :: Package Relationship Definitions ::
           These may be ids that reference a "package name map" module
           as packages may vary in name and number across packaging systems
           Names used in this section can be mapped to specific
           packaging system names via PackageNameMappings modules.

           depends - list of dependent packages
               (debian: Depends, python: install_requires)
           recommends - list of recommended packages
           suggests - list of other useful packages
           enhances - list of packages this package is useful to
           pre-depends - list of packages that must be installed before
                         this package can be installed
           breaks - list of packages that this package will break
           conflicts - list of packages that will conflict with this package
           provides - list of packages this package stands in the place of
           replaces - list of packages that are replaced by this package

       Environment:
           All options are added to the environment as 'metadata:<key>'
           e.g.: 'metadata:name'

       csmake Internals:
           In csmake module implementations, self.env.metadata is a
           MetadataManager containing the information about the current
           metadata and versioning.

       References:
         :: Classifiers ::
           http://pypi.python.org/pypi?:action=list_classifiers

         :: Versioning ::
           http://semver.org
           http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version
           http://www.python.org/dev/peps/pep-0440/
           http://www.rpm.org/max-rpm/s1-rpm-inside-tags.html
           http://guides.rubygems.org/specification-reference/#version
           http//twiki.cern.ch/twiki/bin/view/Main/RPMAndDebVersioning
           http://msdn.microsoft.com/en-us/library/aa370859%28v=vs.85%29.aspx
           http://msdn.microsoft.com/en-us/library/aa372488%28v=vs.85%29.aspx
           <Product Section> definition from OVF Specification:
               http://www.dmtf.org/sites/default/files/standards/documents/DSP0243_1.0.0.pdf

         :: Package Dependencies ::
           https://www.debian.org/doc/debian-policy/ch-relationships.html
    """

    RESERVED_FLAGS = ['description']
    REQUIRED_OPTIONS = ['name', 'version']

    def __init__(self, env, log):
        CsmakeModuleAllPhase.__init__(self, env, log)
        self.files = MetadataFileTracker(self, self.log, self.env)
        self.id = None

    def __repr__(self):
        return "<<metadata step definition>>"

    def __str__(self):
        return "<<metadata step definition>>"

    def __eq__(self, another):
        return id(self) == id(another)

    LIST_INPUTS_SPACE_DELIM= ['classifiers','keywords','depends',
                  'recommends', 'suggests', 'enhances', 'pre-depends',
                  'breaks', 'conflicts', 'provides', 'replaces']
    LIST_INPUTS_PACKAGE_MAP= ['depends',
                  'recommends', 'suggests', 'enhances', 'pre-depends',
                  'breaks', 'conflicts', 'provides', 'replaces']

    def getMetadataId(self):
        return self.id

    def _parseListOptions(self):
        for option in metadata.LIST_INPUTS_SPACE_DELIM:
            try:
                self.original[option] = original[option].strip().split()
            except:
                pass

    def _getFileManager(self):
        return self.files

    def parsePackageMaps(self, options, phase):
        #TODO: Need to define package maps
        #      This is probably an activity better suited for a packager step?
        result = {}
        for option in options:
            newparts = []
            try:
                packages = self.original[option]
                for package in packages:
                    found = False
                    if self.engine.lookupSection(package) is not None:
                        result = self.engine.launchStep(option, phase)
                        if result is not None and result._didPass():
                            returnValue = result._getReturnValue(phase)
                            if returnValue is not None and \
                                type(returnValue) is list:
                                newparts.extend(returnValue)
                                found = True
                    if not found:
                        newparts.append(package)
                result[option] = newparts
            except:
                pass
        return result

    def _addVersionString(self, versionkey, value):
        self.version[versionkey] = value
        self.versionkeys.append(versionkey)

    def _isVersionKeyDefined(self, versionkey):
        return versionkey in self.version

    def _getDefaultDefinedVersion(self, separator='-'):
        versionresult = []
        for key in self.versionkeys:
            versionresult.append(self.version[key])
        return separator.join(versionresult)

    def _getVersionWithFormat(
        self,
        formatting,
        useUnused=False,
        used=None,
        separator='-'):
        versionresult = []
        extras = []
        for formatpart in formatting:
            try:
                versionresult.append(formatpart % self.version)
            except KeyError:
                pass
        if useUnused:
            remainingkeys = copy.copy(self.versionkeys)
            for key in used:
                try:
                    remainingkeys.remove(key)
                except ValueError:
                    pass
            for key in remainingkeys:
                extras.append(self.version[key])
            if len(extras) > 0:
                versionresult.append("%s%s" % (
                    separator,
                    separator.join(extras) ) )
        return ''.join(versionresult)

    def _parseVersionFormatString(self, formatString):
        """Takes a string with version keys in brackets {}"""
        return self._parseBrackets(formatString, self.version)

    def _processCopyrights(self, copyrights):
        copyrightParts = copyrights.split('\n')
        copyrights = ','.join(copyrightParts)
        copyrightParts = copyrights.split(',')
        copyrightResults = []
        currentPhase = self.engine.getPhase()
        for part in copyrightParts:
            part = part.strip()
            result = self.engine.launchStep(
                part,
                currentPhase )
            if result is None or not result._didPass():
                self.log.error("%s step failed", part)
                self.log.failed()
                raise ValueError("Copyright %s failed to execute" % part)
            copyrightResults.append(result._getReturnValue(currentPhase))
        return copyrightResults

    def _getMetadataDefinitions(self, lang=None):
        if lang is None:
            return self.original
        else:
            result = dict(self.original)
            try:
                result.update(self.languages[lang])
            except:
                self.log.error("Language '%s' is not specified")
            return result

    def _getSpecifiedLanguages(self):
        return list(self.languages.keys())

    def _getDefinitionInLanguage(self, key, language):
        return self.languages[language][key]

    def _chatBeginMetadata(self, message):
        if self.log.chatter:
            self.log.chat("   \\-\\")
            self.log.chat("    \\-\\%s" % ('_' * 69))
            self.log.chat("    /-/")
            self.log.chat("   /-/    %s" % message)
            self.log.chat("  /-/")

    def _chatAllMetadataInformation(self):
        if self.log.chatter:
            offset = 12
            for key, value in self.original.items():
                if key == 'version':
                    self.log.chat("%sVersion: %s" % (
                        " " * offset,
                        self._getDefaultDefinedVersion() ) )
                    continue
                self.log.chat("%s%s: %s" % (
                    (" " * offset ),
                    key,
                    value ) )

    def default(self, options):
        currentFileTracking = self.env.metadata.getCurrent().files
        self.original = {}
        self.languages = {'en_US' : self.original}
        self.version = {}
        self.versionkeys = ['primary']
        self.log.devdebug("Options for metadata are: %s", str(options))
        self.id = options['name']
        try:
            self.env.metadata.start(self.id, self)
        except MetadataCurrent as w:
            self.log.debug("Metadata '%s' was invoked/restamped", w.metadata.id)
            self.log.passed()
            return w.metadata.original
        except MetadataWarning as w:
            self._chatBeginMetadata("Resuming with metadata for '%s': %s" % (
                w.metadata.getMetadataId(),
                str(w) ) )
            self.log.passed()
            for key in list(self.env.env.keys()):
                if key.startswith("metadata:"):
                    del self.env.env[key]
            for key, value in w.metadata.original.items():
                self.env.env['metadata:%s'%key] = value
            self.env.env['metadata:version'] = w.metadata.version['primary']
            return w.metadata.original
        for key, value in options.items():
            if key.startswith("**"):
                if key == '**use-parent-filetracking':
                    self.files = currentFileTracking
                continue
            if key.endswith(')'):
                keyparts = key.split('(')
                if len(keyparts) == 1:
                    self.original[key] = value
                else:
                    lang = keyparts[1].rstrip(')')
                    if lang not in self.languages:
                        self.languages[lang] = {}
                    self.languages[lang][key[0]] = value
            else:
                self.original[key] = value
            self.env.env['metadata:%s'%key] = value
        self.version['primary'] = self.original['version']
        self.original['version'] = self.version
        versionCheck = re.match('^([0-9]+)[.]([0-9]+)[.]([0-9]+)$', self.version['primary'])
        if versionCheck is None:
            self.log.warning("The metadata specifies version='%s' for the version, which does not conform to the 'Semantic Versioning' standard.  See metadata documentation (csmake --list-type=metadata) and  http://semver.org", options['version'])
        else:
            self.version['primary-major']=versionCheck.groups()[0]
            self.version['primary-minor']=versionCheck.groups()[1]
            self.version['primary-patch']=versionCheck.groups()[2]

        self._parseListOptions()
        if 'copyrights' in self.original:
            self.original['copyrights'] = self._processCopyrights(
                self.original['copyrights'] )
        self._chatBeginMetadata("Building with metadata for '%s'" % self.id)
        self._chatAllMetadataInformation()
        self.log.passed()
        return self.original
