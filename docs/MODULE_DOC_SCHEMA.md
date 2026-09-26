# csmake Module Documentation Standard

csmake modules document themselves. Each module class carries its documentation
in its Python `__doc__` docstring using a lightweight, semi-structured
"semi-YAML" format. That same text is what `csmake --list-type=<Module>` prints,
what feeds the man pages, and — via `--list-type-format` — what tooling and the
documentation website consume as structured JSON or YAML.

This document is the canonical, **refinable** standard. It is intentionally
lenient: the parser never fails on free-form prose, so existing modules keep
working while new modules adopt the structure more fully over time.

## Where it lives

The docstring is the first string literal in the module's class body:

```python
class Shell(CsmakeModuleAllPhase):
    """Purpose: Execute a shell script
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
```

## Normalization

Before parsing, the docstring is normalized exactly as `--list-type` renders it:

- The **first line** is kept verbatim (it begins `Purpose: ...`).
- The **remaining lines** are run through `textwrap.dedent`, which removes the
  common leading indentation so top-level field headers land at column 0 and
  nested content keeps its relative indentation.

The normalized text is preserved verbatim in the `raw` field of the structured
output, guaranteeing the structured view never loses anything relative to the
plain-text view.

## Fields

A **field** is introduced by a recognized header at the top-level indent,
followed by a colon, e.g. `Options:`. Its value is every following line until
the next top-level header. Field order is free — modules vary, and the parser is
order-independent.

| Header(s) | Key | Meaning |
|-----------|-----|---------|
| `Purpose` | `purpose` | One-line summary (may wrap onto indented continuation lines). **Required**, always first. |
| `Type` | `type` | `Module`, `Submodule`, `Aspect`, … |
| `Library` | `library` | Owning package, e.g. `csmake (core)`, `csmake-swak`. |
| `Implements` | `implements` | Interface a submodule/aspect implements (e.g. `Packager`, `Signature`). |
| `Phases` / `Phase` | `phases` | Phases the module runs in. `*any*`/`Any` means all phases; otherwise a list, optionally `name - description` per line. |
| `Joinpoints` (`… introduced`) | `joinpoints` | Aspect join points. |
| `Flowcontrol Advice` (`… introduced`) | `flowcontrol` | Aspect flow-control advice. |
| `Options` | `options` | Section key/value options (see below). |
| `Flags` | `flags` | Boolean-style options. |
| `Notes` / `Note` / `NOTE` / `Also Note` | `notes` | Free-form notes (repeats are concatenated). |
| `Default` / `Default is` | `default` | Default behavior. |
| `Examples` / `Example` / `Usage` | `examples` | csmakefile snippets (verbatim). |
| `See Also` / `See` / `References` | `see_also` | Related modules/links. |
| `Description` | `description` | Extended prose. |
| `Environment` | `environment` | Environment variables read/written. |
| `Dependencies` | `dependencies` | External requirements. |
| `Install Map Definitions` | `install_map` | Packager install-map contract. |
| `Package Name Format` | `package_name_format` | Packager naming. |
| `File Tracking` | `file_tracking` | File-tracking behavior. |

### Inline pairs

`Type`, `Library`, and `Implements` commonly share one physical line and are
split apart, e.g.:

```
Type: Module   Library: csmake (core)
```

Two or more spaces separate the inline headers. (Only these three keys are split
mid-line, so prose like `see: http://...` is never mistaken for a header.)

### Options sub-structure

Within `Options:` the parser extracts individual options best-effort:

- `:: Sub-group ::` or a `Trailing-colon Label:` starts a named sub-group.
- An entry is `name - description`. The name may include `(<phase>)`, `<...>`,
  or `=value`. Continuation lines extend the previous description.
- `(REQUIRED)` / `(OPTIONAL)` in the description sets `required` to
  `true` / `false` (otherwise `null`).

Lines that don't fit are appended to the current description, so nothing is
dropped.

### Recommended ordering

`Purpose` → `Type` / `Library` → `Implements` → `Phases` → `Options` →
`Joinpoints` / `Flowcontrol Advice` → `Notes` → `Examples` → `See Also`.
Ordering is a convention, not enforced.

## Structured output: `--list-type-format`

```
csmake --list-type=<Module> --list-type-format=json
csmake --list-types        --list-type-format=json
csmake --list-types        --list-type-format=yaml
```

- `text` (default) — unchanged human-readable output.
- `json` — a JSON **array** of module objects (a single `--list-type` still
  yields a one-element array, for uniformity).
- `yaml` — the same data as YAML.

For the full catalog (`--list-types`), modules whose runtime dependencies are
not installed in the current checkout are still included: their documentation is
recovered from source via `ast` (no import required), so the catalog is complete
across every library on `--modules-path`.

### Object shape

```json
{
  "name": "Shell",
  "summary": "Execute a shell script",
  "type": "Module",
  "library": "csmake (core)",
  "implements": null,
  "phases": [{ "name": "any", "description": "" }],
  "joinpoints": [],
  "options": [
    { "group": "Script Definition Options",
      "name": "command(<phase>)",
      "required": null,
      "description": "Shell command to execute in specified phase ..." }
  ],
  "examples": ["[Shell@my-command]\ncommand(build)=echo \"Hello, World\""],
  "fields": [
    { "key": "purpose", "label": "Purpose", "value": "Execute a shell script" }
  ],
  "raw": "Purpose: Execute a shell script\nType: Module   Library: csmake (core)\n...",
  "source": { "path": "./CsmakeModules", "repo": null }
}
```

- `fields` is the ordered, faithful list of every parsed field (the structured
  conveniences above are derived from it).
- `raw` is byte-for-byte what the `text` format prints.

## Implementation

The parser and emitters live in
[`CsmakeCore/ModuleDoc.py`](../CsmakeCore/ModuleDoc.py); the `--list-type-format`
flag is handled in `CsmakeCore/CliDriver.py` (`dumpTypes`). Tests are in
[`CsmakeCore/tests/testModuleDoc.py`](../CsmakeCore/tests/testModuleDoc.py).
