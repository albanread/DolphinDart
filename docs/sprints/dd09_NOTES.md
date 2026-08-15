# DD9 — View core: NOTES (in progress)

**Status: pre-tasks DONE, first translated View classes LOADING.** 2026-08-15.

## Pre-tasks (done)

**Library alias globals.** Censused rather than guessed — corpus-wide receiver
counts for bare library globals: `User32` 434, `Kernel32` 209, `Gdi32` 148,
`OleAut32` 53, `Ole32` 44, `AdvApi32` 36, `UxTheme` 26, `ComCtl32` 22,
`Shell32` 21, `ComDlg32` 13, `Shlwapi` 13, `Version` 2 — against
`XxxLibrary default …` at **10 sites in all of MVP**. So the bare global is the
idiom translated code binds through.

Verified end to end: `User32 getSystemMetrics: 0` → 2560, `Gdi32 == GDILibrary`,
and `User32 getClientRect:` filling a `RECTL` → 2560×1440, on both arches.

⚠️ **Layer order is load-bearing.** In `st/prims/rt` the aliases run *before* the
generated libraries and every global binds nil. They have their own layer now,
loaded last:

```
st/world;st/dolphin_compat;st/prims/rt;st/prims/structs;st/prims;st/prims/aliases
```

**`default` bridge.** `genprims` emits a class-side `default [ ^self ]` on every
library, so both spellings reach the same generated methods.

## The first View wave

`UI.View`, `UI.ContainerView`, `UI.ShellView`, `UI.BorderLayout`,
`UI.LayoutManager` translated: **897 methods, 28 refusals** (~97%). The refusals
are 25 `##(…)` needing image evaluation (`##(self indexOfInstVar: …)` — out of
scope by design) and 3 binding literals.

**Four of the five load into the world**: `ContainerView`, `ShellView`,
`BorderLayout`, `LayoutManager`.

## All five now load

After three translator fixes the whole wave loads and the hierarchy links
(`ShellView inheritsFrom: View` → true, `ContainerView inheritsFrom: View` →
true):

1. **Cascade → statements.** Dolphin allows a whole message chain as a cascade
   part (`^self destroy; isOpen not`); this dialect allows one message. Split
   into statements — semantically identical when the receiver is a simple
   primary, and REFUSED when it is not, since splitting would evaluate a
   side-effecting receiver once per part.
2. **Qualified class constants.** `NMHDR._OffsetOf_hwndFrom` is a constant read
   through its owning class, not an imported pool. The flattener skipped it (the
   second segment starts with `_`) and the bare-name folder never saw it, so it
   reached the parser as `NMHDR` followed by `._OffsetOf_…`. Now folded — which
   also meant pooling EVERY class's own `classConstants:`, not just
   `SharedPool` subclasses.
3. **Load order is dependency order.** The layer loader sorts by filename, so a
   class must sort after its superclass or it loads against a forward-reference
   stub. Emitted alphabetically, `ContainerView` arrived before `View` existed
   and `ShellView inheritsFrom: View` was **false** — a silent wrong answer, not
   an error. Filenames now carry a zero-padded inheritance depth
   (`01_View.mst`, `02_ContainerView.mst`, `03_ShellView.mst`).

## THE NEXT BLOCKER: class-side `super`

The classes load; they cannot yet be **instantiated**. `View class >> new` is
Dolphin's standard idiom:

```smalltalk
View class >> new [ ^super new initialize ]
```

and the front-end answers `st::BuildGraph: unsupported self/super here
(Sprint 4/5)`. **Not a translation artifact** — a two-line hand-written probe
reproduces it:

```smalltalk
Object subclass: SupA [ SupA class >> new [ ^self basicNew ] ]
SupA   subclass: SupB [ SupB class >> new [ ^super new ] ]     "-> unsupported"
```

This is a **front-end gap**, and it gates the DD9 shell gate: nearly every
Dolphin class constructs through `super new`, so until class-side `super` is
supported no translated view can be instantiated. It is the next piece of work
and it belongs in `st_flow_graph_builder.cc`, alongside the class-side dispatch
machinery DD0 already touched.

## What the old blocker was

(Resolved — kept for the record.) `View.mst` first failed at `close`:

```smalltalk
^self destroy; isOpen not.
```

A **cascade segment containing two unary messages**. A returned cascade parses
fine here (`^self a; b` was tested and loads), so the parser's limit is
specifically a multi-message cascade *part*. Dolphin allows it; this dialect
does not.

That makes it a **translator** job, not a VM one — the same call the
`asUnicodeValue` case settled in DD8: where Dolphin and the house dialect differ
in *form*, rewrite at ingestion. The rewrite is mechanical:

```smalltalk
"^self destroy; isOpen not."     -->     "self destroy. ^self isOpen not"
```

i.e. split the cascade into statements, with the final part becoming the return.
It needs a small cascade parser in `emit.py` and golden cases; it is the next
piece of DD9 work, and until it lands `UI.View` itself is held out of `st/mvp`
rather than shipped broken.

## Carried

- `st/mvp/` holds the four loading classes plus the refusal report.
  `test/st_viewwave.dart` loads them and reports per-file.
- The DD9 gate (code-built shell, resize relayout, focus/tab, registry hygiene)
  is not attempted yet — it needs `UI.View`.
- Still open from the brief: the storm-message probe, and drawing through the
  `WM_PAINT` HDC the door already delivers.
