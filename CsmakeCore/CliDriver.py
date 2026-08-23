# <copyright>
# (c) Copyright 2019,2021,2024 Autumn Patterson
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
try:
    import imp
except ImportError:
    # imp was removed in Python 3.12; provide a shim for the three entry points
    # used below: acquire_lock, release_lock, and load_source.
    import threading as _threading
    import importlib.util as _importlib_util

    class _ImpShim(object):
        def __init__(self):
            self._lock = _threading.RLock()
        def acquire_lock(self):
            self._lock.acquire()
        def release_lock(self):
            self._lock.release()
        def load_source(self, name, path):
            spec = _importlib_util.spec_from_file_location(name, path)
            module = _importlib_util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module

    imp = _ImpShim()
import pkgutil
import types
import time
from os import environ, getcwd
from sys import stdout, stderr
import importlib.util as _importlib_util
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
from . import ModuleDoc
from .OutputTee import OutputTee
from . import phases

def _atexit_shutdown():
    OutputTee.endAll()
    try:
        sys.stdout.flush()
    except Exception:
        pass

atexit.register(_atexit_shutdown)

CSMAKE_LIBRARY_VERSION = "3.0.0"

#TODO: Nested settings and settings processing needs to be migrated to
#      Settings.py and fixed to be more generic

#TODO: We need to refactor this into cli stuff and csmake stuff

class CliDriver(object):

    # Class-level extension registry.  Extensions self-register at import
    # time by calling CliDriver.register_extension(MyExtensionClass).
    _extensions = []

    @classmethod
    def register_extension(cls, ext_class):
        """Register a csmake extension class.
        Called by extension modules at module load time (not instance time).
        Each extension class may provide:
            BUILDSPEC_FLAG  - str CLI flag name (without '--') that, when
                              present, overrides the normal --makefile loading.
            get_settings()  - classmethod returning a settings dict in the
                              same form as the CliDriver settings seed.
            load_buildspec(driver) - classmethod that reads the extension's
                              buildspec source and returns a sections dict
                              suitable for RawConfigParser.read_dict(), or
                              None if the extension does not apply.
        """
        if ext_class not in cls._extensions:
            cls._extensions.append(ext_class)

    def __init__(self, settings={}, name='<name>', version='<version>'):
        self.currentPhase = 'default'
        self.settings = Settings(settings)
        self.scriptName = name
        self.scriptVersion = version
        self.modulePathConstruct = None
        self._remoteModulesAttempted = set()
        # Package pins ([~~packages~~], **uses) -- see docs/MODULE_ECOSYSTEM_DESIGN.md.
        # self._packagePins: ambient {package: version} from [~~packages~~].
        # self._pinContext: stack of (package, version) -- the top entry is
        #   the pin scope currently being loaded, consulted by load_module()
        #   so a pinned package's own internal 'from CsmakeModules.X import X'
        #   resolves within that SAME pinned version rather than the bare
        #   default. Maintained only under the imp import lock, so a single
        #   list is safe: csmake's custom loader serializes all module loads
        #   through that lock, including any nested loads a module's own
        #   top-level code triggers while it is being loaded.
        self._packagePins = {}
        self._pinContext = []
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
        try:
            self.cwd = environ['PWD']
        except KeyError:
            self.cwd = getcwd()
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


    def find_spec(self, fullname, path, target=None):
        """Python 3.4+ meta path finder API (replaces find_module)."""
        nameparts = fullname.split('.')
        if nameparts[0] != 'CsmakeModules':
            return None
        if len(nameparts) > 2:
            return None
        return _importlib_util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return None  # use default module creation

    def exec_module(self, module):
        """Populate a module created via find_spec/create_module."""
        fullname = module.__name__
        loaded = self.load_module(fullname)
        # load_module returns the canonical module; redirect sys.modules
        # so that 'from CsmakeModules.X import Y' resolves correctly.
        if loaded is not None:
            module.__dict__.update(loaded.__dict__)
            sys.modules[fullname] = loaded

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

            # While loading a pinned package's own module (a **uses'd
            # section, or a sibling import triggered from one), skip the
            # bare-slot cache check below: the bare slot may hold a
            # DIFFERENT version, and returning it here would defeat the
            # whole point of the pin.  _loadModules(pin=...) does its own
            # (separately-keyed) cache check for the pinned version.
            currentPin = self._pinContext[-1] if self._pinContext else None

            if currentPin is None:
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
            modules, warnings = self._loadModules(nameparts[1], pin=currentPin)
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
        # Structured output (json/yaml) must be the only thing on stdout, so
        # silence module-load chatter/warnings before they can interleave with
        # the emitted document.  Guarded so drivers that do not define the
        # setting keep the historical text behavior.
        docFormat = 'text'
        try:
            docFormat = self.settings['list-type-format'] or 'text'
        except Exception:
            docFormat = 'text'
        if docFormat != 'text':
            self.log.forceQuiet()
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
            originalDoc = None
            docString = "<<Module not documented>>"
            try:
                originalDoc = result.__doc__
                docString = originalDoc
                if docString is not None and '\n' in docString:
                    doclines = docString.split('\n')
                    docString = "%s\n%s" % (
                        doclines[0],
                        textwrap.dedent('\n'.join(doclines[1:])))
            except:
                pass
            outputBlobs[name] = {
                "path" : path,
                "doc" : docString,
                "rawdoc" : originalDoc
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

        # Structured output (--list-type-format=json|yaml): emit the module
        # documentation straight from the modules, byte-clean on stdout, and
        # skip the human-readable text rendering entirely.
        if docFormat != 'text':
            structured = [
                ModuleDoc.parse_module_doc(
                    key,
                    outputBlobs[key].get('rawdoc'),
                    path=outputBlobs[key]['path'])
                for key in blobKeys ]
            # Completeness: recover docs for any documented module that did not
            # import (e.g. a sibling library on --modules-path whose runtime
            # dependencies aren't installed in this checkout).  The docstring is
            # all the doc engine needs, so read it from source via ast.  Only
            # for the full catalog (singleType is None).
            if singleType is None:
                seen = set(outputBlobs.keys())
                for pathtype, modPath in getattr(
                        self, 'modulePathConstruct', []):
                    packageDir = os.path.join(modPath, 'CsmakeModules')
                    for parsed in ModuleDoc.discover_source_docs(
                            packageDir, repo=modPath, skip=seen):
                        structured.append(parsed)
                        seen.add(parsed['name'])
            try:
                rendered = ModuleDoc.render(structured, docFormat)
            except ValueError:
                self.chat(
                    "Error: Unknown --list-type-format: %s "
                    "(expected text, json, or yaml)" % docFormat)
                self.log.forceQuiet()
                sys.exit(255)
            sys.stdout.write(rendered + "\n")
            sys.stdout.flush()
            return

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
        try:
            capture_fd = self.settings['capture-fd']
        except KeyError:
            capture_fd = None
        if capture_fd is not None:
            try:
                capture_stream = os.fdopen(int(capture_fd), 'w', closefd=True)
                OutputTee.addCaptureStream(capture_stream)
            except Exception as e:
                self.log.critical("--capture-fd '%s' could not be opened: %s", capture_fd, str(e))
                sys.exit(2)
        self.logfile = OutputTee
        self.log = ProgramResult(self.environment, self.scriptVersion, self.scriptName, {'Out' : self.logfile })
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

    def _parsePin(self, usesSpec):
        """Parse a **uses value ('pkgname@version') into (pkgname, version).

        Returns None (and logs a warning) for anything malformed -- a
        section with a broken pin falls back to normal unpinned
        resolution rather than failing the whole build.
        """
        if not usesSpec or '@' not in usesSpec:
            self.log.warning(
                "**uses '%s' is not in 'package@version' form; ignoring",
                usesSpec)
            return None
        pkgname, _, version = usesSpec.strip().partition('@')
        pkgname = pkgname.strip()
        version = version.strip()
        if not pkgname or not version:
            self.log.warning(
                "**uses '%s' is not in 'package@version' form; ignoring",
                usesSpec)
            return None
        return (pkgname, version)

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

            pin = None
            usesSpec = stepdict.get('**uses')
            if usesSpec:
                pin = self._parsePin(usesSpec)

            execinstance = self.getSectionTypeInstance(
                sectionType, resultObject, pin=pin)
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
        self.buildspecLock.acquire()
        try:
            self.buildspec.read([spec])
            self.outBuildspec.read([spec])
        finally:
            self.buildspecLock.release()
        return True

    def injectBuildspec(self, sections):
        """Inject a pre-parsed sections dict into the active buildspec.
        Used by extensions that supply their own buildspec source."""
        self.buildspecLock.acquire()
        try:
            self.buildspec.read_dict(sections)
            self.outBuildspec.read_dict(sections)
        finally:
            self.buildspecLock.release()

    def _loadBuildspec(self):
        source, ext = self._resolveActiveBuildspecSource()

        if source == 'extension':
            sections = ext.load_buildspec(self)
            if sections is None:
                self.log.error(
                    "Extension buildspec flag '--%s' was set but produced "
                    "no content.", ext.BUILDSPEC_FLAG)
                return False
            self.injectBuildspec(sections)
            return True

        makefiles = [x.strip() for x in self.settings['makefile'].split(',')]
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
            sys.stdout.flush()
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

    def _discoverExtensions(self):
        """Scan sys.path for CsmakeModules/*Extension.py and load them.

        Each *Extension.py is expected to call
        CliDriver.register_extension(MyExtensionClass) at module level,
        which fires when the file is imported here.  After all extension
        modules have been loaded, any settings they declare are injected
        into self.settings so that _getOptions() can parse them from the
        command line.
        """
        import glob
        import importlib.util as _ilu

        seen = set()

        def _load_ext(ext_path):
            """Load a single Extension__*.py file if not already loaded."""
            if ext_path in seen:
                return
            seen.add(ext_path)
            mod_name = 'CsmakeModules.' + os.path.basename(ext_path)[:-3]
            if mod_name in sys.modules:
                return
            try:
                spec = _ilu.spec_from_file_location(mod_name, ext_path)
                mod  = _ilu.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
            except Exception as e:
                self.log.debug(
                    "Could not load csmake extension %s: %s",
                    ext_path, str(e))

        for base in sys.path:
            if not base:
                base = os.getcwd()

            # Direct scan: <base>/CsmakeModules/Extension__*.py
            for ext_path in sorted(glob.glob(
                    os.path.join(base, 'CsmakeModules', 'Extension__*.py'))):
                _load_ext(ext_path)

            # Subdirectory scan: <base>/<subdir>/CsmakeModules/Extension__*.py
            # Mirrors _constructModulePaths() so extensions in installed
            # packages (e.g. site-packages/CsmakeGHActions/CsmakeModules/)
            # are found even when only the parent is on sys.path.
            try:
                for subdir in sorted(os.listdir(base)):
                    for ext_path in sorted(glob.glob(
                            os.path.join(base, subdir,
                                         'CsmakeModules', 'Extension__*.py'))):
                        _load_ext(ext_path)
            except OSError:
                pass

        # After all modules have self-registered, add their settings so
        # _getOptions() sees the new flags during argument parsing.
        for ext in self._extensions:
            get_settings = getattr(ext, 'get_settings', None)
            if callable(get_settings):
                self.addOptions('', ext.get_settings())

    def _resolveActiveBuildspecSource(self):
        """Return ('extension', ext_class) or ('makefile', None).

        Scans sys.argv left-to-right to find the last buildspec flag
        (--makefile, --csmakefile, or any extension BUILDSPEC_FLAG).
        When both a makefile flag and an extension flag are present,
        the last one wins and a warning is emitted.
        """
        ext_flag_map = {
            '--' + ext.BUILDSPEC_FLAG: ext
            for ext in self._extensions
            if getattr(ext, 'BUILDSPEC_FLAG', None)
        }

        if not ext_flag_map:
            return ('makefile', None)

        makefile_flags = {'--makefile', '--csmakefile'}
        all_flags      = makefile_flags | set(ext_flag_map.keys())

        last_source  = None   # ('makefile', None) | ('extension', ext)
        saw_makefile = False
        saw_extension = False

        for arg in sys.argv[1:]:
            flag = arg.split('=')[0]
            if flag in makefile_flags:
                last_source  = ('makefile', None)
                saw_makefile = True
            elif flag in ext_flag_map:
                last_source  = ('extension', ext_flag_map[flag])
                saw_extension = True

        if saw_makefile and saw_extension:
            if last_source[0] == 'extension':
                flag_used = '--' + last_source[1].BUILDSPEC_FLAG
                self.log.warning(
                    "Both --makefile and %s were specified; "
                    "using %s (appeared last on command line)",
                    flag_used, flag_used)
            else:
                self.log.warning(
                    "Both an extension buildspec flag and --makefile were "
                    "specified; using --makefile (appeared last on command line)")

        return last_source or ('makefile', None)

    def realmain(self):
        self._getCurrentProcesses()
        # Seed sys.path from lazily-downloaded .csm packages so that both
        # extension discovery and module loading see them without any network
        # access (installed packages already live on sys.path via the
        # system packaging).
        try:
            from .ModuleRegistry import ModuleRegistry
            ModuleRegistry().seed_sys_path()
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).debug(
                "ModuleRegistry.seed_sys_path failed (non-fatal): %s", _e)
        self._discoverExtensions()
        self._getOptions()
        self._executeOptions()

        # Structured --list-type(s) output (json/yaml) must own stdout, so
        # silence logging before any startup chatter (e.g. a missing default
        # csmakefile) can leak into the emitted document.  Guarded so drivers
        # that do not define the setting keep the historical behavior.
        try:
            if self.settings['list-type-format'] != 'text' and (
                    self.settings['list-types']
                    or self.settings['list-type'] is not None):
                self.log.forceQuiet()
        except Exception:
            pass

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
        with open(self.fakegit, 'ab') as _f:
            _f.write(b'\x00')


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

        # Load ambient package pins: [~~packages~~] pkgname=version, the
        # spec-level default consulted when a section has no **uses of its
        # own.  See docs/MODULE_ECOSYSTEM_DESIGN.md.
        if self.buildspec.has_section('~~packages~~'):
            for pkgname, version in self.buildspec.items('~~packages~~'):
                self._packagePins[pkgname] = version.strip()

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
            size = os.path.getsize(fakegit)
            if size > 0:
                with open(fakegit, 'r+b') as _f:
                    _f.truncate(size - 1)
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

    def _pinnedPackageRoot(self, pkgname, version):
        """Return the on-disk root for pkgname@version, installing it via
        the module registry first if it isn't already cached.  Returns
        None if it can't be resolved (a warning is logged by the caller).

        A freshly-triggered install re-seeds sys.path: if this pin's
        version turns out to be the greatest one now cached for pkgname,
        an unpinned section elsewhere in the same build should see it too
        ("greatest version among **uses pins, when no ambient pin exists"
        -- see docs/MODULE_ECOSYSTEM_DESIGN.md). seed_sys_path() re-scans
        the cache fresh each call and only inserts paths not already on
        sys.path, so this is safe to call repeatedly. _constructModulePaths
        memoizes its result from sys.path, so that cache must be dropped
        too -- otherwise a later unpinned lookup keeps using the path list
        computed before this install happened (mirrors how the existing
        registry-autoload fallback below already invalidates it after
        appending a freshly-downloaded module's own path).
        """
        root = os.path.join(
            os.path.expanduser('~/.csmake/modules'), pkgname, version)
        if os.path.isdir(root):
            return root
        from .ModuleRegistry import ModuleRegistry
        registry = ModuleRegistry(self.settings)
        installed = registry.install(pkgname, version=version)
        if installed:
            registry.seed_sys_path()
            self.modulePathConstruct = None
        return installed

    def _loadPinnedModule(self, target, pin):
        """Try to load *target* specifically from pin=(pkgname, version)'s
        own cached root.  Returns ([], []) if that package doesn't provide
        *target* -- the caller falls through to the normal unpinned search
        in that case (covers core-shipped and third-party dependencies a
        pinned package relies on, e.g. a packaging module subclassing
        core's Packager).

        Loaded modules are cached and returned under a mangled sys.modules
        key private to this (target, package, version) triple -- distinct
        from the bare slot other, unpinned code sees, so pinned loads are
        strictly additive and never shadow anything.
        """
        pkgname, version = pin
        root = self._pinnedPackageRoot(pkgname, version)
        if root is None:
            self.log.warning(
                "**uses %s@%s: could not resolve; falling back to "
                "unpinned resolution for '%s'", pkgname, version, target)
            return [], []

        packagePath = "%s/CsmakeModules" % root
        modulePath = "%s/%s.py" % (packagePath, target)
        if not os.path.isfile(modulePath):
            return [], []

        mangledName = "%s@@%s@@%s" % (target, pkgname, version)

        imp.acquire_lock()
        try:
            existing = sys.modules.get(mangledName)
        finally:
            imp.release_lock()
        if existing is not None:
            actualModule = existing.__dict__.get(target)
            return [(packagePath, target, existing, actualModule)], []

        warnings = []
        self._pinContext.append(pin)
        try:
            imp.acquire_lock()
            try:
                module = imp.load_source(mangledName, modulePath)
                sys.modules[mangledName] = module
            finally:
                imp.release_lock()
        except Exception as e:
            trbk = traceback.format_exc()
            warnings.append(self._reportLoadModuleError(target, packagePath, e, trbk))
            return [], warnings
        finally:
            self._pinContext.pop()

        actualModule = None
        try:
            actualModule = module.__dict__[target]
            if isinstance(actualModule, types.ModuleType):
                actualModule = actualModule.__dict__[target]
        except Exception:
            warnings.append([
                "There is a naming problem with module '%s'" % target])
            self.log.exception(
                "There was a naming problem with module '%s'", target)

        return [(packagePath, target, module, actualModule)], warnings

    def _loadModules(self, target = '', pin=None):
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

           pin, when given, is a (package, version) tuple (see
           _parsePin/**uses).  The pinned package's own cached root is
           tried FIRST; if it doesn't provide *target*, resolution falls
           through to the normal search below unchanged -- "pinned
           package, then core, then bare" from
           docs/MODULE_ECOSYSTEM_DESIGN.md.  A pinned load never touches
           the bare sys.modules slot, so with pin=None (always true
           unless something is actually pinned) this method's behavior is
           unchanged from before pins existed.

           returns [(path, name, module)], [warnings]"""

        if pin is not None:
            pinnedModules, pinnedWarnings = self._loadPinnedModule(target, pin)
            if pinnedModules:
                return pinnedModules, pinnedWarnings
            # Not provided by the pinned package -- fall through to the
            # normal (core / bare) search below.

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

        # Nothing found locally — try auto-downloading via the module registry
        if len(modules) == 0 and target and target not in self._remoteModulesAttempted:
            self._remoteModulesAttempted.add(target)
            from .ModuleRegistry import ModuleRegistry
            registry = ModuleRegistry(self.settings)
            # Ambient [~~packages~~] pins only matter for what gets fetched
            # here -- a dev checkout / --modules-path entry (layer zero,
            # versionless) already won above if it had *target*, and this
            # branch only runs when nothing local provided it.
            remote_path = registry.find(
                target, pinned_versions=self._packagePins or None)
            if remote_path:
                self.log.devdebug(
                    "Remote module '%s' downloaded to '%s'", target, remote_path)
                self.modulePaths.append(remote_path)
                self.modulePathConstruct = None
                return self._loadModules(target)

        return (modules, warnings)

    def getSectionTypeInstance(self, target, logger=None, pin=None):
        if logger is None:
            logger = Result(self.env, self.log.info)
        # Python's own import machinery auto-populates sys.modules under
        # the dotted 'CsmakeModules.<Name>' key as a side effect of the
        # legacy find_module/load_module loader protocol -- purely its
        # own bookkeeping; nothing in this class ever reads that key (our
        # caches are the bare CsmakeModulesModule dict, for the unpinned
        # case, and a pin-mangled sys.modules key, for a pinned one). Left
        # alone, that auto-cache short-circuits Python's import statement
        # before load_module() is even called again, so a PREVIOUS
        # section's pin could leak into a later section with a different
        # (or no) pin purely via Python's own caching. Clearing it once
        # per section dispatch is safe (we never rely on it for anything)
        # and forces every section to resolve fresh.
        for key in [k for k in sys.modules if k.startswith('CsmakeModules.')]:
            del sys.modules[key]
        modules, warnings = self._loadModules(target, pin=pin)
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
