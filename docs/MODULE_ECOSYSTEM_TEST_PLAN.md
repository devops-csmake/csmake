# Module Ecosystem: Manual Verification Test Plan

Companion to `docs/MODULE_ECOSYSTEM_DESIGN.md`. That document's six phases
are all unit-tested and were dogfooded piecemeal while building them (a
wheel opened by the reference `wheel` library, `HermeticShell` run against
a real Docker daemon, etc.) — this is the pass that exercises them
**together**, by hand, the way an actual user would, before merging
[csmake#64](https://github.com/devops-csmake/csmake/pull/64),
[csmake-packaging#17](https://github.com/devops-csmake/csmake-packaging/pull/17),
and [csmake-registry#1](https://github.com/devops-csmake/csmake-registry/pull/1).

Each item: **Goal** (why this matters), **Steps** (concrete commands),
**Expected** (what "pass" looks like). Check items off as you go.

## Prerequisites

- [ ] `csmake` checked out on `adding-ghactions-auto-download`
      (PR #64), tests green: `./csmake --command=test test`
- [ ] `csmake-packaging` checked out on `module-ecosystem` (PR #17),
      tests green: `python3 <path-to-core>/csmake --command=test test`
- [ ] Docker available locally (only needed for the `HermeticShell`
      section)

**Known blocker, found while drafting this plan** — the `--generation`
setting's help text describes activating a generation via a
`GenerationPromote` module and creating one via `GenerationRemaster`;
neither module actually exists (only the underlying
`CsmakeCore/Generations.py` class does, consumed today by `MirrorSync`
and `CliDriver`'s pin-loading). Section 5 below uses direct Python calls
against `Generations()` as the working interface. Worth deciding: build
the thin CLI-module wrappers the help text promises, or correct the help
text to describe the Python API. Flagging rather than fixing silently,
since it's a scope decision, not just a bug.

**Known blocker, pre-existing** — `csmake-swak` and `csmake-packaging`
aren't fetchable via the real registry yet (no release cut, `sha256`
still empty, [csmake-registry#1](https://github.com/devops-csmake/csmake-registry/pull/1)
intentionally red). Only `csmake-ansible`, `csmake-ghactions`,
`csmake-docker-runtime`, and `csmake-node-runtime` are live today —
Section 3 is scoped to those.

---

## 1. Traditional path & resolver priority

**Goal**: confirm nothing in six phases of new machinery disturbed the
paths that predate all of it, and that "already have it locally" always
wins over "go fetch it."

- [ ] **Bare-checkout Debian build still self-sufficient.** In a clean
      `csmake` checkout with nothing else on the modules path:
      `./csmake clean package`. **Expected**: builds the `.deb` with no
      `--modules-path` needed — the specific guarantee `BUILDING`
      documents, and the reason `DebianPackage` was kept in core this
      round rather than moved out with the other packagers.
- [ ] **Full catalog dump across everything real.** With `csmake-swak`
      and `csmake-ghactions` checked out as siblings:
      `./csmake --modules-path=':../csmake-swak:../csmake-ghactions' --list-types --list-type-format=json | python3 -m json.tool`.
      **Expected**: valid JSON, one entry per module, no parse
      exceptions — this exercises `ModuleDoc` against real docstrings at
      scale, not the synthetic fixtures the unit tests use.
- [ ] **Local checkout beats the registry.** With `csmake-ansible`
      cloned as a sibling and also live in the real registry: run a
      build referencing `[Ansible@x]` twice — once with
      `--modules-path=':../csmake-ansible'`, once without. **Expected**:
      first run uses the local checkout (no network fetch — check with
      `--dev-output --debug` for "Searching module from path"
      entries); second run falls through to the registry and downloads
      into `~/.csmake/modules/`.
- [ ] **Cache-first, not fetch-every-time.** After the registry fetch
      above has happened once, delete nothing and run the same build
      again with network disabled (e.g. `--frozen`, or literally
      disconnect). **Expected**: second run succeeds from
      `~/.csmake/modules/csmake-ansible/<version>/` with no network
      attempt.
- [ ] **Terminal source blocks fallthrough** (only if you want this path
      exercised — it's the walled-garden mechanism, not something a
      typical build hits). Point `~/.csmake/config.json` at a
      `terminal: true` source that doesn't have `csmake-ansible`, then
      try to resolve it. **Expected**: resolution fails rather than
      falling through to the public default — confirms a garden is
      actually a wall.

## 2. Packaging

**Goal**: every packager in `csmake-packaging` still produces valid
output after the `WheelPackage`/`CsmakeModulePackager` rework — not just
the two already verified this round.

Already verified this session (real, not just unit-tested):
`CsmakeModulePackager` (dist-info + manifest, round-tripped through a
real build) and `WheelPackage` (built `csmake-packaging`'s own wheel,
opened it with `wheel.wheelfile.WheelFile`, all 24 files hash-verified).

- [ ] `RpmPackage` — `rpmbuild` must be on PATH (this is also a good
      moment to check the Section 3 preflight message if it isn't).
- [ ] `HomebrewBottle`
- [ ] `HomebrewCask`
- [ ] `ApplePackage` (macOS `.pkg`)
- [ ] `CSUPackage`
- [ ] `DebianPackage` via `csmake-packaging`'s own `debian-only` command
      (distinct from Section 1's core-checkout `.deb` — this exercises
      the sibling-checkout path `BUILDING` documents for everything
      except Debian).
- [ ] **Publish round trip** — the one test that proves the registry
      story end-to-end, not just its pieces: build a `.csm` with
      `CsmakeModulePackager`'s `registry-checkout` option pointed at a
      scratch directory, confirm the merged `index/<name>.json` is
      valid, put that directory behind a `static-index` source
      (`sources.json` → `{"type": "static-index", "url": "file://..."}`),
      then from a **second**, separate csmake invocation, reference the
      package by module name with nothing else on the modules path and
      confirm it autoloads and runs.

## 3. Registry autoload in real flows

**Goal**: `find()` returning a path isn't the same as the module actually
working once loaded.

- [ ] **Ansible, cold.** No `csmake-ansible` checkout, no `ansible`
      binary installed. Reference `[Ansible@x]` in a build.
      **Expected**: preflight (Section 4 below covers this in depth)
      reports the missing `exec` cleanly — "not found on PATH, try
      installing..." — not a raw traceback.
- [ ] **Ansible, warm.** With `ansible`/`ansible-playbook` actually on
      PATH, run a real (trivial) playbook through `[Ansible@x]` or
      `[AnsiblePlaybook@x]`. **Expected**: it runs for real, not just
      "module loaded."
- [ ] **GitHub Actions, a real flow, not just the module.** Use the
      extension mechanism to run an actual workflow YAML as a csmakefile
      (the branch's original scope) with a step from `csmake-ghactions`
      — confirm the workflow parses, the action resolves and downloads
      via `GHActions`/`GHActionsShell`, and the step actually executes.
      This exercises the extension discovery mechanism together with
      registry autoload, which neither half tests alone.

## 4. Package pins & versioned loader (highest risk)

**Goal**: this phase touches the shared module-loader namespace — the
one place a bug could silently corrupt an unrelated, unpinned build. It
has unit tests against synthetic fixtures only; nothing here has been
verified by hand with real packages yet.

- [ ] **Baseline: unpinned build is unaffected.** Run an ordinary build
      referencing a couple of `csmake-packaging` modules with no
      `[~~packages~~]` and no `**uses` anywhere. **Expected**: behaves
      identically to a build on a pre-pinning checkout — this is the
      regression gate the design doc calls out explicitly.
- [ ] **Ambient pin.** Add `[~~packages~~]` with
      `csmake-packaging=<older-version>` (requires two versions actually
      present in `~/.csmake/modules/csmake-packaging/`, e.g. by pinning
      once via `**uses` first to populate the cache, per the resolution
      order in the design doc). **Expected**: sections with no `**uses`
      of their own resolve to the ambient-pinned version.
- [ ] **Use-site override.** Add `**uses=csmake-packaging@<older-version>`
      to one section while another section in the *same build* is
      either unpinned or pinned to a different version. **Expected**:
      each section runs against its own pinned version — this is the
      actual side-by-side-versions claim; verify by having each
      version's module do something observably different (e.g. log its
      own version string) and checking both appear correctly attributed
      in the same build's output.
- [ ] **Intra-package cross-import correctness.** With two versions of
      `csmake-packaging` pinned side by side (previous step), confirm a
      module that imports a sibling from its own package
      (`RpmPackage`'s use of `Packager`, say) sees its *own* package
      version's sibling, not the other pinned version's — this is the
      specific bug class the design doc flags as the dangerous one.

## 5. Cache generations, MirrorSync, `--frozen`

**Goal**: an entire subsystem (remaster/promote/rollback, walled-garden
mirroring, fail-closed builds) with zero manual verification so far.

Using the direct `Generations()` API per the blocker noted above:

```python
from CsmakeCore.Generations import Generations
from CsmakeCore.ModuleRegistry import ModuleRegistry

registry = ModuleRegistry()
combined = registry._get_combined_index()
gens = Generations()
gens.remaster('gen-1', combined)   # packages=None -> re-resolves 'latest' for everything currently pinned
gens.promote('gen-1')
print(gens.current_name())          # 'gen-1'
```

- [ ] **Remaster + promote.** Run the snippet above. **Expected**: a
      new `~/.csmake/generations/gen-1.json` exists with resolved
      versions, `current` now points at it.
- [ ] **`--generation` selects for a single run.** Remaster a second
      generation (`gens.remaster('gen-2', combined)`) without promoting
      it, then run a build with `--generation=gen-2`. **Expected**:
      pins resolve against `gen-2`'s versions even though `current`
      still points at `gen-1` — this is the "test before promoting"
      story.
- [ ] **Rollback.** `gens.rollback()` after promoting `gen-2`.
      **Expected**: `current_name()` reverts to `gen-1` (its parent).
- [ ] **MirrorSync produces a working static-index directory.**
      `[MirrorSync@garden]` with `result=<scratch-dir>`, then inspect
      `<scratch-dir>/index.json` and `<scratch-dir>/index/*.json` —
      **Expected**: valid `static-index` layout, matching Section 1's
      format, immediately usable as a `sources.json` entry.
- [ ] **Idempotent re-sync.** Run the same `MirrorSync` step again with
      nothing changed. **Expected**: no re-downloads (check timestamps
      or add `--dev-output --debug` and look for skip messages).
- [ ] **`--frozen` fails closed.** Point a fresh `sources.json` at
      *only* the mirrored directory from above, then with network
      disabled, resolve something the mirror has (**expected**:
      succeeds) and something it doesn't (**expected**: a clear build
      failure naming what's missing, not a hang or a stack trace).

## 6. HermeticShell (lighter touch — already verified once)

Already run against a real Docker daemon this session (pulled
`alpine:latest`, executed a command, confirmed host env vars don't leak
in). Worth a quick re-run if anything in `csmake-packaging` or
`csmake-docker-runtime` changed since, but not a priority for this pass.

- [ ] Re-run `tests/testHermeticShell.py` against a real (not mocked)
      Docker daemon if anything upstream changed.

## Cross-cutting: the installed binary, not just the checkout

**Goal**: everything above was run from a checkout. Confirm the
Homebrew-installed binary — which exercises the launcher self-location
bootstrap from earlier in this work — behaves identically.

- [ ] Rebuild the Homebrew formula from this branch
      (`./csmake --modules-path=':../csmake-swak:../csmake-packaging' --command=homebrew-only clean package`),
      reinstall via the local tap
      (`brew reinstall devops-csmake/local/csmake`), and spot-check a
      handful of items from Sections 1–3 above using the installed
      `csmake` rather than `python3 <checkout>/csmake`.

---

## Sign-off

- [ ] All sections above checked off, or explicitly deferred with a
      reason noted here
- [ ] Any new findings from this pass filed as follow-up issues /
      folded into `docs/MODULE_ECOSYSTEM_DESIGN.md`'s "Open questions"
- [ ] PRs updated to reflect this plan's outcome before merge
