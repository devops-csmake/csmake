# <copyright>
# (c) Copyright 2020-2021 Autumn Patterson
# (c) Copyright 2021 Cardinal Peak Technologies, LLC
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

import io
import os
import subprocess
import sys
import tempfile
import time
import threading

class OutputTee:
    def __init__(self):
        self.tempdir = tempfile.mkdtemp(prefix='csmake-temp')
        self.executing = True
        self.lock = threading.Lock()
        self.resultIds = {}
        self.writers = []
        self.threadsOpen = {}
        self.threads = []
        self._locals = threading.local()
        self.actual = sys.stdout

    def subsumeStream(self, stream):
        self.actual = stream

    def _consumerThread(self, myfilename):
        buf = ""
        with io.TextIOWrapper(open(myfilename, 'rb', 0), write_through=0) as myfd:
            myfd.seek(0)
            while (self.threadsOpen[myfilename] and self.executing) or len(buf):
                buf = myfd.read(2048)
                if len(buf) == 0:
                    time.sleep(.1)
                    continue
                try:
                    self.actual.write(buf)
                    self.actual.flush()
                except:
                    sys.stderr.write("Couldn't write actual: " + buf + "\n")
                    sys.stderr.flush()
            else:
                buf = myfd.read(2048)
                while len(buf):
                    try:
                        self.actual.write(buf)
                    except:
                        sys.stderr.write("Couldn't write actual: " + buf + "\n")
                        sys.stderr.flush()
                    buf = myfd.read(2048)

    def _init_thread_local(self):
        self._locals.filename = "{}/{}".format(self.tempdir, threading.currentThread().getName())
        self._locals.filebuf = io.TextIOWrapper(open(self._locals.filename, 'wb', 0), write_through=True)
        self._locals.currentResult = None
        self._locals.readerThread = threading.Thread(
            target=self._consumerThread,
            args=(self._locals.filename, ))
        with self.lock:
            self.threadsOpen[self._locals.filename] = True
            self.threads.append(self._locals.readerThread)
        self._locals.readerThread.start()

    def startResult(self, result, repeat=True):
        try:
            cr = self._locals.currentResult
            pos = self._locals.filebuf.tell()
            with self.lock:
                if cr is not None:
                    self.resultIds[cr].append(pos)
                self.resultIds[result] = [self._locals.filename, pos]
        except AttributeError:
            if not repeat:
                raise
            self._init_thread_local()
            self.startResult(result, False)

    def endResult(self, result):
        try:
            self.flush()
            with self.lock:
                self.resultIds[result].append(self._locals.filebuf.tell())
        except:
            pass

    def endAll(self):
        for f in self.writers:
            try:
                f.close()
            except:
                pass
        self.executing = False
        for t in self.threads:
            try:
                t.join()
            except:
                pass
        try:
            self.actual.close()
        except:
            pass
        try:
            "subprocess.call(['rm', '-rf', self.tempdir])"
        except:
            pass

    def close(self):
        try:
            self.threadsOpen[self._locals.filename] = False
            self._locals.filebuf.close()
            with self.lock:
                f.remove(self._locals.filebuf)
        except:
            pass
        try:
            self.actual.flush()
        except:
            pass

    def flush(self):
        try:
            self._locals.filebuf.flush()
        except AttributeError:
            self._init_thread_local()

    def write(self, out, retry=True):
        try:
            return self._locals.filebuf.write(out)
        except AttributeError:
            if retry:
                self._init_thread_local()
                self.write(out, False)

    def fileno(self):
        return self._locals.filebuf.fileno()

    def getResult(self, result):
        with self.lock:
            location = self.resultIds[result]
            if len(location) >= 3:
                f = location[0]
                start = location[1]
                stop = location[-1]
            else:
                f, start = location
                stop = 9999999
        with open(f, 'r+b') as fp:
            fp.seek(start)
            #TODO: Ensure all is read
            return fp.read(stop-start)

    def __del__(self):
        self.endAll()

OutputTee = OutputTee()

