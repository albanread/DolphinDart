# DD5 — The primitive campaign (rolling) `L`

**Objective:** make `docs/PRIM_MAP.md` real: every Dolphin primitive the
translated corpus executes is either aliased to a house primitive, implemented
as a new stprim/intrinsic, or proven to fail cleanly into its fallback. This
is a **rolling campaign** — waves land interleaved with DD3–DD12, each wave
sized to what the next corpus checkpoint needs.

**Read first:** `docs/PRIM_MAP.md` + `docs/HOUSE_PRIMS.md` (DD2),
`docs/prior_art/winvm/dolphin_win_prims.md` (copy the worksheet to
`docs/PRIM_WORKSHEET.md` as the live tick-list; prior art stays pristine),
`port-win/dart_st/st_natives.cc` (how natives register; the catchable-error
discipline at :47-60) and the front-end's `<primitive: N>` dispatch site.

## Wave plan (re-cut freely; record re-cuts in NOTES)

- **W1 — kernel arithmetic/objects** (with DD3's geometry corpus): return
  shortcuts (Dolphin 1/2), SmallInteger arith/compare set, `class`,
  identity/hash, `at:`/`at:put:`/`size`, `basicNew`/`basicNew:`,
  **157 `primitiveNewInitializedObject`** (73 sites — the hot one),
  `instVarAt:`(`put:`), `perform:`(`withArguments:`).
- **W2 — collections/streams/strings** (with DD8): the String/Symbol
  comparison + copy prims, stream next/nextPut family, `replaceFrom:to:with:`.
- **W3 — the GUI-adjacent set** (with DD9): the sets DD9's translated View
  corpus actually hits — derive from translator refusal reports, not guesses.
- **W4 — stragglers** corpus-driven through DD12.

## Per-row discipline (every row, no exceptions)

1. Disposition per PRIM_MAP: `alias` rows are translator work (the number
   rewrite) + a conformance test; `new` rows are C++ (st_natives or a builder
   intrinsic — prefer natives; an intrinsic needs a perf or semantics reason
   written down); `fail-clean` rows get a test proving the fallback runs
   (Dolphin 31/32 pattern).
2. **Two tests minimum:** the primitive path, and the fallback path forced
   (wrong-type arg or explicit failure) — the house idiom keeps real fallback
   code under every `<primitive: N>`, and Dolphin's image assumes it runs.
3. Divergence-flagged rows (DD2) additionally test the flagged edge
   (overflow → LargeInteger promotion, non-SmallInteger receiver, mutability
   of literals, …) against **D8-documented** behavior, with the D8 source
   comment cited in the test comment.
4. Tick `docs/PRIM_WORKSHEET.md` (Impl + Test columns) in the same commit as
   the code; the worksheet is the campaign's single progress instrument.

## Gate (per wave)

- Wave's worksheet rows ticked with tests; dependent translated corpus green;
  full suite count vs baseline recorded in `dd05_NOTES.md` (append per wave).
- No translated method executes an unmapped number (translator hard-errors —
  DD3 negative test stays green as the waves extend the map).

## Traps

- The numbering collision is total on low numbers (house 1=`+`, Dolphin
  1=`^self`) — an alias row transposed silently turns arithmetic into
  self-returns. The DD2 spot-verification exists for this; extend it to any
  row you touch and find suspicious.
- Natives must raise **catchable** errors, never ApiError (the
  isolate-killing bug already fixed once — `st_natives.cc` comment block).
- `perform:withArguments:` interacts with the ext-send dispatch cache in
  `st_natives.cc` — read the cache keying before adding entries.
