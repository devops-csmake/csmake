# <copyright>
# (c) Copyright 2019 Autumn Samantha Jeremiah Patterson
# (c) Copyright 2018 Cardinal Peak Technologies
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
import datetime
import os.path
import os
import hashlib
import re
import threading
import base64

class CsmakeModule:

    #This can be overridden for any subclass to specify parameters that
    #  are required for error checking before launching the section.
    REQUIRED_OPTIONS=[]

    exitCallbacks={}
    exitCallbacksLock = threading.Lock()

    def __init__(self, env, log):
        self.env = env
        self.log = log
        self.engine = env.engine
        self.settings = self.engine.settings
        self.metadata = self.env.metadata.getCurrent()
        self.newfiles = None
        self.mapping = None
        self.yieldsfiles = None
        self.validateFiles = True
        self.deletingFiles = False
        self.outOptions = None
        self.calledId = None
        self.aspects = []

    def __del__(self):
        try:
            if hasattr(self, exitCallbackIds):
                for callbackId in list(exitCallbackIds.values()):
                    try:
                        self.engine.unregisterBuildExitCallback(callbackId)
                    except:
                        self.log.exception("Couldn't unregister id: %s", callbackId)
        except:
            pass

    def _registerOnExitCallback(self, method, ident=None):
        """method - string name of the method to call on the module
           ident - (optional) allows for separate registrations from the
                   same module to be managed separately for every unique
                   ident tag used"""
        key = ("%s%%%s" % (self.__class__.__name__, method), ident)
        callback = getattr(self, method)
        def callbackThunk():
            self.log.chatStartOnExitCallback(method)
            self.log.devdebug(" Callback key: %s", key)
            try:
                callback()
            except:
                self.log.exception("Callback failed")
            finally:
                self.log.chatEndOnExitCallback(method)

        regid = self.engine.registerBuildExitCallback(
            callbackThunk)
        self.exitCallbacksLock.acquire()
        try:
            if regid is not None:
                if key not in self.exitCallbacks:
                    self.exitCallbacks[key] = []
                self.exitCallbacks[key].append(regid)
        finally:
            self.exitCallbacksLock.release()

    def _unregisterOtherClassOnExitCallback(self, classname, method, ident=None):
        key = ("%s%%%s" % (classname, method), ident)
        self.log.devdebug("callbacks unregistering: %s", list(self.exitCallbacks.keys()))
        self.exitCallbacksLock.acquire()
        try:
            regids = self.exitCallbacks[key]
            for regid in regids:
                try:
                    self.engine.unregisterBuildExitCallback(regid)
                except:
                    self.log.exception(
                        "Unregister of on exit '%s' failed", method)
            del self.exitCallbacks[key]
            return True
        except Exception as e:
            self.log.info(
                "Failed to unregister on exit handler: %s: %s",
                method,
                str(e) )
        finally:
            self.exitCallbacksLock.release()
        return False

    def _unregisterOnExitCallback(self, method, ident=None):
        return self._unregisterOtherClassOnExitCallback(
            self.__class__.__name__,
            method,
            ident)

    def initFlowControl(self, flowcontrol):
        self.flowcontrol = flowcontrol

    def _initCallInfo(self, outOptions, calledId):
        self.outOptions = outOptions
        self.calledId = calledId
        self.actualId = calledId
        if '@' in calledId:
            self.actualId = calledId.split('@')[1]

    def _doOptionSubstitutions(self, options):
        self.originalOptions = list(options)
        required = list(self.__class__.REQUIRED_OPTIONS)
        errors = False
        for key, value in options.items():
            if key.startswith('**'):
                continue
            try:
                try:
                    required.remove(key)
                except:
                    pass
                options[key] = self.env.doSubstitutions(value.strip())
                self.outOptions[key] = options[key]
            except KeyError as suberr:
                self.log.error("Option '%s' had a variable '%s' that is undefined", key, str(suberr))
                errors = True

        if errors and not self.engine.settings['keep-going']:
            raise AttributeError("Variables referenced in options that were undefined")
        if len(required) != 0:
            raise ValueError("The following required options were not provided: %s" % ', '.join(required))

    def _setAspects(self, aspects):
        self.aspects = aspects

    def _adviseJoinpoint(self, advice, phase, stepoptions, extras={}):
        self.engine.launchAspects(
            self.aspects,
            advice,
            phase,
            self,
            stepoptions,
            extras )

    def _getResult(self):
        return self.log

    def _dontValidateFiles(self):
        """Call to disable file validation for mapping.
           This is useful when you want to do abnormal, but valid things
           with the information given by the file mapper
           Useful also in the strange instance (which you probably shouldn't
           do) where you would be adding some of the files in the mapping
           and deleting other files in the mapping
           N.B.: Use of this directive is really an
             instance where the mappings should be extended to include
             the actual mapping semantic"""
        self.validateFiles = False

    def _cleaningFiles(self):
        """Call to let file mapping know that the module will delete the files
           given in the mapping.  The mapper will validate that the file
           was cleaned"""
        self.deletingFiles = True

    BRACKET_RE = re.compile(r"\{(?P<sub>[^\n\t\}\{]*)\}(?P<follow>(?=[/{])|[^\}]|[\}][\}]|$)")

    def _parseBrackets(self, parseTarget, parseDict):
        """Substitute {<key>} in parseTarget with parseDict[<key>]
           '}'s may be escaped by using }}"""
        subTarget = CsmakeModule.BRACKET_RE.sub("%(\g<sub>)s\g<follow>", parseTarget.replace('%','%%')).replace('}}',"}")
        return subTarget % parseDict

    def _getReturnValue(self, key):
        return self.log.getReturnValue(key)

    def _didPass(self):
        return self.log.didPass()

    def _didFail(self):
        return self.log.didFail()

    def _fileDigest(self, method, fileobj):
        if type(method) is not list:
            return self._fileDigestList([method], fileobj)[0]
        else:
            return self._fileDigestList(method, fileobj)

    def _fileDigestList(self, methods, fileobj):
        curpos = 0
        try:
            curpos = fileobj.tell()
            fileobj.seek(0)
        except:
            self.log.exception("Caution file object cannot seek")
        shacalcs = []
        for method in methods:
            shacalcs.append(method())
        while True:
            #Limit block size to 10K chunks to avoid OOM issues
            block = fileobj.read(10240)
            if not block:
                break
            for shacalc in shacalcs:
                shacalc.update(block)
        try:
            fileobj.seek(curpos)
        except:
            pass
        results = []
        for shacalc in shacalcs:
            results.append(shacalc.hexdigest())
        return results

    def _fileSHA1(self, fileobj):
        return self._fileDigest(hashlib.sha1, fileobj)

    def _fileSHA256(self, fileobj):
        return self._fileDigest(hashlib.sha256, fileobj)

    def _fileMD5(self, fileobj):
        return self._fileDigest(hashlib.md5, fileobj)

    def _filesize(self, fileobj):
        savespot = fileobj.tell()
        fileobj.seek(0,2)
        size = fileobj.tell()
        try:
            fileobj.seek(savespot)
        except:
            self.log.exception("Could not return file to previous location sending to start of file")
            fileobj.seek(0)
        return size

    def _PEP427Encode(self, data):
        #PEP-427 implementation for base64 urlsafe encoding with no pad
        return base64.urlsafe_b64encode(data).rstrip(b'=')

    def _PEP427Decode(self, data):
        #PEP-427 implementation for base64 urlsafe decoding with no pad
        pad = b'=' * (4 - (len(data) & 3))
        return base64.urlsafe_b64decode(data + pad)

    def _needRebuild(self, fileWorking, fileTarget, ignore=[]):
        #Specific modules may want to do something more extensive
        # than this
        #This will return true if the target file needs rebuilding
        if fileWorking in ignore:
            self.log.devdebug("Ignoring file: %s", fileWorking)
            return False
        if os.path.isfile(fileWorking):
            try:
                workingM = datetime.datetime.fromtimestamp(
                    os.path.getmtime(
                        fileWorking))
                workingM = workingM.replace(microsecond = 0)
                targetM = datetime.datetime.fromtimestamp(
                    os.path.getmtime(
                        fileTarget))
                self.log.devdebug('(%s  W: %s  T: %s) %s',
                    str(workingM >targetM),
                    str(workingM),
                    str(targetM),
                    fileWorking )
                return workingM > targetM
            except Exception as e:
                self.log.devdebug('fileWorking: %s   fileTarget: %s',
                    fileWorking,
                    fileTarget )
                self.log.info("The 'rebuild' comparison failed (%s)", repr(e))
        elif os.path.isdir(fileWorking):
            if not os.path.isdir(fileTarget):
                self.log.info("Directory/File mismatch, 'rebuild' comparison failed")
                return True
            for item in os.listdir(fileWorking):
                if self._needRebuild(
                    os.path.join(
                        fileWorking,
                        item ),
                    os.path.join(
                        fileTarget,
                        item ) ):
                    return True
            return False
        else:
            self.log.info("Referant not file or directory: Unhandled.  'rebuild ' comparison failed.")
            return True
        return True

    def _canAvoid(self, fileWorking, fileTarget):
        #Specialized modules may want to do something different here
        return not self._needRebuild(fileWorking, fileTarget)

    def _ensureDirectoryExists(self, path, isdirectory=False):
        if not isdirectory:
            directory, filename = os.path.split(path)
        else:
            directory = path
        if len(directory) > 0 and not os.path.lexists(directory):
            os.makedirs(directory)

    def _cleanEnsuredDirectory(self, path, isdirectory=False):
        if not isdirectory:
            directory, filename = os.path.split(path)
        else:
            directory = path
        try:
            os.removedirs(directory)
        except Exception as e:
            self.log.info("Directory not removed (%s): %s", directory, str(e))

    def _listSubCommands(self, options):
        """Returns a list of subcommands this module will execute, in order of
           execution"""
        return []

    def _getFileManager(self):
        #TODO: Should we have a global file manager, or just always require
        #      metadata?
        if self.metadata is not None:
            return self.metadata._getFileManager()
        return None

    def _parseCommaAndNewlineList(self, rawlist):
        flat = ','.join([ x.strip() for x in rawlist.split('\n') if len(x.strip()) > 0])
        return [ x.strip() for x in flat.split(',') if len(x.strip()) > 0 ]

    def _lookupPhaseShift(self, phase, stepdict):
        #Allows user to change the phase routed in to the step/aspect
        newPhase = phase
        if '**phases' in stepdict:
            try:
                shifts = self._parseCommaAndNewlineList(stepdict['**phases'])
                for shift in shifts:
                    parts = shift.split('->')
                    if parts[0].strip() == phase:
                        self.log.info("**** Phase shift: %s", shift)
                        newPhase = parts[1]
                        break
            except:
                self.log.exception("There was a problem with the **phases section: %s", stepdict['**phases'])
                raise
        return newPhase

    def _executeFileMapping(self, stepdict):
        #Get the file manager
        fileManager = self._getFileManager()
        if fileManager is not None:
            if self.log.filetrack:
                self.log.filetrackerOut(" ------- ")
                self.log.filetrackerOut(" File manager state")
                self.log.filetrackerOut(str(fileManager))
        else:
            self.log.error("File Tracking can only be utilized with metadata defined")
            return

        if '**files' in stepdict:
            statement = self.env.doSubstitutions(stepdict['**files'])
            self.newfiles = fileManager.parseFileDeclaration(statement)
        if '**maps' in stepdict:
            statement = self.env.doSubstitutions(stepdict['**maps'])
            self.mapping = fileManager.parseFileMap(statement)
        if '**yields-files' in stepdict:
            statement = self.env.doSubstitutions(stepdict['**yields-files'])
            self.yieldsfiles = fileManager.parseFileDeclarationForIndexes(
                                   statement)
            self.log.devdebug("Yielding: %s", self.yieldsfiles)

    def _absorbNewMappedFiles(self):
        fileManager = self._getFileManager()
        if self.yieldsfiles is not None and self._didPass():
            fileManager.addFileIndexes(
                self.yieldsfiles,
                self.env.env['RESULTS'],
                self.deletingFiles,
                self.validateFiles )
        if self.mapping is not None and self._didPass():
            fileManager.absorbMappings(
                self.mapping,
                self.deletingFiles,
                self.validateFiles)

    #Implement default or other build phases
    #  the name of the build phase is dispatched to the module
