# csmake Module Ecosystem Design

Status: **draft** — distilled from design discussion, 2026-08-23.
Sections marked *(settled)* reflect agreed direction; *(proposed)* are
concrete proposals awaiting final blessing; *(later)* are noted for a
future phase.

## Vision

csmake modules belong to packages. Packages are findable, fetchable,
verifiable, and cacheable through one core acquisition mechanism that is
equally at home in two postures, which are the same mechanism with
different configuration:

- **No-config mode**: install csmake, run a build, and every module the
  build needs materializes from the public registry. Convenient and
  deliberately *floating* — resolution tracks the registry.
- **Walled garden**: all acquisition is redirected to a curated artifact
  store / cache generation. Deterministic and replicable by
  construction.

Everything that acquires bytes — the module registry, GitHub Actions
`uses:` fetches, terraform-style providers, wget-style pickers — routes
through the same resolver and cache. This is a general csmake praxis,
not a registry feature.

## Invariants *(settled)*

Lessons from rpm, PyPI, and npm, adopted as hard rules:

1. **Metadata is static data, never executed.** No setup.py analogue, no
   install hooks, no scriptlets — ever. Install is unzip + verify.
2. **Published versions are immutable.** No unpublish, no re-tag.
   Yanking is an index flag, not a deletion; existing pins keep
   resolving.
3. **Hashes are mandatory from day one.** Two-step verification: the
   index records sha256 of the artifact; the embedded manifest records
   sha256 per file.
4. **Claims are machine-verified.** `provides_modules` is checked
   against the artifact contents at publish time; so are declared
   system requirements (lint) and doc-standard compliance (ModuleDoc).
5. **First index to claim a package name wins outright.** Version lists
   are never merged across indices and a lower-priority index can never
   outbid with a higher version. This kills the dependency-confusion
   attack class by construction.
6. **Namespace policy is decided procedurally, before scale**: the first
   PR establishing a package name in the core index requires maintainer
   approval (see Registration).

## Resolver and layered sources *(settled — implemented)*

Implemented as `CsmakeCore/SourceLayers.py` (layer loading/merging/terminal
resolution) and a refactored `CsmakeCore/ModuleRegistry.py` (consumes it for
the `csmake-module` ecosystem). Only that ecosystem is wired up so far —
GHActions'/WgetPicker's own fetch paths in other repos are a follow-up, not
touched by this pass. Three real bugs were found and fixed along the way
(none previously known): `_refresh_registry_cache` returned after the first
*reachable* source, so a second configured source's packages were never
even queried; per-package cache files from different sources would collide
on disk with no provenance; and `_build_combined_index` overwrote by
filename order rather than claiming by source priority, so "first index
wins" wasn't actually implemented. All three are covered by regression
tests (`testModuleRegistry.py`).

One core service:

    resolve(ecosystem, name, constraint) -> (artifact, hash, provenance)

Sources are an ordered list of layers, each entry carrying a scope
(package-name pattern), an ecosystem filter, and a URL. Layer
precedence: org/machine (may be **terminal**, forbidding lower layers
from adding fallthrough — this is what makes a walled garden a wall) >
project > user > built-in default.

The built-in default is exactly: the core index (csmake's GitHub) plus
the local cache. Adding any other index or source is an explicit,
configured act of trust.

`+local` and `--modules-path` are layer zero: versionless local path
sources that win outright (dev checkouts beat everything, as today).

## Cache generations *(settled — implemented)*

Cache-first resolution: if the artifact is in the cache, the cache is
authoritative. The cache changes only at explicit **remaster** time:

1. Build generation N+1 (copy-forward from N plus selective updates).
2. Point a test configuration at N+1; run the builds.
3. Promote: flip the default generation. Keep N for rollback.

The generation is the determinism boundary — there is **no lockfile**.
Resolution is a pure function of (configuration, generation), Go-style:
config resolves, the generation manifest carries the integrity hashes
(the go.sum analogue). A build outside any curated generation
(no-config mode) resolves live and floats; that is by design and should
be documented as such.

Implemented as `CsmakeCore/Generations.py`: `~/.csmake/generations/<name>.json`
(`{"packages": {pkg: version}, "parent": <previous-name-or-null>}`) plus a
`current` pointer file. `remaster(name, combined_index, packages=None)`
re-resolves each package's `latest` against the registry's combined index
(defaulting `packages` to the current generation's own set, so
`remaster('gen-N+1')` with no args is exactly "copy-forward plus
re-resolve"); `promote(name)` flips `current`; `rollback()` reverts to the
current generation's own `parent`. Generations are immutable once
created — `remaster` refuses to overwrite an existing name, matching the
registry's own "published versions are immutable" invariant.

**A generation is just another pin source**, confirming the simplification
found while designing this phase: it plugs into the exact resolution
machinery `[~~packages~~]` already uses (Phase 3), one priority tier
lower — loaded first, then `[~~packages~~]` entries overwrite any
matching key. `--generation=<name>` selects one for a single run
(defaulting to whatever `current` points to), e.g. to test a freshly
remastered generation before promoting it. No new resolution code was
needed for this — verified end to end with an unpinned section correctly
resolving to a generation's pinned (non-"latest") version.

**Walled garden**: `CsmakeModules/MirrorSync.py` downloads every package a
generation pins and re-hosts it as a `static-index` source directory
(Phase 1's format) — `index.json`, `index/<pkg>.json`, `artifacts/*.csm` —
so the freshly mirrored garden is immediately usable by pointing a
`sources.json` entry at it. Its core logic (`mirror_sync`) is a plain,
directly-testable function using only `urllib`/`hashlib`, doing its own
sha256 verification against the index's recorded hash — the same
two-step-verification philosophy as `ModuleRegistry`, not a dependency on
it (it needs the raw `.csm` bytes preserved for re-hosting, which
`ModuleRegistry.install()` doesn't keep around since it extracts
in place). Re-syncing is idempotent: an already-mirrored, hash-matching
artifact is never re-downloaded, so adding a newly promoted generation to
an existing garden only fetches what changed. An optional `base-url`
option points mirrored entries at wherever the directory will actually be
served from; without one, entries point at the local files directly
(`file://...`), which is what makes local verification possible before
any deployment step exists.

**Frozen mode**: `--frozen` (`ModuleRegistry(frozen=True)`) skips the
registry-cache refresh entirely (network-touching) and makes `install()`
fail closed — return `None` with a clear error — for anything not
already present in the local cache, rather than attempting a download.
Verified two ways: a dedicated test patches `urlopen` to explode if
called, and a round-trip test (mirror a generation into a fresh
directory, point a *only* source at it, resolve once unfrozen to warm
the cache, then resolve again frozen) confirms a build can resolve
entirely from a mirrored garden with zero network access.

## Package format: .csm as wheel *(settled — implemented)*

A .csm is a zip carrying `csmake-manifest.json` (metadata + per-file
sha256). It additionally carries a wheel `dist-info` (METADATA / WHEEL /
RECORD), making one artifact valid in both dialects. What this buys:
hostable in any URL-addressable store (S3, nginx, Artifactory generic),
openable by standard tooling. What it does **not** mean: PyPI, pip
resolution, PEP 503 endpoints, or bandersnatch as infrastructure. csmake
keeps its own installer (unzip, two-step verify, seed sys.path) — the
only installer honoring the any-Python-version constraint.

Wheel-writing lives **once**, in core, as a `CsmakeCore` library
(dist-info emission, RECORD hashing, zip assembly). Core's
`CsmakeModulePackager` composes it with the csmake manifest;
csmake-packaging's `WheelPackage` derives from the same primitive for
general Python projects.

Implemented as `CsmakeCore/WheelWriter.py` (stdlib-only: METADATA/WHEEL/
RECORD/top_level.txt generation, PEP 427 name/version escaping). Real
interop bug found and fixed while porting `WheelPackage` onto it: the
wheel filename's distribution/version segments and the dist-info
directory name must use identical escaping (runs of non-alphanumerics →
`_`), or a consumer deriving one from the other — as the reference
`wheel` package's own reader does — computes the wrong path and can't
find RECORD at all. Verified against that reference implementation, both
in `testWheelWriter.py` and by building csmake-packaging's own wheel
end-to-end and opening it with `wheel.wheelfile.WheelFile`.

## Core vs. csmake-packaging split *(settled — implemented)*

**Core owns its own substrate: format (read and write), acquisition,
cache, and format primitives. csmake-packaging owns packaging other
people's software.** Consequences:

- `CsmakeModulePackager` (and the index-entry emitter) promote to core —
  the `npm pack` precedent: making a package must not require fetching
  a package. Moved to `CsmakeModules/CsmakeModulePackager.py` in core;
  now also embeds wheel dist-info and supports a `registry-checkout`
  option that merges the index entry into a local checkout on disk
  (opening the PR stays a manual, explicit step).
- `WheelPackage` stays in csmake-packaging, rebased onto the core wheel
  primitive; also ported off Python 2 (`StringIO`, `sys.maxint`,
  `.iteritems()`) in the process — it would have crashed immediately
  under Python 3 before this pass.
- `DebianPackage` **stays in core** *(revisited this session)* — moving
  it would break the "a bare checkout builds the .deb" guarantee
  `BUILDING` documents; the resulting core/packaging asymmetry (core
  privileges Debian, every other packager needs csmake-packaging) is
  accepted as a known inconsistency rather than fixed by breaking that
  guarantee.

## Index and registration *(settled — implemented)*

The index is a directory of per-package JSON files in csmake's GitHub
(module→package map via `provides_modules`, package→versions/urls/
hashes). Author-controlled via the pithy flow:

- CODEOWNERS entry per index file (implemented:
  `csmake-registry/CODEOWNERS`); a validating GitHub Action
  (`.github/workflows/validate-index.yml`, running
  `scripts/validate_index_entry.py`) checks sha256 presence/match and
  `provides_modules` against the artifact. ModuleDoc lint is deferred —
  no clean standalone distribution of `ModuleDoc.py` yet.
- First PR establishing a package name: maintainer approval (the
  namespace gate) — enforced via branch protection requiring the
  CODEOWNERS review; **enabling that repo setting is a manual step**,
  not something committed code can turn on.
- Subsequent version PRs from the file's owner: automerge on green CI
  *(automerge itself not yet wired up — the validation gate it depends
  on is; automerge configuration is a repo-settings/workflow follow-up)*.
- Registry history is a git log — auditable, mirrorable by clone, no
  service to operate.

Core ships the authoring modules that build the .csm and generate the
index entry (`CsmakeModulePackager`'s `registry-checkout` option); it
merges the entry into a local registry checkout on disk. Opening the PR
remains a manual, explicit step (publishing to others stays a confirmed
action, not something automated).

A static `index.json` manifest listing the package files makes any dumb
file server a registry (the GitHub Contents API is one transport, not
the protocol) — **implemented**: `SourceLayers`' `static-index` source
type, consumed by `ModuleRegistry`.

## Versioning and the module loader *(settled — implemented)*

Modules carry versions; they default to their package's version. Consumers
pin **packages**; pinning a module would be sugar for pinning the package
that provides it (per-module version overrides in `provides_modules`
remain future work — not needed for the loader mechanism itself).

**Loader projection, as built**: a pin is resolved *per section*, not as a
single global "bare name owner" computed up front. `_loadModules` gets an
optional `pin=(package, version)`; when given, it tries that package's own
cached root (`~/.csmake/modules/<pkg>/<ver>/CsmakeModules/<Name>.py`)
first, loading a match under an internal mangled `sys.modules` key
(`Name@@package@@version`) that never touches the bare/unpinned slot. If
the pinned root doesn't provide the target, resolution falls through to
the normal search unchanged — "pinned package, then core, then bare."
With no pin anywhere, this whole path is never entered, so the governing
invariant (byte-identical to pre-pin behavior) holds by construction
rather than by the two implementations happening to agree.

Two safety rules, both realized directly by the existing architecture
rather than needing new machinery:

- **Intra-package references bind to their own package's version.** A
  loading-context stack (`self._pinContext`) is pushed with the active pin
  before `imp.load_source` executes a pinned module's top-level code, and
  popped after. `load_module` (the custom import hook backing
  `CsmakeModules.*` lookups) checks this stack, so a sibling import
  triggered *during* that load — `from CsmakeModules.Helper import
  Helper` — resolves within the same pinned version.
- **Core classes never duplicate.** Falls out for free: `from
  CsmakeCore.CsmakeModule import CsmakeModule` is an ordinary Python
  package import, never routed through the custom `CsmakeModules` loader
  at all, pinned or not.

**Two subtle bugs found and fixed while implementing this** (both
invisible until multiple versions were actually exercised side by side in
the same build):

- Python's own import machinery auto-populates `sys.modules` under the
  *dotted* `CsmakeModules.<Name>` key as a side effect of the legacy
  `find_module`/`load_module` loader protocol — a cache nothing in
  csmake's own code reads (its caches are the bare `CsmakeModulesModule`
  dict and the pin-mangled key), but one that short-circuits the import
  statement *before* `load_module` is ever called again. Left alone, a
  version resolved for one section leaked into a later section with a
  different pin purely via this side-channel cache. Fixed by clearing all
  `CsmakeModules.*` dotted entries once per section dispatch.
- `_constructModulePaths` memoizes its result from `sys.path`. A `**uses`
  pin that triggers a fresh install re-seeds `sys.path` (so an unpinned
  section elsewhere can see the newly-installed version as "greatest in
  play" — see resolution tier 3 below), but without also dropping the
  memoized path list, a later unpinned lookup kept using the list computed
  *before* that install happened. Fixed by invalidating
  `modulePathConstruct` alongside the reseed, mirroring how the
  pre-existing registry-autoload fallback already did the same after
  appending its own freshly-downloaded path.

Both are covered by regression tests in `testVersionedLoader.py`, including
one that distinguishes "greatest version actually installed in this
build" from "whatever the registry calls latest" — the two must not be
conflated, and only the fix above keeps them apart correctly.

### Pin syntax *(settled — implemented)*

Ambient spec-level pins in a built-in passive section, exact versions
only (ranges live in package manifests as author compatibility claims,
never in specs):

    [~~packages~~]
    csmake-packaging=1.1.5
    csmake-swak=1.1.15

Use-site override via a `**` special option (the existing convention
for csmake-processed options; deliberate GHA echo; no grammar impact on
`[Type@id]` headers):

    [RpmPackage@rpm-legacy]
    **uses=csmake-packaging@1.1.4

**Resolution order for package P at section S, as implemented:**

1. S's `**uses` pin — tried against P@v's own cached root directly; a
   miss falls through to (3) rather than failing.
2. `[~~packages~~]`'s ambient pin for P — consulted specifically inside
   the pre-existing registry-autoload fallback (the "nothing found
   locally" branch), via a new `pinned_versions` argument to
   `ModuleRegistry.find`. A dev checkout / `--modules-path` entry (layer
   zero, versionless) already won in step 3 if it had the module, so this
   only matters when nothing local provides it.
3. Normal `+local`/`+path` search — in practice this is where "greatest
   version among other sections' `**uses` pins" actually happens: each
   `**uses` that triggers a fresh install re-seeds `sys.path` with
   whatever is now the greatest cached version for P (see the bug-fix
   note above), so an unpinned section's ordinary search finds it here
   without any separate "collect every pin and compare" step.
4. Registry `latest` (today's existing auto-download fallback, now also
   honoring the `[~~packages~~]` pin from step 2 first).

**Simplified relative to the original proposal**: ambient
`[~~packages~~]` pins are not yet integrated with `SourceLayers`' own
layering (terminal garden / project / user) — they're a single,
buildspec-level dict, consulted only at the registry-fallback point
described above. Extending them to interact with source layers, and the
cache-generation default (tier 4 in the original proposal), are Phase 5
work, not built yet.

`[~~packages~~]` also takes over the package half of the old
`**requires` example usage, leaving `**requires` purely system-level.

## System dependencies *(settled tiers — implemented at the dispatch scope)*

Three tiers of ownership:

1. **Module authors declare** — the only party that knows what their
   code shells out to.
2. **Users declare nothing by default** — the closure walk derives the
   union. `**requires` in `~~phases~~` remains as the spec-level
   supplement for what only the build knows (Shell sections calling
   odd tools).
3. **The garden refines** — platform name translation and/or pinned
   images.

csmake **knows and tells, never installs** (the rpm-scriptlet lesson).
Verified directly: a dedicated test patches `subprocess.run`/`Popen`/
`os.system` to explode if called, then runs the preflight check against
a missing requirement — it must never touch any of them.

### Declaration: the docstring is the manifest *(settled — implemented)*

Authors declare in the module docstring, in the ModuleDoc semi-YAML
standard:

    Requires:
        exec: rpmbuild, gpg
        caps: docker-daemon

Implemented as `ModuleDoc._parse_requires` (a new `requires` field
alongside the existing `dependencies`, which stays package-level). A
bare, unlabeled line — `**requires=`'s only form before this schema
existed — is treated as a legacy `exec` entry, so `phases.py`'s own
long-standing docstring example (`csmake-providers` / `csmake-swak` /
`n81`, one name per line) keeps parsing unchanged.

`CsmakeModulePackager` extracts this via `ModuleDoc.extract_class_docstring`
(source-only, no import needed) at package time into per-module
`system_requires` in the csmake-manifest, unioned across every included
module. Per-module-vs-package-level granularity and the publish lint are
not built — `CsmakeModulePackager` doesn't publish-lint anything yet.

### Checking *(settled — implemented at the "dispatch" scope)*

- `exec` entries: checked via `shutil.which` (portable, honest).
- `caps` entries: a pluggable checker registry
  (`CliDriver.register_prereq_checker(capname, checker)`, mirroring
  `register_extension`) — a package can register a callable for a cap
  name it ships a checker for (e.g. a `docker-daemon` checker pinging the
  socket). An unregistered cap reports "declared, unverifiable" and never
  escalates to a failure even under `--strict-prereqs` — that flag
  escalates *checked, failing* requirements, not merely-unknown ones. A
  checker that raises is treated as a failure, not a crash.
- Translation table: `CsmakeCore/SystemPackageHints.py`, seeded from what
  today's modules already need (gpg, rpmbuild, dpkg-dev, chrpath, ...);
  a lookup miss simply omits the hint rather than failing.
- **Implemented scope: the owning section's declared requirements, at
  dispatch** (`CliDriver._preflightCheck`, called from
  `getSectionTypeInstance` right before a resolved class is instantiated
  — the class is already in hand, so this costs nothing extra to reach).
  Non-strict (default): warns and the section proceeds. `--strict-prereqs`:
  raises before the section runs, with a message naming exactly what's
  missing — "RpmPackage... not found on PATH (try installing 'rpm-build')"
  — not a traceback partway through the section's own work.
  **Not implemented**: the other two scopes from the original proposal —
  a full-closure report at fetch time, and a whole-command union at build
  start before any section runs. Per-section-at-dispatch turned out to be
  the tractable, low-risk increment; the other two need a command's full
  step tree resolved up front (including nested multicommand references),
  which is a larger, separate piece of work.
- Machine-readable output (`--prereqs-format=json`) and the fully
  hermetic caps→pinned-container path are still *(later)*, alongside the
  unbuilt upfront scopes above.

## Preinstall / fetch *(settled)*

A static walk of the buildspec graph (section types + includes +
ecosystem extensions enumerating their artifacts, e.g. workflow `uses:`
lines) resolves the closure into the cache before execution. Modules
that instantiate other modules dynamically from option values declare
it (`Uses-Sections:` in the docstring, machine-checkable) or are caught
by a recorded run. Preinstall warms the cache and emits the prereqs
report; determinism still comes from the generation, not from the walk.

## Phasing (suggested order)

1. Resolver + layered source config in core; `--modules-path` becomes a
   layer; static `index.json` for dumb-server registries.
2. Promote CsmakeModulePackager + wheel primitive + index-entry emitter
   to core; registry CODEOWNERS/CI automerge flow.
3. `[~~packages~~]` + `**uses` + versioned-name loader projection.
4. Docstring `Requires:` + preflight (`_process_requires` body) +
   translation table.
5. Cache generations (remaster/promote/rollback tooling); walled-garden
   package (mirror-sync, frozen mode).
6. DebianPackage migration out of core; hermetic container path.

## Open questions

- Final blessing of the `[~~packages~~]` / `**uses` spellings.
- ModuleDoc: add `Requires` to the field aliases (distinct from
  `Dependencies`, which stays package-level).
- Index signature reservation (room for detached signatures per entry so
  mirrors/gardens can re-sign later without a format break).
- Scoped names (`org/package`) if the curated flat namespace ever
  becomes a growth bottleneck.
