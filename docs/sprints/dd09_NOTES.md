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

## The one that does not, and why

`View.mst` fails at `close`:

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
