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

## The storm probe — and the two bugs it found

`test/st_storm.dart`, with a per-message census and a routing switch in the
door (`win_mvp.cpp`). Routing stays **off** by default: the census counts and
classifies, the switch exists so the same message can be timed both ways in
one run, one variable apart.

### The measurement (arm64, 20,000 sends each)

| message | DefWindowProcW | routed to the image | ratio |
|---|--:|--:|--:|
| WM_NCHITTEST | 4810 ns | 28318 ns | 5.9x |
| WM_MOUSEMOVE | 94 ns | 26616 ns | 283x |
| WM_SETCURSOR | 1018 ns | 25792 ns | 25x |
| WM_SIZE | 102 ns | 24504 ns | 241x |

The prior art's ~154x on WINARM is the right order of magnitude. The absolute
number is what matters for the gate: **~26 µs per routed message**, so a drag
producing a few hundred messages a second spends a few percent of a core in
the door. That is survivable for WM_SIZE relayout — which is what DD9 needs —
and it is why storms stay unrouted by default. WM_NCHITTEST is nearly free to
route in relative terms only because DefWindowProcW's own handling of it is
expensive.

The probe asserts its own integrity: a routed 500-message burst must produce
exactly 500 image entries, and an unrouted one exactly 0. Without those, the
"routed" column could be timing the DefWindowProc path twice and the ratio
would be meaningless.

### 7. A class-variable store in a hot method killed the VM

```
intermediate_language.cc: 51: error:
  expected: !Compiler::IsBackgroundCompilation() || !field.IsOriginal()
```

A background-compiled method may not hold the ORIGINAL `Field` — the mutator
may be changing it. Dart's own builders route every such field through
`MayCloneField` (ast.cc:32, kernel_to_il.cc:2598); this builder did not.
`UiSession wndProc:arg:` does `MessageCount := MessageCount + 1`, and 20,000
sends is enough to promote it to optimizing background compilation.

**Not specific to that method.** Any class-variable assignment in a hot path
would have done it — which is most of the compat kernel's registries and every
Dolphin class that counts something. It had simply never run hot before.
Loads are safe (`LoadStaticFieldInstr` takes a Value and never calls
`CheckField`) and so is the instance-side store (this builder uses the OFFSET
constructor, which holds no Field at all).

### 8. The door resolved its receiver classes BY NAME, per message

`stClassNamed` searches every loaded `st:` library, and the funnel called it on
every message — twice when `UiSession` answered null. First measurement:
**345 µs per routed message**, 3651x DefWindowProcW for WM_MOUSEMOVE.
Resolving once took it to 26 µs — a **13x** improvement from three cached
variables.

Only non-null results are cached, so a class not yet loaded stays unresolved
and is found when it arrives; and both entry points that mark a new world
(installing the dispatch, bumping the generation) forget them, because a world
reload can replace a class outright.

This is the shape of finding the probe exists for. Neither bug was reachable
by any correctness test — one needs a method to run 20,000 times, the other is
invisible until you ask what a message costs.

## Drawing through the WM_PAINT HDC

`test/st_paint.dart` + `st/test/ffi/paint_probe.mst`. The door has handed the
image a real HDC since DD7 and nothing had drawn with it; this closes the
chain — real `WM_PAINT` -> door -> `UiSession` -> a Smalltalk handler -> GDI
through the generated prims.

**Verified by readback, not by counting.** A paint count proves a handler was
entered and nothing more. `SetPixelV` followed by `GetPixel` at the same
coordinate, inside the same `BeginPaint`/`EndPaint` pair, proves the device
context is real, the arguments reached GDI in the right order, and the pixel
landed where we asked. A broken link answers `CLR_INVALID` (16rFFFFFFFF) or the
background colour — it cannot answer the exact COLORREF we wrote by accident.
The ink is pure blue (16rFF0000, COLORREF being 0x00BBGGRR) precisely because
it is neither the background, nor black, nor white.

Also asserted: a SECOND paint after `invalidate` draws too (so this is not a
one-shot that worked during window creation), and the door's paint-fault
counter is zero (so no handler raised and got backstopped by `ValidateRect`).

One finding: `TextOutW` takes the STRING, not its address. The generated
wrapper marshals it itself (`FFICoerce stringTemp:` -> a `Utf16Buffer` freed
under `ensure:`), and handing it a raw address is refused outright — *"FFI:
cannot pass SmallInteger as a string argument"*. That refusal is the floor
working as designed: a wrapper that accepted an integer there would hand
TextOutW whatever happened to be at that address. `cbString` is a CHARACTER
count, not a byte count.

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

## What the storm number decides about the acceptance shell

The remaining gate (code-built shell, BorderLayout, live resize relayout,
focus/tab, clean destroy) needs translated `ShellView` code to own a real
window, and that forces a choice the measurement now settles.

Dolphin's `View` creates its windows against a class whose WndProc is
Dolphin's own dispatcher, and that dispatcher reflects **every** message into
the image, routing it through `View class >> buildMessageMap` — a
message-number → selector table the class builds once. Reflecting everything
at ~26 µs a message is not affordable during a drag.

But `buildMessageMap` is itself the answer: it is an explicit, per-class list
of exactly the messages Dolphin wants. **The door should ask the image for
that set once and reflect only those**, DefWindowProcW-ing the rest — which is
what the census already shows is the common case. The measurement makes this a
design conclusion rather than a preference: the routed cost is fixed and known,
so the lever is the message COUNT, and the corpus hands us the minimal count
for free.

Two mechanical prerequisites, neither started:

1. **A wider funnel.** `_mvpToSmalltalk(wp, lp)` carries a kind and one
   payload; a reflected Windows message needs `(msg, wParam, lParam)`. The
   funnel goes to four arguments — `(kind, a, b, c)` — with paint/command/
   destroy filling `(kind, payload, 0, 0)`. `UiSession wndProc:arg:` gains the
   four-argument form, and the DD7 spike classes must keep working against the
   raw door since they are the door's own regression.
2. **A routed-message set in the door**, replacing the hardcoded
   paint/command/destroy switch plus the DD9 storm list. WM_PAINT keeps its
   named case regardless: it owns the `BeginPaint`/`EndPaint` pair and the
   `ValidateRect` backstop, which is structure, not routing policy.

## Carried

- `st/mvp/` holds the four loading classes plus the refusal report.
  `test/st_viewwave.dart` loads them and reports per-file.
- The DD9 gate (code-built shell, resize relayout, focus/tab, registry hygiene)
  is not attempted yet — it needs `UI.View`.
- Still open from the brief: the storm-message probe, and drawing through the
  `WM_PAINT` HDC the door already delivers.
