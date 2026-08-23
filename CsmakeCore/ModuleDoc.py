# <copyright>
# (c) Copyright 2024 Autumn Patterson
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
"""Parse csmake module docstrings into structured documentation.

csmake modules document themselves in their class ``__doc__`` docstring using a
semi-structured "semi-YAML" format::

    Purpose: <one line summary, may wrap>
    Type: <Module|Submodule|Aspect|...>   Library: <library name>
    Implements: <interface>            (for submodules / aspects)
    Phases: <phase list, or *any*>
    Options:
        :: <optional sub-group> ::
        <name> - <description>
    Joinpoints: ...
    Notes: ...
    Examples:
        <csmakefile snippet>

This module turns that text into a structured dict so the same documentation
that ``csmake --list-type`` prints can also be emitted as JSON or YAML (via the
``--list-type-format`` flag) and consumed by tooling such as the documentation
website.

Design goals:
  - **Lenient.** Real docstrings are free-form; parsing must never raise.  When
    a section cannot be structured it is still preserved verbatim in ``fields``
    and in ``raw``.
  - **Faithful.** ``raw`` is byte-for-byte what ``--list-type`` prints (the
    first line followed by a ``textwrap.dedent`` of the remainder), so nothing
    is ever lost relative to the plain-text view.

See ``docs/MODULE_DOC_SCHEMA.md`` for the canonical, refinable standard.
"""

import ast
import json
import os
import re
import textwrap

__all__ = [
    "normalize_docstring",
    "parse_module_doc",
    "extract_class_docstring",
    "discover_source_docs",
    "dump_json",
    "dump_yaml",
    "render",
]

# Canonical field keys mapped from the header aliases that may introduce them.
# Order matters only for display; lookup is alias-driven.  Aliases are matched
# longest-first so e.g. "Joinpoints introduced" wins over "Joinpoints".
_FIELD_ALIASES = {
    "purpose": ["Purpose"],
    "type": ["Type"],
    "library": ["Library"],
    "implements": ["Implements"],
    "phases": ["Phases", "Phase"],
    "joinpoints": [
        "Joinpoints introduced", "JoinPoints/Phases", "Joinpoints",
        "Joinpoint",
    ],
    "flowcontrol": [
        "Flowcontrol Advice introduced", "Flowcontrol Advice",
    ],
    "options": ["Options"],
    "flags": ["Flags"],
    "notes": ["Notes", "Note", "NOTE", "Also Note", "ALSO NOTE"],
    "warnings": ["WARNING", "Warning"],
    "default": ["Default is", "Default", "DEFAULT"],
    "examples": ["Examples", "Example", "Usage"],
    "see_also": ["See Also", "References", "Reference", "See"],
    "description": ["Description"],
    "environment": ["Environment"],
    "dependencies": ["Dependencies"],
    "requires": ["Requires"],
    "install_map": ["Install Map Definitions"],
    "package_name_format": ["Package Name Format"],
    "file_tracking": ["File Tracking"],
}

# Human-friendly labels for the structured fields, for rendering.
_FIELD_LABELS = {
    "purpose": "Purpose",
    "type": "Type",
    "library": "Library",
    "implements": "Implements",
    "phases": "Phases",
    "joinpoints": "Joinpoints",
    "flowcontrol": "Flowcontrol Advice",
    "options": "Options",
    "flags": "Flags",
    "notes": "Notes",
    "warnings": "Warning",
    "default": "Default",
    "examples": "Examples",
    "see_also": "See Also",
    "description": "Description",
    "environment": "Environment",
    "dependencies": "Dependencies",
    "requires": "Requires",
    "install_map": "Install Map Definitions",
    "package_name_format": "Package Name Format",
    "file_tracking": "File Tracking",
}

# Fields that commonly appear inline as a second header on the same physical
# line, e.g. "Type: Module   Library: csmake (core)".  Only these are split
# mid-line, to avoid mistaking prose like "see: http://..." for a header.
_INLINE_KEYS = ("library", "type", "implements")

# Build a flat alias -> key table and a regex that matches any alias.
_ALIAS_TO_KEY = {}
for _key, _aliases in _FIELD_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_KEY[_alias] = _key
# Longest alias first so multi-word aliases match before their prefixes.
_ALL_ALIASES = sorted(_ALIAS_TO_KEY.keys(), key=len, reverse=True)
_HEADER_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<alias>%s)[ \t]*:(?P<rest>.*)$"
    % "|".join(re.escape(a) for a in _ALL_ALIASES)
)
# Inline (mid-line) second header, only for the inline-pair keys.
_INLINE_ALIASES = sorted(
    [a for a, k in _ALIAS_TO_KEY.items() if k in _INLINE_KEYS],
    key=len, reverse=True)
_INLINE_RE = re.compile(
    r"[ \t]{2,}(?P<alias>%s)[ \t]*:"
    % "|".join(re.escape(a) for a in _INLINE_ALIASES))

NOT_DOCUMENTED = "<<Module not documented>>"


def normalize_docstring(docstring):
    """Return docstring as ``--list-type`` renders it.

    Mirrors ``CliDriver.dumpTypes``: keep the first line as-is, then
    ``textwrap.dedent`` the remainder.  ``None`` becomes the not-documented
    sentinel.
    """
    if docstring is None:
        return NOT_DOCUMENTED
    if '\n' not in docstring:
        return docstring
    doclines = docstring.split('\n')
    return "%s\n%s" % (
        doclines[0],
        textwrap.dedent('\n'.join(doclines[1:])))


def _match_header(line):
    """If ``line`` begins a known field, return (key, indent, rest); else None."""
    m = _HEADER_RE.match(line)
    if not m:
        return None
    return _ALIAS_TO_KEY[m.group("alias")], len(m.group("indent")), m.group("rest")


def _iter_fields(raw):
    """Yield (key, value) field tuples in document order from normalized raw.

    Repeated keys (e.g. several Notes) are yielded multiple times; the caller
    decides how to combine them.
    """
    lines = raw.split('\n')
    base_indent = None
    current_key = None
    buffer = []
    yield_list = []
    for line in lines:
        hdr = _match_header(line)
        is_field = False
        if hdr is not None:
            key, indent, rest = hdr
            if base_indent is None or indent <= base_indent:
                is_field = True
        if is_field:
            # Close the previous field.
            if current_key is not None:
                yield_list.append((current_key, '\n'.join(buffer).rstrip()))
            if base_indent is None:
                base_indent = indent
            # Handle an inline second header on the same line (Type/Library...).
            first_val, extras = _split_inline_simple(rest)
            current_key = key
            buffer = [first_val.strip()]
            for ekey, eval_ in extras:
                # Each inline extra is a complete single-line field.
                yield_list.append((current_key, '\n'.join(buffer).rstrip()))
                current_key = ekey
                buffer = [eval_.strip()]
        else:
            if current_key is None:
                # Preamble before any recognized header - ignore (lenient).
                continue
            buffer.append(line)
    if current_key is not None:
        yield_list.append((current_key, '\n'.join(buffer).rstrip()))
    return yield_list


def _split_inline_simple(rest):
    """Split ``rest`` into (first_value, [(key, value), ...]) at inline headers.

    Only the inline-pair keys (Type/Library/Implements) trigger a split.
    """
    matches = list(_INLINE_RE.finditer(rest))
    if not matches:
        return rest, []
    first = rest[:matches[0].start()]
    extras = []
    for i, m in enumerate(matches):
        key = _ALIAS_TO_KEY[m.group("alias")]
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(rest)
        extras.append((key, rest[start:end]))
    return first, extras


def _collapse(text):
    """Collapse whitespace/newlines in ``text`` to a single line."""
    return re.sub(r"\s+", " ", text).strip()


def _parse_phases(value):
    """Best-effort parse of a Phases field into a list of {name, description}."""
    value = value.strip()
    if not value:
        return []
    # "*any*" / "any" / "Any"
    if re.fullmatch(r"\*?\s*any\s*\*?", value, re.IGNORECASE):
        return [{"name": "any", "description": ""}]
    result = []
    for line in value.split('\n'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?P<names>[^-]+?)\s+-\s+(?P<desc>.*)$", line)
        if m:
            names = m.group("names")
            desc = m.group("desc").strip()
        else:
            names = line
            desc = ""
        for name in re.split(r"[,\s]+", names.strip()):
            if name:
                result.append({"name": name, "description": desc})
    return result


def _parse_options(value):
    """Best-effort parse of an Options field.

    Returns a list of {group, name, required, description}.  ``group`` is the
    current ``:: sub-group ::`` (or a trailing-colon sub-header), or "".
    ``required`` is True/False/None based on (REQUIRED)/(OPTIONAL) markers.
    Never raises; unrecognized lines are appended to the current option's
    description so nothing is dropped.
    """
    options = []
    group = ""
    current = None
    for line in value.split('\n'):
        if not line.strip():
            current = None
            continue
        stripped = line.strip()
        # Sub-group: ":: Foo ::"
        m = re.match(r"^::\s*(.+?)\s*::$", stripped)
        if m:
            group = m.group(1).strip()
            current = None
            continue
        # Sub-header: "Common keywords:" (a label ending in ':' with no ' - ')
        m = re.match(r"^([A-Z][\w ./-]+):$", stripped)
        if m and " - " not in stripped:
            group = m.group(1).strip()
            current = None
            continue
        # Option entry: "name - description"
        m = re.match(r"^(?P<name>\S.*?)\s+-\s+(?P<desc>.*)$", stripped)
        if m:
            desc = m.group("desc").strip()
            required = None
            if re.search(r"\(\s*REQUIRED\s*\)", desc, re.IGNORECASE):
                required = True
            elif re.search(r"\(\s*OPTIONAL\s*\)", desc, re.IGNORECASE):
                required = False
            current = {
                "group": group,
                "name": m.group("name").strip(),
                "required": required,
                "description": desc,
            }
            options.append(current)
            continue
        # Continuation of the current option's description.
        if current is not None:
            current["description"] = (
                current["description"] + " " + stripped).strip()
    return options


def _parse_examples(value):
    """Split an Examples field into one or more verbatim blocks."""
    value = value.strip("\n")
    if not value.strip():
        return []
    # Split on blank-line gaps of 2+ to separate distinct snippets.
    blocks = re.split(r"\n\s*\n\s*\n", value)
    if len(blocks) == 1:
        blocks = re.split(r"\n\s*\n(?=\[)", value)
    return [b.strip("\n") for b in blocks if b.strip()]


def _parse_requires(value):
    """Parse a Requires field into ``{"exec": [...], "caps": [...]}``.

    Recognizes ``exec:`` / ``caps:`` sub-lines (comma- or whitespace-
    separated names). A bare, unlabeled line -- the only form
    ``**requires=`` in ``~~phases~~`` supported before this schema existed
    -- is treated as a legacy ``exec`` entry, so existing docstrings and
    ``**requires=`` blocks keep parsing unchanged.
    """
    result = {"exec": [], "caps": []}
    value = value.strip()
    if not value:
        return result
    for line in value.split('\n'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(exec|caps)\s*:\s*(.*)$', line, re.IGNORECASE)
        if m:
            key = m.group(1).lower()
            names = re.split(r'[,\s]+', m.group(2).strip())
        else:
            key = "exec"
            names = re.split(r'[,\s]+', line)
        result[key].extend(n for n in names if n)
    return result


def parse_module_doc(name, docstring, path=None, repo=None):
    """Parse a module's ``__doc__`` into a structured documentation dict.

    Arguments:
        name      - the module / section-type name.
        docstring - the raw class ``__doc__`` (may be ``None``).
        path      - optional source path (modules-path entry) for provenance.
        repo      - optional repository / library directory name.

    Returns a dict with keys: name, summary, type, library, implements,
    phases, joinpoints, options, examples, fields (ordered, faithful),
    raw, source.  Always succeeds.
    """
    raw = normalize_docstring(docstring)

    # Ordered, faithful field list plus a key -> combined-value map.
    fields = []
    combined = {}
    for key, value in _iter_fields(raw):
        value = value.rstrip()
        if key in combined:
            combined[key] = (combined[key] + "\n" + value).rstrip()
            # Update the existing ordered entry too.
            for entry in fields:
                if entry["key"] == key:
                    entry["value"] = combined[key]
                    break
        else:
            combined[key] = value
            fields.append({
                "key": key,
                "label": _FIELD_LABELS.get(key, key.title()),
                "value": value,
            })

    summary = _collapse(combined.get("purpose", "")) or None

    result = {
        "name": name,
        "summary": summary,
        "type": (combined.get("type") or "").strip() or None,
        "library": (combined.get("library") or "").strip() or None,
        "implements": (combined.get("implements") or "").strip() or None,
        "phases": _parse_phases(combined.get("phases", "")),
        "joinpoints": _parse_phases(combined.get("joinpoints", "")),
        "options": _parse_options(combined.get("options", "")),
        "examples": _parse_examples(combined.get("examples", "")),
        "requires": _parse_requires(combined.get("requires", "")),
        "fields": fields,
        "raw": raw,
        "source": {"path": path, "repo": repo},
    }
    return result


# --------------------------------------------------------------------------
# Source extraction (no import required)
# --------------------------------------------------------------------------

def extract_class_docstring(source_path, class_name=None):
    """Return a module class docstring read straight from source via ``ast``.

    csmake module files name their primary class after the file stem.  This
    extracts that class's docstring without importing the module, so
    documentation can be recovered even when the module's runtime dependencies
    are not installed (e.g. a sibling library in a dev checkout).

    Returns the raw docstring string, or ``None`` if the file can't be parsed
    or has no documented class.
    """
    if class_name is None:
        class_name = os.path.splitext(os.path.basename(source_path))[0]
    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=source_path)
    except Exception:
        return None
    named = None
    first = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if first is None:
                first = node
            if node.name == class_name:
                named = node
                break
    target = named if named is not None else first
    if target is None:
        return None
    return ast.get_docstring(target, clean=False)


def discover_source_docs(package_dir, repo=None, skip=None):
    """Parse every csmake module ``.py`` in ``package_dir`` from source.

    Yields ``parse_module_doc`` results for each documented module.  Names in
    ``skip`` (already loaded elsewhere) are ignored.  Files that fail to parse
    or carry no docstring are silently skipped (lenient).
    """
    skip = skip or set()
    try:
        entries = sorted(os.listdir(package_dir))
    except Exception:
        return
    for entry in entries:
        name, ext = os.path.splitext(entry)
        if ext != ".py" or name.startswith("__") or name in skip:
            continue
        source_path = os.path.join(package_dir, entry)
        if not os.path.isfile(source_path):
            continue
        docstring = extract_class_docstring(source_path, name)
        if docstring is None:
            continue
        yield parse_module_doc(name, docstring, path=package_dir, repo=repo)


# --------------------------------------------------------------------------
# Serializers
# --------------------------------------------------------------------------

def dump_json(objs):
    """Serialize one object or a list of objects to pretty JSON."""
    return json.dumps(objs, indent=2, ensure_ascii=False)


def dump_yaml(objs):
    """Serialize to YAML.

    Uses PyYAML when available for full correctness; otherwise falls back to a
    small dependency-free emitter sufficient for the doc structure (csmake core
    must not require a YAML dependency).
    """
    try:
        import yaml  # type: ignore
        return yaml.safe_dump(
            objs, sort_keys=False, default_flow_style=False, width=1000,
            allow_unicode=True)
    except Exception:
        return _yaml_fallback(objs, 0).rstrip("\n") + "\n"


def _yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    # Use a double-quoted scalar; escape backslashes and quotes.
    if ("\n" in text or text != text.strip()
            or re.search(r'[:#\[\]{}&*!|>%@`",]', text)
            or text[0] in "-?:,[]{}#&*!|>'\"%@` "):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        escaped = escaped.replace("\n", "\\n").replace("\t", "\\t")
        return '"%s"' % escaped
    return text


def _yaml_fallback(node, indent):
    pad = "  " * indent
    lines = []
    if isinstance(node, dict):
        if not node:
            return pad + "{}\n"
        for key, value in node.items():
            if isinstance(value, (dict, list)) and value:
                lines.append("%s%s:\n" % (pad, key))
                lines.append(_yaml_fallback(value, indent + 1))
            elif isinstance(value, (dict, list)):
                lines.append("%s%s: %s\n" % (
                    pad, key, "{}" if isinstance(value, dict) else "[]"))
            else:
                lines.append("%s%s: %s\n" % (pad, key, _yaml_scalar(value)))
        return "".join(lines)
    if isinstance(node, list):
        if not node:
            return pad + "[]\n"
        for item in node:
            if isinstance(item, dict) and item:
                inner = _yaml_fallback(item, indent + 1)
                inner = inner[len(pad) + 2:]  # strip leading pad of first line
                lines.append("%s- %s" % (pad, inner))
            elif isinstance(item, list) and item:
                lines.append("%s-\n%s" % (pad, _yaml_fallback(item, indent + 1)))
            else:
                lines.append("%s- %s\n" % (pad, _yaml_scalar(item)))
        return "".join(lines)
    return pad + _yaml_scalar(node) + "\n"


def render(objs, fmt):
    """Render parsed object(s) in the requested format: json | yaml."""
    if fmt == "json":
        return dump_json(objs)
    if fmt == "yaml":
        return dump_yaml(objs)
    raise ValueError("Unknown structured doc format: %r" % fmt)
