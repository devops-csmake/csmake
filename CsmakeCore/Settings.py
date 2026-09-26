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

class Setting:
    def __init__(self, key, default, description, isFlag, short=None):
        self.key = key
        self.value = default
        self.description = description
        self.isFlag = isFlag
        self.short = short
        if short is None:
            self.short = description

        def keys(self):
            if self.value.has_method("keys"):
                return list(self.value.keys())
            else:
                []

        self.keys = keys

    def __getitem__(self, key):
        return self.value[key].value

    def __setitem__(self, key, value):
        self.value[key].value = value

    def getObject(self, key):
        return self.value[key]
        

class Settings:
    def initSettings(self, root, settingsDict):
        # Settings are in the form [default value, help text, isFlag, short text]
        root.value = {}
        for (key, value) in settingsDict.items():
            if value is not type(dict):
                if len(value) == 3:
                    root.value[key] = Setting(
                        key, value[0], value[1], value[2])
                else:
                    root.value[key] = Setting(
                        key, value[0], value[1], value[2], value[3])
            else:
                self.initSetting(root.value[key], value)

    def __init__(self, settingsSeed):
        self.allsettings = Setting("<root>", {}, "Root", False, "Root")
        self.initSettings(self.allsettings, settingsSeed)
        
    def __getitem__(self, key):
        return self.lookupSetting(key).value

    def __setitem__(self, key, value):
        try:
            self.lookupSetting(key).value = value
        except KeyError:
            self.lookupSetting(key[:-1]).value[key] = Setting(key,value,"",False)

    def getObject(self, key):
        return self.lookupSetting(key)

    def keys(self):
        return list(self.allsettings.value.keys())

    def lookupSetting(self, key):
        if len(key) == 0:
            return self.allsettings
        keylist = key.split(':')
        keypath = keylist[:-1]
        keyelem = keylist[-1]
        current = self.allsettings
        for part in keypath:
            current = current.value[part]
        return current.value[keyelem]

    def getDescription(self, key):
        setting = self.lookupSetting(key)
        return setting.description

    def isFlag(self, key):
        setting = self.lookupSetting(key)
        return setting.isFlag

    def appendSettings(self, key, newSettings):
        """Add settings for CLI use without disturbing existing settings.
           newSettings is a dict of the form:
               { name: [default, description, isFlag] }
           or with an optional fourth element for the short description:
               { name: [default, description, isFlag, short] }

           Where:
               name        - option name from the command line, file, or JSON
               default     - default value
               description - help text
               isFlag      - True if the option takes no value (boolean flag)
                             False if the option expects a parameter
        """
        if len(key) == 0:
            # Merge into root settings — existing keys are preserved.
            for k, v in newSettings.items():
                if k not in self.allsettings.value:
                    if len(v) == 3:
                        self.allsettings.value[k] = Setting(
                            k, v[0], v[1], v[2])
                    else:
                        self.allsettings.value[k] = Setting(
                            k, v[0], v[1], v[2], v[3])

