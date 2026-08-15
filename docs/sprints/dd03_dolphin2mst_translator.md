# DD3 — `dolphin2mst` translator core `L`

**Objective:** the ingestion tool that turns unmodified D8 sources into house
`.mst`, mechanically and repeatably. The prior-art G2 spec
(`docs/prior_art/winvm/dolphin_ui_sprints.md` §G2 + the design §5.4)
**transfers nearly whole** — this doc lists only the deltas and the gate.

**Read first:** prior-art G2 (both docs), `DOLPHIN_PORT.md` §4 rows A1–A4,
`docs/PRIM_MAP.md` (DD2), `st/world/06_smallinteger.mst` (the target idiom:
class body, `<primitive: N>` + fallback, doc comments), a real D8 `.cls`
(`C:\projects\dsfork\Core\Object Arts\Dolphin\MVP\Base\UI.View.cls`) and the
load-bearing `.pax` (`…\MVP\Base\Dolphin MVP Base.pax`).

**Home:** `tools/dolphin2mst/` (Python; the ARM64 Python 3.12 at
`%LOCALAPPDATA%\Programs\Python\Python312-arm64\python.exe`).

## Work (the G2 spec, with Dart-substrate deltas)

1. Chunk parser: UTF-8 **BOM**, CRLF, `!!` escaping; one class per `.cls`.
2. `.pax` reader: manifest + shared-pool class defs + **loose methods** (the
   trap: 181 `OS.UserLibrary` methods live in `Dolphin MVP Base.pax`).
3. D8 class-def parse (`subclass:instanceVariableNames:classVariableNames:
   classInstanceVariableNames:imports:…`) → house
   `Super subclass: Name [ … ]` form; category/comment carried as the house
   doc-comment idiom.
4. Name resolution: namespace flattening + rename table (seeded by DD2's
   collision scan; config file in `tools/dolphin2mst/renames.toml`).
5. Foldings/rewrites, each a named *rewrite class* with golden-file tests:
   pools → literals; `##(…)` → folded literal (fold only the closed set of
   compile-time-safe expressions; anything else is a reported refusal, never a
   guess); `??` → `ifNil:`; annotations/pragmas; **primitive renumbering via
   `PRIM_MAP`** (delta vs WINVM: their numbering matched by construction, ours
   never does — an unmapped number in translated input is a hard error, not a
   passthrough).
6. `<stdcall:>`/`<cdecl:>` descriptors → the house FFI pragma form (the
   `"primitive: FFI …"` shape the builder already parses at
   `st_flow_graph_builder.cc:3058`). Until DD6 fixes the final form, emit
   behind a `--ffi-form` switch so re-emission is a flag flip, not a rewrite.
7. Struct-accessor generation for the core structs (RECT/POINT/MSG/WNDCLASS/
   PAINTSTRUCT/NMHDR/SCROLLINFO) — target representation per DD6's model;
   stub emit acceptable this sprint if DD6 hasn't landed (flagged, like #6).
8. Collision report + refusal report (every construct the translator will not
   translate, with file:line — silence is the failure mode).
9. Patch-overlay dir (`tools/dolphin2mst/overlays/`): hand adjustments live as
   overlay entries applied at emit; generated `.mst` is never hand-edited.
10. **First corpus:** `Graphics.Point`, `Graphics.Rectangle` + their D8 tests,
    per the prior-art §8 Q1 collision decision (they may collide with house
    `28_point.mst` — the rename table's first real customer).

## Gate

- Translated geometry classes + tests load and run green in the world
  (headless, arm64).
- Golden-file test per rewrite class (input chunk → expected `.mst`).
- Re-run over the full MVP closure is **byte-stable** (twice → identical
  output tree) and its refusal/collision reports are committed.
- An unmapped primitive number, an unfoldable `##()`, and a `.pax` loose
  method each demonstrably surface in reports (negative tests).

## Traps

- Read `.pax` before `.cls` — package pools must exist before method bodies
  fold them.
- D8 sources are BOM'd; a naive `open()` reads `\ufeff` into the first token.
- House `28_point.mst` already defines Point — the geometry corpus decision
  (translate Dolphin's as the conformity target, alias or rename per prior-art
  Q1) must be recorded in `dd03_NOTES.md`, not improvised.
