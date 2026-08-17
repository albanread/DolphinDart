# Loose ends

Everything this port is knowingly carrying: scaffolding that must die,
divergences it has accepted, defects seen but not chased, and constructs the
translator still refuses.

**Why a single file.** Each of these is already commented at its site, which is
the right place for *how*. It is the wrong place for *what is still owed* —
that answer was spread across a dozen files and three sprint notes, and the
only way to assemble it was to grep for the word "scaffolding". Anything
recorded here should stay recorded at its site too; this is an index, not a
relocation.

**The rule this file exists to enforce:** a stand-in is allowed, a stand-in
without a named retirement is not. Every entry below says what kills it.

Status as of DD11 (22/22 gates green; `st_controls` runs a real
`SysTreeView32` and `SysListView32` on Dolphin's own classes).

---

## 1. Scaffolding — has a retirement, is not dead yet

### 1.1 ~~The `WinView` adapter family~~ — RETIRED
Deleted: `06_winview.mst`, `09_wincontrol.mst`, `10_winmenu.mst`, their four
probes and their four gates. Everything now runs on Dolphin's own classes.

**This entry's original claim was WRONG and that is worth keeping.** It said
`st_shell` was "fully superseded by `st_dolphinshell`". Checking the assertion
lists rather than trusting the note showed each retiring gate carried coverage
its successor did not — focus, two-fields-one-model, command enablement, the
acceptance app — so the probes were migrated and the assertions came with
them. Deleting on the strength of this note would have dropped four
behaviours silently.

**A note in this file is a claim, not a fact.** Check it before acting on it.
See `docs/JOURNAL.md` for the migration.

### 1.2 The font-walk terminator
`st/mvp_compat/01_view_overrides.mst` — `SystemFont`, `DesktopView>>getActualFont`

`View>>getActualFont` walks the parent chain to the desktop, where Dolphin
answers a real `Graphics.Font`. `Graphics.Font` is not translated. The walk
ends at an object satisfying exactly the protocol `ControlView>>setFont:` uses
(`atDpi:` answers self, `asParameter` answers 0) so that no Dolphin method is
overridden — and WM_SETFONT with a NULL font handle is Windows' own documented
"use the system font", so the behaviour is right rather than merely harmless.

**Retires when:** `Graphics.Font` is translated (DD11 graphics wave).
**The gate that proves it:** any test asserting a control uses the font it was
ASKED for rather than the system default. That assertion is impossible while
this stand-in is here, which is the honest reason it counts as scaffolding.

### 1.3 `Behavior>>bindingFor:`
`st/dolphin_compat/03_kernel.mst`

Dolphin answers a live class-variable binding so a holder can write through it
later. This dialect binds class variables statically, so it answers a detached
Association.

**The cost, precisely:** the one caller is `SystemMetrics class >> initialize`,
which stores those bindings so `reset`/`onSettingChanged:` can null four
caches — `HasFlatMenus`, `MessageDuration`, `MouseHoverTime`,
`WheelScrollLines`. Writing through a detached association does not clear the
real class variable, so those four values stay as first read. **A user changing
mouse hover time or flat-menu style mid-session will not see it until
restart.**

**Retires when:** the front-end grows a dynamic class-variable accessor
(`classVarAt:put:`). Not needed for DD12's dialogs; worth doing when something
needs live system-setting changes.

### 1.4 `GUID newUnique`
`st/dolphin_compat/03_kernel.mst`

Composed from the millisecond clock and a counter, not `CoCreateGuid`. Enough
for the registry keys Dolphin uses it for and needs no COM. Recorded at its
site as a v1 shortcut.

**Retires when:** something needs a GUID that is unique across processes or
machines. Nothing does today.

### 1.5 `st/world/47_worker.mst` — LOADED, and inert
Recorded in DD10's first status block: its bodies are numbered-primitive
pragmas (prims 227/228, MOP pickle), which this port compiles to `^self`. It
describes a primary/worker VM design inherited from the world layer, not this
port's mechanism — DD10's actual workers are Dart isolates
(`st/dolphin_compat/11_worker.mst`, gate `st_worker`).

**It is not dead code sitting unreferenced.** `st/world` is in BOOT, so the
class `Worker` is defined in every gate, answering `self` from every method.
That is the dangerous shape: a name that resolves, and a call that silently
does nothing. Anyone reaching for `Worker spawn:` gets a no-op rather than a
doesNotUnderstand.

**Retires when:** either it is deleted, or its methods are made to raise
`self shouldNotImplement`. The second is better if the design text is worth
keeping — it converts a silent no-op into a loud one, which is this project's
whole standing rule.

### 1.6a `View>>onEraseRequired:` answers nil
`st/mvp_compat/01_view_overrides.mst`

Declines WM_ERASEBKGND so Windows erases with the window class brush. That is
Dolphin's own documented way to accept default processing, not a stub — but it
is used here because `aColorEvent canvas` needs `Graphics.Canvas`, which is
not translated.

**The cost:** a view's `backcolor` is NOT honoured when erasing. Set a view to
red and it still erases to the class brush.

**Retires when:** `Graphics.Canvas` is translated (DD11).
**The gate that proves it:** fill a view with a named colour and read the
pixel back — the DD9 paint probe already does exactly that for WM_PAINT.

### 1.6b `Color` system colours supplied from `GetSysColor`
`st/mvp_compat/01_view_overrides.mst`

`Graphics.Color` declares `Window`, `WindowText`, `Face3d` as class variables
and only ever READS them; the system-colour package that assigns them is not
in the wave. `View>>defaultBackcolor` is `^Color classVarWindow`, so without
this every `actualBackcolor` was nil.

Answered from Windows rather than a constant, so a themed or high-contrast
desktop gets its real colour.

**Retires when:** Dolphin's system-colour package is translated (DD11).

### 1.6c `addClassVariable:` with a COMPUTED name is a no-op
`st/dolphin_compat/03_kernel.mst`

The translator rewrites `self addClassVariable: 'X' value: E` to `X := E`, but
`Color class >> initialize` ends with a loop whose name is computed
(`each capitalized`). No dynamic class-variable store exists, so that
assignment cannot happen.

**The cost:** `Color Black` and `Color White` answer nil. The lowercase
`Color black`/`Color white`, which go through `named:`, work normally and are
what the port uses.

**Retires when:** the front-end grows `classVarAt:put:` — the same one
`bindingFor:` (1.3) waits on.

### 1.6 `Cursor`
`st/dolphin_compat/12_view_create.mst`

Answers the Win32 SYSTEM cursors only (`wait`, `arrow`) with Dolphin's
`Graphics.Icon>>showWhile:` semantics. That is everything `UI.View` asks for.

**Retires when:** `Graphics.Cursor` and `Graphics.Icon` are translated with
DD11's graphics wave — together, because `showWhile:` is `Icon`'s, not
`Cursor`'s.

### 1.7 `Object>>conformsToProtocol:` answers false
`st/dolphin_compat/03_kernel.mst`

**The boundary:** a model that handles its own commands will NOT be placed on
the command route, so its `queryCommand:`/`performCommand:` are never
consulted. Commands still route through the presenter and view chain, which is
where DD10's app puts them, and conforming to `#commandTarget` is opt-in in
Dolphin so false is also the common answer.

Cannot be faked usefully: the question is whether INSTANCES conform, and
`respondsTo:` (prim 246) answers for the receiver — sent to a class it tests
the class side, the wrong dictionary.

**Retires when:** the front-end exposes `Behavior>>canUnderstand:` (DD11
reflection work).

---

## 2. Accepted divergences — documented, not scheduled

These are not scaffolding. They are decisions, and they should be revisited
only if something actually depends on the difference.

### 2.1 Immutability is a no-op
`Object>>beImmutableObject` answers self; `isImmutable` answers false;
`whileMutableDo:` is `aBlock value`. Dolphin marks objects immutable so its VM
traps writes; this VM has no equivalent. `View class >> initialize` marks its
MessageMap immutable, and `registerMessageMappings:` unfreezes it to edit —
both work, neither protects anything. Pretending otherwise (by copying, say)
would change identity for something the caller expects to be the same object.

### 2.2 `Utf16Buffer` is not a String, and `size` disagrees
In Dolphin, `Utf16String` IS a String subclass — `UserLibrary>>getWindowText:`
ends `^text` and callers treat the answer as text. Here it is an
`ExternalMemory` given the text protocol (`printOn:` quoted, `displayOn:` bare,
`=` by content).

**`size` is deliberately NOT aliased.** It is a universal helper the IL builder
rewrites at the call site, and `ExternalMemory>>size` (the BYTE count) is what
marshalling needs — where Dolphin's `Utf16String>>size` is the CHARACTER count.
**A caller wanting characters must ask `stringValue size`.** This is the one
place the two dialects give different answers to the same send, and it is
written here so it is findable when it bites.

### 2.3 Numbered `<primitive: N>` pragmas compile to `^self`
Long-standing: they are INTENT, not dispatch. Only `primitive: FFI` and the
D157 constructor lowering are handled. Recorded in `DOLPHIN_PORT.md`.

### 2.4 Green processes are replaced, not emulated
Scope rule 8: workers on Dart isolates REPLACE Dolphin's processes outright.
`Processor activeProcess newWindow:` is a plain variable, not a process slot.
This is a project-level decision (`docs/WORKERS.md`), not a gap.

---

## 3. Open — seen, reproducible, not chased

### 3.1 ~~`Cursor` is undefined~~ — CLOSED, and what it uncovered
A compat `Cursor` now exists (`st/dolphin_compat/12_view_create.mst`) with
Dolphin's `showWhile:` semantics: the block runs under `ensure:`, and the
cursor restored is the one `SetCursor` ACTUALLY returned rather than the one
we believed was current. It is scaffolding — see 1.6.

Fixing it let the action path run one step further each time, which uncovered
a chain: `DelegatingCommandPolicy` untranslated (so `CommandPolicy
defaultClass` answered nil), `identityIncludes:` and `conformsToProtocol:`
missing, and then **the `new:` defect in 3.7**, which was much bigger than any
of them.

*Original entry, kept because the diagnosis is the useful part:*

### 3.1a `Cursor` was undefined → `'wait' called on null`
**Symptom:** during shell creation, twice:
`UiSession: handler error — NoSuchMethodError: The method 'wait' was called on null`

**Cause:** `UI.View` has two sites —
`st/mvp/01_View.mst:2076` and `:2111` — both `Cursor wait showWhile: [...]`,
wrapping `#actionPerformed` and the long-action path. `Cursor` is not defined
anywhere in this port, so `Cursor wait` sends to nil.

**Why it is contained:** it raises inside `UiSession dispatchMessage:`, whose
handler-error path catches, counts and answers nil. Nothing depends on the
result yet.

**Why it still matters:** it means the ACTION PATH is currently broken for any
view that reaches it — a button press routed through `performAction` would
raise rather than run the action. DD10's command gate does not go through this
path, which is why it is green; DD12's dialogs will.

**Fix:** a `Cursor` compat class with `wait`/`normal` and `showWhile:`
(SetCursor + restore), or translate `Graphics.Cursor` with the DD11 graphics
wave. The second is better and lands anyway.

### 3.7 ~~`new:` on a growable collection answered the CLASS~~ — CLOSED
**The largest silent wrong answer found so far, and it was pre-existing.**

No growable collection defined a class-side `new:`, so the send fell through
to `Behavior>>new: n` → `basicNew: n`, and `basicNew:` on a NON-INDEXABLE
class answers the class itself rather than failing. `OrderedCollection new:
12`, `Set new: 4`, `Dictionary new: 4` all answered a `_Type`: an object that
responds to sends and is simply not the thing asked for.

`CommandPolicy>>routeFrom:` opens with `path := OrderedCollection new: 12`, so
**every command route in the port had been building on a class** — surfacing
three layers away as `Class '_Type' has no instance method
'identityIncludes_'`.

Fixed per class (`st/world/52_collection_ext.mst`), NOT on `Collection`: Array
and String are Collections too and theirs is indexable `new:`, so a definition
on `Collection` would have sat between them and `Behavior` and broken
`Array new: 4` while fixing the rest. Guarded in
`st/test/features/test_collection_protocol.mst` with `isKindOf:` rather than a
size check — a class answers 0 to `size` as readily as an empty collection
does, so a size check would have passed throughout.

**THE ROOT CAUSE IS STILL OPEN.** `basicNew:` on a non-indexable class
answering the class, rather than raising, is the front-end behaviour that made
this invisible. The per-class `new:` fixes the symptom. Making `basicNew:`
raise would turn any remaining instance of this shape loud, and is worth doing
— carefully, since something may be depending on the current answer by
accident.

### 3.11 genstructs cannot size ENUM-typed fields — ~~OPEN~~ **RETIRED (DD11)**
`tools/dolphin2mst/genstructs.py` emitted a comment instead of an accessor when
it could not determine a field's width, which was the right refusal — guessing
silently writes the wrong number of bytes and corrupts the neighbour. But the
fields it refused were Win32 ENUMS (`MENUINFO_MASK`, `MENU_ITEM_TYPE`,
`MENU_ITEM_STATE`, …), and a Win32 enum in a struct is a DWORD.

The named fix was "follow an enum-typed field to its underlying integer type
in winkb". **Done.** winkb records `size_bits` on an enum exactly as on a
struct (`LIST_VIEW_ITEM_STATE_FLAGS` is `kind='enum', size_bits=32`), and
`field_accessor` now takes an enum table and answers the matching unsigned
accessor. The eight hand-written accessors in
`st/mvp_compat/03_struct_accessors.mst` are deleted — the generator emits them
at the same offsets, and a second definition of a generated accessor is a
silent override waiting for the generator to change.

Found because `LVITEMW>>stateMask:` was missing and `ListView` cannot be
created without it. Two other gaps came out of the same file and are also
closed: the generator emitted a setter only for 32-bit fields (so every
pointer field had a getter and no setter — `MENUITEMINFOW>>dwTypeData:` was
hand-written for exactly that), and `ExternalMemory` had no `int32At:put:`,
`int16At:put:` or `int8At:put:` at all.

What REMAINS in `03_struct_accessors.mst` is Dolphin's own Smalltalk over the
layout (`MENUINFO>>style:`, `MENUITEMINFOW>>commandMenuItem:metrics:`), which
was never the generator's to emit. Its retirement is the `--reopen` path added
for `OS.LVCOLUMNW` in DD11 — see 3.14.

### 3.14 Dolphin's struct `.cls` field offsets are 32-BIT
`OS.LVCOLUMNW.cls` declares `_OffsetOf_pszText -> 16rC` (12) and
`_LVCOLUMNW_Size -> 16r2C` (44). Those are the 32-bit layout. On this port's
targets the pointer is 8-aligned, so the field is at 16 and the struct is 56
bytes — which is what `genstructs` emits, from winkb, per target.

This is **the one place in the translator where the corpus's own value is the
wrong one**, and it is not a refusal: folding `_OffsetOf_pszText` to 12 wrote a
caption pointer into `cx` and the process died inside comctl32 with an access
violation, with no Smalltalk error anywhere.

`emit_loose`'s reopen path therefore rewrites a bare `_OffsetOf_*` or
`_<NAME>_Size` to a send to the generated class rather than folding it, so the
offset used is always the one the accessors were built from.

**Standing obligation:** any future `--reopen` of a struct `.cls` inherits
this. Do not "fix" it by adding the class's own constants to the fold imports.

### 3.15 `onStartup` is sent from an explicit list
Dolphin runs two class-side initializers at image start: `initialize` for what
is known when the class is defined, and `onStartup` for what depends on the
machine. This port never sent the second at all, and
`ListView class >> onStartup` is the one that sets `SelectionStateMask` — so
creating a ListView wrote nil into an LVITEMW's `stateMask`.

Dolphin drives it from `View class >> onStartup`, which walks
`allSubclassesDo:` and sends `onStartup` only to classes that DEFINE one. That
guard matters — sending to a class that merely inherits it re-runs an
ancestor's once-per-image action once per subclass — and this port has no
`Behavior>>includesSelector:`, so `DolphinBoot class >> initializeViewClasses`
names `ListView` explicitly instead.

**Retirement:** implement `includesSelector:`, then replace the list with
`View onStartup`. Until then, a translated class with its own `onStartup` will
be silently skipped, which is the same class of failure this entry records.

### 3.12 A class-side `self` send binds to the DEFINING class
Recorded twice now, and it caused a Win32 failure the second time.

`self foo` inside a class-side method resolves through class-side lookup from
the DEFINING class, not the receiver's. So an inherited class method cannot
call an override:

  - `Object class >> bindingFor:` had to be defined on both sides because
    `SystemMetrics class >> initialize` sends `self bindingFor:`.
  - Adding `ExternalMemory class >> sizeInBytes [ ^0 ]` as a base default
    made the inherited `newBuffer`'s `self sizeInBytes` answer 0 for EVERY
    struct — `cbSize` was written as 0 and InsertMenuItem failed with
    ERROR_INVALID_PARAMETER. A Win32 error a long way from a Smalltalk method
    added for an unrelated reason.

**Until this is understood or fixed, do not add a base-class default for
anything an inherited class-side method calls on `self`.** The rule is in
`00_external_memory.mst` at the site.

### 3.9 `nameOf:` is missing
Sending `printString` to a `Presenter` raises `does not understand nameOf:`,
from somewhere in its `printOn:`. Seen while probing; not chased. Harmless
until something prints a presenter, which a debugger or a log line will.

### 3.8 ~~An INTEGER on the command route~~ — CLOSED
**The door was swallowing WM_COMMAND.** Its DD7 spike channel intercepted
message 273 before the routed branch and carried only `LOWORD(wParam)` — the
control id. Dolphin's `View class >> buildMessageMap` maps 273 to
`wmCommand:wParam:lParam:`, which needs the FULL wParam and lParam to tell a
menu command (lParam null → look up a CommandDescription by id → `onCommand:`)
from a control notification (lParam is the control's hwnd → `command:id:`).
The narrow channel reached Dolphin's `onCommand: aCommandDescription` with an
INTEGER.

The door now offers the routed path first and falls back to the spike channel,
so a gate installing Dolphin's map gets Dolphin's handler with real arguments
and a spike window keeps the contract it was written against.

Behind it, two more: `Integer>>lowWord`/`highWord` (Dolphin's word accessors,
absent), and the whole EVENT family — `UI.Event`, `WindowsEvent`, `PointEvent`,
`MouseEvent`, `KeyEvent` — which every mouse and key handler constructs and
which were unbound globals, so each handler sent to nil.

### 3.10 ~~The binding moment did not bind the HANDLE~~ — CLOSED
`UiSession bindNewWindow:` registered the view in the hwnd→view map so the
door could ROUTE to it, and never gave the VIEW its handle. Dolphin's handlers
assume `handle` is live from WM_NCCREATE onward: `View>>wmCreate:` ends in
`event defaultWindowProcessing`, which is `User32 defWindowProc: handle ...` —
a pure-word prim with NO wrapper, so a nil handle is not coerced to 0, it is
an FFI refusal. `handle` stayed nil until CreateWindowExW *returned*, which is
after every message it sends during creation.

Now uses Dolphin's own `attachHandle:`, which does both halves.

**This was invisible for three sprints** because no gate had installed
Dolphin's message map, so no Dolphin handler ran during creation.
`Class 'int' has no instance method 'queryCommand_'`, from the WM_COMMAND path
in `st_textedit`. Contained by the handler-error path; the gate is green
because nothing asserts on command routing there yet.

Something is appending an integer as a command target. This is DD10's own
remaining item 4 (commands in anger), so it is next rather than deferred.

### 3.2 `<commandQuery:>` pragmas are dropped — 14 sites
All 14 remaining `[pragma]` refusals are `<commandQuery: #canCut>` and kin, all
in `UI.TextEdit`. Dolphin uses them declaratively to answer `queryCommand:`,
which is what enables and disables menu items.

**Consequence:** cut/copy/paste/undo menu items over a `TextEdit` will not
enable or disable themselves. `st_command` is green because its enablement is
written explicitly rather than declared by pragma.

**This is on DD10's own remaining list** (item 4: the acceptance app with
`queryCommand:` enablement observable), so it is not deferred — it is the next
thing after the menu wave.

### 3.3 `#{...}` variable-binding literals — 14 sites
Refused with no house equivalent. Sites include `UI.View`, `UI.Menu`,
`UI.Presenter` (×2), `UI.Shell`, `UI.ContainerView`, `UI.ControlView`,
`Graphics.Rectangle`. A `#{Foo.Bar}` is a late-bound reference to a global.

**Not yet a problem** because each refusal is in a method nothing has called.
The refusal is loud and per-site, so this will surface as a missing method
rather than a wrong answer — which is the intended failure mode.

### 3.4 `##(...)` now evaluates at RUNTIME — 54 sites
No longer a refusal: an unfoldable compile-time constant is lowered to
`[ ... ] value`. Semantically equivalent for the constant-answering methods it
appears in; the cost is that the value is rebuilt per call rather than once.

**Worth revisiting** if one turns up on a hot path. `ControlView>>commonNotificationMap`
builds an IdentityDictionary and is the most likely candidate.

### 3.5 Cascade refusals — 22 sites
`cascade on a receiver this rewriter cannot bound`. Deliberate: splitting a
cascade whose receiver is not a simple primary would re-evaluate a
side-effecting receiver. Each is a method that will fail loudly if called.

### 3.6 Orphan loose methods — 10 sites
`.pax` methods filed onto classes not in the translation set. Harmless while
those classes are absent; each becomes a real gap the moment one is translated.

---

## 4. Tooling and harness

### 4.1 Recorded invocations — done, keep them that way
`tools/gen_prims.py`, `tools/translate_mvp.py`, `tools/gates.py`. Three
failures in one afternoon came from invocations that lived only in shell
one-liners — one of them silently rewrote `UserLibrary` from 232 external
methods to 1, over the good floor.

**Standing rule:** a generator or gate invoked from a one-liner is a defect.
Put it in a script.

### 4.2a Contained handler errors are now COUNTED and located — done
`UiSession noteHandlerError:` used to print the exception's messageText alone:
no message number, no selector, no receiver. A diagnostic that says only that
something went wrong somewhere.

It now reports `<ViewClass>>><selector> (WM n) — <Class>: <text>` and
increments `UiSession handlerErrors`, which gates assert is ZERO. That is the
only way a deliberately swallowed error becomes a test failure rather than a
line in a log nobody reads — every command in `st_textedit` was dying while
every assertion in it still passed.

**Add `expect('no handler error was contained', 'UiSession handlerErrors
printString', "'0'")` to any gate that pumps messages.**

### 4.2 A shared `test/gate_util.dart` — recommended, still not built
`ev`/`must`/`expect` and the paint-liveness helper are copy-pasted across 20+
gates. The gate-harness defect pattern keeps recurring in the copies:

  - boolean compared to `0` (`true != 0` always passes, `false == 0` never does)
  - `must(x != 0)` passing on the `-1` that `num` answers for a RAISED
    expression — reported a healthy window for a send that never worked
  - `must(seen >= before)` on a monotonic counter — unconditionally true
  - flaky paint thresholds under WM_PAINT coalescing

Each was found and fixed in one gate at a time. A shared helper with `mustBe`
(equality, not inequality) and a `numOrFail` that cannot silently answer -1
would have prevented all four shapes.

### 4.3 `st/prims/_refusals.txt` is 6785 lines and unreviewed
The FLOOR's refusal report (distinct from `st/mvp/_refusals.txt`). Mostly
struct-by-value and float arguments, both genuinely unrepresentable. Nobody has
read it end to end to check nothing important is hiding there.

---

## 5. Not loose ends

Recorded so they are not re-investigated:

- **`_report.md` refusal counts look alarming and are not.** `TextEdit` shows
  21 refusals against 179 methods; all 21 are the pragma/binding-literal/
  cascade classes above, and the class works.
- **`Object class >> icon` appears twice** in `st/mvp/90_Object_loose.mst` and
  the loader prints `[lastwins]`. Two `.pax` files each file an `icon` onto
  Object; both bodies are equivalent. Noise, not a defect.
- **Windows answers `'Edit'`, not `'EDIT'`.** Window class names are
  case-insensitive; `st_textedit` compares case-folded.

### 3.16 `CommCtrlLibrary` records init flags but does not act on them
Dolphin's control classes each declare which comctl32 family they need —
`TreeView class >> initialize` is `CommCtrlLibrary addInitFlag:
ICC_TREEVIEW_CLASSES` — and Dolphin's `CommCtrlLibrary class >> open` ORs the
accumulated flags into one `INITCOMMONCONTROLSEX`.

This port keeps the ledger (`st/mvp_compat/03_commctrl.mst`) but does NOT make
the call. The door does, in `EnsureCommonControls()` on the class-registration
path, with a fixed superset — because the call must happen on the UI thread
before the first control is created, and the door is the only code that knows
when that is.

**The divergence:** a control family Dolphin did not ask for is initialized
anyway. Wasteful, never wrong.

**Retirement:** have the door ask Smalltalk for `CommCtrlLibrary initFlags`
instead of hard-coding the superset; `open` here then becomes the real call.

### 3.17 `Object>>value` lives in Dart, not Smalltalk
Dolphin's `Core.Object>>value ^self` is what makes `at: k ifAbsent: 0` legal,
and the corpus takes that freedom (`View>>getNoRedrawCount`).

It **cannot** be written in the compat kernel. `value` is one of the universal
helpers the IL builder rewrites at the call site, so defining it made every ST
receiver's `value` resolve back into `stValue0`'s own slow path — the whole MVP
suite died with an access violation on a blown stack.

It lives in `_stValue0Slow` (`port-win/dart_st/cocoa.dart`), which is the
single point every niladic-valuable send funnels through. Note that no static
probe can gate it: `_stHasMethod` sees only the receiver's own class chain,
`stRespondsTo` adds the extension holders, and neither sees
`_stCharProtocol` — where `Character>>value`, the code-point accessor,
actually lives. So the send is attempted and the miss caught on the message
naming `value`.

**This is a permanent placement, not a stand-in** — recorded here because the
obvious "cleanup" is to move it into Smalltalk, and that breaks everything.

### 3.18 Class-side reopens of `Array` are INERT — and always have been
`Array` is a BRIDGED class: `Array class name` answers `_Type@…`, a Dart Type.
This file's naming rule already warns that a compat method on a bridged class
(Character, String, Integer) does not reach the native receiver's extension
holder from a later file. The CLASS side of `Array` is the same, and worse —
it does not work from ANY file, including the one that defines the class.

Measured three ways in DD11:

* `Array class >> withAll:` is written in `st/world/52_collection_ext.mst` and
  has never been reachable. It predates this sprint by a long way.
* A trivial `Array class >> zzProbe [ ^42 ]` added to `10_array.mst`, in the
  same class body and immediately before the working `Array class >> with:`,
  is not found either — so it is not a load-order or a merge question.
* `Array respondsTo: #new:withAll:` answers false.

`Array class >> with:` and friends DO work, so the class side is populated
from somewhere that source reopens do not reach.

**The cost, today:** `Array new: <n> withAll: <v>` and `Array writeStream: <n>`
are both sent by Dolphin's TreeView/ListView code from inside a WM_NOTIFY
handler. The handler contains its errors by design — a raising handler would
take the window down — so they appear only as `handler error in
…>>wmNotify:` lines in a gate's output and never as a failed assertion. This
is what blocks `st_browser`.

**Retirement:** find where `Array`'s class-side protocol is registered (it is
not in `st/world`) and add the two methods there, or make a source reopen of a
bridged class's class side actually install. The second is the real fix — the
first leaves the trap for the next selector.

**Until then: do not add a class-side method to `Array` in a `.mst` file.** It
will load without complaint and never be called.

### 3.19 `TVINSERTSTRUCTW` is sized by hand — winkb cannot see its `item`
Win32Metadata models `TVINSERTSTRUCTW`'s `item` as an ANONYMOUS UNION
(`_Anonymous_e__Union`, recorded as a 64-bit primitive), so `genstructs`
emitted `sizeInBytes 24` for a 96-byte structure — 8 + 8 + an inline 80-byte
`TVITEMEXW` at offset 16.

That is an UNDER-ALLOCATION, not a missing accessor: `newBuffer` would hand
comctl32 a 24-byte buffer to read 96 bytes from.

`st/mvp_compat/03_struct_accessors.mst` restates the size, DERIVED from the
two numbers the generator did get right (`_OffsetOf_Anonymous` and
`TVITEMEXW sizeInBytes`) rather than written as a literal, plus a typed view
for `item` and Dolphin's `hParent:hInsertAfter:` / `allCallbacks` /
`callbacksForItem:` constructors.

**Retirement:** resolve an anonymous-union member to its largest alternative
in `genstructs`. winkb records the union's members; the generator does not
walk them. Any other struct with an anonymous union has the same silent
under-allocation waiting.

### 3.20 No per-row icons — `View class >> defaultGetImageBlock` answers nil
Dolphin's port-wide default image block runs `rowObject icon` ->
`^##(self defaultIcon)` — and `defaultIcon` lives in Dolphin's BASE IMAGE,
outside the translated slice, with the whole icon chain behind it
(`Icon>>extent` over GetIconInfo, `addToImageList:mask:` over real HICONs).
Every image-request callback raised, contained, ~80 per two-second run.

Stand-in at the shallowest honest point (`st/mvp_compat/06_listview.mst`):
a nil getImageBlock is Dolphin's own first-class "list without images" state.
The TreeView is unaffected (its image branch gates on `hasIcons`, false at
the #noIcons default).

**Retires when:** defaultIcon + Icon>>extent + ImageList population are
translated — then DELETE the override. Trap recorded for that day: the
`##()` lowering re-evaluates per send with dynamic self, so class-side
`defaultIcon` overrides will be honoured where Dolphin's compile-time
binding deliberately ignores them (see 3.21).

### 3.21 Translator defects surfaced by the LVITEMW reopen (agent-reported)
Four distinct emitter gaps, each currently patched around in
`st/mvp_compat/06_listview.mst` with the emitted original documented there:

* **Qualified pool references are emitted verbatim** — `OS.Win32Constants.
  LPSTR_TEXTCALLBACK` comes out as `Win32Constants.LPSTR_TEXTCALLBACK`,
  which parses as an unbound global (nil) plus stray statements. Fold
  qualified `Ns.Pool.CONST` like bare names.
* **`??` rewrite gaps** — a qualified right-hand side mangles
  (`(x ifNil: [UI]) .ListView.NoImageIndex`), and four methods keep LITERAL
  `??` sends. Those are now LIVE via `Object>>??`/`UndefinedObject>>??`
  (Dolphin semantics, operand always evaluated; checked against
  audit_helpers — not a universal helper), but the rewrite should cover
  every form.
* **ByteArray classConstants are 32-bit snapshots** — `CallbackPrototype`
  is a 60-byte Win32 LVITEMW image copied byte-for-byte into
  `initializeClassConstants`, loading as a plain List. Re-derive or refuse;
  never copy. (`callbacksForIndex:` is rebuilt fresh in 06 instead.)
* **`##()` lowers to `[...] value`** — re-evaluated per send with dynamic
  self, where Dolphin binds once at compile time. A semantic divergence,
  benign today, recorded with the defaultIcon trap above.
