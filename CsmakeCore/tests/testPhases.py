# <copyright>
# (c) Copyright 2026 Autumn Patterson
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
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import phases  # noqa: E402  (CsmakeCore on path)


class TestProcessRequires(unittest.TestCase):
    def setUp(self):
        self.log = logging.getLogger("testPhases")

    def test_exec_and_caps_schema(self):
        p = phases.phases({
            '**requires': 'exec: rpmbuild, gpg\ncaps: docker-daemon',
        }, self.log)
        self.assertEqual(
            p.phases['requires'], {
                'exec': ['rpmbuild', 'gpg'],
                'caps': ['docker-daemon'],
            })

    def test_legacy_bare_lines_treated_as_exec(self):
        # The docstring's own long-standing example, predating the
        # exec:/caps: schema -- must keep working unchanged.
        p = phases.phases({
            '**requires': 'csmake-providers\ncsmake-swak\nn81',
        }, self.log)
        self.assertEqual(
            p.phases['requires']['exec'],
            ['csmake-providers', 'csmake-swak', 'n81'])
        self.assertEqual(p.phases['requires']['caps'], [])

    def test_no_requires_section_is_absent(self):
        p = phases.phases({'build': 'do the build'}, self.log)
        self.assertNotIn('requires', p.phases)

    def test_none_options_is_safe(self):
        p = phases.phases(None, self.log)
        self.assertNotIn('requires', p.phases)


if __name__ == "__main__":
    unittest.main()
