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
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Generations  # noqa: E402  (CsmakeCore on path)


COMBINED_INDEX_V1 = {
    'packages': {
        'csmake-packaging': {'latest': '1.1.5'},
        'csmake-swak': {'latest': '1.1.15'},
    }
}
COMBINED_INDEX_V2 = {
    'packages': {
        'csmake-packaging': {'latest': '1.2.0'},
        'csmake-swak': {'latest': '1.1.15'},
    }
}


class GenerationsTestBase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.gens = Generations.Generations(root=self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestNoGenerationYet(GenerationsTestBase):
    def test_current_name_is_none(self):
        self.assertIsNone(self.gens.current_name())

    def test_current_is_none(self):
        self.assertIsNone(self.gens.current())

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.gens.get('nonexistent'))


class TestRemaster(GenerationsTestBase):
    def test_first_remaster_from_explicit_packages(self):
        manifest = self.gens.remaster(
            'gen-1', COMBINED_INDEX_V1,
            packages=['csmake-packaging', 'csmake-swak'])
        self.assertEqual(manifest['packages'], {
            'csmake-packaging': '1.1.5', 'csmake-swak': '1.1.15'})
        self.assertIsNone(manifest['parent'])

    def test_remaster_does_not_auto_promote(self):
        self.gens.remaster('gen-1', COMBINED_INDEX_V1, packages=['csmake-swak'])
        self.assertIsNone(self.gens.current_name())

    def test_remaster_unknown_package_raises(self):
        with self.assertRaises(Generations.GenerationError):
            self.gens.remaster(
                'gen-1', COMBINED_INDEX_V1, packages=['does-not-exist'])

    def test_remaster_existing_name_raises(self):
        self.gens.remaster('gen-1', COMBINED_INDEX_V1, packages=['csmake-swak'])
        with self.assertRaises(Generations.GenerationError):
            self.gens.remaster('gen-1', COMBINED_INDEX_V1, packages=['csmake-swak'])

    def test_remaster_without_packages_reuses_current_generation_set(self):
        self.gens.remaster(
            'gen-1', COMBINED_INDEX_V1,
            packages=['csmake-packaging', 'csmake-swak'])
        self.gens.promote('gen-1')
        # No packages= given -- picks up gen-1's own package set, and
        # re-resolves each against the NEW (v2) index.
        manifest = self.gens.remaster('gen-2', COMBINED_INDEX_V2)
        self.assertEqual(manifest['packages'], {
            'csmake-packaging': '1.2.0', 'csmake-swak': '1.1.15'})
        self.assertEqual(manifest['parent'], 'gen-1')


class TestPromoteAndRollback(GenerationsTestBase):
    def setUp(self):
        super().setUp()
        self.gens.remaster('gen-1', COMBINED_INDEX_V1, packages=['csmake-swak'])
        self.gens.promote('gen-1')
        self.gens.remaster('gen-2', COMBINED_INDEX_V2)
        self.gens.promote('gen-2')

    def test_promote_updates_current(self):
        self.assertEqual(self.gens.current_name(), 'gen-2')
        self.assertEqual(
            self.gens.current()['packages']['csmake-swak'], '1.1.15')

    def test_promote_nonexistent_raises(self):
        with self.assertRaises(Generations.GenerationError):
            self.gens.promote('does-not-exist')

    def test_rollback_reverts_to_parent(self):
        restored = self.gens.rollback()
        self.assertEqual(restored, 'gen-1')
        self.assertEqual(self.gens.current_name(), 'gen-1')

    def test_rollback_with_no_parent_raises(self):
        self.gens.rollback()  # now on gen-1, which has no parent
        with self.assertRaises(Generations.GenerationError):
            self.gens.rollback()

    def test_generations_are_immutable_rollback_then_forward_again_works(self):
        self.gens.rollback()
        self.gens.promote('gen-2')
        self.assertEqual(self.gens.current_name(), 'gen-2')


class TestRollbackWithNoGeneration(GenerationsTestBase):
    def test_rollback_raises(self):
        with self.assertRaises(Generations.GenerationError):
            self.gens.rollback()


if __name__ == "__main__":
    unittest.main()
