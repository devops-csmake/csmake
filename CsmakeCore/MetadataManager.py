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
from .FileManager import MetadataFileTracker
import warnings

class DefaultMetadataModule:
    """This is a metadata placeholder - consider possibly deduping the
       metadata module interface into here."""
    def __init__(self, log, env):
        self.env = env
        self.log = log
        self.files = MetadataFileTracker(self, self.log, self.env)
        self.versionkeys = ['primary']
        self.original = {
            'name' : 'initial-bogus-metadata-section-REPLACE',
            'version' : {
                'primary' : '0.0.0',
                'primary-major' : '0',
                'primary-minor' : '0',
                'primary-patch' : '0'
            },
            'description' : 'The csmakefile does not yet specify metadata to used for the project(s) that are being built...A metadata SECTION SHOULD BE DEFINED ASAP'
        }
        self.id = "initial-bogus-metadata-section-REPLACE"

    def _getFileManager(self):
        return self.files

    def _getMetadataDefinitions(self, lang=None):
        self.log.warning("Package metadata has not been defined, metadata has been requested by the build configuration")
        return self.original

    def _getDefaultDefinedVersion(self, separator='-'):
        self.log.warning("Package metadata has not been defined, however, the version is being used by the build configuration")
        versionresult = []
        for key in self.versionkeys:
            versionresult.append(self.version[key])
        return separator.join(versionresult)

    def _getVersionWithFormat(self, formatting, useUnused=False, used=None, separator='-'):
        self._getDefaultDefinedVersion(separator=separator)

    def _addVersionString(self, versionkey, value):
        self.log.warning("Package metadata has not been defined, however, the version is being used by the build configuration")
        self.version[versionkey] = value
        self.versionkeys.append(versionkey)

    def _isVersionKeyDefined(self, versionkey):
        self.log.warning("Package metadata has not been defined, however, the version is being used by the build configuration")

    def _getSpecifiedLanguages(self):
        self.log.warning("Package metadata has not been defined, metadata languages have been requested by the build configuration - an unreasonable default is being returned.")
        return ['X']

    def _getDefinitionInLanguage(self, key, language):
        self.log.warning("Package metadata has not been defined, metadata language strings have been requested by the build configuration - the default (bad) metadata strings are being accessed")
        return self.original[key]

class MetadataWarning(Warning):
    def __init__(self, metadata, popped, message):
        Warning.__init__(self, message)
        self.metadata = metadata
        self.popped = popped

class MetadataCurrent(MetadataWarning):
    """This warning is raised when the metadata is already the
       current metadata
       
       It's not really a problem unless you didn't expect that
       the metadata was already defined for the given id.

       In a stack metadata, recalling your metadata is a way
       to go back through the stack popping all the children off"""
    pass

class MetadataParent(MetadataWarning):
    """This warning is raised when the metadata is a parent of
       the current metadata and the is now current"""

class MetadataResumed(MetadataWarning):
    """This warning is reaised when the metadata is not a
       parent of any of the current metadata"""
    pass


class MetadataManager:
    """The MetadataManager will allow a hierarchy of metadata - one can use 
       this mechanism to specify an entire set of well scoped metadata from
       a installed compute environment down to an individual file"""
    def __init__(self, log, env):
        self.metadataDictionary = {}
        self.metadataStack = []
        self.env = env
        self.log = log

    def parentOf(self, metaid):
        for key, meta in self.metadataDictionary.items():
            for child in meta['contains']:
                if child == metaid:
                    return meta
        return None

    def start(self, mid, metadata):
        if mid in self.metadataDictionary:
            actual = self.metadataDictionary[mid]
            if actual not in self.metadataStack:
                self.metadataStack.append(actual)
                raise MetadataResumed(
                        actual,
                        [],
                        "The metadata '%s' was reactivated" % mid)
            elif self.metadataStack[-1] is actual:
                raise MetadataCurrent(
                    actual,
                    [],
                    "The metadata '%s' was already the current one" % mid)
            else:
                popped = []
                while self.metadataStack[-1] is not actual:
                    popped.append(self.metadataStack[-1])
                    self.endCurrent(self.metadataStack[-1].getMetadataId())
                raise MetadataParent(
                    actual,
                    popped,
                    "The metadata '%s' was a parent of the current one.  The stack has been adjusted to reflect this change" % mid)
        current = metadata
        self.metadataDictionary[mid] = current
        self.metadataStack.append(current)

    def endCurrent(self, mid):
        assert len(self.metadataStack) > 0 and mid == self.metadataStack[-1].getMetadataId()
        return self.metadataStack.pop()

    def getCurrent(self):
        if len(self.metadataStack) == 0:
            return None
        return self.metadataStack[-1]

