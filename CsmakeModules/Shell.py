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
import os
import subprocess
import sys
import re

class Shell(CsmakeModuleAllPhase):
    """Purpose: Execute a shell script
       Type: Module   Library: csmake (core)
       Options:
         :: Script Definition Options ::
           command(<phase>) - Shell command to execute in specified phase
                 If (<phase>) is not specified: 'build' is assumed
           command-clean(<phase>) - Like 'command', but file tracking
                           will assume cleaning is occurring
                           Thus files for file delcarations
                           and mappings will be checked for removal.
                 If (<phase>) is not specified: 'clean' is assumed
           command-no-verify(<phase>) - Like command, except file tracking
                           will not verify the files for tracking.
           NOTE: If multiple commands are specified for a single phase
                 the first one found is used.
           ALSO NOTE: <phase> may specify multiple phases comma (,) delimited

         :: Execution Options ::
           env - (OPTIONAL) Reference to one or more ShellEnv
                            section(s) to evaluate.
                            (May be any section that yields a dictionary
                             with keys that are valid shell identifiers)
                    Default: Uses the csmake execution environment
                    (comma and/or newline delimited)
           exec - (OPTIONAL) Will execute given command as the shell
                    Default: /bin/bash

         :: Parsing Options ::
           line-pad - (OPTIONAL) character to use to pad every line to preserve
                                 leading spaces.  Useful if using python as
                                 the 'exec', for example.
       Phase: Any
       File Tracking:
           A shell variable is defined named _MAPPING that represents the
           definition of **maps in the shell environment.
           _MAPPING may be iterested in the shell, e.g.:
               for map in $_MAPPING
           The structure of each map is:
                <from1>,,<from2>,,...;;<to1>,,<to2>,,...
           If exec is a bash shell patched with the shellshock fixes,
           the environment will also contain two accessor functions
                _froms and _tos
           The functions should be used in a subshell like:
                $(_froms $map)
           Which would yield:
                <from1> <from2> ...
           NOTE: because of the use of ';;' and ',,' as delimiters, the mapping
                 functions cannot handle files containing ',,' and ';;'.
           ALSO NOTE: The shellshock patch requires exported functions to
                      be surrounded with BASH_FUNC_<name>%% to be valid
                      in the bash environment..._froms and _tos are both defined
                      in this manner.
       Examples:
           [ShellEnv@my-command-env]
           THIS_DIR=mydir

           [Shell@my-command]
           command = mkdir -p ${THIS_DIR} && pushd ${THIS_DIR}
              ifconfig > my.cfg
              ls
              popd
              ls
           env = my-command-env, default-env

           The following will iterate through a group of
           files defined in the my-files group and move each one to
           essentially a new path and a new extension
           in the test and build phases:

           [Shell@my-mapped-command]
           **maps=<my-files> -(1-1)-> %(APATH)s/[~~filename~~].newer
           command(test, build) = for x in $_MAPPING
              do
                  for from in $(_froms $x)
                  do
                      for to in $(_tos $x)
                      do
                          mv $from $to
                      done
                  done
              done

           This example will create a tarball containing the given files in
           the mapping in the 'build' phase and cleans the zip up in the 'clean'
           phase:
           [ShellWithMapping@my-archive]
           **maps=<the-files> -(*-1)-> %(LOCATION)s/my-archive.zip
           command = for x in $_MAPPING
               do
                   tar -czf $(_tos $x) $(_froms $x)
               done
           clean-command = for x in $_MAPPING
               do
                   rm -rf $(_tos $x)
               done
           NOTE: This wouldn't cover all cases, say where a second file was
                 introduced in the "to" side of the mapping and the mapping
                 was changed to a -(*-*)-> or possibly if a second clause
                 is added using the '&&' conjunction for **maps
    """

    RESERVED_FLAGS = ['description']

    def _getCommand(self, options, phase):
        phaseString = r"((?P<command>command(-clean|-no-verify)?)\(((.|\s)*,)*\s*%s\s*(,(.|\s)*)*\)$)" % phase
        if phase == 'build':
            phaseString = phaseString + r"|(?P<default>^command$)"
        elif phase == 'clean':
            phaseString = phaseString + r"|(?P<default>^command-clean$)"
        phasere = re.compile(phaseString)
        for key, value in options.items():
            match = phasere.match(key)
            if match is not None:
                commandType = match.group("command")
                if commandType is None:
                    commandType = match.group("default")
                # There is no need to do substitution here because it's done by either CsmakeAspect or CliDriver.
                command = value
                self.log.info("Executing %s '%s' in phase '%s'" % (
                    commandType,
                    command,
                    phase ) )
                return (commandType, command)
        self.log.debug("Command for phase '%s' not defined" % phase)
        return (None, None)

    def _getEnvironment(self, options, newenv):
        if 'env' in options:
            refs = ','.join(options['env'].split('\n')).split(',')
            for ref in refs:
                ref = self.env.doSubstitutions(ref)
                result = self.engine.launchStep(
                    ref.strip(),
                    self.engine.getPhase())
                if result is not None:
                    result = result._getReturnValue(self.engine.getPhase())
                    try:
                        self.log.info("Adding to environment: %s", result)
                        newenv.update(result)
                    except Exception as e:
                        self.log.exception(
                            "Processing environment %s failed",
                            ref )

        #Grock any prefix and suffix requirements for bash functions
        bash_func_prefix="BASH_FUNC_"
        bash_func_suffix="%%"
        try:
            defresult = subprocess.check_output(
                "foo(){ echo t; }; export -f foo; env | grep foo",
                executable='/bin/bash',
                shell=True)
            parts = defresult.split('foo')
            bash_func_prefix = parts[0]
            bash_func_suffix = parts[1].split('=')[0]
        except Exception as e:
            self.log.warning("_froms and _tos may not work properly: %s", str(e))

        #Add in the ability to access the mappings from the shell
        mappingenv = []
        if self.mapping is not None:
            for froms, tos in self.mapping.iterfiles():
                mappingenv.append("%s;;%s" % (',,'.join(froms),',,'.join(tos)))
        newenv.update({
            '_MAPPING' : ' '.join(mappingenv),
            '{}_froms{}'.format(bash_func_prefix,bash_func_suffix):
                 '() { aaa=(${1//\;\;/ }\n); echo ${aaa[0]//,,/ }\n}',
            '{}_tos{}'.format(bash_func_prefix,bash_func_suffix):
                 '() { aaa=(${1//\;\;/ }\n); echo ${aaa[1]//,,/ }\n}'
            })
        return newenv

    def _getStartingEnvironment(self, options):
        return os.environ

    def _executeShell(self, command, env, execer='/bin/bash'):
        modcommand = command
        if self._linepad is not None:
            self.log.debug(self._linepad)
            modcommand = command.replace('\n%s' % self._linepad, '\n')
            if modcommand[0:len(self._linepad)] == self._linepad:
                modcommand = modcommand[len(self._linepad):]
        result  = subprocess.call(
            modcommand,
            shell=True,
            env=env,
            stdout=self.log.out(),
            stderr=self.log.err(),
            executable=execer)
        return result

    def _setFileTracking(self, commandType):
        if commandType == 'command-clean':
            self._cleaningFiles()
        elif commandType == 'command-no-verify':
            self._dontValidateFiles()

    def _getExecer(self, options):
        if 'exec' in options:
            execer = self.env.doSubstitutions(options['exec'].strip())
        else:
            execer = '/bin/bash'
        return execer

    def __init__(self, env, log):
        self._linepad = None
        CsmakeModuleAllPhase.__init__(self, env, log)

    def default(self, options):
        if 'line-pad' in options:
            self._linepad = options['line-pad']
        execer = self._getExecer(options)
        phase = self.engine.getPhase()
        newenv = self._getStartingEnvironment(options).copy()
        newenv = self._getEnvironment(options, newenv)
        (commandType, command) = self._getCommand(options, phase)
        if command is None:
            self._dontValidateFiles()
            self.log.skipped()
            return None
        self._setFileTracking(commandType)
        result = self._executeShell(command, newenv, execer)
        if result == 0:
            self.log.passed()
        else:
            self.log.failed()
