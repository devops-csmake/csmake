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
import base64
import csv
import hashlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import WheelWriter  # noqa: E402  (CsmakeCore on path)


class TestDigest(unittest.TestCase):
    def test_matches_manual_computation(self):
        data = b'hello wheel'
        expected = 'sha256=' + base64.urlsafe_b64encode(
            hashlib.sha256(data).digest()).rstrip(b'=').decode('ascii')
        self.assertEqual(WheelWriter.pep427_digest(data), expected)

    def test_no_padding_characters(self):
        digest = WheelWriter.pep427_digest(b'x')
        _, _, b64_portion = digest.partition('=')  # split off the 'sha256=' prefix
        self.assertNotIn('=', b64_portion)


class TestDistInfoDirname(unittest.TestCase):
    def test_hyphenated_name_escaped_to_underscore(self):
        # PEP 427: a hyphen in the distribution name must become '_' so
        # that a wheel filename built from the same name is unambiguous
        # to split back into its components.
        self.assertEqual(
            WheelWriter.dist_info_dirname('csmake-packaging', '1.1.5'),
            'csmake_packaging-1.1.5.dist-info')

    def test_normalizes_separators(self):
        self.assertEqual(
            WheelWriter.dist_info_dirname('my_weird.name', '1.0'),
            'my_weird.name-1.0.dist-info')

    def test_matches_real_wheel_library_expectation(self):
        # End-to-end regression test for a real interop bug found while
        # verifying WheelPackage's port: a naively-hyphenated dist-info
        # name (e.g. 'csmake-packaging-1.1.5.dist-info') doesn't match
        # what the reference `wheel` package derives from the wheel
        # filename ('csmake_packaging-1.1.5.dist-info'), so pip/wheel
        # can't find RECORD and refuse to open the wheel at all.
        try:
            from wheel.wheelfile import WheelFile
        except ImportError:
            self.skipTest("wheel package not installed")
        import tempfile
        import zipfile

        name, version = 'csmake-packaging', '1.1.5'
        payload = {'pkg/mod.py': b'# x\n'}
        dist_info_files = WheelWriter.build_dist_info(name, version, payload)

        # The filename's distribution/version segments must use the same
        # escaping as dist_info_dirname -- this is the invariant the test
        # exists to verify (a real bug WheelPackage.py had before its port
        # applied the same escape_name_component call to both places).
        filename = '%s-%s-py3-none-any.whl' % (
            WheelWriter.escape_name_component(name),
            WheelWriter.escape_name_component(version))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, filename)
            with zipfile.ZipFile(path, 'w') as zf:
                for archive_path, data in payload.items():
                    zf.writestr(archive_path, data)
                for archive_path, data in dist_info_files.items():
                    zf.writestr(archive_path, data)
            # Must not raise WheelError("Missing ... RECORD file").
            wf = WheelFile(path)
            wf.close()


class TestEscapeNameComponent(unittest.TestCase):
    def test_hyphen_and_dot_and_underscore_collapse(self):
        self.assertEqual(
            WheelWriter.escape_name_component('csmake-packaging'),
            'csmake_packaging')

    def test_already_safe_name_unchanged(self):
        self.assertEqual(
            WheelWriter.escape_name_component('simple123'), 'simple123')


class TestMetadata(unittest.TestCase):
    def test_required_fields(self):
        content = WheelWriter.generate_metadata('csmake-packaging', '1.1.5')
        text = content.decode('utf-8')
        self.assertIn('Metadata-Version: 2.1', text)
        self.assertIn('Name: csmake-packaging', text)
        self.assertIn('Version: 1.1.5', text)

    def test_summary_collapsed_to_one_line(self):
        content = WheelWriter.generate_metadata(
            'x', '1.0', description='line one\n   line two')
        text = content.decode('utf-8')
        self.assertIn('Summary: line one line two', text)

    def test_authors_and_classifiers(self):
        content = WheelWriter.generate_metadata(
            'x', '1.0',
            authors=[('Autumn Patterson', 'autumn@example.com'),
                     ('Anonymous', None)],
            classifiers=['Programming Language :: Python :: 3'])
        text = content.decode('utf-8')
        self.assertIn('Author: Autumn Patterson', text)
        self.assertIn('Author-email: autumn@example.com', text)
        self.assertIn('Author: Anonymous', text)
        self.assertIn('Classifier: Programming Language :: Python :: 3', text)


class TestWheelFile(unittest.TestCase):
    def test_purelib_true(self):
        content = WheelWriter.generate_wheel_file('py3-none-any').decode('utf-8')
        self.assertIn('Root-Is-Purelib: true', content)
        self.assertIn('Tag: py3-none-any', content)

    def test_purelib_false_and_build(self):
        content = WheelWriter.generate_wheel_file(
            'py3-cp312-macosx', root_is_purelib=False, build='7').decode('utf-8')
        self.assertIn('Root-Is-Purelib: false', content)
        self.assertIn('Build: 7', content)


class TestRecord(unittest.TestCase):
    def test_raw_bytes_hashed_and_precomputed_passthrough(self):
        payload = b'print("hi")\n'
        precomputed_digest = WheelWriter.pep427_digest(b'other')
        hashes = {
            'pkg/a.py': payload,
            'pkg/b.py': (precomputed_digest, 5),
        }
        record = WheelWriter.generate_record(hashes, 'pkg.dist-info/RECORD')
        rows = list(csv.reader(io.StringIO(record.decode('utf-8'))))
        by_path = {r[0]: r for r in rows}
        self.assertEqual(
            by_path['pkg/a.py'][1], WheelWriter.pep427_digest(payload))
        self.assertEqual(by_path['pkg/a.py'][2], str(len(payload)))
        self.assertEqual(by_path['pkg/b.py'][1], precomputed_digest)
        self.assertEqual(by_path['pkg/b.py'][2], '5')

    def test_record_lists_itself_blank(self):
        record = WheelWriter.generate_record(
            {'a.py': b'x'}, 'pkg.dist-info/RECORD')
        rows = list(csv.reader(io.StringIO(record.decode('utf-8'))))
        by_path = {r[0]: r for r in rows}
        self.assertEqual(by_path['pkg.dist-info/RECORD'][1], '')
        self.assertEqual(by_path['pkg.dist-info/RECORD'][2], '')


class TestBuildDistInfo(unittest.TestCase):
    def setUp(self):
        self.files = {
            'CsmakeModules/RpmPackage.py': b'# rpm packager\n',
            'CsmakeModules/HomebrewFormula.py': b'# brew formula\n',
        }
        self.result = WheelWriter.build_dist_info(
            'csmake-packaging', '1.1.5', self.files,
            description='Packaging modules for csmake',
            authors=[('Autumn Patterson', None)])

    def test_expected_files_present(self):
        prefix = 'csmake_packaging-1.1.5.dist-info/'
        self.assertEqual(set(self.result.keys()), {
            prefix + 'METADATA', prefix + 'WHEEL',
            prefix + 'top_level.txt', prefix + 'RECORD',
        })

    def test_top_level_defaults_to_package_name(self):
        prefix = 'csmake_packaging-1.1.5.dist-info/'
        self.assertEqual(
            self.result[prefix + 'top_level.txt'], b'csmake-packaging\n')

    def test_record_covers_payload_and_dist_info(self):
        prefix = 'csmake_packaging-1.1.5.dist-info/'
        record_text = self.result[prefix + 'RECORD'].decode('utf-8')
        rows = list(csv.reader(io.StringIO(record_text)))
        paths = {r[0] for r in rows}
        self.assertIn('CsmakeModules/RpmPackage.py', paths)
        self.assertIn('CsmakeModules/HomebrewFormula.py', paths)
        self.assertIn(prefix + 'METADATA', paths)
        self.assertIn(prefix + 'WHEEL', paths)
        self.assertIn(prefix + 'RECORD', paths)
        # Payload files use the hashes actually supplied, not re-hashed.
        by_path = {r[0]: r for r in rows}
        self.assertEqual(
            by_path['CsmakeModules/RpmPackage.py'][1],
            WheelWriter.pep427_digest(self.files['CsmakeModules/RpmPackage.py']))

    def test_metadata_content(self):
        prefix = 'csmake_packaging-1.1.5.dist-info/'
        text = self.result[prefix + 'METADATA'].decode('utf-8')
        self.assertIn('Name: csmake-packaging', text)
        self.assertIn('Author: Autumn Patterson', text)


if __name__ == "__main__":
    unittest.main()
