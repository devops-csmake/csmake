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
"""Unit tests for CliDriver's system-requirements preflight check.

CliDriver constructs standalone (unlike CsmakeModule, which needs a fully
wired Environment), so this drives _preflightCheck directly rather than
through a full build -- faster and more targeted than a subprocess test.
"""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from CsmakeCore.CliDriver import CliDriver


class WithNoRequires(object):
    """Purpose: A fixture module with no Requires: field at all"""


class WithMissingExec(object):
    """Purpose: A fixture module that needs a made-up binary
       Requires:
           exec: totally-made-up-binary-xyz-nonexistent
    """


class WithPresentExec(object):
    """Purpose: A fixture module that needs something always present
       Requires:
           exec: python3
    """


class WithUnregisteredCap(object):
    """Purpose: A fixture module declaring an unregistered capability
       Requires:
           caps: some-unregistered-capability-xyz
    """


class WithRegisteredCapFails(object):
    """Purpose: A fixture module declaring a registered-but-failing capability
       Requires:
           caps: fixture-cap-that-fails
    """


class WithRegisteredCapPasses(object):
    """Purpose: A fixture module declaring a registered-and-passing capability
       Requires:
           caps: fixture-cap-that-passes
    """


class PreflightCheckTestBase(unittest.TestCase):
    def setUp(self):
        self.driver = CliDriver()
        self.driver.addOptions('', {
            'strict-prereqs': [False, 'test', True],
        })
        self._saved_checkers = dict(CliDriver._prereqCheckers)

    def tearDown(self):
        CliDriver._prereqCheckers.clear()
        CliDriver._prereqCheckers.update(self._saved_checkers)

    def _set_strict(self, value):
        self.driver.settings['strict-prereqs'] = value


class TestNonStrictMode(PreflightCheckTestBase):
    def test_no_requires_is_a_silent_noop(self):
        # Must not raise, must not even attempt anything.
        self.driver._preflightCheck('WithNoRequires', WithNoRequires)

    def test_present_exec_is_fine(self):
        self.driver._preflightCheck('WithPresentExec', WithPresentExec)

    def test_missing_exec_only_warns(self):
        # Non-strict: reported, but does not raise.
        self.driver._preflightCheck('WithMissingExec', WithMissingExec)

    def test_unregistered_cap_only_informs(self):
        self.driver._preflightCheck('WithUnregisteredCap', WithUnregisteredCap)

    def test_registered_cap_pass(self):
        CliDriver.register_prereq_checker(
            'fixture-cap-that-passes', lambda: True)
        self.driver._preflightCheck(
            'WithRegisteredCapPasses', WithRegisteredCapPasses)

    def test_registered_cap_fail_only_warns(self):
        CliDriver.register_prereq_checker(
            'fixture-cap-that-fails', lambda: False)
        self.driver._preflightCheck(
            'WithRegisteredCapFails', WithRegisteredCapFails)

    def test_checker_exception_treated_as_failure_not_a_crash(self):
        def _boom():
            raise RuntimeError("checker blew up")
        CliDriver.register_prereq_checker('fixture-cap-that-fails', _boom)
        # Must not propagate -- a broken checker must not break the build.
        self.driver._preflightCheck(
            'WithRegisteredCapFails', WithRegisteredCapFails)


class TestStrictMode(PreflightCheckTestBase):
    def setUp(self):
        super().setUp()
        self._set_strict(True)

    def test_no_requires_still_a_noop(self):
        self.driver._preflightCheck('WithNoRequires', WithNoRequires)

    def test_present_exec_still_fine(self):
        self.driver._preflightCheck('WithPresentExec', WithPresentExec)

    def test_missing_exec_raises(self):
        with self.assertRaises(Exception):
            self.driver._preflightCheck('WithMissingExec', WithMissingExec)

    def test_registered_cap_fail_raises(self):
        CliDriver.register_prereq_checker(
            'fixture-cap-that-fails', lambda: False)
        with self.assertRaises(Exception):
            self.driver._preflightCheck(
                'WithRegisteredCapFails', WithRegisteredCapFails)

    def test_registered_cap_pass_does_not_raise(self):
        CliDriver.register_prereq_checker(
            'fixture-cap-that-passes', lambda: True)
        self.driver._preflightCheck(
            'WithRegisteredCapPasses', WithRegisteredCapPasses)

    def test_unregistered_cap_unverifiable_does_not_raise(self):
        # Declared-but-unverifiable is distinct from failing -- strict
        # mode escalates actual failures, not merely-unknown capabilities
        # that no checker exists for yet.
        self.driver._preflightCheck('WithUnregisteredCap', WithUnregisteredCap)


class TestNeverInstalls(PreflightCheckTestBase):
    def test_missing_exec_never_attempts_a_subprocess_install(self):
        # Knows and tells, never installs -- the core invariant. Patch
        # subprocess.run/Popen/os.system to explosive stand-ins; the
        # preflight check must never touch any of them.
        import subprocess
        import os as os_module

        def _explode(*a, **k):
            raise AssertionError("preflight check must never execute anything")

        orig_run, orig_popen, orig_system = (
            subprocess.run, subprocess.Popen, os_module.system)
        subprocess.run = _explode
        subprocess.Popen = _explode
        os_module.system = _explode
        try:
            self.driver._preflightCheck('WithMissingExec', WithMissingExec)
        finally:
            subprocess.run, subprocess.Popen, os_module.system = (
                orig_run, orig_popen, orig_system)


if __name__ == "__main__":
    unittest.main()
