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
from CsmakeCore.CsmakeModuleAllPhase import CsmakeModuleAllPhase
import sys

class installmap(CsmakeModuleAllPhase):
    """Purpose: Generically describe a set of files and their intended
                installation points for a Packager installer target.
       Type: Module   Library: csmake (core)
       Description:
                The module will parse the various section options and return
                a list of dictionaries with the following keys (as defined in
                Options, below):
                   maps - dictionary of file mappings into the installation
                          target
                   key - <key>
                   type - <source-type>
                   intent - <source-intent> (None if unspecified)
                   destination - <destination>
                   copyright - [ parsed copyright dictionaries ]
                      (If not defined, will inherit the copyrights defined
                       in the metadata.  If that's not defined, will
                       be None)
                   files - list of dict containing:
                       owner - (<owner>, uid)
                       group - (<group>, gid)
                       mod - "chmod" style octal code
                       file - <file or directory to install>
       Phases:
           *any*
       Options:
           map_<mapkey> -
               map: a file mapping (as in **maps)
               [copyright: <copyright-id>]
                   should refer to a copyright specification in the makefile
                   if not included, the metadata's copyright will be used.
               owner: a user on the installed system
               group: a group on the installed system
               permissions: permissions to provide for the installed file

           path_<pathkey> - <ID>
               The pathkey represents a semantic mapping that
               packaging modules would define.
               The ID is used in the maps enclosed in curly braces
               to denote a necessary substitution.

               For example:
                   path_root=INSTALL_ROOT
                   map_mymap=map: <bin> -(1-1)-> {INSTALL_ROOT}/bin/[~~file~~]

               A Packager would key off of the "root" part to define its
               understanding of what 'root' means.  INSTALL_ROOT would
               mark where that 'root' path goes in the mappings.

               The purpose for having this 'path_root=<ID>' notation is
               to allow the 'installmap' section the ability to unify different
               Packager's paths into a common delivery definition.  For example,
               say we have a WindowsMSIPackage and a DebianPackage that
               we want to create a common 'installmap' section for.
               For the sake of the example, let's assume DebianPackage has
               a "root" path, and WindowsMSIPackage has a "ProgramFiles" path
               and we want to unify these concepts into a single ID,
               INSTALLATION_POINT.  We would define the following options in
               the installmap section:
                   path_root=INSTALLATION_POINT
                   path_ProgramFiles=INSTALLATION_POINT

               By doing this, we have avoided the need for two separate
               installmaps, even though the concepts of "root" and
               "ProgramFiles" are vastly different.

           owner_<userkey> - <ID>
           group_<groupkey> - <ID>
               These options allow the installmap to unify differing user
               definitions as a single user.  For example, a linux-oriented
               packager may have a concept of a "root" user and root user
               permissions, but a windows-oriented packager may have a
               concept of an "Administrator" user and Administrator permissions
               Allowing an installmap, for this example, to define:
                  user_root=ROOT
                  user_Administrator=ROOT
               Allows the installmap to unify these permissions into a single
               installmap definition.

       See Also:
           copyright module
    """
    def __str__(self):
        return "<installmap object>"

    def __repr__(self):
        return "<installmap object>"

    def default(self, options):
        self.definitions = {'map':{}}
        self.fileManager = self.metadata._getFileManager()
        nonDefinitionOptions = {}
        if self.fileManager is None:
            self.log.error("Metadata must be defined before attempting to create an installmap")
            self.log.failed()
            return None
        result = []

        #Parse the lists
        for key, value in options.items():
            parts = key.split('_')
            if len(parts) >= 2:
                section = parts[0]
                item = '_'.join(parts[1:])
                if section not in self.definitions:
                    self.definitions[section] = {}
                self.definitions[section][item] = value
            else:
                nonDefinitionOptions[key] = value

        #Parse the maps
        mapDefinitions = {}
        for key, value in self.definitions['map'].items():
            mapDefinitions[key] = {}
            parts = value.strip().split('\n')
            for part in parts:
                partparts = part.split(':', 1)
                if len(partparts) == 2:
                    mapDefinitions[key][partparts[0].strip()] = \
                        partparts[1].strip()
        self.definitions['map'] = mapDefinitions

        #Just return the mappings
        self.log.passed()
        return self.definitions
