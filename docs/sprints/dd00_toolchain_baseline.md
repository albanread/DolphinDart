# DD0 — Toolchain + baseline from the new home `S`

**Objective:** prove this repo builds and runs from `C:\projects\DolphinDart`
against the external quarry, on both arches, and freeze the baseline numbers
every later gate is measured against.

**Read first:** `README.md` (Building), `port-win/extract.py` header (the
de-pinned location scheme + env overrides), `port-win/build.ps1` params
(`-Arch`, `-Tree`, `-Clean`), `st/PROVENANCE.md` (the functional checks),
`SPRINTS_ARM64.md` tail (the arm64 port's own gate style).

**The external layout (do not vendor any of it):**
- Quarry (Dart 1.24.3 sources): `C:\projects\WINDARTARM\sdk-1.24.3`
- Extracted tree: `C:\projects\WINDARTARM\tree`
- Builds: `C:\projects\WINDARTARM\build-x64`, `…\build-arm64`

## Work

1. Read `extract.py`/`build.ps1` and determine the exact override names for
   quarry/tree/build when the repo is NOT inside `WINDARTARM`. Run extract (it
   is documented idempotent) and both builds from this repo's checkout.
2. Run the headless world boot on **arm64** (primary; x64 too if the machine
   permits): the PROVENANCE invocation (`dart.exe <runner> st/world` — locate
   the actual runner script; PROVENANCE names `st_world_run.dart`) and the
   functional checks it lists (`inject:into:` → 5050, Fraction `5/6`, etc.).
3. Run the TCL smoke (`tcl/test_arm64_smoke.tcl`) against the built host.
4. Write `docs/TOOLCHAIN.md`: the layout above, the exact commands, the env
   overrides, and the rule that builds/quarry never enter this repo.
5. Record the baseline in `docs/sprints/dd00_NOTES.md`: world files loaded,
   classes registered, checks passed, both arch outputs, wall-clock.

## Out of scope

Any source change beyond `docs/`. If a build breaks from the new location,
fixing path assumptions in `extract.py`/`build.ps1`/CMake IS in scope (that is
the point of the sprint) — fix minimally and note each.

## Gate

- `build-x64` and `build-arm64` `dart.exe` both built from this checkout, PE
  machine types verified (`AA64` for arm64 — never infer arch from a path).
- Headless world boot green with the PROVENANCE functional checks on arm64.
- TCL smoke green.
- `docs/TOOLCHAIN.md` + `dd00_NOTES.md` committed with the measured numbers.

## Traps

- The Store `python3` alias stub is not Python; use
  `%LOCALAPPDATA%\Programs\Python\Python312-arm64\python.exe`.
- `build.ps1` drives MSVC via vcvars; run it from PowerShell, not bash.
- Do not "fix" the un-vendored quarry by vendoring it — its BSD-3 licence and
  the extract-patch flow are deliberate (see README Licensing).
