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

## Resolver and layered sources *(settled)*

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

## Cache generations *(settled)*

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

## Package format: .csm as wheel *(settled)*

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

## Core vs. csmake-packaging split *(settled)*

**Core owns its own substrate: format (read and write), acquisition,
cache, and format primitives. csmake-packaging owns packaging other
people's software.** Consequences:

- `CsmakeModulePackager` (and the index-entry emitter) promote to core —
  the `npm pack` precedent: making a package must not require fetching
  a package.
- `WheelPackage` stays in csmake-packaging, rebased onto the core wheel
  primitive.
- `DebianPackage` migrates **out** of core to csmake-packaging *(later)*
  — autoloading makes this workable, and it dissolves the historical
  core-privileges-Debian asymmetry.

## Index and registration *(settled)*

The index is a directory of per-package JSON files in csmake's GitHub
(module→package map via `provides_modules`, package→versions/urls/
hashes). Author-controlled via the pithy flow:

- CODEOWNERS entry per index file; a validating GitHub Action checks
  sha256 presence/match, `provides_modules` against the artifact, and
  ModuleDoc lint.
- First PR establishing a package name: maintainer approval (the
  namespace gate).
- Subsequent version PRs from the file's owner: automerge on green CI.
- Registry history is a git log — auditable, mirrorable by clone, no
  service to operate.

Core ships the authoring modules that build the .csm, generate the
index entry, and open the PR, so publishing works from a bare csmake
install.

A static `index.json` manifest listing the package files makes any dumb
file server a registry (the GitHub Contents API is one transport, not
the protocol) *(near-term gap to close)*.

## Versioning and the module loader *(settled rules, proposed syntax)*

Modules carry versions; they default to their package's version, with
per-module overrides as author-side metadata (`provides_modules`
becomes name→version). Consumers pin **packages**; pinning a module is
sugar for pinning the package that provides it.

**Loader projection**: versioned cache roots
(`~/.csmake/modules/<pkg>/<ver>/`) project into the flat CsmakeModules
namespace. The newest version *in play in this build* takes the bare
name; other in-play versions take identifier-mangled versioned names
(e.g. `RpmPackage__v1_1_4`). Nothing on disk is renamed — projection is
a path-construction-time decision, made under the existing imp lock.

Two safety rules:

- **Intra-package references bind to their own package's version.**
  While loading package P@v, `CsmakeModules.*` lookups resolve first
  within P@v, then core, then bare. (An internal reference is a
  reference *from* that package, so it takes the package's version —
  the same defaulting rule modules themselves follow.)
- **Core classes never duplicate.** `CsmakeModule` and other core base
  classes load from core exactly once, so no isinstance-across-copies
  hazards. Sections interact through the environment and file tracker
  (data, not object graphs), which is what makes side-by-side versions
  viable at all.

### Pin syntax *(proposed)*

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

**Resolution order for package P at section S:**

1. S's `**uses` pin.
2. Ambient pin from the highest-precedence config layer
   (terminal garden > project `[~~packages~~]` > user config).
3. Greatest version among other sections' `**uses` pins for P
   (fires only when no ambient pin exists).
4. The cache generation's default for P.

Registry "latest" participates only in no-config mode, where the live
registry effectively is the generation. Preflight lints that `**uses`
names a package providing the section's type.

`[~~packages~~]` also takes over the package half of the old
`**requires` example usage, leaving `**requires` purely system-level.

## System dependencies *(settled tiers, proposed mechanics)*

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

### Declaration: the docstring is the manifest *(proposed)*

Authors declare in the module docstring, in the ModuleDoc semi-YAML
standard:

    Requires:
        exec: rpmbuild, gpg
        caps: docker-daemon

`CsmakeModulePackager` extracts this via ModuleDoc at package time into
per-module `system_requires` in the csmake-manifest. Granularity is
per-module with a package-level shared default (mirrors module version
defaulting). Publish lint soft-warns when a module visibly shells out
but declares nothing.

### Checking *(proposed)*

- `exec` entries: core checks PATH presence (portable, honest).
- `caps` entries: pluggable checker modules (packages or the garden
  ship them; e.g. a `docker-daemon` checker pings the socket). Unknown
  caps report "declared, unverifiable" — never a hard default failure;
  garden config or a strict flag escalates.
- Translation table (exec name → apt/dnf/brew package hints): core
  ships defaults as data, packages extend, garden config overrides —
  the same layering as everything else.
- Three scopes, one function: full closure at fetch time (the report),
  command closure at build start (the warning), the owning section's
  declared execs at dispatch (so failures read
  "RpmPackage requires rpmbuild — apt install rpm", not a traceback
  forty minutes in). `_process_requires` in phases.py becomes the
  preflight entry point.
- Machine-readable output (`--prereqs-format=json`, echoing
  `--list-type-format`) feeds garden image generation *(later)*; the
  fully hermetic path maps caps to pinned container images run via
  docker-runtime/chroot *(later)*.

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
