# DD11 — Common controls (= milestone UI-4) `L`

**Objective:** the comctl32 wave, ending in the classic Dolphin acceptance
idiom: a live two-pane class browser. Prior-art G6 transfers as scope + gate.

**Read first:** prior-art G6; the `.pax` CommCtrl constant pools (the
translator folds them — verify DD3 ingested `OS.CommCtrlConstants`);
`InitCommonControlsEx` requirements per control class; the seed's
`59_reflection.mst`/`76_reflection.mst` (the live data source for the gate).

## The wave

`ListView` (report + icon modes, **static update mode v1**), `TreeView`
(`#dynamic` mode), `TabView`/`CardContainer`, `StatusBar`,
`ScrollingDecorator`, `Splitter` + `ProportionalLayout`, ImageList + `.ico`
loading, `ListPresenter`/`TreePresenter`.

## Work

1. Translate the wave; DD6 allowlist grows by the comctl32 set
   (`InitCommonControlsEx`, the `SendMessage` families the controls ride on —
   `WM_NOTIFY` routing lands in the DD7 door if not already).
2. `WM_NOTIFY`: fields read inside the dispatch (per-message struct views via
   the DD6 struct model); **`idFrom` converts UNSIGNED** (WINARM measured the
   `as i64` trap making out-of-range ids plausibly negative — same trap
   exists in any signed conversion here).
3. The acceptance browser (hand-written shell + translated controls): left a
   `TreeView` of the world's classes (from the reflection layer), right a
   `ListView` of the selected class's selectors, bottom a read-only text pane
   showing the method source; selection wiring through presenters.
4. TCL-driven: select a known class → snapshot; select a selector → text pane
   content assert (string, then snapshot).

## Gate (prior-art G6, carried)

- The two-pane browser runs over **live reflection data** — select
  `OrderedCollection`, see its selectors, open one's source.
- ListView report mode shows ≥3 columns with real data; TreeView expands
  lazily (#dynamic proven by a counter on the children-request path).
- Tab/Splitter/StatusBar present and functional in the browser shell.
- Suite green vs baseline; corpus checkpoint recorded (≈ +40 band).

## Traps

- Common controls need `InitCommonControlsEx` **before** the first control
  class is created, on the UI thread — put it in the DD7 host init, not in a
  lazily-hit native.
- ListView/TreeView item text lives in *your* memory during
  `LVN_GETDISPINFO`-style callbacks — the struct model must keep the UTF-16
  buffer alive past the native return (a use-after-free that snapshots
  correctly 99 times).
- Icon plumbing (`ImageList`) can eat a week — v1 ships with a single stock
  icon set; fidelity is backlog.
