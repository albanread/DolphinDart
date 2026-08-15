# DIALECT_GAPS — house Smalltalk vs Dolphin D8 (DD2)

The measured conformity register. Supersedes `DOLPHIN_PORT.md` §4 (audit v0).
Dispositions: **T** translate away at ingestion · **C** compat kernel (in-image)
· **D** dialect/front-end change · **V** VM work (natives/builder) · **–** defer.

Rows marked *(census)* carry numbers from the DD2 MVP-closure measurement; see
`dd02_NOTES.md`.

| # | Area | What Dolphin needs | Substrate today (measured) | Disp | Owner |
|---|---|---|---|---|---|
| A1 | Source format | UTF-8-BOM CRLF bang-chunk `.cls`; `.pax` manifests carrying pools **and loose methods** | house `.mst`; no chunk reader. **Census: 1001 `.cls` + 86 `.pax`; 1084/1087 have a BOM — 3 do NOT** | **T** | DD3 |
| A2 | Namespaces | namespaces-as-classes, dotted refs, `imports:` | none in the parser. **Census: ZERO collisions — no base name appears twice at all; 986/986 declared FQNs match their filename stem** | **T** — flatten; rename table ~empty | DD3 |
| A3 | Pools / `##()` / `??` | compile-time folding, ifNil sugar | none. **Census: `##(` 978 sites/283 files, `??` 133/65** | **T** | DD3 |
| A4 | Primitives | Dolphin's 256-slot numbering | different numbering space; **205/210 rows are kernel-only and moot** — see [PRIM_MAP.md](PRIM_MAP.md) | **T** | DD3 (+DD5 on demand) |
| A5 | Exceptions | ANSI hierarchy, `pass`/`outer`/`retry`/`return:`, **resumable** `Warning`/`Notification` | **CLOSED (DD4).** The hierarchy was already in `st_prelude.h` (DD0 looked only in `st/world` and mis-recorded it as absent); DD4 added `Notification`, the resumable-default rule, Dolphin's exact superclass chain, and DNU→`MessageNotUnderstood` on both the ST and native paths. **v1 does not resume to the signal point** — measured divergence: `resume:` has 0 MVP sites, and `resume:` now refuses loudly | **done** | DD4 |
| A6 | Processes | green processes, `ProcessorScheduler`, `Delay`, `Semaphore` | none (house doctrine: no green threads); Dart isolates + a native pump. **Census: `Processor` 109 sites/35 files, `critical:` 85, `Semaphore` 50/23, `Delay` 25/11, `fork*` family 51.** Mostly Base, but ~13 MVP files are real | **C** — site-by-site | DD8/DD10 |
| A7 | Weak / finalization | weak collections, mourning | none in-image; Dart embedder has weak persistent handles. **Census: `makeWeak` 0, `mourn`/`mourn:` 0 — mourning is spelled `elementsExpired:` (18/6). `beFinalizable` 15/14, `beUnfinalizable` 28/21, incl. GDI classes** | **–/V** strong-refs v1 | backlog |
| A8 | `become:` | the view-resource proxy | VM has forwarding (`vm/become.h`, hot-reload). **Census: 14 real sends corpus-wide, exactly ONE in MVP** — `UI.STBViewProxy>>restoreView` | **T** design around the one | DD3/DD12 |
| A9 | Strings | `Utf16String` at every API edge; `AnsiString`/`Utf8String` | **Dart strings ARE UTF-16** — the native case. **Census: `Utf16String` 222 refs/85 files (dominant), `Utf8String` 71/27, `AnsiString` 34/15** | **C** thin classes | DD8 |
| A10 | Numeric tower | LargeInteger, Fraction, ScaledDecimal | native bigints; world has Fraction + ScaledDecimal; **43/43 numerics + 95/95 number-protocol assertions green (DD0)** | **C** (tests, not construction) | DD8 |
| A11 | External calls | `<stdcall:>`/`<cdecl:>`, structs, `GetLastError` | per-function C++ natives work; generic `ST_ffiCall` **stubbed on Windows**. **Census: `<stdcall:` 667 sites/29 files, `<cdecl:` 77/4** | **V** | DD6 |
| A12 | Callbacks (wndproc) | synchronous re-entrant native→image dispatch, arbitrary depth | embedder API + view-server precedent; depth unproven | **V** | DD7 |
| A13 | Boot | source-boot (`Boot.st` lineage) | house source-boot, now **layered** (DD1) | aligned | — |
| A14 | Image snapshot | `.img` save/load | none (rebuild-from-source) | **–** TBD | owner, end of DD10 |

## Confirmed by DD0/DD1 measurement, not assumption

- **A5's mechanism is real.** `test_exceptions` passes 21/21 against `stOnDo`/
  `stEnsure`. What remains unmeasured is *resumability* — Dolphin's `resume:`
  returns to the signal point while Dart try/catch destroys the frames first.
  That is DD4's opening spike and the one place a front-end change is expected.
- **A4 is nearly empty.** See PRIM_MAP: keeping our own kernel makes Dolphin's
  kernel primitives moot. One lowering rule (D157) is the whole measured demand.
- **A9 is nearly free.** Dart strings are UTF-16 code units, so Dolphin's
  `Utf16String` is the *native* representation and WINVM's whole V4 sprint
  dissolves into thin compat classes plus edge conversions.
- **A13 is aligned and now layered.** DD1 made the world a semicolon-separated
  layer stack, which is how `dolphin_compat` (DD8) and the translated corpus
  (DD9+) will arrive.

## Class-side dispatch — a gap that was found, not predicted

Not in audit v0, and it would have hurt: **a class-side miss silently answered
nil** in this port (fixed in DD0). Dolphin's MVP is class-side-send heavy
(`View new`, `Rectangle origin:extent:`, every `…class>>` constructor), so a
missing method would have become a `nil` surfacing arbitrarily far from its
cause. The lesson generalises: audit v0 was built by reading, and reading found
the gaps it was looking for. Running the vendored battery found four it was not.
