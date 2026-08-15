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

Both mechanical prerequisites are now **DONE** — gate `test/st_routed.dart`.

1. **The funnel carries four arguments.** `_mvpToSmalltalk(kind, a, b, c)`;
   paint/command/destroy fill `(kind, payload, 0, 0)`, a reflected Windows
   message fills `(5, msg, wParam, lParam)`. `UiSession` gains
   `wndProc:a:b:c:`, and the two-argument `wndProc:arg:` stays as a forwarder
   because the DD7 spike suite drives it and those tortures are the door's own
   regression.

2. **A routed-message set in the door.** `Win32 mvpSetRoutedMessages:` takes
   the ids; everything outside the set goes straight to DefWindowProcW. It is
   a flat BITMAP over ids below WM_USER with a short linear tail above,
   because the lookup runs on every message that reaches the default branch —
   it must be a load and a mask, not a search. WM_PAINT keeps its named case:
   it owns the `BeginPaint`/`EndPaint` pair and the `ValidateRect` backstop,
   which is structure, not routing policy.

   `mvpSetRoutedMessages:` answers how many ids it ACCEPTED so a caller can
   compare against what it sent — silently dropping half a message map looks
   exactly like handlers that never fire.

**NIL MEANS NOT HANDLED**, and it is the distinction the whole mechanism turns
on. A view answering nil falls through to DefWindowProcW; answering 0 is an
ordinary LRESULT, and for WM_NCHITTEST it means HTNOWHERE. Collapse the two
and a view can never decline a message it asked to receive. The gate asserts
it by comparing a declined send against an UNROUTED send of the same message,
rather than against a constant — DefWindowProcW's answer depends on its
arguments, so a hardcoded expectation would test the probe's coordinates
instead of the door. (The first version did exactly that and failed:
WM_NCHITTEST at screen point (0,0) is outside the window and correctly answers
HTNOWHERE, which is 0.)

What remains for the acceptance shell is now Smalltalk-side: drive the set
from a translated `buildMessageMap`, and give `UI.View` a real window.

## Carried

- `st/mvp/` holds the four loading classes plus the refusal report.
  `test/st_viewwave.dart` loads them and reports per-file.
- The DD9 gate (code-built shell, resize relayout, focus/tab, registry hygiene)
  is not attempted yet — it needs `UI.View`.
- Still open from the brief: the storm-message probe, and drawing through the
  `WM_PAINT` HDC the door already delivers.

## Dolphin's own message map drives the door

`test/st_mapped.dart`. `UI.View class >> buildMessageMap` is Dolphin's own
method, translated unmodified, answering a 1024-slot Array from message number
+ 1 to a handler selector. `UiSession routeMessagesFrom: View` installs it and
derives the door's routed set from it in one step — **66 messages**, which is
the whole affordability argument made concrete.

Asserted: the map runs and WM_PAINT maps to `#wmPaint:wParam:lParam:`; the
routed set and the map AGREE (a map entry whose message is not routed never
arrives, and that is the silent half of the pair); WM_SIZE and WM_SETCURSOR
reach *different* selectors, so the map is choosing rather than funnelling; a
mapped message the view does not implement DECLINES to DefWindowProcW, which is
how every real Dolphin view behaves since the map is built once on `View` and
each subclass handles its own subset.

## THE D157 CONSTRUCTOR BUG — a silent wrong answer in the translator

Found by asking `Rectangle origin: 3@4 extent: 10@20` for its corner.

`lower_prim157` emits Dolphin's constructor as

```smalltalk
^self basicNew instVarAt: 1 put: a; instVarAt: 2 put: b; yourself
```

and `rewrite_cascades` then split it into

```smalltalk
self basicNew instVarAt: 1 put: a. self instVarAt: 2 put: b. ^self yourself
```

**The cascade receiver is the receiver of the LAST message in the head segment,
not its first token.** Here that is `self basicNew`, not `self`. So the
constructor allocated an object, wrote the first field into it, threw it away,
wrote the remaining fields into the CLASS, and answered the class.

`Rectangle` raised — "class 'Rectangle' has no class-side method
'instVarAt:put:'" — which is the lucky case. A class that happened to
understand the selector would have corrupted itself in silence. This is the
D157 lowering, which is how EVERY Dolphin constructor with a numbered
primitive is translated.

The rewriter now splits the head properly: a keyword message starts at the
first top-level `keyword:` token, a binary at the first top-level operator,
and an all-unary head's final message is its last token — everything before
that is the receiver. A receiver that is a bare primary is repeated as before
(re-evaluating `self` costs nothing); **anything else is bound to a fresh
temporary**, because repeating `self basicNew` would allocate one object per
cascade part. The temporary is merged into the method's own declaration.

Two golden cases pin it, including the exact D157 shape. Refusals moved 13 to
15 — the two new ones are parenthesised receivers, which the rewriter declines
rather than guesses.

## Geometry: the world's omission, reversed

`st/world/28_point.mst` records that `extent:`/`corner:`/`insetRect:` were
"DELIBERATELY NOT ported — they return/accept a Rectangle, Strongtalk's own
UI-toolkit geometry class, which MACVM has no use for at all: the GUI is
HTML/JS-rendered". Correct for MACVM; **this project's goal reverses it**.
`BorderLayout` computes in Rectangles and builds every one of them with
`left @ top extent: width @ height`.

So `Graphics.Rectangle` and `UI.LayoutContext` are translated (not
reimplemented), and the Point-side constructors come back in the compat layer —
`st/dolphin_compat/05_point_rect.mst` — rather than in the world, whose
rationale still holds for the world. Verified: `(Rectangle origin: 3@4 extent:
10@20) corner` -> `13@24`, printing in Dolphin's own format.

One thing worth not misreading: `LayoutContext>>apply` translates to
`true ifFalse: [^self]`. That is the constant folder working — the original is
`DeferRectangles ifFalse: [^self]` and `DeferRectangles` is a class constant
whose value is `true`. The branch is genuinely dead in Dolphin too.

## THE DD9 GATE IS GREEN — the acceptance shell

`test/st_shell.dart` + `st/test/ffi/shell_probe.mst`. A code-built window with
three real Win32 controls, arranged by **Dolphin's own `BorderLayout` running
unmodified**, relaid on every real `WM_SIZE` through Dolphin's own message map.

What is Dolphin's: the layout algorithm (`UI.BorderLayout`), the deferred
batching (`UI.LayoutContext`, `UI.LayoutPlacement`, which routes through the
real `BeginDeferWindowPos`/`DeferWindowPos`/`EndDeferWindowPos`), the geometry
(`Graphics.Rectangle`, `Point`), and the dispatch (`buildMessageMap`). What is
ours: the window, its controls, and `WinView` — the adapter answering Dolphin's
view protocol from Win32 calls.

Asserted against what the north/center/south rules REQUIRE, computed in the
gate independently of the implementation, from `GetWindowRect` — where Windows
actually put the controls, not where the layout intended to:

```
north  [0, 0,   384, 28]     after resize  [0, 0,   624, 28]
centre [0, 28,  384, 205]                  [0, 28,  624, 385]
south  [0, 233, 384, 28]                   [0, 413, 624, 28]
```

Plus: focus moves and a relayout does not steal it (that is what
`SWP_NOACTIVATE` buys, and without the assertion a regression there is
invisible); clean destroy takes the controls with it; the registry empties; and
zero paint faults across the run.

### What the adapter needed, in the order it asked

Each of these was a real gap found by running Dolphin's code, not by reading it:

1. **`LayoutPlacement class >> view:`** — refused by `lower_prim157` as "1 arg
   vs 3 instance variables". But primitive 157 copies arguments into the FIRST
   N instance variables, so fewer arguments than variables is well defined and
   the rest stay nil. Refusing it left `LayoutContext` unable to make a
   placement at all, which took the whole layout down. More arguments than
   variables is still refused.
2. **`WriteStream>>position`** — the ivar was always there, never exposed.
   `repositionSubViewsOf:` uses it as the placement count.
3. **`Object>>species`** — ANSI; a growing stream asks its collection for it.
4. **Stream growth must preserve the backing collection's IDENTITY.** Dolphin
   writes `stream := WriteStream on: (newPlacements := Array new)` and then
   reads back through `newPlacements at: i`. The world's `growTo:` allocates a
   replacement, so that reference stayed the original empty Array and the loop
   raised. Dolphin grows arrays in place; a Dart List does too, so appending
   preserves identity exactly. Two traps inside this one: `(Array new) isKindOf:
   Array` answers **false** (Array is bridged, its instances are Dart Lists), so
   the first version's kind test silently never fired; and `Array>>add:` mangles
   to `add_`, which no Dart List has — hence
   `Smalltalk class >> arrayAppend:with:` in the prelude.
5. **A cross-file reopen cannot call `super`.** `super nextPut:` looks in the
   SUPERCLASS, not at the definition being replaced. The other branch repeats
   the world's two lines instead.
6. **`screenOrigin` is the CLIENT origin, not the window origin.** A child is
   positioned relative to the client area, which the border and caption inset
   from the frame. Using `GetWindowRect`'s top-left put every control out by
   exactly the frame thickness — (8, 31) here — while every width, height and
   *relative* position was already correct. That is the signature of a
   coordinate-space error: the layout looks right and sits in the wrong place.
   `ClientToScreen` on (0,0) is the offset to subtract.
