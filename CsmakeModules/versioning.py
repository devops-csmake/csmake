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
from Csmake.CsmakeModuleAllPhase import CsmakeModuleAllPhase
import subprocess

class versioning(CsmakeModuleAllPhase):
    """Purpose:
           To add special version information beyond the standard
           "major"."minor"."patch" defined in the metadata.
       Type: Module   Library: csmake (core)
       Description:
           The version information defined by this section will have a
           designation (defined by the label provided in the "designation"
           option for this section).
           The designation is used when constructing a specialized
           version.  For example, the FormatVersionEnv module has a "format"
           option that will substitute a {<designation>} with the value
           defined for that designation in the 'versioning' section.
       Phases: *any*
       Options:
           designation=Will add to the metadata version string.
                Warning: Specifying a version designation of 'primary'
                         will overwrite the version specified in the metadata.
           format= Any string.  keys are enclosed with curlies
                e.g., {datetime}.{getSHA}
                Note: Any specified csmake environment variables are substituted
                before the keys are processed.
           shell_<key>= executes a shell command and puts the
                        result in for any references of {<key>} in the format
                        option.
           step_<key>=  executes a specified step and puts the result in for
                        any references of {<key>} in the format option
           value_<key>= places the string in for any references of {<key>}
                        in the format option.
           dry-run=(OPTIONAL) if True will only return the calculated
                   version string without updating the metadata.
                   Default: False
        Example:
            [versioning@my-special-version]
            designation=special
            format= +++{special-major}.{special-minor}-BUILD {build-no}
            value_special-major=99
            value_special-minor=133
            shell_build-no=echo ${BUILDNO}

            When this section is executed (assuming BUILDNO is defined in the
               shell environment that executed csmake, and the definition
               is for this example BUILDNO=52252) the "special" version
               designation will contain or produce the value:
                   +++99.133-BUILD 52252
    """

    REQUIRED_OPTIONS=['designation', 'format']

    def __repr__(self):
        return "<<versioning step definition>>"

    def __str__(self):
        return "<<versioning step definition>>"

    def default(self, options):
        self.format = options['format']
        formatdict = {}
        for key, value in options.items():
            keyparts = key.split('_')
            if len(keyparts) != 2:
                continue
            #TODO: Structure this so keyparts[0] makes a call
            #      using the value so that it's easy to extend this
            #      apparatus
            if keyparts[0] == 'shell':
                p = subprocess.Popen(
                    value,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE )
                stdout, stderr = p.communicate()
                if p.returncode != 0:
                    self.log.warning("%s produced a non-zero returncode (%d)",
                        value,
                        p.returncode )
                    self.log.warning("   As a result, <<error>> will be given instead of the intended value")
                    formatdict[keyparts[1]] = '<<error>>'
                else:
                    resultvalue = str(stdout).strip()
                    self.log.debug("Version %s: %s", keyparts[1], resultvalue)
                    formatdict[keyparts[1]] = resultvalue
            elif keyparts[0] == 'value':
                formatdict[keyparts[1]] = value
            elif keyparts[0] == 'step':
                phase = self.engine.getPhase()
                result = self.engine.launchStep(
                    value,
                    phase)
                if result is None or not result._didPass():
                    self.log.warning("%s step failed", value)
                    self.log.warning("   As a result, <<error>> will be given instead of the intended value")
                    formatdict[keyparts[1]] = '<<error>>'
                else:
                    formatdict[keyparts[1]] = str(result._getReturnValue(phase))
        result = self.format
        result = self._parseBrackets(result, formatdict)
        if self.metadata is not None and (
            'dry-run' not in options or options['dry-run'].strip() != 'True'):
            self.metadata._addVersionString(options['designation'], result)
        self.log.passed()
        return result
