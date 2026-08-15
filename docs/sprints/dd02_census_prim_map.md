# DD2 — Conformity census + prim map `M`

**Objective:** finish the conformity audit DOLPHIN_PORT.md §4 started, with
measured numbers from both trees, and disposition **every one of Dolphin's 215
declared primitives** into the mapping table DD3/DD5 execute against. Pure
analysis — no VM or world change.

**Read first:** `DOLPHIN_PORT.md` §4 (audit v0),
`docs/prior_art/winvm/dolphin_win_prims.md` (the inventory — transfers whole),
`docs/prior_art/winvm/dolphin_ui_porting.md` §2–§3 (corpus + architecture),
`C:\projects\dsfork\Core\DolphinVM\PrimitivesTable.cpp` (semantic reference —
**read-only; the dsfork VM does not work and is never run**).

## Work

1. **House primitive table.** Extract the substrate's own numbering: grep
   `<primitive:` across `st/world/` → table (house #, selector, class, file) —
   plus where the front-end dispatches numbers (find the `<primitive: N>`
   handling in `port-win/dart_st/`; note also the `"primitive: FFI "` pragma
   at `st_flow_graph_builder.cc:3058`). Commit as `docs/HOUSE_PRIMS.md`.
2. **`docs/PRIM_MAP.md` v1.** For each of the 215 Dolphin numbers (424 sites):
   one of `alias(house #)` — same semantics, translator rewrites the number;
   `new` — needs a new stprim/intrinsic (DD5); `fail-clean` — the 31/32
   pattern, must fail into fallback; `ffi` — the 48/80/96 family, becomes the
   DD6 binding form; `defer(reason)`. Semantics judged from Dolphin image
   fallback code + `PrimitivesTable.cpp` reading. Flag every row where edge
   cases plausibly diverge (overflow, non-SmallInteger args, mutability) —
   those rows get mandatory divergence tests in DD5.
3. **MVP-closure census** over `C:\projects\dsfork` (the ~700-class closure
   from the prior-art audit, not all 3,164): counts + class lists for
   `Process`/`fork`/`ProcessorScheduler`/`Delay`, weak
   (`WeakArray`/`weak`/mourning selectors), `become:`, `AnsiString`/
   `Utf8String`/`Utf16String`, `thisContext`, `##(`, `??`, pool references.
   This either confirms the prior-art gap register (G-f/G-g green-process
   table, one `become:`) or surprises us **now**, before DD9 commits.
4. **Namespace collision pre-scan:** all class basenames across D8 namespaces
   in the closure → duplicates list → seed the DD3 rename table.
5. **Finalize `docs/DIALECT_GAPS.md`** from DOLPHIN_PORT §4 + everything
   above, each row carrying its disposition and owning sprint.

## Gate

- `docs/HOUSE_PRIMS.md`, `docs/PRIM_MAP.md` (215/215 rows dispositioned, none
  blank), `docs/DIALECT_GAPS.md` final, census numbers + collision list
  committed in `dd02_NOTES.md`.
- Spot-verification: 10 randomly chosen PRIM_MAP rows re-derived by a second
  read (different agent or fresh pass) agree — this table steers two sprints;
  a silent transposition costs weeks.

## Traps

- Dolphin 1/2 are return-shortcuts (`^self`/`^false`); house 1/2/3 are
  SmallInteger `+`/`-`/`*` (measured, `06_smallinteger.mst:85-100`). The
  spaces collide on almost every low number — there is no "probably the same"
  row.
- Primitives 31/32 are declared but map to `unusedPrimitive` — they must FAIL
  cleanly into Smalltalk fallbacks, never compute (prior-art inventory,
  "Things the porter must know").
- Prim 157 (`primitiveNewInitializedObject`, 73 sites) is the hot one — its
  PRIM_MAP row deserves the most careful semantics note.
- The census greps `.pax` files too (loose methods — the `.pax` trap).
