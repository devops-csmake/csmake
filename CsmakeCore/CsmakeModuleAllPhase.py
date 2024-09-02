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
from .CsmakeModule import CsmakeModule

class CsmakeModuleAllPhase(CsmakeModule):
    def __init__(self, env, log):
        CsmakeModule.__init__(self, env, log)

    def __repr__(self):
        return "<<%s Csmake Module - Does All Phases>>" % self.__class__.__name__

    def __str__(self):
        return self.__repr__()

    def default(self, options):
        self.log.info("default Not Implemented: skipping step")
        return None

    def __getattr__(self, name):
        if name.startswith('_'):
            self.log.error("__getattr__ should not be invoked for items that begin with '_': %s", name)
            self.log.error("    Failing lookup")
            raise AttributeError(name)
        self.log.devdebug("__getattr__ Looking up '%s': returning 'default", name)
        return self.default

    def build(self, options):
        return self.default(options)

    def clean(self, options):
        return self.default(options)

    def test(self, options):
        return self.default(options)

    def package(self, options):
        return self.default(options)

    def install(self, options):
        return self.default(options)
