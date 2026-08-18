# Journal

Running log of what changed and why, newest last. Status lives HERE, not in
chat. `docs/LOOSE_ENDS.md` holds what is still owed; this holds what happened.

---

## Retiring the `WinView` adapter family

**Goal:** delete `WinView`, `WinControl`/`WinTextEdit`/`WinButton`/`WinLabel`,
`WinMenu`/`WinAccelerators` and `TextField` — the DD8/DD9 stand-ins that
answered Dolphin's view protocol over raw HWNDs before the real classes were
reachable.

**They cannot go one at a time.** `WinControl` is a `WinView` subclass and the
probes build on both, so the family is one commit.

### What depends on them, measured rather than assumed

Code references (mentions in the surviving gates are all COMMENTS):

| probe | uses | gate |
|---|---|---|
| `shell_probe.mst` | WinView | `st_shell` |
| `text_probe.mst` | WinView, WinTextEdit, TextField | `st_text` |
| `command_probe.mst` | WinMenu | `st_command` |
| `counter_app.mst` | all of them | `st_app` |

### The decision: MIGRATE, not delete

`docs/LOOSE_ENDS.md` said `st_shell` was "fully superseded by
`st_dolphinshell`". **That was wrong**, and checking the assertion lists
rather than trusting the note is what caught it. Each old gate carries
coverage its Dolphin-side successor does not:

- **`st_shell`** — FOCUS: focus moves between controls, and a relayout does
  not steal it. `st_dolphinshell` asserts arrangement only.
- **`st_text`** — TWO fields sharing ONE model, both directions. `st_textedit`
  has a single field.
- **`st_command`** — command ENABLEMENT (`queryCommand:` greying an item).
  `st_menu` asserts routing only.
- **`st_app`** — the acceptance app: bad-input revert, long command, worker.

Deleting them would have retired the scaffolding and quietly dropped four
distinct behaviours from the suite. So the probes move to Dolphin's own
classes and the assertions come with them.

### Done — the family is gone, 21/21

Deleted: `06_winview.mst`, `09_wincontrol.mst`, `10_winmenu.mst`,
`shell_probe.mst`, `text_probe.mst`, `command_probe.mst`, `counter_app.mst`,
and the four gates that drove them.

Coverage moved first, then the deletion:

| was | now | on |
|---|---|---|
| `st_shell` focus | `st_dolphinshell` | `UI.View setFocus/hasFocus` |
| `st_text` two fields one model | `st_textedit` | two `UI.TextEdit` + `TextPresenter` |
| `st_command` enablement | `st_menu` | `queryCommand:` + `CommandQuery` |
| `st_app` acceptance app | `st_dolphinapp` | `UI.ShellView`/`TextEdit`/`MenuBar` |

**The deletion broke the layout, and the reason is worth keeping.**
`06_winview.mst` also contained `Dictionary>>lookup:` — nothing to do with
the adapter, it just lived there because `WinView` and the `LayoutContext`
work were written at the same time. `LayoutContext` asks
`(placements lookup: aView)` on every pass, so with it gone the whole
BorderLayout arrangement silently reverted to the 100x100 creation default:
every view still laid out, none at the size it asked for.

**When deleting a scaffolding file, what it HOSTS is not what it is FOR.**
The gates caught it on the first sweep after the delete, which is the only
reason it is a footnote rather than an incident.

### What the migration cost, in substrate

Each of these was found by the app failing, not by inspection:

- `DesktopView` needed three more walk terminators — `nameOf:`,
  `ambientBackcolor`, `backcolor`. `View>>name` and `View>>actualBackcolor`
  both walk the parent chain to the desktop, and Dolphin's DesktopView ends
  both walks. Ours ended neither.
- `Color class >> initialize` was failing, so `Color default` was nil and
  every WM_ERASEBKGND raised. Behind it: `Graphics.RGB` untranslated
  (`Color>>asRGB` needs it), `asSortedArray:`/`asArrayCopy` missing, and
  `addClassVariable:` — the same dynamic-name shape as `addClassConstant:`,
  so the translator rewrite was widened to cover both.
- `Color`'s `Window`/`WindowText`/`Face3d` class variables are only ever READ
  in `Color.cls`; the system-colour package that assigns them is not in the
  wave. Supplied from `GetSysColor` so a themed desktop gets its real colour.
- `View>>onEraseRequired:` now answers nil — declining the message, which is
  Dolphin's own documented way to accept default window processing. It needs
  `Graphics.Canvas` (DD11). **Cost: a view's `backcolor` is not honoured when
  erasing.** Recorded in LOOSE_ENDS with the gate that will prove its
  retirement.
- A multi-statement `stRun` abandons the rest of the string on a raise, so
  `App create. App show. App build.` left `model` nil and every later
  assertion blamed the model. Setup sends are separate now.

## The bad-input path — DD4's exceptions in anger

`st_dolphinapp` now drives Dolphin's own `updateModel`, which carries the
whole policy:

```smalltalk
[self model value: (self typeconverter convertFromRightToLeft: self displayValue)]
    on: InvalidFormat
    do: [:e | e beep.
              self value: self typeconverter leftNullValue; refreshContents]
```

The probe catches NOTHING. Wrapping it would replace Dolphin's policy with
the test's, and the policy is what is under test.

Three things had to be right for it to run at all, and each was silent:

1. **The converter must be installed BEFORE the presenter connects.**
   Connecting pushes the model's value through the view's converter
   immediately; installing it afterwards re-ran that path against whatever
   text the control held and wrote nil back into the model. The app started
   empty and every later assertion blamed the model.

2. **`setWindowText:` does not set the modify flag.** `TextEdit>>updateModel`
   opens with `self isTextModified ifFalse: [^self]` — Windows' EM_GETMODIFY,
   which real typing sets and a programmatic WM_SETTEXT deliberately does not.
   Without `isTextModified: true` the update returned immediately: the probe
   looked like it had typed and nothing had happened.

3. **`Boolean>>asParameter`.** `isTextModified:` sends
   `aBoolean asParameter` and `Object>>asParameter` answers self, so a Boolean
   reached the FFI floor and was refused. Added Dolphin's own method AND made
   the floor accept true/false as 1/0 — the mirror of `#b`, exactly as nil is
   the mirror of `#h`: a BOOL-returning call ANSWERS a Boolean, so Booleans
   are values the floor produces and must take back.

Plus `Exception>>beep` — the audible half, and not decoration: it is the only
feedback a user gets that what they typed was rejected.

**21/21.** DD10's acceptance items are now all covered on Dolphin's own
classes: two fields one model, converters and the bad-input revert, commands
with `queryCommand:` enablement, menus, a worker-backed long command, and
accelerators via `UI.AcceleratorTable`.

**Still owed for DD10: a VISIBLE shell, and the first attempt did not count.**

`demos/dolphin_app.dart` puts a window on screen with a menu and two fields
attached, and that is all it proves. Judged as a demo it is not interesting:
it has no real event loop of its own beyond a `UiSession pump` slice in a
Dart `while`, nothing was driven through it by hand, and a screenshot of a
window is not evidence that anything in it works. Keeping it as "done" would
have been the same self-deception this project keeps writing gates to avoid.

The demo file stays — it is a harness worth having — but **the item is still
open**, and what it actually needs is: a shell that owns its own message loop,
keyboard input reaching a control, a menu opened and clicked by a person, and
the accelerator firing. None of that is shown yet.

## DD11 — the graphics wave lands; the font stand-in is retired

`Graphics.Canvas`, `Font`, `AbstractFont`, `SystemFont`, `StockFont`, `Pen`,
`StockPen`, `Brush`, `StockBrush`, `Image`, `Icon`, `Cursor` translated and
loading. 21/21.

**`SystemFont` (LOOSE_ENDS 1.2) is RETIRED** — and deleting it was not
optional, it was forced. Dolphin's own class is `Graphics.SystemFont`, which
flattens to `SystemFont`: the same name as the stand-in. `st/mvp_compat` loads
AFTER `st/mvp`, so the stand-in would have silently overwritten Dolphin's
class and every font in the port would have been a null handle wearing
Dolphin's name. The font walk now ends where Dolphin ends it:
`^self font ifNil: [self iconTitleFont]`.

Four things had to be fixed to get there:

1. **A qualified class-variable WRITE was translated as an assignment to a
   message send.** `Cursor.Current := self` in `Icon>>showWhile:` became
   `Cursor classVarCurrent := self`, which is not Smalltalk — it took
   `Graphics.Icon` down at load. Writes now become `Cursor classVarCurrent:
   self`, and `emit_class` emits the setter beside every reader.

2. **`byteSize`** — Dolphin's spelling for a struct's size, sent to BOTH the
   class and an instance (`struct := aClass new. ... uiParam: struct
   byteSize`). Emitted per struct on both sides by `genstructs`, as a literal
   rather than `^self size`: `size` is a universal helper rewritten at the
   call site, and it cannot be aliased on `ExternalMemory` because a `self`
   send inside an inherited class-side method binds to the defining class
   (LOOSE_ENDS 3.12).

3. **`StockFont` was missing**, so `AbstractFont class >> reset` —
   `System := self fromId: 13` → `StockFont newId:` — left `System` nil and
   every `Font system` answered nil.

4. **`gen_prims.py` now runs `genstructs` too.** They share a corpus root and
   a winkb and write into the same tree; regenerating one without the other
   is how a field offset and the call that reads it drift apart. It was
   another required `--corpus` with no default.

**Still standing:** `View>>onEraseRequired:` still answers nil. `Canvas` is
translated but the erase path wants a Canvas built from a DC, which is the
next piece — so a view's `backcolor` is still not honoured when erasing.
`Cursor` likewise: Dolphin's own is translated but the compat one still
shadows it, and that swap needs the same care the font swap did.

## DD11 — common controls: translated and loading; the gate is WIP

`UI.ListControlView`, `UI.IconicListAbstract`, `UI.ListView`, `UI.TreeView`,
`UI.ListModel`, `Graphics.ImageList`, `ImageManager`, `IconImageManager` all
translate and load. 21/22 — everything green except `st_controls`, which is
the new gate and not yet passing.

**`InitCommonControlsEx` is in the door**, on the class-registration path
(`EnsureTopClass`), which is the DD11 brief's named trap. The first control
CREATED decides whether the whole comctl32 wave works, and a lazily-hit call
can land on the wrong thread or after the fact. Without it `CreateWindowExW`
for `SysListView32` fails with ERROR_CANNOT_FIND_WND_CLASS — a plain creation
failure with nothing in it to say a registration step was missed.

### Two translator defects, both of which took a class file down at load

**A qualified constant that could not be folded was left as `Owner.NAME`,
which is a SYNTAX ERROR.** `UI.IconicListAbstract` reads
`NMCUSTOMDRAW._OffsetOf_dwDrawStage`, and those constants live in a struct
`.cls` this pipeline does not parse — the structs come from winkb. It now
rewrites to the SEND `Owner NAME`, the same choice and reasoning as the
class-variable rewrite: a doesNotUnderstand at the call is loud and locatable
where a parse error is neither. `genstructs` emits `_OffsetOf_<field>`
class-side for every generated struct so these resolve, ZERO-BASED to match
Dolphin (the accessors add 1 for this dialect's indexing; emitting the
1-based number would be off by one everywhere, silently).

**That fix immediately over-fired.** `External.FunctionDescriptor` matches the
same pattern and is a NAMESPACED CLASS NAME, not a constant — rewriting it to
`External FunctionDescriptor` made `Menu class >> initialize` send to a nil
`External`, and `st_dolphinview` caught it on the next sweep. The
discriminator is the one this file already documented: a constant starts with
`_` or is SHOUT_CASE; a class name is CamelCase.

### The pools, again

`TreeView>>defaultWindowStyle` failed with *"the method `|` was called on
null"* — an unfolded `TVS_*` constant reaching a `bitOr:`. `OS.TreeViewConstants`
and `OS.ListViewConstants` live in `MVP/Views/Common Controls`, which was not
in REFERENCES. **This is the fourth time an unfolded pool constant has cost a
debugging session**, and it always presents the same way: a nil inside an
arithmetic or bitwise send, never a refusal.

### OPEN — a VM assertion, and it blocks the gate

```
assembler_arm64.cc: 377: error: expected: object.IsOld()
  dart::Assembler::CanLoadFromObjectPool
  dart::Assembler::LoadObjectHelper
  dart::CompileFunctionHelper / DRT_CompileFunction
```

Compiling something in the newly-translated control wave embeds a NEW-SPACE
object in the generated code's object pool, which the ARM64 assembler asserts
against. Same family as the DD9 `Field::IsOriginal` crash that needed the
field cloned under background compilation — an object that must be old-space
to be referenced from code.

**This is the next thing.** It is a VM-level fix, not a translation one, and
it wants a fresh session rather than the tail of a long one: the honest next
step is to find which literal is being embedded (the object pool entry names
it) rather than guess at the wave.

---

## DD11 — `st_controls` GREEN. 22/22.

A real `SysTreeView32` and a real `SysListView32`, created by Dolphin's own
`View>>create`, subclassed by its own `ControlView>>subclassWindow`, with
Windows asked for each class name rather than the Smalltalk class trusted.

Twelve distinct defects between the last entry and this one. They are worth
listing because only one of them was in the control wave.

### 1. The VM assertion — a Dart 1.24 bug, and the same function proves it

`assembler_arm64.cc:377 expected: object.IsOld()`. A diagnostic in the flow
graph builder's `Constant()` named the object immediately: `Type: class
'TreeView'`, with `canonical?=1 canonIsOld=0 sameAsCanon=1`. So the class's
own canonical type was new-space.

A second diagnostic, at the store (`Class::set_canonical_type`), named the
creator: `Object.runtimeType` → `Instance::GetType(Heap::kNew)` →
`Type::Canonicalize`. And `Type::Canonicalize` has TWO paths. The general one
promotes before installing:

```cpp
if (this->IsNew()) { type ^= Object::Clone(*this, Heap::kOld); }
else               { type ^= this->raw(); }
ASSERT(type.IsOld());
```

The FAST path — non-generic, non-closure, non-typedef, i.e. every Smalltalk
class in this port — stored `*this` with no promotion. So printing an object
before any code embedded its type poisoned the class permanently, and the
failure surfaced arbitrarily later inside the assembler with only compiler
frames on the stack.

Fixed by applying the same promotion in the fast path, and
`Class::set_canonical_type` now `ASSERT(value.IsOld())` so any future
violation fails at the store rather than in the ARM64 assembler.

### 2. `classConstants:` values were being dropped — nine classes, not three

`TreeView>>updateMode:` died with `at:` sent to nil. `UpdateModes` was
DECLARED as a class variable and never assigned. So were `LvModes` and
`ViewModes`, and each was briefly a hand-written table in `mvp_compat`.

They were all wrong. The values ARE in the corpus:

```
classConstants: {
    'UpdateModes' -> (IdentityDictionary withAll: {
            #dynamic -> TreeViewDynamicUpdateMode. ... })
}
```

`pools._ENTRY` stops a value at the first `.`, newline or `}` — right for the
scalars it was written for, and it silently truncated every multi-line one.
`pools.class_constant_entries` now walks the brace group properly, and
`emit_class` emits an `initializeClassConstants` per class, CALLED as a
top-level statement at the class's own place in the load order (a file-in
loader never sends a class-side `initialize` — the second time this port has
paid for that). Nine classes got one, not the three being chased.

### 3. Dolphin's struct `.cls` offsets are 32-BIT

The most dangerous find. `OS.LVCOLUMNW.cls` declares `_OffsetOf_pszText ->
16rC` (12) and `_LVCOLUMNW_Size -> 16r2C` (44). On a 64-bit target the pointer
is 8-aligned: the field is at 16 and the struct is 56 bytes, which is what
`genstructs` emits from winkb.

Folding the corpus's own constant wrote a caption pointer into `cx` and the
process died in comctl32 with an access violation — no Smalltalk error at all.
The `--reopen` path now rewrites `_OffsetOf_*` to a send to the generated
class rather than folding, so the offset that is used is always the one the
accessors were built from. **This is the one place in the translator where
the corpus's own value is the wrong one.**

### 4-12, shorter

* **`Message` had no constructors.** `View class >> defaultGetTextBlock` is
  `^Message selector: #displayString` — a Message used as a monadic valuable.
  Ours was a two-accessor DNU payload. Now Dolphin's real one, including
  `value:`; the VM's DNU reification pointed at a phantom `STMessage` that no
  layer defined, so the one path it existed for always threw.
* **`Object>>value ^self`** — Dolphin defines it, which is what makes
  `at: k ifAbsent: 0` legal, and `View>>getNoRedrawCount` is exactly that.
  It CANNOT be written in Smalltalk here: `value` is a universal helper the
  builder rewrites at the call site, and defining it took out every MVP gate
  with an access violation on a blown stack. It lives in `_stValue0Slow`.
  Neither `_stHasMethod` nor `stRespondsTo` can gate it — `Character>>value`
  is in `_stCharProtocol`, reached through the VM's object-NSM hook — so the
  send is attempted and the miss caught on the message naming `value`.
* **`Point` arithmetic did not coerce.** `(16@16) * 144` raised `int has no
  method 'x'`. Dolphin's contract is `asPoint` on the operand;
  `scaledImageExtent` is `imageExtent * self dpi // 96`, so DPI-scaling every
  icon in every list and tree was broken — on a 96-dpi display too.
* **`genstructs` discovery missed a whole category.** It took struct names
  from `X*` FFI-pragma arguments; the common controls are driven by
  `SendMessage`, so no pragma ever names `LVCOLUMNW`. Now also: DECLARED as an
  `External.Structure` subclass (transitively — `LVITEMW` descends from
  `CCITEM`) and referenced from another file.
* **`--reopen`**, new: translate a `.cls`'s own methods onto a class this
  project GENERATES. `genstructs` builds the layout, the `.cls` carries
  `fromColumn:`. An ivar list in a reopen REDEFINES the class in this dialect
  (it dropped `sizeInBytes` and `newBuffer` then allocated nothing), so the
  struct's own ivars are emitted by `genstructs` instead.
* **Enum-typed struct fields now get accessors.** winkb records `size_bits`
  for an enum exactly as for a struct. This RETIRES the LOOSE_ENDS entry and
  the eight hand-written accessors in `03_struct_accessors.mst`.
* **Setters for every width.** The generator emitted one only for 32-bit
  fields, so every pointer field had a getter and no setter —
  `MENUITEMINFOW>>dwTypeData:` among them, hand-written to make menus work.
* **`SearchPolicy>>newLookupTable`**, **`removePropertyAt:ifAbsent:`**,
  **`Point>>strictlyPositive`**, **`int32At:put:`/`int16At:put:`/`int8At:put:`**,
  **`ExternalMemory>>bytes`/`yourAddress`** — plain gaps, each on the
  construction path.
* **`onStartup` was never sent.** A second initializer Dolphin runs at image
  start, for what depends on the machine rather than the class.
  `ListView class >> onStartup` sets `SelectionStateMask`, so creating a
  ListView wrote nil into an LVITEMW. Sent explicitly for `ListView` in
  `initializeViewClasses`; retires when `includesSelector:` exists.

### Still open

`View>>onEraseRequired:` answers nil; `basicNew:` answers the class rather
than raising; `<commandQuery:>` pragmas dropped (14 sites); and the VISIBLE
SHELL — a real message loop, keyboard reaching a control, a menu clicked by a
person. That last one is still the honest gap and is not closed by any gate.

---

## DD11 — the browser gate: registered, WIP, and blocked on one thing

`st_browser` builds a three-pane shell over LIVE reflection data
(`ClassMirror allClasses` / `selectorsOf:`), populates a TreeView through
Dolphin's own `TreeModel>>add:asChildOf:`, and asks WINDOWS for the item
counts (TVM_GETCOUNT, LVM_GETITEMCOUNT) rather than trusting the models.

What passes already: the reflection data is real and the hierarchy assertions
hold; the shell opens; `populateTree` completes; **the tree has one root**,
which is the shape assertion — Magnitude is the root and Number/Integer
descend from it, so a flat tree fails there and nowhere else.

Two things were needed to get that far, both now in:

* **`TVINSERTSTRUCTW`** — genstructs sized it 24 bytes because Win32Metadata
  models its `item` as an anonymous union. It is 96. That is an
  under-allocation handed straight to comctl32, not a missing accessor.
  Restated in `03_struct_accessors.mst`, derived from the two numbers the
  generator did get right. LOOSE_ENDS 3.19.
* **Handle typedefs, derived rather than listed.** Win32Metadata models every
  opaque handle as a struct with one pointer-sized `Value` field. `HWND` was
  in genstructs' hardcoded name list; `HTREEITEM` was not, so it came out as a
  read-only nested VIEW and `TVINSERTSTRUCTW>>hParent:` did not exist at all.
  The rule is now derived from the metadata, which also stops the list growing
  once per control family.

### The blocker, and it is older than this sprint

`Array class >> new:withAll:` and `Array class >> writeStream:` are sent by
Dolphin's tree and list code. Adding them to `st/world/10_array.mst` did
nothing. Neither did a trivial `zzProbe` in the same class body immediately
before the working `Array class >> with:`.

`Array` is BRIDGED — `Array class name` answers `_Type@…` — and its class side
is populated from somewhere a `.mst` reopen does not reach. The proof that
this predates DD11: `Array class >> withAll:`, written in
`52_collection_ext.mst` long ago, has never been reachable either.

**A class-side method on `Array` in a `.mst` file loads without complaint and
is never called.** That is the exact silent-no-op shape this project keeps
paying for, and it is now LOOSE_ENDS 3.18 with a named retirement.

The two missing methods are both reached from inside a WM_NOTIFY handler,
which contains its errors by design, so they never surface as a failed
assertion — only as `handler error in …>>wmNotify:` lines. Worth remembering
when the next control refuses to populate.

**Next:** find where `Array`'s class-side protocol is registered and either add
the two methods there or make a bridged class's class-side reopen install
properly. The second is the real fix; the first leaves the trap for the next
selector.

---

## DD11 — the bridged-class dispatch hole, and st_browser at 1

### `Array` class-side reopens: the hole was in `STSendCommon`, not `stClassSend`

`st_loader.cc` holder-izes a bridged core name — a world file's
`ArrayedCollection subclass: Array [...]` registers as `Array ext` — so its
class-side methods land on `Array ext class`. The first fix added that shadow
to `STClassSendCommon`'s lookup and changed nothing, because **these sends
never reach `stClassSend` at all**. The error said so and I did not read it:
`stSend: Array class has no method 'withAll:'`.

For a bridged name the class value is the PRELUDE's Dart class, so the builder
emits a DYNAMIC send. `STSendCommon` then walks `recv.clazz()` — the internal
`_Type` — whose chain holds no Smalltalk whatsoever, and the metaclass shadow
was never consulted from that path.

The fix is a class-side fallback in `STSendCommon`: when the dynamic walk
misses and the receiver is a Type, look up the metaclass shadows via
`LookupClassSideMethod` (`Foo class`, then `Foo ext class`), holder second so
it can only fill genuine misses. `Array class >> withAll:` — dead since the
day it was written in `52_collection_ext.mst` — now resolves, and
`new:withAll:` / `writeStream:` sit beside it and work.

### Two more flattenings, both in genstructs, both silent

**Handle typedefs, now derived.** Win32Metadata models every opaque handle as
a struct with one pointer-sized `Value` field. `HWND` was in a hardcoded name
list; `HTREEITEM` was not, so it came out as a read-only nested VIEW and
`TVINSERTSTRUCTW>>hParent:` did not exist. Derived from the metadata now,
which also stops the list growing once per control family.

**The struct HIERARCHY, now preserved.** `OS.TVITEMEXW` is a subclass of
`OS.TVITEMW`, which is a subclass of `OS.CCITEM`. genstructs emitted all three
as flat `ExternalMemory` subclasses, so `maskIn:`, `children:` and
`beStateExpandedOnce` — which TreeView's notify handlers are written entirely
over — were unreachable from the subclass that actually receives them.

### Two translator bugs the reopen path surfaced

* The `_OffsetOf_*` rewrite ran BEFORE pool folding, so folding then replaced
  the name the rewrite had just qualified: `TVITEMW _OffsetOf_mask` came out
  as `TVITEMW 0`. Those names are SHADOWED now, which is the existing "already
  bound, do not fold" mechanism.
* The `bytes` -> `self bytes` rewrite fired on a cascade PART, where `bytes`
  is a selector rather than the ivar. `TVITEMW class >>
  initializeCallbackPrototype` is `self new allCallbacks; bytes` and became
  `; self bytes`, which is not a cascade part and would not parse.

### st_browser: 1 assertion short, and it is a real one

Everything else is green — reflection data, the shell, `populateTree`, the
tree's SHAPE (one root), the root item reaching Windows, the ListView filled
from real selectors with the count matching reflection, the text pane, and
BOTH dependent panes re-driving on a class change. No contained handler
errors.

The remaining failure is the lazy child insert: a `#dynamic` TreeView holds
only its roots until expansion, and `expand:` does not yet produce children in
the control. The whole chain exists and now has its protocol — TVM_EXPAND ->
TVN_GETDISPINFO -> `onDisplayDetailsRequired:` -> `children:` ->
TVN_ITEMEXPANDING -> `addItems:inHandle:afterHandle:` -> TVM_INSERTITEM. What
is not yet established is which link is silent; nothing raises, so it is a
notification that is not arriving or a lookup answering nil on the quiet path.

**Next:** instrument the tree with a counting subclass to find which
notification does not arrive, rather than reasoning about it. That is one
sitting, not a sprint.

### A day lost to two bad readings, worth recording

`gen_snapshot.exe` began failing mid-session. Git-bash reports a Windows
Application Control block as "Segmentation fault", and a `| tail` pipeline
made `EXIT=$?` report tail's status rather than the program's — so a policy
block read as a crash that appeared to come and go. I bisected the VM for it.
The cause was **Smart App Control**, which arms itself on a clean install and
flips from evaluation to enforced on its own. Turning it off needs a REBOOT:
the registry state goes to 0 immediately and the loaded policy keeps
enforcing until restart.

---

## DD11 — a pump, a camera, and what they immediately showed

Both at the user's suggestion, and both earned their place within the hour.

### The pump

`UiSession pump` drains a budget and returns, which is right for a gate and
useless for a window a human is looking at: nothing pumps, so WM_PAINT never
runs. **Every window this port has shown anyone has been an unpainted frame.**

`runFor:` and `runUntilClosedOr:` pump until a deadline, sleeping (SleepEx 10)
when the queue is empty rather than spinning. Provisional and named so: a real
run loop blocks in GetMessage and idles at zero cost; this wakes 100 times a
second regardless. Retirement is a blocking wait in the door.

### The camera

`Win32 mvpCapture:path:clientOnly:` — PrintWindow with a BitBlt fallback, into
a 24-bit BMP; `tools/shot.py` re-wraps it as PNG with nothing but `zlib` and
`struct`. `test/st_demo.dart` opens the browser shell, pumps for a real
interval, and photographs it at intervals.

**The first picture was worth the whole detour.** It showed: the window
painting; BorderLayout placing all three panes correctly; the TextEdit
displaying LIVE reflection data — `Integer | 33 selectors`; the ListView with
a working scrollbar sized for 33 rows — and **not one row of text, and an
empty tree**.

That is a distinction no assertion in this suite could make. `listItemCount`
answers 33 and passes either way.

### What the picture led to, and what it did NOT

Reading the corpus against the generated structs found a real defect:
**Dolphin's WM_NOTIFY handlers index past NMHDR with 32-bit literals.**
`NMHDR` is 12 bytes on Win32 and 24 on x64, so

    nmGetDispInfoW:   `pNMHDR asInteger + 12`   should be + 24
    tvnItemExpanding: `uint32AtOffset: 12`      should be 24  (action)
                      `pNMHDR asInteger + 56`   should be 88  (itemNew)

Same shape as LOOSE_ENDS 3.14 one level up, and it fails silently: the expand
guard compares a slice of `idFrom` to TVE_EXPAND, finds it unequal, and
returns. `st/mvp_compat/05_notify_offsets.mst` overrides both families with
offsets DERIVED from the generated `_OffsetOf_` constants, and records the
handlers deliberately left alone.

**It changed nothing on screen, and that is the finding.** A counter in each
overridden handler came back EMPTY: `Dictionary ()`. Neither
TVN_GETDISPINFO nor TVN_ITEMEXPANDING reaches the image at all. WM_NOTIFY
does reach the shell — its earlier `Array` errors are how the whole
class-side hole was found — but it is not being dispatched onward to the
control's own handler.

So the offsets were a bug fixed by reading, sitting behind the bug that
actually matters. Worth keeping (they would have been wrong the moment
dispatch started working) and worth being clear that they are not the fix.

**Next, and it is now a narrow question:** follow WM_NOTIFY from
`View>>wmNotify:wParam:lParam:` to the child control and find where the chain
stops. The counters are in place to answer it in one run.

---

## DD11 — the notify dispatch: ONE LINE was stopping every handler

`ControlView>>nmNotify:` decodes a notification's code as

    pNMHDR int32AtOffset: 8

which is right for Win32's 12-byte `NMHDR` — `{ HWND; UINT_PTR; UINT code; }`
with 4-byte pointers — and wrong here, where the two leading fields are 8 bytes
and `code` sits at **16**. So every notification decoded as a slice of
`idFrom`, missed its map, fell through `ifNil: [super nmNotify:]`, missed
again, and answered nil. **No WM_NOTIFY handler in the port had ever run.**

Counters before and after say it plainly: `Dictionary ()` -> `#getDispInfo->182`.

Fixed as a TRANSLATOR REWRITE (`rewrite_nmhdr_code`), not an override,
because `TreeView` and `ListView` build their notification maps INLINE inside
`nmNotify:` — overriding would have meant copying ~30 lines of generated map
into a hand-maintained file to change one number.

### The standing rule, now tooled

**Dolphin 8 is a 32-bit system. Assume every byte offset and struct size in
the corpus is wrong here.** `tools/audit_offsets.py` hunts them instead of
waiting: it reads the real layouts out of the 384 generated structs, then
reports every literal offset in the wave that is NOT a field of the struct its
variable is named after. It never rewrites — each needs a judgement.

First run: 7 suspects. Six were the same "index past the header" idiom
(`pNMHDR asInteger + 12`, `uint32AtOffset: 12`) and are now re-derived
generically as `NMHDR sizeInBytes`. The seventh was
`wantCustomDrawItemNotifications:` measuring the paint rect at
`NMCUSTOMDRAW.rc` = 20 (it is 40 here) — guarded by `customDrawBlock notNil`
so currently unreachable, and fixed anyway, because it would have come alive
silently and answered false for every item.

### Where the tree stops now, and it is a clean edge

All 182 callbacks raise `does not understand truncated`, from
`CCITEM>>textInBuffer:` — the method that writes an item's text into the
buffer the control supplies. `OS.CCITEM` is Dolphin's ABSTRACT BASE for
`TVITEMW`/`LVITEMW` and holds `textInBuffer:`, `maskIn:` and the rest of the
shared item protocol.

**It can never be generated.** genstructs builds structs from winkb, and
CCITEM is not a Win32 struct — it is Dolphin's own class. So `_struct_super`
finds no layout for it and both item structs root at `ExternalMemory`,
inheriting nothing.

**Next, and it is one well-shaped piece:** emit `CCITEM` as a hand-written
`ExternalMemory` subclass carrying the corpus's shared item protocol (or
`--reopen` it onto such a base), and let `_struct_super` treat a declared
struct parent as valid when this port supplies it rather than winkb. Then
`TVITEMW`/`LVITEMW` inherit `textInBuffer:` and the callbacks can answer.

---

## DD11 — THE TREE DRAWS. `Magnitude`, from live reflection, in a real SysTreeView32.

Four defects between the last entry and a tree node on screen, each hidden
behind the one before it.

### 1. `OS.CCITEM` — the base that could not be generated

Dolphin's abstract parent of every common-control item struct (`TVITEMW`,
`LVITEMW`, `TCITEMW`), carrying the shared protocol those structs are driven
through: `mask`/`maskIn:`, `newTextBuffer:`, `textInBuffer:`.

genstructs builds from winkb, and **CCITEM is not a Win32 struct** — it is
Dolphin's own class, so no layout exists for it and both item structs rooted at
`ExternalMemory` inheriting none of it.

It is TRANSLATED now, with two new pieces of machinery:

* `--rename External.Structure=ExternalMemory`, so a corpus struct class can be
  translated whole rather than hand-transcribed.
* `--supplied CCITEM` to genstructs, so `_struct_super` accepts a base this
  PORT provides rather than only ones winkb knows.

It is relocated to `st/prims/rt`, which BOOT loads two layers before
`st/prims/structs`. That is not tidiness: emitted with the rest of the wave it
would arrive AFTER `TVITEMW`, the loader would auto-vivify a stub, and the real
declaration could not reopen it — it carries an ivar (`text`), which makes it a
REPLACEMENT rather than a reopen, leaving TVITEMW bound to the empty stub.

### 2. `asInteger` is a UNIVERSAL HELPER — the oldest trap in this port

`View>>wmNotify:wParam:lParam:` boxes lParam with `asExternalAddress`, and every
notification handler then indexes off `pNMHDR asInteger + <offset>`.

`{"asInteger", "stTruncated", 0}` in the builder's table means `asInteger` is
rewritten AT THE CALL SITE. So an `ExternalMemory>>asInteger` written in
Smalltalk is never reached — I wrote one, and it changed nothing. The send went
to `.truncated()` and raised **`does not understand truncated`** on a receiver
that is not a number and never was.

Fixed in `_stTruncSlow`, asked by PROTOCOL not class name: anything carrying an
`address` is an external pointer and its integer value is that address.

### 3. `textInBuffer:` needed a CRT this port does not have

Dolphin copies an item's text into the control-supplied buffer with
`OS.Ucrt wcsncpy_s:...`. `Ucrt` is not bound here, so the send went to nil —
and it is the LAST link in the ?VN_GETDISPINFO chain, the one that actually
gives a node its text. Written directly over the buffer protocol, clamped to
`cchTextMax - 1` because the CONTROL owns that buffer. Dolphin's ellipsis on
overflow is NOT reproduced and is recorded as such.

### 4. The door threw away every contained error

The count said something raised; the message was dropped. An exception in a
notification handler is contained TWICE — the image's own `on: Error do:` and
then the door — so removing the image-side guard to get a stack merely moves
the silence. The door now PRINTS what it contained (rate-limited to 8).

### How it was actually found, and the lesson

Not by reading. Counters wired into the handler, stepped one statement at a
time, narrowed it to the exact send: `gdi_cls` fired 183 times and `gdi_addr`
never, so the raise was inside `pNMHDR asInteger` — a line that looks like
nothing.

**The screenshot is what made each step checkable.** `handlerErrors` fell
184 -> 171 across these fixes and would have told you almost nothing; the
picture went from an empty pane to the word `Magnitude`.

### Where it stands

* TREE: draws its root from live reflection data. ✔
* Expansion: `itemExpanding` now FIRES (it never did before), but children are
  still not inserted — `treeItemCount` stays 1.
* LIST: still draws no rows despite a correct scrollbar and count. Its
  `onDisplayDetailsRequired:` is `ListView`'s own, not the one just proven.

**Next:** the same counter technique on the ListView's display path, and on
`tvnItemExpanding:` past its entry — both now reachable, which they were not
this morning.

---

## DD11 — the tree EXPANDS and draws its hierarchy

Screenshot: Magnitude / Number (live expand glyph) / Integer, indented, in a
real SysTreeView32 — the class hierarchy from live reflection.

One proven defect and one wrong assertion, found under the new working method
(counters first, camera as arbiter — CLAUDE.md rules 4 and 5):

### `dwState` — Dolphin RENAMED an SDK field, and the reopen missed

Counters: `tie_item->2`, then silence. `isStateExpandedOnce` raised at
`TVITEMW _OffsetOf_dwState` — the corpus's name for what the SDK (and
therefore winkb, and therefore the generated struct) calls `state`.

Closed as a CLASS in genstructs: the corpus's declared `_OffsetOf_*` NAMES are
collected per struct (from `.cls` files only — a `.pax` re-declares many
classes and briefly attributed the whole pool to each), each name matching no
winkb field is de-Hungarianed (`dwState` -> `state`), and when exactly ONE
field matches, an alias constant carrying the SAME x64 offset is emitted.
Ambiguity emits a comment, never a guess. This fixes LVITEMW's `dwState` too,
before anything sends it.

### The gate asserted a count Dolphin never promises

"WINDOWS holds the root item == 1" failed the moment expansion WORKED —
because Dolphin auto-expands roots on refresh when the tree lacks
lines-at-root (`basicRefreshContents`: `hasLinesAtRoot ifFalse: [roots
reverseDo: [:each | self expand: each]]`). The assertion had only ever passed
because the auto-expand was raising into the contained path and inserting
nothing. A probe-vs-gate discrepancy (probe forgot `routeDolphinMessages`)
briefly made three harnesses give three different counts, which is what forced
reading the corpus instead of trusting the number.

The gate now asserts the real contract: populate -> 2 (root + auto-expanded
child, proving insert AND the synchronous expand chain in one number),
re-expand -> 2 (idempotence — the exact `isStateExpandedOnce` read that used
to raise), expand Number -> 3.

### Standing

Every functional st_browser assertion is green. The only failure is
`handlerErrors 12` — the ListView's `textPointerOffset` residual, which is the
concurrent agent task's acceptance target. 22/23 gates.

---

## DD11 — THE CLASS BROWSER IS DONE. 23/23, handlerErrors 0.

Screenshot: Magnitude / Number / Integer expanded in the tree; Integer's real
selectors in two columns in the list (`/`, `allMask:`, `anyMask:`, `asFloat`,
`asFraction` ... `gcd:`, `hash`); "Integer | 33 selectors" in the text pane.
Live reflection end to end, in real comctl32 controls.

This was the first run of the new working method, and it held:

* **One agent, one task, reviewed.** The ListView work went to a single agent
  in a worktree with CLAUDE.md, counters, the camera, and acceptance criteria
  (named assertions green + a screenshot it had to READ). It came back with
  all four criteria met, every claim counter-proven, five overrides in house
  style with named retirements, and four translator defects reported rather
  than worked around silently (now LOOSE_ENDS 3.21). Review dropped exactly
  one thing: its hand `dwState` alias, superseded mid-flight by the genstructs
  alias emission from the tree-expansion side — the duplicate would have been
  a silent override waiting for the generator to change.
* **The two halves met in the middle.** The tree side closed the corpus
  field-rename class in genstructs; the agent hit the same rename on LVITEMW
  and its counters (`#lv_state->80`) proved the alias is exercised on the demo
  path — load-bearing from both directions.
* **Merge cost:** one self-inflicted parse error (unescaped quotes inside a
  Smalltalk comment I edited) — caught by the gate in one run.

DD11's deliverable — a two-pane class browser over live reflection data —
exists, is photographed, and is asserted by `st_browser` end to end:
construction, population, expansion (with idempotence), selection re-driving
both panes, teardown, empty registry, zero contained errors.

Still ahead in DD11's tail before DD12: a HUMAN driving it — clicking a tree
node to drive the list is wired through TVN_SELCHANGED but has no gate, and
per-row icons wait on the icon machinery (LOOSE_ENDS 3.20).

---

## DD11 -> DD12 — THE REAL CLASS BROWSER. The whole image. 24/24.

The user called the three-node tree what it was — a toy — and the correction
is on screen: `ClassBrowserShell` over the ENTIRE live image.

Screenshot: a menu bar ("Class"); a tree with expand buttons, connector lines
and lines-at-root, opened COLLAPSED and here shown with Object unfolded —
Message, Boolean, UndefinedObject, Behavior, BlockClosure, Magnitude
(unfolded: Number highlighted as the selection, Character), Collection,
Association, SystemDictionary, ReadStream... — over 705 classes; Number's 23
selectors in two columns in the list; `Number < Magnitude | 23 selectors` in
the detail pane. handlerErrors 0.

### What it is, and what it deliberately is not

The user's design rule, verbatim: "we are running the dolphin MVP but we are
not dolphin, and our image is not accessed the same way, it is the GUI
behaviour we need." Dolphin's own ClassBrowserShell reads its panes from STB
view resources serialized in its image. This browser keeps the GUI BEHAVIOUR —
the same controls, MVP wiring, lazy dynamic tree, selection event chain,
keyboard semantics, menu bar with real commands — over THIS VM's reflection
surface (`ClassMirror`), which is the honest equivalent of the image.

### What made it a few dozen lines instead of a sprint

Everything hard was already proven by the probe gates: notify dispatch, the
dispinfo text path, lazy expansion, selection events, keyboard. The browser is
just Dolphin's own pieces assembled: `hasButtons:/hasLines:/hasLinesAtRoot:`
(which also switches OFF the auto-expand — the same corpus line the probe gate
had to learn about), a TreeModel built from `allClasses` with transitive
parent resolution and name-dedup (a bridged core class and its extension
holder both answer the same name; first wins), and the `#selectionChanged`
observer reading the CONTROL's selection back.

One trap avoided by the audit habit: `beginsWith:` does not exist in the world
layer (`startsWith:` does) — caught at first load, not in a window.

### Gates

`st_classbrowser` (new): menu bar confirmed by `User32 getMenu:`, >500-class
floor (deliberately far below the real ~705 so class-count drift never fails
it for the wrong reason), collapsed == roots on open, expanding Object inserts
exactly `childrenOf: Object` size, selection fills the list with the selected
class's own selectors, VK_DOWN moves the selection and the list FOLLOWS THE
CONTROL (`selectionOrNil`), not a prediction. The three-node `st_browser`
stays — its assertions are countable in a way 705 classes are not.

24/24. The demo now takes the shell class as an argument:
`... st_demo.dart <layers> ... dolphin_class_browser.mst 60 <shots> ClassBrowserShell`

---

## DD12 begun — the dialog wave is in, the modal loop is decided

The whole dialog family now translates and loads with the suite green:
`Dialog` (the buffered presenter — `model:` wraps the subject in a
ValueBuffer, `ok` applies-and-closes, `cancel` discards), `ValueDialog`,
`DialogView` + `CreateDialog` (its create function — untranslated it was a
send to nil at the first `create`), `Prompter`, `CommandButton`/`PushButton`
(there is no `UI.Button`; naming one emitted nothing, silently),
`Clipboard`, `CommonDialog`/`FileDialog`/`FileOpenDialog` over the generated
ComDlgLibrary + OPENFILENAMEW floor.

THE MODAL DECISION, made once and recorded (`st/mvp_compat/07_dialogs.mst`):
Dolphin's `runModalLoop` forks a green UI process; this port's process model
is isolates, and the user's rule — GUI behaviour, not Dolphin's machinery —
picks the NESTED PUMP: `InputState>>loopWhile:` over the provisional pump,
`runModalLoop` routed to Dolphin's own `runModalInProcessLoop`, which was
already written in exactly that shape. Stacked modals fall out of pump
nesting and unwind innermost-first. A gate drives a modal it is itself
blocked under by posting a deferred action BEFORE `showModal` — actions
drain inside the nested pump.

**Next (the goal gate itself):** a modal probe — DialogView + PushButtons
over a buffered ValueHolder; assert owner disabled while open, OK applies
the buffered value and Cancel discards it, `showModal` returns, two stacked
modals unwind in order. Then the prompter view (programmatic, per the
not-Dolphin rule), the file-open round trip, clipboard paste — and the
camera on all of it.

---

## DD12 — the modal dialog: five layers down, one to go

A `DialogView` with a TextEdit and OK/Cancel `PushButton`s over a
`ValueBuffer` now CREATES — window class `#32770`, real handle, edit seeded
from the buffer which reads the subject. `showModal` no longer hangs and no
longer dies in the first three places it did. Five defects, each hidden
behind the last, each fixed at its own level:

1. **Dialogs are RESOURCE TEMPLATES in Dolphin.** `CreateDialog>>create:`
   calls `CreateDialogParamW` with `templateId asResourceId` and a DLGPROC.
   This port ships no resource DLL, so the first probe died on `int has no
   method asResourceId` before a window existed. Re-pointed
   `DialogView>>creationFunction:dpi:` at the ORDINARY `CreateWindow` path —
   which is how a native Win32 app writes a modal that is not `DialogBox`,
   and leaves every other part of DialogView (owner disable, `answer`,
   `isModal`, the close path) Dolphin's own. Its `defaultWindowStyle` still
   makes it LOOK like a dialog.
2. **`endDialog:` cannot destroy a window `DialogBox` did not create**, and
   Dolphin's `destroy` then deliberately skips `super destroy` on the modal
   path — which would strand the window forever here. Overridden to always
   destroy: our dialog is an ordinary window and there is no second process
   to hand destruction to.
3. **`Semaphore` and `postToMessageQueue`** — the fork handshake. Degenerate
   in one process (the loop ends because `destroy` set `isModal: false`), but
   an unbound `Semaphore` meant `initialize` left `endModal` nil and the close
   path failed, contained. `postToMessageQueue` is this port's own
   `UiSession postAction:`.
4. **`MonitorFromPoint` takes a POINT BY VALUE**, which `genprims` refuses
   outright rather than guess an ABI — so it is absent from the floor, and
   `showModal`'s centring died on it. Answered with `MonitorFromRect` over a
   degenerate rect: a different, exact API doing the same job, not a guess at
   the by-value ABI. Verified equal to `MonitorFromWindow` (65537).
5. **A THIRD initializer shape.** `DisplayMonitor`'s `Instances` cache is
   built neither in `initialize` (which only wires a settings handler) nor in
   `onStartup` — but in **`reset`**. LOOSE_ENDS 3.15 predicted this class of
   bug and named the wrong selector. The lesson generalises: find where the
   class variable is ASSIGNED; do not assume which initializer holds it.
   `SharedLookupTable` was missing too (a plain LookupTable here — this
   port's UI is one thread; concurrency is isolates).

**Where it stands:** `showModal` now reaches `DisplayMonitor>>fromHandle:`
and fails there — reported as `fromHandle_` sent to null WITH a null
argument, and the same error then appears for an unrelated expression in the
same run, which means the report itself is suspect (a stale or pending
exception surfacing through the probe harness). `fromHandle:` is
`Instances at: h ifAbsentPut: [self new handle: h; yourself]`, so the first
thing to check is whether `LookupTable` answers `at:ifAbsentPut:` at all —
if it does not, the DNU is being mis-attributed.

**Next, in order:** (a) confirm `at:ifAbsentPut:` on LookupTable with a
one-line probe and fix at that level; (b) then the modal assertions —
owner disabled while open, `showModal` blocking (proved by a deferred action
dismissing it from inside the nested pump), OK applying the buffer and Cancel
discarding, two stacked modals unwinding innermost-first; (c) the camera on
all of it.

24/24 gates stay green throughout — every piece above is additive compat.

---

## DD12 — `reset` was in the wrong initializer; the last modal link is still open

**Fixed:** the `DisplayMonitor reset` call added last session went into
`DolphinBoot class >> initializeClasses`, but every gate calls
`initializeViewClasses` — so it never ran, and `Instances` stayed nil. Moved.
`DisplayMonitor classVarInstances` now answers a real Dictionary and
`at:ifAbsentPut:` is no longer sent to nil. (`at:ifAbsentPut:` does exist on
Dictionary, and LookupTable inherits it — the first suspicion in the previous
entry was wrong and is retracted here.)

**Still open, and now precisely bounded.** `DisplayMonitor fromHandle: 65537`
raises `fromHandle_` sent to NULL with the right argument, while
`DisplayMonitor classVarInstances`, `DisplayMonitor new` and
`DisplayMonitor new handle: 65537; yourself` all work in the same run. So the
class resolves, the class-side dispatch reaches SOMETHING, and the receiver
arriving at that send is null.

**A dead end worth recording so nobody repeats it:** `respondsTo:` cannot see
class-side methods. It answers false for `DisplayMonitor reset`, which
demonstrably works — so it is useless for "is this class method installed?"
and any conclusion drawn from it (I drew one) is void. A real probe is to
CALL the method.

**Two live hypotheses for the next sitting**, in order of cheapness:

1. The emitted `fromHandle:` body is a multi-line CASCADE INSIDE A BLOCK
   (`[self new handle: h; yourself]`). If that parses in a way that detaches
   the method, the send would fall through to the dynamic path — where
   `recv.clazz()` is `_Type` and the DD11 class-side fallback in
   `STSendCommon` re-dispatches. Read the emitted text byte-for-byte and try
   the same shape in a fresh class.
2. The class-side fallback added in DD11 (`LookupClassSideMethod`, `Foo class`
   then `Foo ext class`) may be invoking with the wrong argument 0 for a
   TRANSLATED class reached dynamically. A one-line probe distinguishes them:
   define the identical method on a fresh class and call it.

24/24 gates stay green — the modal work remains additive compat.

---

## DD12 — a real Dolphin 8 image becomes the ORACLE

Both hypotheses from the previous entry were WRONG, and the way they were
wrong is the point of this entry. `fromHandle:` was never broken:
`(DisplayMonitor fromHandle: 65537) class name` answers `'DisplayMonitor'`.
What failed was `printString` on the result, several classes away — and
because the probe printed its answer, the reported failure named the wrong
method. Both hypotheses were about a method that worked.

That is the second time in three sittings that careful reading of the corpus
produced a confident, wrong conclusion. So this sitting stopped inferring and
started ASKING.

### The oracle

`C:\projects\dolphin-oracle` is a booted **Dolphin Professional 8.2.3**
image, isolated from `dsfork` so running it dirties no repo.
`tools/oracle.py` drives it:

    Dolphin8.exe DPRO.img8 -u -q -f <chunkfile> -x

`-f` and `-x` both QUEUE DEFERRED ACTIONS, in the order the option table in
`Tools.DevelopmentSessionManager class >> commandLineParser` declares them, so
the image files in a script and only then quits. The script compiles each
expression with `Compiler evaluate:` and writes `index<TAB>printString`.
Four traps are recorded in the tool's header; the one that cost most is that
a chunk which fails part-way leaves the file it opened EMPTY, because `close`
never runs — an empty results file means the RUN died, not that the
expressions answered nothing.

**The oracle is 32-BIT.** `VMConstants.IntPtrMask` answers `16rFFFFFFFF` and
`HalfPtrBits` answers `16`. It is therefore authoritative about SEMANTICS
always, and about LAYOUT only where no pointer is involved. That is rule 1
restated as a working procedure rather than a warning.

It also settled the `lowPartSigned` decision made last sitting on reasoning
alone: `16rFFFE lowPartSigned` answers **-2**. The corpus was written where
half-a-pointer IS 16 bits, so keeping these 16-bit here — rather than
widening them to half of 64 — reproduces what every call site expects.

### What the differential sweep found

`tools/conform_structs.py` asks Dolphin for every generated struct's
`byteSize` and classifies the disagreements, because on a 32-bit oracle a
raw diff is mostly noise:

    agree, byte for byte ......................... 141
    differ, POINTER-BEARING (expected 32 vs 64) ..  81
    differ, pointer-free — REVIEW ................  24
    not defined by Dolphin ....................... 141

Pointer-bearing is detected TRANSITIVELY from winkb, and that detail is the
tool: every `NM*` notification struct embeds `NMHDR`, whose `hwndFrom` is a
pointer, so a top-level-only scan files nine false alarms. In all 24 review
cases ours agrees with winkb, so there is no struct where we disagree with
both opinions.

**MONITORINFOEXW = 104**, straight from Dolphin, independently confirming the
size the generator now takes from winkb's `types.size_bits` — and confirming
that the previous 48 (last field's offset + a pointer width, because a
trailing `char[]` has no width in the metadata) was a real defect. Dolphin's
own `defineFields` says `self byteSize: 104` too, so three sources agree.

**A genuine finding: `BITMAPFILEHEADER`.** Dolphin says 14, we say 16.
Dolphin is right — the struct is `#pragma pack(2)`, `bfOffBits` sits at 10,
and we put it at 12. **winkb does not model `#pragma pack`; Dolphin does.**
Nothing in `st/mvp` reads it yet, so this is latent rather than live, but it
is a whole CLASS of defect that the winkb-is-authoritative rule cannot see,
and the oracle is the only thing here that can.

### DisplayMonitor now matches Dolphin

The chain `cacheInfo` → `rectangle`/`workArea`/`deviceName`/`isPrimary` was
dead at every link. Six causes, each hiding the next:

  * `ByteArray class >> newFixed:` did not exist (5 call sites; Dolphin's
    primitive 76, the fixed-heap allocation an API out-parameter needs).
  * `SHCore`, `Dwmapi`, `Ucrt` and `VM` were unbound library globals — `VM`
    with 17 sends. Sourced now from each library's own
    `sharedVariableName`, not from a call-site census, which is what missed
    them.
  * `DpiAwareness` and `CreateInDpiAwarenessContext` were never translated.
  * `UserLibrary class >> initialize` — Dolphin's own, setting
    `DpiAwarenessContext` — was never called.
  * `addClassConstant:value:` did not exist, so `DpiAwareness initialize`
    aborted at its first element and `Awarenesses` stayed nil.
  * `MONITORINFOEXW` needed `SizedStructure`'s size stamping (emitted by the
    generator now, from the corpus's own declared superclass) and
    `MONITORINFOF_PRIMARY` bound.

Side by side, ours against the oracle:

    deviceName    '\.\DISPLAY1'   ==  '\.\DISPLAY1'
    isPrimary     true             ==  true
    rectangle     0@0..2560@1440   vs  0@0..3840@2160   (dpi 96 vs 144)

The rectangle difference is NOT a defect: 3840/1.5 = 2560 exactly. Dolphin
runs per-monitor DPI aware; this port currently runs DPI-UNAWARE, so Windows
virtualises the desktop for it. Recorded as an open item rather than papered
over — `UserLibrary initialize` runs too late to take effect.

`Utf16Buffer class >> fromAddress:` now scans to the NUL. A view of unknown
size answered '' for every wide string Windows handed back, which is how
`szDevice` produced an empty monitor name with no error at all.

### Still open

`st_modal` is not green. With the monitor chain fixed the failure moved to
view construction, where the oracle again disagrees with us: Dolphin accepts
`aTextEdit parentView: aShell` on an UNCREATED view and creates the subview
inside `addSubView:`, while ours raises a bare `Win32Error` from
`parentView:` and `does not understand value` from `basicAddSubView:`.
`ShellView new create` also raises `defaultIcon` once the containment is
removed — previously swallowed. Three more latent defects, all now visible
because the probe stopped swallowing them.

---

## DD12 — correcting 90 struct sizes regressed five gates; the oracle found why

Taking sizes from winkb rather than from arithmetic changed 90 of them, and
the next full sweep went **24/24 -> 19/25**. Five gates that had passed for
weeks — st_browser, st_classbrowser, st_controls, st_dolphinapp, st_textedit —
all failed the same way: `does not understand value`.

**Bisected to one struct.** `tools/bisect_sizes.sh` applies the winkb size to
a named subset and holds the rest at the old arithmetic, so the culprit falls
out in eight runs instead of ninety: **`LOGFONTW`, 36 -> 92**. Dolphin 8
answers `OS.LOGFONTW byteSize` -> `92`, so 92 is right on both architectures
and 36 was the trailing-`char[]` fallback again.

**The regression was a latent bug being UNCOVERED, not created.** At 36 bytes
`SystemParametersInfoForDpi` was handed a too-small buffer and FAILED, so
`SystemMetrics>>getIconTitleFont` always took its `ifError:` path. At 92 the
call SUCCEEDS, and control reaches the last line of
`getSysParamForDpi:type:ifError:` — Dolphin's own `^struct value` — for the
first time. That line had never executed in this port.

`value` is a universal helper (rule 2), and its slow path already implements
`Object>>value ^self` by ATTEMPTING the send and catching the miss. It caught
only Dart's `NoSuchMethodError` — which is what a NATIVE receiver raises. An
ST receiver takes the reify path instead, because the world defines
`Object>>doesNotUnderstand:`, and that signals a real ST
`MessageNotUnderstood`: an ST object, not a Dart error, so the existing
`on NoSuchMethodError` clause could not see it. Two halves of one rule, with
only one of them implemented.

Fixed in the slow path (`_stValue0Slow`, cocoa.dart), matching on the exact
text `Object>>doesNotUnderstand:` builds — narrower than a class check, and
robust in a way a class check is not, since asking the caught object for its
`class` is itself a send. **Asked of the oracle rather than assumed:**
`aLOGFONTW value == aLOGFONTW` answers `true` in Dolphin 8, so self is the
right answer.

All five recovered. The lesson is the one this port keeps re-learning from a
new angle: a wrong number does not fail, it takes a different branch, and the
branch it takes can be green for weeks.

### Open: this port runs DPI-UNAWARE, and should not

The oracle comparison turned up something no gate asserts. Dolphin reports
the primary monitor as `0@0 corner: 3840@2160` at 144 dpi; this port reports
`0@0 corner: 2560@1440` at 96. 3840/1.5 = 2560 exactly — Windows is
virtualising the desktop for us, which it only does for a DPI-unaware
process.

That is not for want of asking: `dartui.exe` carries an embedded manifest
declaring `PerMonitorV2`, and `win_host.cpp:482` calls
`SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)`.
Something is defeating both, and `UserLibrary dpiAwareness` answering
`DpiAwareness unaware` is consistent with `GetThreadDpiAwarenessContext`
coming back as an unsigned pseudo-handle that `fromHandle:` cannot map
(`Awarenesses lookup: anInteger asInteger negated` wants -1..-5). Unresolved;
recorded because every coordinate in the port is wrong by a factor of 1.5
until it is, and nothing currently notices.

---

## Oracle cost, and Dolphin's artwork on ARM64

**The oracle was slow for a stupid reason, and it is now fast.** A 387-
expression sweep ran as ONE Dolphin invocation with a 900s budget, so a single
hang cost the entire batch and there was no partial credit — the results file
is only flushed on `close`. `ask()` now chunks (25 per run, 60s each), flushes
per line so a killed chunk keeps the answers it already computed, and kills
the process on timeout rather than waiting on it. The full struct sweep went
from over an hour to **9.3 seconds**, same results.

Worth recording because it was the opposite of the suspicion: Dolphin starts
and evaluates in about a third of a second — `(1 to: 8000000) inject: 0 into:`
answers correctly in 1.2s wall including image start. The cost was never
per-run; it was running the whole thing repeatedly with no way to salvage a
partial answer.

**Dolphin's artwork now loads through Dolphin's own mechanism.** 295 icons and
5 bitmaps, extracted from `DolphinDR8.dll` (they are not in the source repo —
`git ls-files Core/DolphinVM/Res` answers four files, none of them images),
rebuilt into an **ARM64** `DolphinDR8.dll` by `tools/build_resources.py`.
`LoadImage` against it returns real HICONs for every name, and all 300
resources extracted back out are byte-identical to the files they were built
from.

The name is kept on purpose: `SessionManager>>defaultResLibPath` answers
`'DolphinDR8'`, so an identically-named library means the corpus's own
`Image class >> fromId:` path resolves with no override to maintain.

Three things cost a build each, all now in the tools:

  * A resource NAME cannot be recovered from its filename. `!APPLICATION` has
    no extension and had `.ico` appended; `CLASSBROWSERSHELL.ICO` is a name
    that ENDS in `.ICO`. Stripping the extension to guess broke the second
    kind, and `FindResource` missed while the resources were plainly in the
    DLL. `MANIFEST.tsv` records the mapping at extraction time.
  * Resource names in a `.rc` are written BARE. Quoted, rc.exe keeps the
    quotes as part of the name — ours enumerated as `'"HEADERPIN.BMP"'` where
    Object Arts' enumerated as `'HEADERPIN.BMP'`. Dolphin's own `devres.rc`
    shows the form.
  * `/NOENTRY`, because a resource-only DLL has no code.

Incidentally measured and worth knowing: Object Arts' 32-bit DLL DOES serve
resources to an ARM64 process — resources are architecture-neutral data, and
`LoadImage` against it returns valid handles. Shipping theirs would work. Ours
is built anyway so the asset path carries no foreign-architecture dependency.

NOT YET WIRED. The DLL exists and is verified from outside the image; nothing
in `st/` loads it yet. `External.ResourceLibrary` and `Image class >> fromId:`
still need porting, which is what `ShellView new create` raising `defaultIcon`
is waiting on, and LOOSE_ENDS 3.20 (no per-row icons) with it.

---

## Icons: Dolphin's own retrieval path, end to end, on ARM64

`ShellView new create` raising `defaultIcon` turned out to name the LAST link
of a chain with four missing pieces. The chain, entirely Dolphin's:

    Foo class >> icon                      ^##(self) defaultIcon
    ClassDescription >> defaultIcon        ^Icon fromId: self defaultIconName
    ClassDescription >> defaultIconName    ^File composeStem: self name
                                                extension: '.ico'
    Image class >> fromId:                 ^self fromId: anId in:
                                             SessionManager current
                                               defaultResourceLibrary
    SessionManager >> defaultResLibPath    ^'DolphinDR8'

**Now working:** `(Icon fromId: 'ShellView.ico') handle` answers a real HICON,
`ShellView icon` answers the Icon, and the class browser wears
`ClassBrowserShell.ico` in its title bar — photographed, not asserted.

Translated rather than written: `External.ResourceLibrary`,
`Graphics.ImageFromResourceInitializer` and its String subclass. An earlier
pass had deliberately skipped the resource initializers because "nothing
constructed in this port loads an image from a resource"; that stopped being
true the moment `resources/DolphinDR8.dll` existed.

Five gaps supplied, each the smallest thing that lets Dolphin's own code run:

  * `DynamicLinkLibrary`'s `handle` ivar. `genprims` emits a near-empty class
    of that name, and the translated `ResourceLibrary` subclasses it and reads
    `handle` directly. Declared in `st/prims/aliases` because a superclass
    must be final BEFORE the subclass is created — in `st/mvp_compat` it would
    have been a different class that `ResourceLibrary` was not descended from.
  * `File`'s four path-splitting operations, with the exact semantics the
    ORACLE gave (`splitPathFrom:` keeps its trailing separator;
    `composeStem:extension:` is plain concatenation, the extension carrying
    its own dot). Not Dolphin's File class — nothing here opens a file.
  * `Object class >> name`. `Behavior>>name` exists and a DYNAMIC send to a
    class finds it, but `self name` written inside a class method compiles to
    a class-side send and misses. The corpus writes `self name` in class
    methods freely, so it is answered once rather than per caller.
  * `asResourceId`. Integer answers self (MAKEINTRESOURCE passes the ordinal
    AS the pointer); String LOWERCASES, which the oracle settled. Reproduced
    rather than skipped because the identifier is also Dolphin's image CACHE
    KEY, and two spellings of one icon must not become two entries.
  * Marshalling in `loadResource:fromModule:extent:flags:`. In Dolphin a
    String is directly passable as LPCTSTR; this port's FFI floor refuses,
    which is the floor doing its job. Overridden ONLY to marshal — the
    `bitOr: 64` (LR_DEFAULTSIZE) and everything else stays Dolphin's.

Verified along the way, so it is not re-derived: Dolphin's own load flags
(`defaultLoadFlags` = 34 = AS_IMAGE_RESOURCE | AS_DATAFILE) give the same
module handle and the same HICON as an ordinary load, and Windows compares
resource names case-insensitively, so `defaultIconName`'s 'ShellView.ico'
finds the DLL's `SHELLVIEW.ICO`.
