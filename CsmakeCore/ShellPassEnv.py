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
import subprocess
import pickle

class ShellPassEnv:

    ENV_SEP='~~~~~~~ START ENV ~~~~~~~'
    def call(self, command, stdout, stderr, env, shell=True):
        actualStdout = subprocess.PIPE
        if stdout == stderr:
            actualStderr = subprocess.STDOUT
        else:
            actualStderr = subprocess.STDERR 

        actual = '%s && set +x && echo "%s" && python -c "import os; import pickle; print pickle.dumps(os.environ)"' % (
            command[-1],
            ShellPassEnv.ENV_SEP )
        command[-1] = actual
        #TODO: Consider parameter: executable='/bin/bash'
        proc = subprocess.Popen(command, stdout=actualStdout, stderr=actualStderr, env=env, shell=shell)
        stdoutResult, stderrResult = proc.communicate()
        result = proc.returncode
        if result == 0:
            splitStdOut = stdoutResult.split(ShellPassEnv.ENV_SEP)
            stdout.write(splitStdOut[0])
            picklein = ShellPassEnv.ENV_SEP.join(splitStdOut[1:]).strip()
            newenv = pickle.loads(picklein)
            if stdout != stderr:
                stderr.write(stderrResult)
            return(result, newenv)
        else:
            stdout.write(stdoutResult)
            if stdout != stderr:
                stderr.write(stderrResult)
            return(result, None)

