# DolphinDart — Dolphin Smalltalk on the Dart VM

**Status:** plan of record. **Date:** 2026-08-15.
**Commitment:** *faster, portable Dolphin on the Dart VM* — the Dolphin Smalltalk
dialect and the Windows primitives it needs, running on this repo's Dart-1.24.3
VM with its C++ Smalltalk front-end, on Windows x64 **and** ARM64 from one
source tree. **The goal gate is the Dolphin MVP GUI running** (milestone UI-5,
sprint DD12), with our own GamePane kept alongside it as a supported extension
for games, including sound (DD13).

**Companions:** [DOLPHIN_SPRINTS.md](DOLPHIN_SPRINTS.md) (the ladder),
`docs/sprints/dd*.md` (per-sprint detail for implementing agents),
[docs/prior_art/winvm/](docs/prior_art/winvm/README.md) (the first attempt's
corpus, with per-document standing notes).

---

## 0. Executive summary

- **The execution thesis.** Smalltalk here is not interpreted and has no
  bytecode: the C++ front-end (`port-win/dart_st/`) compiles `.mst` source
  directly to Dart flow-graph IR, and the Dart 1.24.3 optimizing JIT runs it —
  the same VM that shipped production Windows x64 JITs in 2017, already ported
  in this tree to Windows ARM64. That is the "faster, portable" claim: one
  Smalltalk, two native CPU targets today, more in principle (the VM has ia32/
  arm/arm64/x64 backends), tier-up optimization for free.
- **What we port** (owner's scope rule): Dolphin's **Smalltalk language layer**
  (the dialect semantics + the kernel/MVP class corpus) and the **Windows
  primitives** it needs. **Not** Dolphin's bytecode interpreter — execution
  stays front-end → Dart IR → Dart JIT.
- **The source is proven clean.** `C:\projects\dsfork` (verified 2026-08-15):
  MVP is byte-identical to upstream MIT-licensed Dolphin 8; the fork diverges
  only in its C++ VM — which **does not work** and is reading material only.
- **The substrate is further along than WINVM's was.** Measured today:
  exceptions *mechanism* already exists (`on:do:`/`ensure:`/`ifCurtailed:`
  lower onto Dart try/catch/finally with NLR home tokens), numbered
  `<primitive: N>`-with-fallback is already the dialect's idiom, `become:`
  exists in the VM (hot-reload's forwarding machinery), Dart strings are
  natively UTF-16, Dart 1.x integers are natively arbitrary-precision, and a
  C++ Win32 natives layer with a working host window, D3D11 game pane and
  XAudio2 already ships in the seed. The big holes are: no ANSI Exception
  *hierarchy*, no Dolphin-numbered primitives (numbering spaces differ), no
  general Windows FFI call path (`ST_ffiCall` is stubbed on Windows), and no
  translator for Dolphin's chunk/`.pax` source format.
- **Shape of the port:** a translator (`dolphin2mst`) ingests D8 sources into
  the house dialect; a compat kernel bridges Dolphin idioms onto our kernel;
  the MVP corpus arrives in translated waves behind a native wndproc door; the
  ladder ends with the MVP triad, common controls, and dialogs — the same
  milestone ladder the WINVM design proved on paper, re-grounded on this VM.

## 1. Scope rules (binding, from the project owner, 2026-08-15)

1. **Port the Smalltalk language layer + the Windows prims. Never the Dolphin
   bytecode interpreter.** Execution model is fixed: ST front-end → Dart
   flow-graph IR → Dart JIT.
2. **The dsfork VM does not work.** It is never an oracle and never a
   dependency. Selected Dolphin **C++ VM features may be mined** — i.e., their
   *semantics* re-implemented in our front-end/natives — with
   `Core/DolphinVM/` as reading material (e.g. `PrimitivesTable.cpp` as the
   semantic reference for DD5).
3. **Image format: TBD.** Options stay open (rebuild-from-source worlds — the
   house model; Dart snapshot machinery; a dsfork `.img` reader). Decision
   point: end of DD10, with data. Until then, source-boot only — which matches
   Dolphin's own dev channel (`Boot.st`/`PreBoot.st` in the corpus).
4. **The seed's IDE surface is not needed** (dartui workspace, browser,
   debugger tabs, cocoa-UI world layers). **The GamePane is needed** — it
   stays, re-homed as an extension package for games including sound (D3D11 +
   XAudio2 + its world wiring). The Dolphin MVP framework is the UI story.
5. **Dialect changes to the front-end are in scope** where Dolphin conformity
   cannot be reached by translation (the resumable-exception decision, DD4, is
   the expected case).
6. **The goal is the Dolphin MVP GUI running** — DD12's gate is the project's
   acceptance test.
7. **THE MVP IS DOLPHIN'S, IN SMALLTALK** (added 2026-08-16, after a caught
   drift). The deliverable is Dolphin's own MVP framework — translated
   Smalltalk — running. Never an MVP-shaped framework of our own, in any
   language. **Dart is an implementation substrate with exactly the standing
   C++ has in this VM**: the door/pump, the FFI floor, the worker transport
   and the test harnesses may be Dart, the same way primitives may be C++ —
   MVP and application logic may not be either. Hand-written compat Smalltalk
   that duplicates a translated Dolphin class's role is SCAFFOLDING: it must
   be named as such in the sprint notes together with the exact thing that
   retires it, and a gate only counts toward the goal when its load-bearing
   classes are Dolphin's own.
8. **Workers on Dart isolates REPLACE Dolphin's processes/green threads**
   (2026-08-16). This VM has no green processes and will not grow any. A
   Dolphin `fork`/`Process` site translates to a `Worker do:with:then:`
   submission whose continuation is POSTED to the UI thread — never to a
   green-thread scheduler. `docs/WORKERS.md` is the doctrine and the
   mechanism; `st/world/47_worker.mst` is a specification document only
   (numbered-primitive bodies, inert here).

## 2. The substrate, measured (2026-08-15)

Seed: WINDARTTALK @ `c2aec79`, branch `windows-arm64-port`, clean tree,
vendored whole as this repo's first commit. Facts verified by reading this
tree, not recalled:

| Area | Fact | Where |
|---|---|---|
| VM | Dart 1.24.3 (last V1 release), MSVC build, x64 + native ARM64; quarry un-vendored, builds live outside the repo | `README.md`, `port-win/extract.py` (repo-relative defaults + env overrides), `build.ps1 -Arch/-Tree` |
| ST front-end | C++ in-VM: lexer → parser → AST → flow-graph builder → loader → natives; 11,358 lines incl. 2,648 of `cocoa.dart` shims | `port-win/dart_st/` |
| Dialect | House Strongtalk-style: `Super subclass: Name [ … ]` (a special-cased keyword send, `st_parser.cc:174`), optional type annotations, doc-comment strings | `st/world/*.mst` |
| Primitives | `<primitive: N>` with in-image fallback is already the idiom; **house numbering** (measured: 1=`+`, 2=`-`, 3=`*`, 108=`asDouble` on SmallInteger) | `st/world/06_smallinteger.mst:61-100` |
| Exceptions | `on:do:` → `stOnDo(protected, type, handler)`; `ensure:`/`ifCurtailed:` → `stEnsure` = Dart try/finally, runs during NLR unwind; **no ANSI Exception class hierarchy in the world** (grep: zero `subclass: Exception/Error/Warning`) | `st_flow_graph_builder.cc:1250-1258` |
| NLR | `needs_nlr_`, per-activation Context as the NLR home token, method-level NLR catch | `st_flow_graph_builder.cc:298,756,850,2029` |
| `become:` | The VM has it (`vm/become.h`, `Become::ElementsForwardIdentity`, used by hot-reload); the ST layer wires it with guarded refusals | `st_natives.cc:31` |
| FFI | POSIX path: `dlsym` floor; **`ST_ffiCall` stubbed on Windows** ("Win64 trampoline pending"); the working Windows surface is per-function **C++ natives** (`dart_win32/`: view-server, D2D, D3D11 game pane, XAudio2, SQLite) | `st_natives.cc:14-18`, `port-win/dart_win32/` |
| World | 97 top-level + 12 bench `.mst`, 179 classes, **boots headless on Windows ARM64** with functional checks; vendored + SHA-verified from MACDARTV1 | `st/PROVENANCE.md` |
| Strings | Dart strings are UTF-16 code units → Dolphin 8's `Utf16String` is the *native* case; `…W` marshalling is cheap | Dart 1.24 semantics |
| LargeInteger | Dart 1.x ints are arbitrary-precision natively; the world already binds `07_largeinteger.mst` | world |
| Harness | TCL drive-and-snapshot harness working against the Windows host | `tcl/*.tcl` |
| Error discipline | Native misses raise **catchable** Dart errors (the ApiError-kills-isolate bug is fixed and regression-covered) | `st_natives.cc:47-60` |

**What this changes vs the WINVM attempt:** WINVM spent its whole first sprint
(G0) making nested host→VM entry sound in a setjmp/VEH world and still had the
`&mut VmState` seam unbuilt when work stopped. Here, host→VM entry is the Dart
embedder API's day job (the view-server already reflects native events into
the VM), so DD7 is a *spike-then-build* sprint, not a soundness campaign. The
UTF-16 sprint (WINVM V4) dissolves almost entirely. The exceptions sprint
builds a hierarchy on an existing mechanism instead of building the mechanism.
The costs that move the *other* way: we must build the Windows FFI/marshalling
floor ourselves (WINVM had a working x64 FFI + winkb), and every Dolphin
primitive number must cross a mapping table because the numbering spaces
collide (house 1=`+` vs Dolphin 1=`^self`).

## 3. The source, measured (2026-08-15)

`C:\projects\dsfork` — clone of github.com/albanread/dsfork (72 MB, MIT ©2015
Object Arts, 17 commits over baseline `c7f4b77` of 2026-04-18):

- 3,164 `.cls` under `Core/Object Arts/Dolphin`; Base kernel = 391 `.cls`
  (after excluding `Tests`/`Deprecated`); 394 `.pax`.
- **MVP is byte-identical to upstream D8** (diff vs baseline: 4 files, none in
  MVP — `Boot.st` + 3 product-definition classes). We port unmodified D8.
- **The `.pax` trap stands:** `Dolphin MVP Base.pax` (162 KB) carries the GUI
  constant pools *and* 181 loose `OS.UserLibrary` FFI methods. A `.cls`-only
  reader silently loses the entire User32 binding. The translator reads `.pax`
  as source.
- The fork's own VM analysis docs (`ffi.md`, `ffi-callbacks.md`, `gc.md`, …)
  named by the prior-art design are **not in this clone** (shallower fork
  state than the 105-commit tree the design reviewed). Their loss is absorbed:
  what we needed from them is superseded by owner rule #1 (no interpreter, no
  working VM) and by `dolphin_win_prims.md`, which was extracted while they
  were available.
- Naming correction for the GUI sprints: there is **no `GdiCanvas`** in the
  corpus — the class is `Graphics.Canvas` (prior-art G4 gate text is wrong).

Scale expectations carried from the prior-art review (they audited this exact
corpus): minimal Shell+controls closure ≈ 700 classes / 165 k lines; realistic
v1 translated corpus ≈ **150–200 classes / 40–60 k lines** + ~5 k hand-written
compat/substrate lines; language gap small (one functional `become:` in MVP,
zero `thisContext`, zero runtime compilation).

## 4. Conformity audit v0 — house dialect vs Dolphin D8

The measured starting register; DD2 finishes it and turns it into
`docs/DIALECT_GAPS.md` + `docs/PRIM_MAP.md`. Dispositions: **T** = translate
away at ingestion, **C** = compat kernel (in-image), **D** = dialect/front-end
change, **V** = VM-feature work (C++ natives/builder), **–** = defer.

| # | Area | Dolphin needs | Substrate today (measured) | Disposition |
|---|---|---|---|---|
| A1 | Source format | UTF-8-BOM CRLF bang-chunk `.cls`, `.pax` manifests with loose methods + pools | house `.mst`, no chunk reader | **T** — `dolphin2mst` (DD3); `.pax` is source |
| A2 | Namespaces | namespaces-as-classes, dotted refs, `imports:` | none in the parser | **T** — flatten + rename table (prior-art decision); collision report gates a revisit |
| A3 | Pools / `##()` / `??` | compile-time folding, ifNil sugar | none | **T** — fold/rewrite at ingestion |
| A4 | Primitives | Dolphin's 256-slot numbering (215 declared / 424 sites) | `<primitive: N>` exists, **different numbering space** | **T+V** — mapping table (DD2), alias-or-implement campaign (DD5) |
| A5 | Exceptions | ANSI hierarchy: `signal`/`signal:`, `on:do:`, `pass`/`outer`/`retry`/`return:`, **resumable** `Warning`/`Notification`, DNU→MNU catchable | `stOnDo`/`stEnsure` mechanism only; Dart try/catch unwinds before handler runs | **C+D** — hierarchy in-image (DD4); resumability is the one place a front-end change is expected (§6 risk 1) |
| A6 | Processes | green processes, `ProcessorScheduler`, `Delay` | none (deliberate house doctrine: no green threads); Dart isolates + host pump exist | **C/–** — MULTIVM doctrine transfers: pump-native + isolate workers; shim only what the corpus census (DD2) proves MVP needs |
| A7 | Weak/finalization | weak collections, mourning/bereavement | none in-image; Dart embedder has weak persistent handles | **–/V** — strong-refs v1 + explicit `free` (prior-art decision); mourning is minable later |
| A8 | `become:` | 1 functional site in MVP (view-resource proxy) | VM has forwarding | **T first** — keep the prior-art design-around (resource transpilation); the VM support is a fallback, not an invitation |
| A9 | Strings | `Utf16String` everywhere at the API edge; `AnsiString`/`Utf8String` classes | Dart strings *are* UTF-16 | **C** — thin classes; policy: internal = native String, edges = UTF-16 by construction |
| A10 | LargeInteger / ScaledDecimal / Fraction | full numeric tower | native bigints; world has Fraction + ScaledDecimal files | **C** — conformity tests, not construction |
| A11 | External calls | `<stdcall:>`/`<cdecl:>` descriptors, structs, `GetLastError`, callbacks | per-function C++ natives working; generic `ST_ffiCall` stubbed on Windows | **V** — DD6 builds the floor; winkb DB (`C:\projects\windows_api\windows_api.db`) generates signatures |
| A12 | Callbacks (wndproc) | synchronous re-entrant native→image dispatch to arbitrary depth | embedder API + view-server precedent; depth/nesting unproven | **V** — DD7 spike-then-build with the prior-art torture gates |
| A13 | Boot | source-boot (`Boot.st` lineage) | house source-boot worlds | aligned — no work |
| A14 | Image snapshot | `.img` save/load | none (rebuild-from-source) | **–** — TBD by owner rule #3 |

## 5. Consolidation map (what comes from where)

- **From WINVM** (`docs/prior_art/winvm/`): the corpus audit and Dolphin
  architecture review (§0–§3 of the design — fully standing); the gap register
  G-a…G-n and decision log (largely standing); the **G2 translator spec**
  (transfers nearly whole → DD3); the **G3 compat-kernel inventory** → DD8;
  the G4–G7 milestone ladder + acceptance gates → DD9–DD12; the
  **215-primitive inventory** with worksheet → DD5's live document; the G0
  *lesson* (prove re-entrancy to depth before the GUI leans on it) → DD7's
  spike gates. **Not** transferring: G0's Rust machinery, V4 UTF-16 (dissolves),
  the WebView2/COM surface notes.
- **From dsfork** (`C:\projects\dsfork`): the D8 Smalltalk sources (the thing
  being ported); `PrimitivesTable.cpp` as *semantic reference* for DD5;
  `Boot.st`/`DBOOT.sml` as the boot-order reference; the `.img` format if the
  TBD lands that way. Never its runtime behavior — it does not run.
- **From the seed itself:** everything — front-end, natives layer, world, TCL
  harness, GamePane/XAudio2 (kept per owner rule #4), the ARM64 port and its
  engineering logs.
- **From the sibling projects:** `C:\projects\windows_api\windows_api.db`
  (18,271 functions / 97,402 constants / 66,708 struct fields with typed
  params) as the generator source for DD6 bindings — same DB the WINVM/WINARM
  winkb work validated.

## 6. Risks, ranked

1. **Resumable exceptions on a try/catch substrate.** Dolphin's `resume:`
   returns control to the signal point; Dart try/catch destroys the frames
   first. The fix is a raise-time handler search (handler runs as a closure
   *before* unwind; unwind only on non-resumption) — a front-end change in the
   builder. DD4 opens with this as a decision spike; the fallback (v1
   non-resumable, `Notification` returns its default) is recorded as an
   explicit, testable divergence.
2. **Primitive semantic drift.** Same table row ≠ same edge cases. Every DD5
   row lands with tests that exercise the primitive *and* its fallback (house
   rule; the numbering collision makes silent drift extra cheap to create).
3. **Re-entrant depth through the embedder API.** Believed cheap (view-server
   precedent), unproven at depth with ST exceptions/NLR crossing native
   frames. DD7's first deliverable is the depth-5/DNU/fault spike, gated,
   before any MVP class assumes it.
4. **Namespace flattening collisions at MVP scale.** The translator emits a
   collision report; the rename table is the pressure valve; a real clash
   pattern forces the A2 revisit.
5. **We own a 2017 VM.** Mitigated: it is already ported, benchmarked and
   logged in this tree; the maintenance surface is the front-end + natives we
   write, not the Dart core.
6. **The corpus census could surprise** (A6/A7): if MVP's runtime dependence
   on green processes or weak collections is broader than the prior-art audit
   suggests, DD2's census exists to find it *before* DD9 commits.

## 7. Decision log

1. **No Dolphin bytecode interpreter; execution = front-end → Dart IR → JIT**
   (owner rule, 2026-08-15).
2. **Ingestion by translator (`dolphin2mst`), not a parser fork.** Dialect
   (front-end) changes only where translation cannot express *semantics* —
   expected: exception resumability. (Carries WINVM decision + owner rule #5.)
3. **Prim numbering: mapping table; house numbers stay authoritative in-VM.**
   Dolphin numbers exist only in the translator's table and the worksheet.
4. **IDE surface out, GamePane in.** The dartui IDE and cocoa-UI world layers
   leave the default build/world in DD1; the D3D11+XAudio2 GamePane is
   re-homed as the games extension and kept green from DD1 onward (owner rule
   #4, revised 2026-08-15).
5. **MULTIVM doctrine carries:** no green threads; the pump is native; workers
   are Dart isolates; long-command UX per prior-art G-f.
6. **Image format TBD** — decide end of DD10 with data (owner rule #3).
7. **The goal gate is DD12** (MVP triad + controls + dialogs = "the Dolphin
   MVP GUI running"), with DD13 delivering the GamePane-in-MVP extension.

## 8. Open questions

- Resumability design detail (DD4 spike output).
- `AnsiString` policy at the API edge (census-driven, DD2).
- How much `ProcessorScheduler`/`Delay` surface the v1 corpus actually touches
  (DD2 census; prior-art table G-f/G-g says: replace site-by-site).
- Image format (owner TBD; decision point end of DD10).
- Whether DD6 finishes the generic Win64 `ST_ffiCall` trampoline or ships
  generated per-function natives first (cost decision inside DD6; the winkb
  generator makes the second cheap).
