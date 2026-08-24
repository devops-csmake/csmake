# <copyright>
# (c) Copyright 2024 Autumn Patterson
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
"""Unit tests for CsmakeCore.ModuleDoc.

Self-contained (only stdlib + ModuleDoc).  Run with:

    python3 -m unittest CsmakeCore.tests.testModuleDoc
    # or, from this directory:
    python3 testModuleDoc.py
"""
import json
import os
import sys
import textwrap
import unittest

# Allow running directly (python3 testModuleDoc.py) as well as as a package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ModuleDoc  # noqa: E402  (CsmakeCore on path)


SHELL_DOC = """Purpose: Execute a shell script
       Type: Module   Library: csmake (core)
       Options:
         :: Script Definition Options ::
           command(<phase>) - Shell command to execute in specified phase
                 If (<phase>) is not specified: 'build' is assumed
       Phase: Any
       Examples:
           [Shell@my-command]
           command(build)=echo "Hello, World"
    """

# Mirrors DebianPackage: Implements appears *before* Type (order independence),
# and Phases carries per-line descriptions.
DEBIAN_DOC = """Purpose: To create a .deb package that can be consumed by dpkg.
       Implements: Packager
       Type: Module   Library: csmake (core)
       Phases:
           package - Will build a debian package
           clean, package_clean - will delete the package
       Options:
           Common keywords:
               package-version - the version for the package
               arch - (OPTIONAL) Specify the architecture
    """

ANSIBLE_DOC = """Purpose: Execute an Ansible module as a csmake build step.
       Type: Module   Library: csmake-ansible
       Phases: *any*
       Options:
           --module      - (REQUIRED) Ansible module to run.
           --hosts       - Host pattern to target (default: localhost)
       Notes:
           Requires ansible on PATH.
       Also Note:
           Return codes follow Ansible conventions.
    """

SUBMODULE_DOC = """Purpose: Returns an object that behaves like a hash function.
                That object returns an ASCII armored GPG signature.
       Type: Submodule   Library: csmake-swak
       Implements: Signature
       Phases: *any*
       Options:
           signer - (OPTIONAL) Default will be a default key holder
    """


class TestNormalize(unittest.TestCase):
    def test_none_is_sentinel(self):
        self.assertEqual(
            ModuleDoc.normalize_docstring(None), ModuleDoc.NOT_DOCUMENTED)

    def test_single_line_passthrough(self):
        self.assertEqual(ModuleDoc.normalize_docstring("hi"), "hi")

    def test_dedents_remainder_keeps_first_line(self):
        raw = ModuleDoc.normalize_docstring(SHELL_DOC)
        lines = raw.split("\n")
        self.assertEqual(lines[0], "Purpose: Execute a shell script")
        # Top-level headers land at column 0 after dedent.
        self.assertIn("Type: Module   Library: csmake (core)", lines)
        self.assertTrue(any(l.startswith("Options:") for l in lines))


class TestShell(unittest.TestCase):
    def setUp(self):
        self.obj = ModuleDoc.parse_module_doc("Shell", SHELL_DOC,
                                              path="./CsmakeModules")

    def test_basic_fields(self):
        self.assertEqual(self.obj["name"], "Shell")
        self.assertEqual(self.obj["summary"], "Execute a shell script")
        self.assertEqual(self.obj["type"], "Module")
        self.assertEqual(self.obj["library"], "csmake (core)")
        self.assertIsNone(self.obj["implements"])

    def test_phase_any(self):
        self.assertEqual(self.obj["phases"], [{"name": "any", "description": ""}])

    def test_option_group_and_continuation(self):
        opts = self.obj["options"]
        self.assertEqual(len(opts), 1)
        opt = opts[0]
        self.assertEqual(opt["group"], "Script Definition Options")
        self.assertEqual(opt["name"], "command(<phase>)")
        # Continuation line folded into the description.
        self.assertIn("build' is assumed", opt["description"])

    def test_raw_is_faithful(self):
        self.assertEqual(self.obj["raw"],
                         ModuleDoc.normalize_docstring(SHELL_DOC))

    def test_examples_captured(self):
        self.assertEqual(len(self.obj["examples"]), 1)
        self.assertIn("[Shell@my-command]", self.obj["examples"][0])


class TestOrderIndependenceAndPhases(unittest.TestCase):
    def setUp(self):
        self.obj = ModuleDoc.parse_module_doc("DebianPackage", DEBIAN_DOC)

    def test_implements_before_type(self):
        self.assertEqual(self.obj["implements"], "Packager")
        self.assertEqual(self.obj["type"], "Module")
        self.assertEqual(self.obj["library"], "csmake (core)")

    def test_phase_descriptions_and_comma_split(self):
        names = [p["name"] for p in self.obj["phases"]]
        self.assertEqual(names, ["package", "clean", "package_clean"])
        byname = {p["name"]: p["description"] for p in self.obj["phases"]}
        self.assertEqual(byname["package"], "Will build a debian package")
        self.assertEqual(byname["clean"], "will delete the package")

    def test_subheader_group(self):
        groups = {o["group"] for o in self.obj["options"]}
        self.assertIn("Common keywords", groups)


class TestRequiredOptional(unittest.TestCase):
    def test_required_detected(self):
        obj = ModuleDoc.parse_module_doc("Ansible", ANSIBLE_DOC)
        byname = {o["name"]: o for o in obj["options"]}
        self.assertTrue(byname["--module"]["required"])
        self.assertIsNone(byname["--hosts"]["required"])

    def test_repeated_notes_concatenated(self):
        obj = ModuleDoc.parse_module_doc("Ansible", ANSIBLE_DOC)
        note_fields = [f for f in obj["fields"] if f["key"] == "notes"]
        self.assertEqual(len(note_fields), 1)  # combined
        self.assertIn("Requires ansible", note_fields[0]["value"])
        self.assertIn("Ansible conventions", note_fields[0]["value"])

    def test_optional_detected_and_submodule(self):
        obj = ModuleDoc.parse_module_doc("AsciiGPGSignature", SUBMODULE_DOC)
        self.assertEqual(obj["type"], "Submodule")
        self.assertEqual(obj["implements"], "Signature")
        self.assertFalse(obj["options"][0]["required"])
        # Multi-line Purpose collapses into a single summary.
        self.assertIn("ASCII armored GPG signature", obj["summary"])


class TestUndocumented(unittest.TestCase):
    def test_none_doc(self):
        obj = ModuleDoc.parse_module_doc("Mystery", None)
        self.assertEqual(obj["raw"], ModuleDoc.NOT_DOCUMENTED)
        self.assertIsNone(obj["summary"])
        self.assertEqual(obj["options"], [])


RPMPACKAGE_DOC = """Purpose: Build an RPM package
       Type: Module   Library: csmake-packaging
       Requires:
           exec: rpmbuild, rpm2cpio
           caps: docker-daemon
    """

PROSE_REQUIRES_DOC = """Purpose: A module with a pre-schema, free-form Requires field
       Type: Module   Library: csmake (core)
       Requires:
           coverage (>= 4.0 preferred)
               (apt-get install python-coverage
                or pip install coverage)
    """


class TestRequires(unittest.TestCase):
    def test_exec_and_caps_parsed(self):
        obj = ModuleDoc.parse_module_doc("RpmPackage", RPMPACKAGE_DOC)
        self.assertEqual(obj["requires"]["exec"], ["rpmbuild", "rpm2cpio"])
        self.assertEqual(obj["requires"]["caps"], ["docker-daemon"])

    def test_no_requires_field_yields_empty(self):
        obj = ModuleDoc.parse_module_doc("Shell", SHELL_DOC)
        self.assertEqual(obj["requires"], {"exec": [], "caps": []})

    def test_prose_requires_field_yields_empty_not_misparsed(self):
        # Regression test: TestPython.py's own pre-existing Requires:
        # field is free-form prose written before this schema existed
        # ("coverage (>= 4.0 preferred) (apt-get install ...)"). A naive
        # bare-line-as-exec-list fallback would tokenize this into
        # nonsense exec names ('(>=', '4.0', 'preferred)', ...) and the
        # preflight check would then warn about all of them being
        # missing from PATH. Module docstrings must stay lenient: only
        # exec:/caps: sub-headers are structured; anything else is
        # silently ignored, never guessed at.
        obj = ModuleDoc.parse_module_doc("Prose", PROSE_REQUIRES_DOC)
        self.assertEqual(obj["requires"], {"exec": [], "caps": []})

    def test_legacy_bare_as_exec_opt_in_for_requires_supplement(self):
        # Only **requires= in ~~phases~~ opts into this (its own
        # established convention was genuinely "one name per line") --
        # see phases.py._process_requires and testPhases.py.
        result = ModuleDoc._parse_requires(
            "csmake-providers\ncsmake-swak\nn81", legacy_bare_as_exec=True)
        self.assertEqual(
            result["exec"], ["csmake-providers", "csmake-swak", "n81"])
        self.assertEqual(result["caps"], [])


class TestSerializers(unittest.TestCase):
    def setUp(self):
        self.objs = [
            ModuleDoc.parse_module_doc("Shell", SHELL_DOC),
            ModuleDoc.parse_module_doc("Ansible", ANSIBLE_DOC),
        ]

    def test_json_roundtrip(self):
        text = ModuleDoc.dump_json(self.objs)
        back = json.loads(text)
        self.assertEqual(len(back), 2)
        self.assertEqual(back[0]["name"], "Shell")

    def test_yaml_emits_string(self):
        text = ModuleDoc.dump_yaml(self.objs)
        self.assertIsInstance(text, str)
        self.assertIn("name", text)
        self.assertIn("Shell", text)

    def test_render_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            ModuleDoc.render(self.objs, "xml")


class TestSourceExtraction(unittest.TestCase):
    def test_extract_from_temp_source(self):
        import tempfile
        src = textwrap.dedent('''\
            class Widget(object):
                """Purpose: Do widget things
                   Type: Module   Library: csmake-test
                """
                pass
        ''')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "Widget.py")
            with open(path, "w") as handle:
                handle.write(src)
            doc = ModuleDoc.extract_class_docstring(path)
            self.assertIsNotNone(doc)
            obj = ModuleDoc.parse_module_doc("Widget", doc, path=d)
            self.assertEqual(obj["summary"], "Do widget things")
            self.assertEqual(obj["library"], "csmake-test")
            # discover_source_docs finds it and honors skip.
            found = list(ModuleDoc.discover_source_docs(d))
            self.assertEqual([o["name"] for o in found], ["Widget"])
            self.assertEqual(
                list(ModuleDoc.discover_source_docs(d, skip={"Widget"})), [])


if __name__ == "__main__":
    unittest.main()
