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
from Csmake.CsmakeModule import CsmakeModule

class TestOnExitHandler(CsmakeModule):
    """Purpose: To test csmake aspects, that is all"""
        
    def build(self, options):
        ident = None
        if 'ident' in options:
            ident = options['ident']
        self._registerOnExitCallback("_onExit", ident)
        self.log.debug("Registered _onExit: %s", ident)
        self.log.passed()
        return True

    def clean(self, options):
        ident = None
        if 'ident' in options:
            ident = options['ident']
        self._unregisterOnExitCallback("_onExit", ident)
        self.log.debug("Unregistered _onExit: %s", ident)
        self.log.passed()
        return True

    def _onExit(self):
        print("_onExit called")

