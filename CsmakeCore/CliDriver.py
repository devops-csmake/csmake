# <copyright>
# (c) Copyright 2019,2021 Autumn Patterson
# (c) Copyright 2021 Cardinal Peak Technologies, LLC
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
import atexit
import traceback
import imp
import pkgutil
import types
import time
from os import environ
from sys import stdout, stderr
import sys
import os
import os.path
import getopt
import json
import logging
import configparser
import subprocess
import textwrap
import threading
import uuid
import signal

from .Settings import Settings
from .Settings import Setting
from .Environment import Environment
from .CsmakeModulesModule import CsmakeModulesModule
from .Result import Result
from .ProgramResult import ProgramResult
from .AspectResult import AspectResult
from .AspectFlowControl import AspectFlowControl
from .ParallelLaunchStack import ParallelLaunchStack
from .MetadataManager import DefaultMetadataModule
from .OutputTee import OutputTee
from . import phases

atexit.register(OutputTee.endAll)

CSMAKE_LIBRARY_VERSION = "3.0.0"

#TODO: Nested settings and settings processing needs to be migrated to
#      Settings.py and fixed to be more generic

#TODO: We need to refactor this into cli stuff and csmake stuff

class CliDriver(object):

    def __init__(self, settings={}, name='<name>', version='<version>'):
        self.currentPhase = 'default'
        self.settings = Settings(settings)
        self.scriptName = name
        self.scriptVersion = version
        self.modulePathConstruct = None
        #This will be replaced with a "Results" type object
        logging.basicConfig()
        self.log = logging.getLogger("%s.%s" % (
            self.__class__.__module__,
            self.__class__.__name__))
        #Patch this up until the result is created
        self.log.devdebug = self.log.debug
        self.log.startResult = lambda: 1
        self.log.endResult = lambda: 1
        self.log.endAll = lambda: 1
        self.log.finished = lambda: 1
        self.cwd = environ['PWD']
        self.oldcwd = self.cwd
        sys.meta_path.append(self)
        self.environment = Environment(self)
        self.launchStack = ParallelLaunchStack()
        self.launchStack.append(self)
        self.results = []
        self.stackDumps = []
        self.buildspecLock = threading.Lock()
        self.buildspec = configparser.RawConfigParser()
        self.buildspec.optionxform = str
        self.outBuildspec = configparser.RawConfigParser()
        self.outBuildspec.optionxform = str
        self.phasesDecl = None
        self.onBuildExits = {}

        try:
            self.tty = os.open(os.ctermid(), os.O_RDWR)
        except OSError:
            self.log.info("There is no tty to manipulate")
            self.tty = None
        if self.tty is not None:
            try:
                self.previous_fg_pgrp = os.tcgetpgrp(self.tty)
            except OSError:
                self.previous_fg_pgrp = None
        os.setpgrp()
        #H/T https://stackoverflow.com/questions/15200700/how-do-i-set-the-terminal-foreground-process-group-for-a-process-im-running-und
        self.ttou_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        if self.tty is not None:
            try:
                os.tcsetpgrp(self.tty, os.getpgrp())
            except OSError:
                pass

    def _endOfPhaseFlush(self):
        #This need to be invoked at the end of every phase
        #  Each phase will go through the same environment setup and tracking
        #  steps - saving state would compromise this
        self.environment.flushAll()
        defaultMetadata = DefaultMetadataModule(
                self.log,
                self.environment )
        self.environment.metadata.start(
            defaultMetadata.original['name'],
            defaultMetadata )


    def find_module(self, fullname, path=None):
        """This is called by python - we do this so that if a module
           imports another module, it has the same import behavior
           as the module lookup"""
        nameparts = fullname.split('.')
        self.log.devdebug("Import attempting import for '%s:%s'", fullname, nameparts[0])
        if nameparts[0] == 'CsmakeModules':
            self.log.devdebug("Csmake identified the import as a csmake module import")
            if len(nameparts) > 2:
                self.log.error("import %s: Subpackages are not allowed for csmake modules", fullname)
                raise ImportError(fullname)

            #We will handle this import request
            return self

        self.log.devdebug("Csmake will not handle this request")
        return None

    def load_module(self, fullname):
        nameparts = fullname.split('.')

        self.log.devdebug("Attempting to load module: %s", fullname)

        if nameparts[0] == 'CsmakeModules':
            if len(nameparts) == 1:
                imp.acquire_lock()
                try:
                    if 'CsmakeModules' in sys.modules:
                        return sys.modules['CsmakeModules']
                    else:
                        module = CsmakeModulesModule(self)
                        sys.modules['CsmakeModules'] = module
                        self.log.devdebug("Module: %s", module)
                        return module
                finally:
                    imp.release_lock()

            elif len(nameparts) != 2:
                self.log.error("import %s: Subpackages are not allowed for csmake modules", fullname)
                raise ImportError(fullname)

            imp.acquire_lock()
            try:
                if 'CsmakeModules' in sys.modules:
                    csmakeModulesModule = sys.modules['CsmakeModules']
                    if nameparts[1] in csmakeModulesModule.__dict__:
                        self.log.devdebug("Module already loaded")
                        self.log.devdebug("Module: %s", csmakeModulesModule.__dict__[nameparts[1]])
                        self.log.devdebug("All Modules: %s", str(sys.modules))
                        return csmakeModulesModule.__dict__[nameparts[1]]
            finally:
                imp.release_lock()

            self.log.devdebug("Loading module for the first time")
            modules, warnings = self._loadModules(nameparts[1])
            if len(warnings) != 0:
                self.log.warning("import %s:  There were some problems")
                for warning in warnings:
                    for line in warning:
                        self.log.warning(line)
            if len(modules) == 0:
                self.log.error("import %s:  Failed")
                raise ImportError(fullname)
            #This is now done in _loadModules
            #imp.acquire_lock()
            #try:
            #    sys.modules['CsmakeModules'].__dict__[nameparts[1]] = modules[0][2]
            #finally:
            #    imp.release_lock()
            self.log.devdebug("Returning module: %s", repr(modules[0]))
            self.log.devdebug("Returning %s:", repr(modules[0][2]))
            return modules[0][2]

        self.log.error("import %s: Unsupported request", fullname)
        raise ImportError(fullname)

    def chat(self, text, cr=True):
        try:
            self.log.chat(text, cr)
        except:
            if cr:
                print(text)
            else:
                sys.stdout.write('x ' + text)

    def getSettingsOptions(self):
        result = []
        for key in list(self.settings.keys()):
            option = key
            if isinstance(self.settings[key], dict):
                for subkey in list(self.settings[key].keys()):
                    entry = option + ":" + subkey
                    if not self.settings[key][subkey].isFlag:
                        entry = entry + "="
                    result.append(entry)
            else:
                if not self.settings.getObject(key).isFlag:
                    option = option + "="
                result.append(option)
        return result

    def showVersion(self):
        stderr.write("%s version: %s (lib: v%s)\n" % (
            self.scriptName,
            self.scriptVersion,
            CSMAKE_LIBRARY_VERSION))

    def usage(self, message, useLong=False):
        """Output a generic usage message"""

        if message != None:
            self.chat( "Build could not be completed: " + message)

        if useLong:
            self.chat("Usage (Defaults shown for values):")
        else:
            self.chat("Brief usage (use --help-long for more information):")

        self.chat("")
        self.chat("     %s [Options] [Phases]" % sys.argv[0])

        keys = sorted(self.settings.keys())
        groupKeys = []

        self.chat("")
        self.chat('================ Basic Options ================')
        for key in keys:
            setting = self.settings.getObject(key)

            if key == '*':
                continue
            if isinstance(self.settings[key], dict):
                groupKeys.append(key)
                continue

            description = setting.short
            if useLong:
                description = setting.description
                if not setting.isFlag:
                    if "passw" in key.lower():
                        self.settings[key] = "<REDACTED>"
                    self.chat( "    --%s=%s : " % (
                        key,
                        self.settings[key]))
                else:
                    self.chat( "    --%s : " % key)
                self.chat( "        %s" % description)
            else:
                self.chat("    --%s: %s" % (key, description))

        for key in groupKeys:
            self.chat("")
            self.chat( "  ==== %s options ====" % key)
            for subkey, value in self.settings[key].items():
                description = value.short
                if useLong:
                    description = value.description
                    if "passw" in subkey.lower():
                        self.settings[key][subkey] = "<REDACTED>"
                    if not value.isFlag:
                        self.chat( "    --%s:%s=%s :" % (
                            key,
                            subkey,
                            value.value))
                    else:
                        self.chat( "    --%s:%s :" % (
                        key,
                        subkey))
                    self.chat( "        %s" % description)
                else:
                    self.chat("    --%s:%s - %s" % (
                        key,
                        subkey,
                        description ) )
        self.chat("")
        if useLong:
            self.chat("For more information:")
            self.chat("    man csmake")
            self.chat("    man 5 csmakefile")
            self.chat("    man 5 CsmakeModules")
        else:
            self.chat("For more information see man pages for csmake")

    def _addInternalDumpTypes(self, modules):
        phases.__dict__['~~phases~~'] = phases.phases
        modules.append(('(built-in)', '~~phases~~', phases, phases.phases))

    def dumpTypes(self, singleType=None):
        self._parseModulePaths()
        modules, warnings = self._loadModules()
        outputBlobs = {}
        self._addInternalDumpTypes(modules)
        for path, name, module, actualModule in modules:
            self.log.devdebug("---Gathering %s, %s, %s, %s",
                path,
                name,
                module,
                actualModule )
            if name in list(outputBlobs.keys()):
                warnings.append([
                    "Warning: found duplicate module '%s'" % name,
                    "    Loaded:     %s" % outputBlobs[name]["path"],
                    "    NOT Loaded: %s" % path])
                continue

            result = actualModule
            docString = "<<Module not documented>>"
            try:
                docString = result.__doc__
                if docString is not None and '\n' in docString:
                    doclines = docString.split('\n')
                    docString = "%s\n%s" % (
                        doclines[0],
                        textwrap.dedent('\n'.join(doclines[1:])))
            except:
                pass
            outputBlobs[name] = {
                "path" : path,
                "doc" : docString
            }

        blobKeys = list(outputBlobs.keys())
        blobKeys.sort()
        if singleType is not None:
            singleType = singleType.strip()
            if singleType in blobKeys:
                blobKeys = [singleType]
            else:
                self.chat("Error: Module (Section Type) not defined: %s" % singleType)
                self.log.forceQuiet()
                sys.exit(255)
        for key in blobKeys:
            self.chat("_"*51)
            self.chat("")
            self.chat("Section Type: %s" % key)
            self.chat("Path:         %s" % outputBlobs[key]['path'])
            self.chat("----Info----")
            self.chat(outputBlobs[key]['doc'])
        if len(warnings) != 0:
            self.chat("")
            self.chat("="*51)
            self.chat("NOTE: Some problems were detected with your modules")
            for warning in warnings:
                for line in warning:
                    self.chat(line)

    def dumpActions(self):
        self.chat("")
        self.chat( "================= Defined commands =================")
        #show all the defined commands
        sections = self.buildspec.sections()
        for section in sections:
            if section.startswith("command@"):
                self.chat("    ", False)
                self.chat( section[len("command@"):], False)
                if len(section) == len("command@"):
                    self.chat("(default)", False)
                if self.buildspec.has_option(section, "description"):
                    self.chat( " - %s" % self.buildspec.get(section,'description'), False)
                self.chat("")
        self.phasesDecl.dumpMulticommands()

    def registerBuildExitCallback(self, callback):
        #Takes a callback that takes no parameters
        #Returns a uuid key to unregister the callback
        result = uuid.uuid4()
        self.onBuildExits[result] = callback
        return result

    def unregisterBuildExitCallback(self, key):
        del self.onBuildExits[key]
        return True

    def getFileOptions(self, filenames):
        parser = configparser.RawConfigParser()
        parser.read(filenames)
        try:
            sections = parser.sections()
            for section in sections:
                params = parser.items(section)
                for option, arg in params:
                    if section == 'settings':
                        if option in list(self.settings.keys()):
                            if self.settings.getObject(option).isFlag:
                                self.settings[option] = True
                            else:
                                self.settings[option] = arg.strip()
                        else:
                            stderr.write(
                                "WARNING: option '%s' not found (FILE)" % option)
                    else:
                        if section not in list(self.settings.keys()):
                            self.settings[section] = {}
                        if option not in self.settings[section]:
                            self.settings[section][option] = Setting(
                                "%s:%s" % (
                                    section,
                                    option ),
                                None, "", False )
                        if self.settings[section][option].isFlag:
                            self.settings[section][option].value = True
                        else:
                            self.settings[section][option].value = arg.strip()
        except:
            pass

    def handleSynonyms(self, options):
        addins = {}
        for option, arg in options:
            if '--csmakefile' == option:
                if '--makefile' not in addins:
                    addins['--makefile'] = arg
            else:
                addins[option] = arg
        options = [ (option,addins[option]) for option in list(addins.keys()) ]
        return options

    def getCommandLineOptions(self):
        longOptions = self.getSettingsOptions()
        options = None
        remaining = None
        try:
            options, remaining = getopt.getopt(sys.argv[1:], "", longOptions)
            self.settings['*'] = remaining
        except Exception as e:
            logging.critical(str(e))
            self.usage(str(e))
            sys.exit(1)

        options = self.handleSynonyms(options)

        for option, arg in options:
            key = option[2:]
            subkey = None
            setting = None
            if ':' in option:
                parts = key.split(':')
                key = parts[0]
                subkey = parts[1]
            if subkey == None:
                if self.settings.getObject(key).isFlag:
                    self.settings[key] = True
                else:
                    self.settings[key] = arg.strip()
            else:
                if self.settings[key][subkey].isFlag:
                    self.settings[key][subkey].value = True
                else:
                    self.settings[key][subkey].value = arg.strip()

    def _setupLogging(self):
        if self.settings['log'] is not None:
            try:
                self.logfile = open(self.settings['log'], 'w')
            except Exception as e:
                self.log.critical("Log file '%s' could not be opened: (%s) %s", self.settings['log'], e.__class__.__name__, str(e))
                sys.exit(2)
        else:
            self.logfile = sys.stdout
        OutputTee.subsumeStream(self.logfile)
        self.logfile = OutputTee
        self.log = ProgramResult(self.environment, self.scriptVersion, {'Out' : self.logfile })
        self.log.setTargetModule(self)

    def _getOptions(self):
        self.getFileOptions([environ['HOME']+"/.csmake.conf", "./.csmake.conf"])
        self.getCommandLineOptions()
        configFile = self.settings['configuration']
        if configFile != None:
            if self.getFileOptions(configFile.split(":")):
                # We successfully loaded a user specified config file
                # We need to reload the command lines:
                self.getCommandLineOptions()

        if self.settings['settings'] != None:
            for (key, value) in list(json.loads(self.settings['settings']).items()):
                if isinstance(value, dict):
                    self.settings[key] = value
                    for subkey in list(value.keys()):
                        self.settings[key][subkey] = Setting(
                            "%s:%s" % (
                                key,
                                subkey ),
                            value[subkey], "", False )
                else:
                    self.settings[key] = value

    def _executeOptions(self):
        self._setupLogging()

        cwd = self.settings['working-dir']
        #Yeah, this is weird - but we don't want the path for the cwd
        # in the sys.path we want ''
        if self.cwd in sys.path:
            ind = sys.path.index(self.cwd)
            sys.path.remove(self.cwd)
            sys.path.insert(ind, '')
        if cwd != '.':
            if not os.path.isdir(cwd):
                self.log.critical("--working-dir '%s' not found", cwd)
                sys.exit(5)
            self.cwd = cwd
            os.chdir(cwd)

        self.environment.addTransPhase('WORKING', cwd)

        if self.settings['version']:
            self.showVersion()
            self.log.forceQuiet()
            sys.exit(0)

        if self.settings['help']:
            self.usage(None, self.settings['verbose'])
            self.log.forceQuiet()
            sys.exit(0)

        if self.settings['help-long']:
            self.usage(None, True)
            self.log.forceQuiet()
            sys.exit(0)


    def addOptions(self, group, options):
        """Adds a group of options to the settings"""

        self.settings.appendSettings(group, options)


    def _parseModulePaths(self):
        self.modulePaths = ['+local', '+path']
        pathspec = self.settings["modules-path"]
        if pathspec is not None:
            parts = pathspec.split(':')
            if len(parts[0]) == 0:
                #Take care of leading colon
                self.modulePaths.extend(parts[1:])
            else:
                self.modulePaths = parts

            if self.modulePaths != ['+local', '+path']:
                self.log.info("Module paths is modified: %s", self.modulePaths)

    def _afterLoadSettings(self):
        """This is called after the settings are loaded and ready for consumption"""
        pass

    def _lookupAspects(self, step):
        stepId = step
        result = []
        if '@' in step:
            stepId = step.split('@')[1]
        sections = None
        self.buildspecLock.acquire()
        try:
            sections = self.buildspec.sections()
        finally:
            self.buildspecLock.release()
        for section in sections:
            if section[0] != '&':
                continue
            parts = section.split('@')
            if len(parts) == 2:
                cutsParts = parts[1].split(' ')
                if cutsParts[0] == stepId:
                    result.append(section)
        return result

    def lookupSection(self, step):
        #TODO: Detect ambiguity
        if '@' in step:
            if self.buildspec.has_section(step):
                return step
            else:
                return None
        sections = None
        self.buildspecLock.acquire()
        try:
            sections = self.buildspec.sections()
        finally:
            self.buildspecLock.release()
        for section in sections:
            if section[0] == '&':
                continue
            parts = section.split('@')
            if len(parts) == 2 and parts[1] == step:
                return section
        return None

    def launchAspects(
        self,
        aspects,
        joinpoint,
        phase,
        execinstance,
        stepdict,
        extraOptions={} ):

        if len(aspects) == 0:
            return False

        execinstance.log.devdebug("Invoking %s on aspects", joinpoint)
        joinpointsImplemented = False

        for aspect, aspectdict in aspects:
            aspectdict.update(extraOptions)
            execinstance.log.devdebug(
                "Dispatching '%s' Aspect: %s",
                joinpoint,
                repr(aspect))
            method = None
            actualPhase = aspect._lookupPhaseShift(phase, aspectdict)
            try:
                method = aspect._joinPointLookup(
                    joinpoint,
                    actualPhase,
                    aspectdict )
            except:
                aspect.log.exception("Attempt to lookup joinpoint failed")
            if method is not None:
                if not joinpointsImplemented:
                    execinstance.log.chatStartJoinPoint(joinpoint)
                joinpointsImplemented = True
                aspect.log.executing()
                aspect.log.chatStart()
                aspect._executeFileMapping(aspectdict)
                aspect.log.setReturnValue(
                    method(phase, aspectdict, execinstance, stepdict),
                    joinpoint)
                aspect._absorbNewMappedFiles()
                aspect.log.chatStatus()
                aspect.log.chatEnd()
            else:
                aspect.log.skipped()
                aspect._dontValidateFiles()
                aspect._absorbNewMappedFiles()

        if not joinpointsImplemented:
            self.log.debug("No joinpoints were defined: %s", joinpoint)
        else:
            execinstance.log.chatEndJoinPoint()
        aspect.log.finished()
        execinstance.log.devdebug("Completed %s on aspects", joinpoint)
        return joinpointsImplemented

    #extraOptions are overridden by buildspec
    #overrideOptions override the buildspec
    def launchStep(self, step, phase, extraOptions={}, overrideOptions={}):
        section = "<Unspecified>"
        resultObject = None
        execinstance = None
        aspects = []
        launchPassed = False
        pushedModule = False
        stepdict = {}
        stepdict.update(extraOptions)
        flowcontrol = AspectFlowControl(self.log)
        try:
            self.log.devdebug("Looking up section for: %s", step)
            section = self.lookupSection(step)
            if section is None:
                raise KeyError("The requested build section '%s' was not found in the build specification" % step)
            sectionParts = section.split('@')
            sectionId = sectionParts[1]
            sectionType = sectionParts[0]
            self.log.devdebug("Looking up aspects for: %s", sectionId)
            aspectSections = self._lookupAspects(sectionId)
            self.log.devdebug("--------------------------------------------")
            self.log.devdebug("Launching step: %s", section)
            if len(aspectSections) > 0:
                self.log.devdebug("~~~ With ASPECTS: %s", str(aspectSections))

            self.log.devdebug("--- Environment is %s", self.environment)
            resultObject = Result(self.environment, {
                'Out':self.log.out(),
                'Err':self.log.err(),
                'Type':sectionType,
                'Id':sectionId })
            self.buildspecLock.acquire()
            try:
                stanzas = self.buildspec.options(section)
                for stanza in stanzas:
                    stepdict[stanza] = self.buildspec.get(section, stanza)
                stepdict.update(overrideOptions)
            finally:
                self.buildspecLock.release()

            self.log.devdebug("stepdict: %s", str(stepdict))
            self.log.devdebug("extraOptions: %s", str(extraOptions))
            self.log.devdebug("overrideOptions: %s", str(overrideOptions))
            self.log.devdebug("Looking up module: %s", sectionType)

            execinstance = self.getSectionTypeInstance(sectionType, resultObject)
            #TODO: Give section module instance its id - short and full
            self.log.devdebug("Lookup result is: %s", execinstance)
            if execinstance is None:
                self.log.error("Couldn't find a module for '%s'", sectionType)
                self.log.devdebug("Lookup failed for '%s'", sectionType)
                return None
            pushedModule = True
            self.log.devdebug("Pushing child result")
            self.log.devdebug("Parent is: %s", str(self.launchStack[-1]))
            self.launchStack[-1].log.appendChild(resultObject)
            self.log.devdebug("Pushing new exec")
            self.launchStack.append(execinstance)
            self.log.devdebug("Setting up results for module")
            resultObject.setTargetModule(execinstance)
            resultObject.executing()
            resultObject.chatStart(len(self.launchStack)-1)
            execinstance._executeFileMapping(
                stepdict )
            self.log.devdebug("Got an instance of %s: %s" % (sectionType, execinstance))

            execinstance.initFlowControl(flowcontrol)
            execinstance._initCallInfo(
                self.outBuildspec._sections[section],
                section )
            execinstance._doOptionSubstitutions(stepdict)

            aspectResultInfo = {
                'Out':self.log.out(),
                'Err':self.log.err(),
                'Type':'',
                'Id':sectionId,
                'cuts':section }
            aspects = []
            for aspectSection in aspectSections:
                aspectDict = {}
                aspectParts = aspectSection.split('@')
                aspectClass = aspectParts[0][1:]
                aspectCutsParts = aspectParts[1].split(' ')
                aspectCuts = aspectCutsParts[0]
                if len(aspectCutsParts) > 1:
                    aspectId = aspectCutsParts[1]
                else:
                    aspectId = ''

                aspectResultInfo['Type'] = aspectClass
                aspectResultInfo['AspectId'] = aspectId
                self.log.devdebug("Looking up aspect: %s", aspectSection)

                self.buildspecLock.acquire()
                try:
                    aspectStanzas = self.buildspec.options(aspectSection)
                    for stanza in aspectStanzas:
                        aspectDict[stanza] = self.buildspec.get(aspectSection, stanza)
                finally:
                    self.buildspecLock.release()

                aspectResult = AspectResult(self.environment, aspectResultInfo)
                resultObject.appendChild(aspectResult)
                aspectInstance = self.getSectionTypeInstance(aspectClass, aspectResult)

                if aspectInstance is None:
                    self.log.error(
                        "Aspect module '%s' not found",
                        aspectClass)
                    #TODO: Stop processing unless keepgoing
                    continue

                aspectResult.setTargetModule(aspectInstance)
                aspectInstance.initFlowControl(flowcontrol)
                aspectInstance._initCallInfo(
                    self.outBuildspec._sections[section],
                    section )
                aspectInstance._doOptionSubstitutions(aspectDict)

                self.log.devdebug("Found aspect: %s", aspectSection)
                aspects.append((aspectInstance,aspectDict))

            execinstance._setAspects(aspects)
            self.launchAspects(
                aspects,
                'start',
                phase,
                execinstance,
                stepdict,
                {} )
            if flowcontrol.advice('doNotStart'):
                resultObject.notice("Aspects advised not to starting section '%s'", section)
                resultObject.skipped()
                execinstance._dontValidateFiles()
                execinstance._absorbNewMappedFiles()
                return execinstance
            method = None
            actualPhase = execinstance._lookupPhaseShift(phase, stepdict)
            self.log.devdebug("Actual phase to use for lookup: %s", actualPhase)
            try:
                method = getattr(execinstance, actualPhase)
            except:
                try:
                    method = getattr(execinstance, "default")
                except:
                    self.log.notice("Section '%s' doesn't have a '%s' or 'default' method.  (This is probably okay) ", section, self.getPhase())
            if method is not None:
                tryagain = True
                while tryagain:
                    tryagain = False
                    try:
                        result = method(stepdict)
                        execinstance.log.setReturnValue(
                            result,
                            phase )
                        if execinstance.log.didPass():
                            launchPassed = True
                            self.launchAspects(
                                aspects,
                                'passed',
                                phase,
                                execinstance,
                                stepdict)
                            execinstance._absorbNewMappedFiles()
                        elif execinstance.log.didFail():
                            self.launchAspects(
                                aspects,
                                'failed',
                                phase,
                                execinstance,
                                stepdict )
                        tryagain = flowcontrol.advice("tryAgain")
                        if tryagain:
                            self.log.notice("Aspects advise to attempt step again")
                    except Exception as e:
                        resultObject.exception(
                            "Attempt to execute step '%s' in phase '%s' failed",
                            step,
                            phase )
                        self.launchAspects(
                            aspects,
                            'exception',
                            phase,
                            execinstance,
                            stepdict,
                            { '__ex__' : e } )
                        tryagain = flowcontrol.advice("tryAgain")
                        if not tryagain:
                            self.log.devdebug("Not trying step again on exception")
                            raise e

            else:
                self.log.info("Could not find an appropriate method to call")
                self.log.info("---(%s) Looking for method: %s", step, phase)
                execinstance.log.skipped()
                execinstance._dontValidateFiles()
                execinstance._absorbNewMappedFiles()
            return execinstance
        except Exception as e:
            self.log.exception(
                "Attempt to execute step %s failed",
                str(step) )
            if resultObject is not None:
                resultObject.failed()
            return execinstance
        finally:
            try:
                self.launchAspects(
                    aspects,
                    'end',
                    phase,
                    execinstance,
                    stepdict)
            finally:
                lastStackResult = None
                if len(self.stackDumps):
                    lastStackResult = self.stackDumps[-1][1]
                if resultObject is not None and resultObject.params['status'] == "Failed" and not resultObject.isChild(lastStackResult):
                    parent, stack = self.launchStack._getCurrentStack(threading.currentThread())
                    while parent is not None:
                        parent, pstack = self.launchStack._getCurrentStack(parent)
                        stack = pstack + stack
                    self.stackDumps.append((list(stack), resultObject, phase))
                if pushedModule:
                    if self.launchStack[-1] is not execinstance:
                        self.log.error("DEVERROR: Launch stack not pointing to current launch")
                        self.log.devdebug("stack top: %s    Instance: %s" %(
                            self.launchStack[-1],
                            execinstance ) )
                    elif self.launchStack[-1] is self:
                        self.log.error("DEVERROR: Launch stack pointing to engine: Cannot pop")
                    else:
                        self.launchStack.pop()

                if resultObject is not None:
                    resultObject.chatStatus()
                    resultObject.chatEnd()
                self.log.devdebug(" Step Completed: %s" % section)
                self.log.devdebug("-----------------------------------------")
                if resultObject is not None:
                    resultObject.finished()

    def includeBuildspec(self, spec):
        if not os.path.isfile(spec):
            self.log.error("File missing: build specification '%s' could not be found.", spec)
            return False
        else:
            self.buildspecLock.acquire()
            try:
                self.buildspec.read([spec])
                self.outBuildspec.read([spec])
            finally:
                self.buildspecLock.release()
            return True

    def _loadBuildspec(self):
        makefiles = [ x.strip() for x in self.settings['makefile'].split(',') ]
        wasErrors = False
        for makefile in makefiles:
            wasErrors = self.includeBuildspec(makefile) and wasErrors
        return not wasErrors


    def main(self):
        self.fakegit = None
        self.resultsDir = None
        returncode = -1
        try:
            self.realmain()
            returncode = 0
        except SystemExit as sysexit:
            if str(sysexit) != '0':
                self.log.error("csmake exited with code %s", str(sysexit))
                returncode = int(str(sysexit))
            else:
                returncode = 0
        except BaseException as e:
            self.log.exception("csmake exited on exception")
            returncode = 1
        finally:
            oldhandler = signal.signal(signal.SIGINT, signal.SIG_IGN)
            self.log.info("csmake exit sequence - ctrl-c disabled")
            if self.log.__class__ == ProgramResult \
               and self.fakegit is not None \
               and self.resultsDir is not None:
                if returncode != 0:
                    self.log.failed()
                self._finishUp()
                self._cleanUp(self.fakegit, self.resultsDir)
            elif returncode != 0:
                self.log.error("XXX Execution of csmake failed")
                returncode = 1
            self.log.finished()
            OutputTee.endAll()
            if self.tty is not None:
                try:
                    os.tcsetpgrp(self.tty, self.previous_fg_pgrp)
                except OSError:
                    pass
                try:
                    os.close(self.tty)
                except:
                    pass
            os.system('stty sane')
            signal.signal(signal.SIGTTOU, self.ttou_handler)

        os._exit(returncode)

    def realmain(self):
        self._getCurrentProcesses()
        self._getOptions()
        self._executeOptions()

        result = None

        self._afterLoadSettings()

        target = self.settings['results-dir']
        self.resultsDir = target
        if not os.path.isdir(target):
            if os.path.exists(target):
                self.log.error("--results-dir %s is not a directory", target)
                sys.exit(1)
            self.log.info("Creating --results-dir %s", target)
            try:
                os.mkdir(target)
            except:
                self.log.exception("Got exception on file creation for %s, attempting to proceed", target)

        #Make git believe this is something that isn't part of our repo
        #TODO: Add a truncate +/- to allow multiple simultaneous runs
        fakegit = target + '/.git'
        self.fakegit = fakegit
        subprocess.call(
            [ 'truncate', '--size', '+1', self.fakegit ],
            stdout=self.log.out(),
            stderr=self.log.err() )


        self.environment.addTransPhase('RESULTS', target)

        defaultMetadata = DefaultMetadataModule(
                self.log,
                self.environment )
        self.environment.metadata.start(
            defaultMetadata.original['name'],
            defaultMetadata )

        if not self._loadBuildspec():
            self.chat( "#"*50)
            self.chat("Build Failure: One or more build specifications could not be found")
            sys.exit(5)

        # Load phases section
        if self.buildspec.has_section('~~phases~~'):
            self.phasesDecl = phases.phases(
                                  self.buildspec._sections['~~phases~~'],
                                  self.log)
        else:
            self.phasesDecl = phases.phases(None, self.log)

        #Inclusions could be added here, though it might be better to just

        #Figure out what to do first....
        #Parse out the path
        self._parseModulePaths()

        if self.settings['help-all']:
            self.usage(None, True)
            self.chat( "")
            self.buildspec = configparser.RawConfigParser()
            self._loadBuildspec()
            self.dumpTypes()
            self.dumpActions()
            self.phasesDecl.dumpPhases()
            self.log.forceQuiet()
            sys.exit(0)

        if self.settings['list-types'] or self.settings['list-commands'] \
            or self.settings['list-type'] is not None or self.settings['list-phases']:
            if self.settings['list-phases']:
                self.phasesDecl.dumpPhases()
            if self.settings['list-types']:
                self.dumpTypes()
            if self.settings['list-commands']:
                self.dumpActions()
            if self.settings['list-type'] is not None:
                self.dumpTypes(self.settings['list-type'])
            self.log.forceQuiet()
            sys.exit(0)

        #default trys are: command@, command@default,
        #   or first command@ section we find (not necessarily in spec order)
        self.log.chatStart()
        rawcommand = self.settings['command']
        command = None
        if rawcommand is not None:
            #Support multi-command
            if ',' in rawcommand or '&' in rawcommand:
                newcommand = 'command@~~multicommand~~'
                #Add the command to the spec
                if self.buildspec.has_section(newcommand):
                    logging.critical("The specification has defined a section [command@~~multicommand~~], but this is used by csmake.  Resolution: rename the section with an id that does not start and end with two tildes '~'")
                    sys.exit(99)
                self.buildspec.add_section(newcommand)
                self.buildspec.set(newcommand, '0', rawcommand.strip())
                #TODO: OUTSPEC: need restructuring...
                self.outBuildspec.add_section(newcommand)
                self.outBuildspec.set(newcommand, '0', rawcommand.strip())
                command = newcommand
            else:
                command = 'command@%s' % rawcommand
                try:
                    steps = self.buildspec.options(command)
                except Exception as e:
                    try:
                        logging.critical("The requested command '%s' failed to launch (%s) %s" % (
                            rawcommand,
                            e.__class__.__name__,
                            e ) )
                    except:
                        logging.critical("The requested command '%s' failed to launch" % rawcommand)
                    finally:
                        self.chat( "#"*50)
                        self.chat( "csmake: Failed to launch: Did not find a command section for %s.  Looking for a section called '[command@%s]'" % (rawcommand, rawcommand))
                        sys.exit(253)
        else:
            try:
                command = "command@"
                steps = self.buildspec.options(command)
            except configparser.NoSectionError:
                try:
                    command = "command@default"
                    steps = self.buildspec.options(command)
                except configparser.NoSectionError:
                    sections = self.buildspec.sections()
                    for section in sections:
                        if 'command@' in section:
                            command = section
                            break
        if command is None:
            self.chat( "#"*50)
            logging.critical("Did not find a default command section. Looking for a section called '[command@default]' or [command@]")
            self.chat( "csmake: Failed to launch: Did not find a default command section.")
            sys.exit(254)

        self.phases = []
        try:
            if len(self.settings['*']) > 0:
                self.phases = [ x.strip() for x in self.settings['*'] ]
        except:
            pass
        settingsMethod = self.settings['phase']
        if settingsMethod is not None:
            methods = settingsMethod.split(',')
            overridephases = [ x.strip() for x in methods ]
            if len(overridephases) != 0:
                self.phases = overridephases
        if len(self.phases) == 0:
            self.phases = self.phasesDecl.getDefaultSequence()
        if len(self.phases) == 0:
            self.phases = [ 'default' ]

        passed = True
        for phase in self.phases:
            self.currentPhase = phase
            phaseValid, phaseDoc = self.phasesDecl.validatePhase(phase)
            self.log.chatStartPhase(phase, phaseDoc)

            result = self.launchStep(command, phase)
            self.log.chatEndPhase(phase, phaseDoc)
            if result is None or result._didFail() and not self.settings['keep-going']:
                self.log.failed()
                passed = False
                break
            self._endOfPhaseFlush()

        if passed:
            self.log.passed()
        else:
            self.log.failed()
        self.log.chatEndLastPhaseBanner()
        sequenceValid, sequenceDoc = \
            self.phasesDecl.validateSequence(
                self.phases )
        self.log.chatEndSequence(self.phases, sequenceDoc)

        if not passed:
            sys.exit(1)

    def _getCurrentProcesses(self):
        psproc = subprocess.Popen(
            ['ps', '-e', '-o', 'pid,pgid'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE )
        pidlist,err = psproc.communicate()
        pidlist = pidlist.decode('utf8')
        psprocpid = str(psproc.pid)
        processedlist = [ x.split() for x in pidlist.split('\n') if len(x.split()) >= 2 ]
        processedlist = [ x for x in processedlist if x[0] != psprocpid ]
        self._previouslyRunningProcesses = processedlist

    def _pgidTerminator(self):
        psproc = subprocess.Popen(
            ['ps', '-e', '-o', 'pid,pgid,cmd'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE )
        pidlist,err = psproc.communicate()
        pidlist = pidlist.decode('utf8')
        psprocpid = str(psproc.pid)
        processedlist = [ x.split() for x in pidlist.split('\n') if len(x.split()) >= 3 ]
        processedlist = [ x for x in processedlist if x[0] != psprocpid and x[1] != psprocpid ]
        #self._pidTreeTerminatorHelper([parent], processedlist)
        mypid = str(os.getpid())
        mypgrp = str(os.getpgrp())
        self.log.debug("csmake pgroup: %s", mypgrp)
        self.log.devdebug("processedlist: %s", str(processedlist))
        for item in processedlist:
            proc = item[0]
            grp = item[1]
            cmdname = ' '.join(item[2:])
            if grp == mypgrp and proc != mypid:
                if item[0:2] in self._previouslyRunningProcesses:
                    self.log.devdebug("Process %s running before csmake started", str(item))
                    continue
                self.log.warning("Process %s (%s) is being killed - check build to ensure all processes are contained", proc, str(cmdname))
                try:
                    subprocess.check_call(
                        ['kill', '-9', proc],
                        stdout=self.log.out(),
                        stderr=self.log.err() )
                except:
                    subprocess.call(
                        ['sudo', 'kill', '-9', proc],
                        stdout=self.log.out(),
                        stderr=self.log.err() )

    def _finishUp(self):
        #Kill off all child processes
        self._pgidTerminator()
        buildExitsExist = len(list(self.onBuildExits.keys())) != 0
        if buildExitsExist:
            self.log.chat("""
  .::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::.
  ::         /\ /\ /\  END of csmake build output  /\ /\ /\             ::
  ::         || || ||  ``````````````````````````  || || ||             ::
  ::                                                                    ::
  :: NOTE: Past this point begins cleanup output                        ::
  ::       Any error from the csmake build will be above                ::
  `::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::'
""")
        for uid in list(self.onBuildExits.keys()):
            try:
                callback = self.onBuildExits[uid]
                callback()
            except:
                self.log.exception("Build Exit Callback '%s' failed on exception", str(callback))

        if buildExitsExist:
            self.log.chat("""
  .::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::.
  ::  ATTENTION:                                                        ::
  ::      Clean up code was executed after the build failed             ::
  ::      Look above for "END of csmake build output"                   ::
  ::                      ``````````````````````````                    ::
  ::      A box above like this will mark the end of the failure output ::
  `::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::'
""")
        try:
            if self.outBuildspec is not None \
                and self.settings['replay'] is not None:
                with open(self.settings['replay'], 'w') as replayer:
                    self.outBuildspec.write(replayer)
        except Exception as e:
            self.log.error(
                "Replay file could not be written: (%s) %s",
                e.__class__.__name__,
                str(e))

        self.log.dumpStacks(self.stackDumps)
        self.log.chatStatus()
        self.log.chatEnd()

    def _cleanUp(self, fakegit, target):
        try:
            subprocess.call([
                'truncate', '--size', '-1', fakegit ],
                stdout=self.log.out(),
                stderr=self.log.err() )
            if os.path.getsize(fakegit) == 0:
                os.remove(fakegit)
        except:
            self.log.exception("Could not remove .git barrier: %s", fakegit)

        try:
            os.rmdir(target)
        except:
            self.log.debug("(normal behavior) Results directory could not be removed")

    def getPhase(self):
        return self.currentPhase

    def _reportLoadModuleError(self, moduleName, modulePath, e, trbk):
        warning = [
            "Warning: Module '%s' failed to load" % moduleName,
            "    Module: %s" % moduleName,
            "    Path:   %s" % modulePath]
        warning.append("    Except: %s" % repr(e))
        warning.append("    Trace:   %s" % trbk)
        return warning

    def _constructModulePaths(self):
        if self.modulePathConstruct is not None:
            return self.modulePathConstruct

        allPaths = []
        #Gather up the proper order of the paths.
        #Avoiding any paths that don't have CsmakeModules subdirectories
        for path in self.modulePaths:
            if path == '+local':
                if os.path.isdir('CsmakeModules'):
                    allPaths.append((path,'.'))
            elif path == '+path':
                for syspath in sys.path:
                    #Avoid local path here
                    if len(syspath) == 0 or syspath == '.':
                        continue
                    #Append the actual path
                    if os.path.isdir(os.path.join(
                        syspath,
                        'CsmakeModules') ):
                        allPaths.append((path, syspath))

                    #Now look at all the subdirectories
                    try:
                        syspathdirs = os.listdir(syspath)
                        for syssubpath in syspathdirs:
                            if os.path.isdir(os.path.join(
                                syspath,
                                syssubpath,
                                'CsmakeModules' )):
                                allPaths.append((path, os.path.join(
                                    syspath,
                                    syssubpath )))
                    except:
                        pass
            else:
                if os.path.isdir(os.path.join(
                    path,
                    'CsmakeModules') ):
                    allPaths.append(('cmdline', path))
        self.modulePathConstruct = allPaths
        return allPaths

    def _loadModules(self, target = ''):
        """Yes, this is a custom import routine to avoid the manner in
           which python deals with packages broken across paths.
           In csmake we want to support the notion of being able to
           write custom steps that are in the local directory,
           and also load standard steps delivered with csmake,
           and also be required to put the steps in a directory
           making the steps into a package according to the way
           python works.  This package mechanism has a sordid past
           (and future) and would require users of the tool to
           write fragile package path patching code that could break
           the normal functioning of csmake.

           returns [(path, name, module)], [warnings]"""

        allPaths = self._constructModulePaths()

        modules = []
        warnings = []

        if len(target) != 0:
            self.log.devdebug("Attempting to look up '%s'", target)
        else:
            self.log.devdebug("Attempting to find all csmake modules")

        for pathtype, path in allPaths:
            self.log.devdebug(
                "Searching module from path '%s:%s'",
                pathtype,
                path )

            packagePath = "%s/CsmakeModules" % path

            #If there's a specific target, optimize by seeking the module
            #in the current directory
            found = False
            if target is not None and len(target) != 0:
                packageFiles = ["%s.py"%target]
                stopOnFoundOrFail = True
            else:
                stopOnFoundOrFail = False
                try:
                    packageFiles = os.listdir(packagePath)
                except Exception as e:
                    self.log.devdebug("No modules in '%s'", packagePath)
                    continue

            for packageFile in packageFiles:
                modulePath = "%s/%s" % (
                    packagePath,
                    packageFile )
                name, ext = os.path.splitext(packageFile)
                if not os.path.isfile(modulePath) or ext != '.py':
                    self.log.devdebug(
                        "Skipping '%s': Not a python module",
                        modulePath )
                    continue
                try:
                    self.log.devdebug(
                        "Attempting load of '%s'", modulePath)
                    module = None

                    imp.acquire_lock()
                    try:
                        if 'CsmakeModules' in sys.modules:
                            if name in sys.modules['CsmakeModules'].__dict__:
                                module = sys.modules['CsmakeModules'].__dict__[name]
                        else:
                            sys.modules['CsmakeModules'] = CsmakeModulesModule(self)

                        if module is None:
                            module = imp.load_source(
                                name,
                                modulePath )
                            sys.modules['CsmakeModules'].__dict__[name] = module
                            sys.modules['CsmakeModules.' + name] = module
                    finally:
                        imp.release_lock()

                    actualModule = None
                    try:
                        actualModule = module.__dict__[name]
                        if isinstance(actualModule, types.ModuleType):
                            actualModule = actualModule.__dict__[name]
                    except:
                        warnings.append([
                            "There is a naming problem with module '%s'" % \
                            name ])
                        self.log.exception(
                            "There was a naming problem with module '%s'",
                            name)

                    modules.append((
                        packagePath,
                        name,
                        module,
                        actualModule))
                    found = True
                except IOError as ioerr:
                    self.log.devdebug("Didn't find module here '%s'" %
                        modulePath )
                except Exception as e:
                    found = True
                    trbk = traceback.format_exc();
                    warning = self._reportLoadModuleError(
                        name, packagePath, e, trbk )
                    warnings.append(warning)
                if found and stopOnFoundOrFail:
                    self.log.devdebug("Module '%s' was found", target)
                    return (modules, warnings)
        return (modules, warnings)

    def getSectionTypeInstance(self, target, logger=None):
        if logger is None:
            logger = Result(self.env, self.log.info)
        modules, warnings = self._loadModules(target)
        if len(warnings) != 0:
            self.log.info("There were problems loading '%s'" % target)
            for warning in warnings:
                for line in warning:
                    self.log.info(line)

        if len(modules) == 0:
            self.log.error("The step '%s' could not be executed" % target)
            return None

        module = modules[0][2]
        usedPath = modules[0][0]

        try:
            result = module.__dict__[target]
            if isinstance(result, types.ModuleType):
                result = result.__dict__[target]
            instance = result(self.environment, logger)
            return instance
        except Exception as e:
            try:
                self.log.exception(
                    "Module '%s' is improperly constructed for csmake (%s) %s" % (
                        target,
                        e.__class__.__name__,
                        e ) )
            except:
               self.log.exception(
                    "Module '%s' is improperly constructed for csmake",
                    target )
            finally:
               self.log.error(
                    "     Attempting to use %s/%s.py" % (
                        usedPath,
                        target ) )
        self.log.warning(
            """
csmake modules handling section types are required to have
a class with the name of the type of the section,
e.g., [%s@mysectionid] expects to find a module named %s.py
in the path:
    %s
under a subdirectory called CsmakeModules with a "class %s(CsmakeModule):"
definition.

A CsmakeModules/%s.py module was found in %s, but doesn't
appear to have the proper class definition.
Sorry it didn't work out""" % (
                    target,
                    target,
                    self.modulePaths,
                    target,
                    target,
                    usedPath ) )
        return None
