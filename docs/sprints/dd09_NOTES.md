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

## RESOLVED: class-side `super`, and the four gaps behind it

**`View new`, `ContainerView new` and `ShellView new` all construct.** Getting
there took one front-end change and four more fixes, each of which was hidden
behind the one before it. Gate: `test/st_viewwave.dart` — 11 files load, the
hierarchy links, and the three views instantiate. Battery 17 suites / 0 fails
on both arches.

### 1. Class-side `super` — the front-end gap (st_flow_graph_builder.cc)

`TranslateClassSuperSend`, the instance-side `TranslateSuperSend` one metalevel
up. Resolution starts in the OWNER SHADOW's superclass and walks the shadow
chain; **argument 0 stays `self`, the receiving class**. That is the whole
semantic: resolution goes up, `self` does not — which is why `ShellView new`,
running View's inherited `^super new initialize`, answers a ShellView.

The fallback is the part that carries the corpus. No ancestor defines a
class-side `new`: Dolphin inherits it from a kernel `Object class` this world
does not translate (`st/world/01_object.mst` has no class side at all). So an
unresolved `super new` means RAW ALLOCATION of the receiving class, guarded
inline (StrictCompare against the owner's instance class, `stBasicNew` on the
subclass path). It must NOT re-dispatch: `stClassNewDispatch` would look `new`
up from the receiver, find the running method, and recurse until the stack
ends. Anything else unresolved is refused rather than restarted at the
receiver — a subclass override would otherwise capture a `super` send.

Measured over dsfork, class-side `super` sends: `defineFields` 196, `new` 147,
`stbConvertFrom:` 45, `publishedAspects` 32, `helperClassesDo:` 16, `new:` 9 —
**572 in total**. Pinned by `st/test/features/test_class_super.mst` (15
assertions), including the inherited-constructor case and an explicit
non-recursion check.

### 2. `Object>>initialize` — a compat gap the fix immediately exposed

Quoting Dolphin's `Core.Object.cls`: the default is to do nothing, and it
**answers the receiver**. Both halves matter — `^super new initialize` returns
whatever `initialize` answers. Its instance-side twin (`super initialize` from
a subclass's own) needs it too.

### 3. An ivar may shadow an inherited method — Dart says no (st_loader.cc)

`field 'events' of class 'View' conflicts with method 'events' of super class
'Object ext'`. Dolphin **depends** on that shadow: `Object>>events` answers a
registry-backed collection and 17 corpus classes — View, Presenter, Model,
ListModel, MessageBox, CardLayout … — cache theirs in an ivar of the same name
and override the accessor. Renaming the compat method instead would split the
event store in two (compat `when:send:to:` writing the registry, translated
code reading the ivar), so the FIELD takes a synthetic `events$iv` name while
the Smalltalk spelling is untouched; `IvarOffset` resolves both. `$` cannot
occur in a Smalltalk identifier, so the synthetic name can never collide.

Measured against every unary method our Object carries: `events` is the ONLY
collision. `tools/check_ivar_collisions.py` re-derives the set, because each
new compat method on Object silently widens it.

Two attempts were needed: the first used `Class::LookupFunction`, which routes
through `EnsureIsFinalized` -> the Dart parser and died on
`expected: cls.is_type_finalized()` — the same lazy-parse trap DD0 met. The
check scans each superclass's `functions()` array directly.

### 4. Pool imports are INHERITED (tools/dolphin2mst)

`UI.ContainerView` declares `imports: #()` and writes `WS_EX_CONTROLPARENT`,
binding it through `UI.View`'s `OS.Win32Constants`; `UI.ShellView` declares
only `OS.ButtonConstants` and writes `WS_SYSMENU`. Folding only a class's own
imports left both bare, and a bare constant is not a refusal — it is a runtime
nil inside a bitOr (`_bitOrFromInteger was called on null`).

### 5. `|` is an operator, and the temps scanner did not know

The one worth remembering. `rewrite_pool_constants` collected temporaries with
a bare `\|([^|]*)\|` scan, so in

```smalltalk
##(WS_THICKFRAME | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
```

it read `| WS_CAPTION |` and `| WS_MINIMIZEBOX |` as declarations and shadowed
**every other operand**. Three of five folded; two stayed bare and the method
answered nil. *Alternate* operands surviving is the signature. `collect_temps`
now only opens a declaration where one is legal — start of body, or inside a
block after its `:arg` list. Refusals fell 38 → 32.

### 6. Two more compat gaps the constructor walked into

- **`Graphics.Color`** — `View>>initialize` ends at `backcolor := Color
  default`. Translated as a wave (Color, AbstractRGB, ColorRef, ColorDefault,
  ColorNone, ARGB) rather than stubbed; every painting path in the shell gate
  needs it next.
- **Integer bit-mask protocol** — `st/dolphin_compat/04_integer_bits.mst`.
  The world had none of it and the corpus sends it ~1,300 times: `allMask:`
  505, `mask:set:` 343, `anyMask:` 218, `bitInvert` 71, `maskSet:` 67,
  `maskClear:` 66, `noMask:` 63. Bodies transcribed from `Core.Integer.cls` —
  bit semantics are not worth reinventing. Pinned by
  `st/test/features/test_integer_bits.mst` against hand-computed literals,
  including that `mask:set:` does not mutate its receiver.

### Also landed

`tools/translate_mvp.py` — the regeneration command for `st/mvp`, which was
not written down anywhere. Its reference set is DIRECTORIES on purpose: the
first version listed four files, and that guess silently lost
`NMHDR._OffsetOf_hwndFrom`, which the wider set had folded.

## The original blocker, as it was written

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
