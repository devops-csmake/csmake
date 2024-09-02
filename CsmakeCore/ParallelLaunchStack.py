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
import threading

class ParallelLaunchStack:

    #NOTE: Overarching assumption is that parents will not proceed
    #      until all children are completed.
    #      Only methods required for CliParser execution are implemented
    #      This should be changed to only support stack operations
    def __init__(self):
        self.mainThread = threading.currentThread()
        self.children = {self.mainThread : (None, [])}

    def _getCurrentStack(self, thread):
        if thread not in self.children:
            return None
        return self.children[thread]

    def append(self, item):
        thread = threading.currentThread()
        stack = self._getCurrentStack(thread)
        if stack is None:
            self.children[thread] = (thread.parent(), [])
        self.children[thread][1].append(item)

    def pop(self):
        #TODO: This only pops the last item, the general pop case is not yet
        #      supported.
        thread = threading.currentThread()
        stack = self._getCurrentStack(thread)
        result = stack[1].pop()
        if len(stack[1]) == 0:
            del self.children[thread]

    def __len__(self):
        thread = threading.currentThread()
        stack = self._getCurrentStack(thread)
        if stack is None:
            stack = self._getCurrentStack(thread.parent())
        result = 0
        current = stack
        while True:
            result = result + len(current[1])
            parent = current[0]
            if parent is None:
                break
            current = self._getCurrentStack(parent)
        return result

    def __getitem__(self, key):
        #TODO: Implement general lookup
        #if key >= 0:
        #    raise ValueError("General index lookup not implemented yet")
        thread = threading.currentThread()
        stack = self._getCurrentStack(thread)
        if stack is None:
            stack = self._getCurrentStack(thread.parent())
        return stack[1][key]
