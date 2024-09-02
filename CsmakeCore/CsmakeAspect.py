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

class CsmakeAspect(CsmakeModule):
    """Default joinpoints are:
           start
           passed
           failed
           exception
           end """

    def __init__(self, env, log):
        CsmakeModule.__init__(self, env, log)
        self.optionSubstitutionsDone = False

    def _getDispatchString(self, joinpoint, phase):
        dispatchString = "%s__%s" % (
            joinpoint,
            phase )
        return dispatchString

    def _doOptionSubstitutions(self, options):
        self.optionSubstitutionsDone = True
        CsmakeModule._doOptionSubstitutions(self, options)

    def _joinPointLookup(self, joinpoint, phase, options):
        result = None
        alsoResult = None
        finalResult = None
        dispatchString = self._getDispatchString(
            joinpoint,
            phase )
        try:
            self.log.devdebug("<<Aspect looking up %s>>",
                dispatchString )
            result = getattr(self, dispatchString)
        except:
            self.log.devdebug("<<phase specific joinpoint not found>>")
            pass
        try:
            self.log.devdebug("<<Aspect looking up %s>>",
                joinpoint )
            alsoResult = getattr(self, joinpoint)
        except:
            self.log.devdebug("<<phase generic joinpoint not found>>")
            pass
        if result is None and alsoResult is None:
            self.log.devdebug(
                "<<%s join point not implemented>>",
                dispatchString)
        if result is not None and alsoResult is not None:
            #Doing this allows subclasses to override the more
            # specific behavior and still have the generic
            # implementation called in the super class (or vice versa)
            # (if implemented).
            #  specific == start__build  (<advise>__<phase>)
            #  generic  ==  start  (<advise>) 
            #This allows for implementation knowledge decoupling
            # between the sub and super - for the dynamic dispatch style
            # used here and the fact that these are aspects, this 
            # decoupling can be extremely helpful
            # but could also be annoying because it goes outside of
            # python's normal behavior of requiring explicit super calls
            # and the semantic is that the generic and specific are
            # as if they are one in the same method dispatch...
            # given both the complexity of the idea of aspect subclassing
            # dynamic dispatch that has two possible targets,
            # and what correct behavior might actually mean, it's probably worth
            # the trade off to require subclass implementers to
            # override both the generic and specific behavior of the super class
            # if they want to explicitly do a different (or no) behavior.
            #And, if you think about it....that would be expected behavior
            # in the case of a regular single target dispatch....you have to
            # override to change behavior...so, there you go. :)
            #This has the additional advantage that one could define
            # the specific and generic behavior for advise given.
            def dualCall(phase, aspectdict, execinstance, stepdict):
                return (
                    result(phase, aspectdict, execinstance, stepdict),
                    alsoResult(phase, aspectdict, execinstance, stepdict) )
            finalResult = dualCall
        elif result is not None:
            finalResult = result
        elif alsoResult is not None:
            finalResult = alsoResult
        else:
            return None
        if not self.optionSubstitutionsDone:
            callResult = finalResult
            #Doing the substitutions this way allows lazy evaluation
            #of the options which means both efficiency, because they
            # are only evaluated if needed, and closer error locality
            # This will be both less annoying for users because it
            # will only throw errors when the options are needed to be used
            # meaning the user has a mental context for why the error
            # is occurring (it's at least more likely).  And,
            # the error will occur after the headers are chatted in this
            # case, providing a more meaningful output context for the
            # errors. 
            def setupOptions(phase, aspectdict, execinstance, stepdict):
                self._doOptionSubstitutions(stepdict)
                return callResult(phase, aspectdict, execinstance, stepdict)
            finalResult = callResult
        return finalResult

