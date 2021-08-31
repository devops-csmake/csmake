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
from Csmake.MetadataManager import MetadataManager
from Csmake.FileManager import MetadataFileTracker

class Environment:
    """Shared environment for all build steps"""
    def __init__(self, engine):
        self.transPhase = {}
        self.env = {}
        self.engine = engine
        self.settings = engine.settings
        self.metadata = MetadataManager(self.engine.log, self)

    def __repr__(self):
        return "Env: %s" % str(self.env)

    def addTransPhase(self, key, value):
        self.transPhase[key] = value
        self.env[key] = value

    def flushAll(self):
        self.env = self.transPhase.copy()
        self.metadata = MetadataManager(self.engine.log, self)
        
    def update(self, dictionary):
        tryAgain = False
        for key, value in dictionary.items():
            if key.startswith('**'):
                continue
            try:
                self.env[key] = self.doSubstitutions(value.strip())
            except:
                tryAgain = True
                self.engine.log.devdebug("update failed on '%s' - first pass" % key )
        if tryAgain:
            for key, value in dictionary.items():
                if key.startswith('**'):
                    continue
                self.env[key] = self.doSubstitutions(value.strip())

    def doSubstitutions(self, target):
        return target % self.env
