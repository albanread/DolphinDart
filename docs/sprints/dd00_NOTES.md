# DD0 — toolchain + baseline: NOTES

**Status: DONE.** 2026-08-15. Gate green on arm64 and x64.

## Baseline (the numbers every later sprint is measured against)

| Measure | Value |
|---|---|
| Build, arm64 | 591/591 targets, 0 errors — `dart.exe` PE machine **AA64** (native) |
| Build, x64 | 591/591 targets, 0 errors (arm64 cross-tools, runs emulated — the control) |
| World boot | **97 files**, headless, both arches |
| World functional checks | **9/9** (`inject:into:`→6, Dictionary→30, Set dedup→2, Interval→5050, SortedColl 1..3, Fraction 5/6, WriteStream, String map, inject/select→30) |
| **ST feature battery** | **12 suites, 566 assertions, 0 failures** |

Battery per suite: ClassSide 34 · CollectionProtocol 73 · Collections 39 ·
Control 40 · Exceptions 21 · NumberProtocol 95 · Numerics 43 · Reflection 41 ·
ReflectionProtocol 44 · StreamProtocol 32 · StringProtocol 73 · Strings 31.

## What landed

**1. The work area is explicit.** `extract.py` and `build.ps1` derived their
workroot as the repo's parent's parent, which assumed the repo sits *inside* its
work area (`<workroot>\WINDARTTALK`). Cloned at `C:\projects\DolphinDart` that
resolves to `C:\projects` — scattering `tree/` and `build-*/` across the projects
root and, worse, **sharing a generated tree with the sibling WINDART port**,
whose patches diverge from ours the moment DD4/DD6 touch the front-end. Both
scripts now take `WINDART_WORKROOT` (env) / `-WorkRoot` (param), defaulting to
the old behavior. Layout and commands: `docs/TOOLCHAIN.md`.

**2. The regression net exists.** `st/test/features` was never vendored into
this port (`st/world/PROVENANCE.md` recorded it as "not required to run the
world"). Vendored from MACDARTV1 @ `68b1689` — 13 suites. See
`st/test/PROVENANCE.md`.

**3. Four inherited substrate defects, found by running that battery for the
first time, all fixed.** Each was verified inherited, not introduced, by
reproducing against the sibling WINDARTTALK build with its own tree.

### D0-1 — `_Type` lazy-parse: the VM crashed (`st_loader.cc`)

`TestClassSide` took the process down at `class_finalizer.cc:2667`
("a concrete class must carry ≥1 function"). Core-snapshot classes finalize
members lazily: `_Type` boots `is_finalized()=false` with `functions()` empty,
and the patched `_Type.noSuchMethod` — the hook giving a Smalltalk class value
its class-side dispatch — only exists once `EnsureIsFinalized` runs
`Compiler::CompileClass`. ST must use the *other* finalizer on its own classes
(`ClassFinalizer::FinalizeClass` — no member parse; ST classes have no token
stream), and that cascades into marking `_Type` finalized with members never
parsed.

MACDART fixed this in 2026-08 with a **LAZY-PARSE GUARD**; the Windows port
never received it. Ported verbatim into `Loader::Load`: force full finalization
of the Type family (and Object, the NSM root) before any ST class loads.

*Windows divergence worth keeping in mind:* on macOS the corruption was
**silent** (class values quietly lost class-side dispatch, breaking unrelated
String code whole suites later); here the debug assert fires instead. Loud beats
silent, but it is the same defect.

### D0-2 — `=` was a partial function (`st_natives.cc`, `ST_eq`)

`true = false` and `false = true` **raised**; `true = true` and `false = false`
answered correctly; every other native receiver (int/String/Symbol/Double/
Character/Array/nil) was fine. The asymmetry is the tell: the call site's inline
identity check short-circuits equal operands, so `ST_eq` is only reached when
operands *differ*, and Dart's `bool` is the one bridged type with no reachable
ST `=` on its Dart super chain. `~=` inherited it via `^(self = anObject) not`.

Fixed by giving `ST_eq` an identity fallback when the chain declares no `=` —
which is not a compromise but Smalltalk's own root definition, stated in the
world as `Object >> = anObject [ ^self == anObject ]`.

### D0-3 — class-side misses answered nil (`st_flow_graph_builder.cc`)

`Set totallyBogusSelector` evaluated to **nil**; `Set new bogusSelector` raised
correctly. The builder's class-name routing carried the comment *"A genuine miss
now becomes an honest doesNotUnderstand instead of a silent nil"* directly above
a call emitting **`stSendExtOrNil`**, whose own docstring reads *"GRACEFUL on a
total miss: answers nil instead of throwing"*. Comment and code disagreed;
MACDART has no `stSendExtOrNil` at all and reaches `stSendExt` here. Fixed by
emitting what the comment always claimed.

This is the defect the suite's own header warns about: silence of exactly this
kind hid five never-written methods in the MACDART lineage. Dolphin's MVP leans
on class-side sends constantly (`View new`, `Rectangle origin:extent:`), so this
one would have cost the port dearly and late.

*Method note:* two speculative fixes were tried first and **reverted** —
raising from `stTypeNSM`, and porting the naming block alone. Neither changed
behavior, which is what proved the send reached neither path. Instrumenting both
candidate paths (and seeing *neither* fire) is what located the real site.

### D0-4 — `Transcript basicPrint:` never existed (`st_prelude.h`)

Exposed *by* D0-3: with the raise restored, one assertion failed honestly.
`Transcript` resolves to the **prelude class**, not the world's
`Transcript := TranscriptStream new` instance, and the prelude class had `show:`,
`cr`, `showCr:` but not `basicPrint:` — so a primitive-coverage probe had been
asserting "printed, survived" about a send that only ever did the surviving.
Added, matching MACDART.

## Findings carried forward

- **`test_exceptions` passes 21/21 on the existing `stOnDo`/`stEnsure`
  machinery.** Good news for DD4: the mechanism is real and exercised. It says
  nothing yet about *resumability*, which remains DD4's opening spike.
- **The friendly-naming block from MACDART's `STSendCommon` is now in** (a Type
  receiver reports as `Set class`, never `_Type`, never with an ` ext` suffix).
  Dolphin error messages will inherit this.
- **`dartui.exe` still builds** and is the interim GamePane host until DD13.
  DD1 demotes it; nothing new may depend on it.
- **The TCL smoke (`tcl/test_arm64_smoke.tcl`) was not run.** It drives the live
  IDE over the vm-service, and DD1 atticks that surface; `tclsh` is present
  (`/clangarm64/bin/tclsh`) if it is ever wanted. The battery replaced it as the
  gate, which is a strictly better instrument for this project: headless,
  assertion-counted, and about the language rather than the IDE.
- **`st/test` also carries three loose suites** (`primitive_probes.mst`,
  `type_conformance.mst`, `galaxigans_smoke.mst`) not yet wired into a driver.
  `primitive_probes` and `type_conformance` are directly relevant to DD2/DD5 —
  wiring them is cheap and belongs in DD2.

## Traps confirmed (for whoever runs the next sprint)

- `cocoa.dart` is embedded into the snapshot from **the repo** (`${STDIR}/cocoa.dart`
  via `dart_gen_builtin`), not from the extracted tree — editing it and
  rebuilding is enough; no re-extract needed. Verified by checking `cocoa_gen.cc`
  regenerated after an edit.
- Re-run `extract.py` only when a `port-*/**.patch` changes; it is idempotent.
- The Store `python3` on PATH is an alias stub. Use the arm64 Python 3.12.
- Never infer arch from a path — read the PE machine type (`AA64` / `8664`).
