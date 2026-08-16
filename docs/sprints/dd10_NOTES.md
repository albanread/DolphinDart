# DD10 — The MVP triad: NOTES (in progress)

**Status: the model side is translated and green.** 2026-08-15.
Gate: `test/st_triad.dart`. 27 classes now translated into `st/mvp`.

## The wave so far

Dolphin's own, translated and running: `Core.Model`, `UI.ValueModel`,
`UI.ValueHolder`, `UI.ValueAdaptor`, `UI.ValueAspectAdaptor`, `UI.ValueBuffer`,
`UI.TypeConverter`, `UI.NullConverter`, `UI.AbstractToTextConverter`,
`UI.NumberToText`, `UI.IntegerToText`, `UI.Presenter`, `UI.Shell` — on top of
DD9's view and colour waves.

## The DD8 stand-ins are gone

`Model` and `ValueModel` were hand-written in `st/dolphin_compat/03_kernel.mst`
so DD8 and DD9 had a model side at all. DD10 translates Dolphin's own, and
**both cannot coexist**: two classes of each name with the winner decided by
load order is exactly the silent-wrong-answer shape this project keeps paying
for. They are deleted, and the contracts `test_compat_kernel.mst` asserted are
now asserted against the real classes in `test/st_triad.dart`.

That the assertions transferred unchanged is the useful result: the DD8
stand-ins were written from Dolphin's source and the real ones agree with them.

## What the gate asserts, and why in that shape

- **Two subscribers, not one.** One subscriber proves a callback fires; two
  prove the model BROADCASTS rather than remembering the last registration.
- **`setValue:` must not notify** where `value:` does. That difference is the
  whole reason `ValueBuffer` can hold an edit back until it is accepted, and a
  ValueModel that notified on both would look correct in every single-write
  test.
- **Bad input RAISES.** `NumberToText rightToLeft: 'not a number'` signals
  `InvalidFormat` rather than answering nil. A converter that answers nil puts
  nil into the model and the failure surfaces wherever that nil is next used —
  arbitrarily far from the field the user typed in. Raising is what lets a
  presenter beep and revert at the point of the mistake, which is the DD10
  gate's bad-input path and the reason DD4 gates this sprint.

Direction convention worth stating once: **LEFT is the model's type, RIGHT is
the view's**. `leftToRight:` is number → text, `rightToLeft:` is text → number.
The first version of the gate had them the other way round and "passed" one
assertion by accident.

## Two gaps found by running it

1. **`String empty`** — a common Dolphin idiom, absent from the bridged class.
   Added to the builder's `kBridgedClassSends` table as `stStrEmpty`, answering
   the empty STRING. Deliberately not `String new`, which answers a mutable
   char buffer (a Dart List); a converter returning one of those where a String
   is expected fails much later.
2. **`Number class >> fromString:`** — `st/dolphin_compat/08_number_parse.mst`.
   The world's `String>>asInteger` answers nil on bad input, which is the right
   contract for a query and the wrong one here. This raises `InvalidFormat`,
   and offers `fromString:ifInvalid:` for a caller with somewhere better to put
   the failure.

## Next in DD10

- `TextPresenter`/`NumberPresenter` and the view side of the triad.
- The Command framework (`queryCommand:`, `CommandDescription`), `Menu`/
  `MenuBar` + accelerators.
- The worker doctrine: a command shipping work to a Dart isolate, with the
  continuation updating a `ValueModel` **on the UI thread via the posted-action
  queue** — never from the worker. `docs/WORKERS.md`.
- The acceptance app and its beep-and-revert path.

## The worker doctrine: settled, not yet built (`docs/WORKERS.md`)

Dolphin runs long work on green processes. This VM has no green processes and
will not grow any — Dart's unit is the isolate, which copies rather than
shares. The doctrine that replaces `fork`:

> Work happens in an isolate. The UI is touched only on the UI thread, and only
> through the posted-action queue.

The queue is not a convenience. The door enters the image from inside a
`WndProc`, synchronously and to arbitrary depth, and DD7 established both that
a handler must not rebuild the window it is being called from, and that a raise
inside a door entry cannot be caught outside it. A worker continuation is the
same hazard arriving from a different direction, and `UiSession postAction:` is
where DD8 already proved deferral works — a self-posting action defers to the
NEXT pump rather than extending the current drain.

The continuation updates a **ValueModel**, never a view. The triad already
propagates a model change to every subscriber, so a worker result reaches the
screen by the same route a keystroke does.

### `st/world/47_worker.mst` is INERT here — and that is a finding

The world carries a `Worker` class from the MACVM lineage with the whole
primary/worker doctrine written up in its header. It does not work in this
port: its methods are bodied with **numbered primitives** (220–228, 250), and
in this VM a numbered `<primitive: N>` is intent, not dispatch — the rule the
DD8 `identityHash` defect established. Every one of those methods compiles to
`^self`.

It is therefore a SPECIFICATION to reimplement against isolates, not a
starting point to wire up. Its doctrine transfers wholesale; only the transport
changes. Nothing loads it today, and nothing should until that is done.

The build order, and the one step that carries the doctrine, are in
`docs/WORKERS.md` §"The build order when it lands" — step 3 must POST the
continuation, not call it. Calling it directly from the reply handler would
work, look correct, and violate every reason above.

## Per-window routing — the prerequisite the brief did not name

Gate: `test/st_twowin.dart`.

The door's funnel carried `(kind, msg, wParam, lParam)` and `UiSession`
dispatched to `LastWindow` — whichever view registered most recently. **Every
door gate in the tree passed under that**, because every one of them opens
exactly one window. It is wrong the moment two exist: a shell owning an EDIT
control needs `WM_COMMAND` to reach the control's OWNER, and DD12's stacked
modals cannot work at all.

The funnel now carries the HWND: `(kind, hwnd, a, b, c)`. Every dispatch
resolves its receiver through `viewFor:` — a registry that **already existed
and was already maintained**; the handle was the only missing piece.
`LastWindow` survives solely as the fallback for an unregistered hwnd, which
is what the DD7 spike suites present (they drive the raw door without
registering a view). A real window is always registered, so the fallback never
fires for one.

The gate opens two windows and asserts each message lands on exactly one:
WM_SIZE through Dolphin's map with each window's own lParam, the named
WM_COMMAND channel, and paint. Each assertion is written as **"A saw it AND B
did not"** — a broadcast to both would satisfy "A saw it" on its own. It also
checks that closing A leaves B routable, which is exactly what a
LastWindow-shaped router breaks.

One thing the first run caught in the gate itself: invalidating a HIDDEN window
produces no WM_PAINT, so the paint check passed on two zeroes and proved
nothing. Both windows are shown first now.

## The triad over real Win32 EDIT controls

Gate: `test/st_text.dart` + `st/test/ffi/text_probe.mst`. **Two fields, one
model.** Edit either and both it and the model move; the other field follows.
Set the model directly and both follow.

Everything load-bearing is Dolphin's: `UI.ValueHolder` is the model,
`UI.NumberToText` the conversion, Dolphin's event system the notification,
`InvalidFormat` the bad-input signal. Ours is `WinTextEdit` — a real Win32
EDIT control (`st/dolphin_compat/09_wincontrol.mst`).

**Controls come through the generated floor**, `User32 createWindowEx:…`,
straight from Dolphin's own pragma — not the door's `mvpCreateButton`. That
native was a DD7 spike convenience for proving WM_COMMAND arrived at all; a
real control wants its own class name, style and id, and the prim already
marshals every one. The door keeps only the TOP-LEVEL window class, because
that is the one whose WndProc has to be ours.

The text assertions read the WINDOW through `GetWindowTextW`. A gate that
asked the presenter what it thinks the text is would pass on a field that
never updated.

### `lpClassName` is a POINTER, and that is Win32's doing

`createWindowEx:` marshals `lpWindowName` for us but refuses a String for
`lpClassName` — "FFI: cannot pass String as a pointer argument". Correct, and
not a generator defect: the parameter accepts either a name **or a registered
class ATOM**, so Dolphin's pragma cannot type it as a string. `WinControl`
marshals it itself into a `Utf16Buffer`, freed under `ensure:`. The refusal is
the floor working — a wrapper that accepted a String there would hand
CreateWindowExW an object pointer.

### Beep-and-revert, the reason DD4 gates this sprint

A field whose text will not convert must do three things, and the gate asserts
all three separately because any one of them can be got right while another is
wrong: it must NOT write the model (no nil in the model), it must revert its
own text to the model's current value rendered back through the converter, and
it must leave every OTHER view alone. A fourth assertion flushes the reverted
field again — a field that reverts visually but keeps a stale value behind
would pass the first three and fail on the next flush.

One structural note carried into the presenter: model→view refresh is guarded
by an `updating` flag, because `flush` writes the model, which notifies, which
lands back on the field. Without the guard a keystroke overwrites the text the
user is still typing.

## Commands and menus

Gate: `test/st_command.dart` + `st/test/ffi/command_probe.mst`. 36 classes
translated now — the whole Command framework and menu tree came across:
`UI.CommandDescription`, `UI.CommandQuery`, `UI.CommandPolicy`,
`Graphics.GraphicsTool`, `UI.MenuItem`, `UI.Menu`, `UI.MenuBar`.

**The menus themselves translate; the CONTROLS do not.** `Menu` hangs off
`Graphics.GraphicsTool`, which is Object-rooted and small, so the whole tree
is ordinary Smalltalk. A control is a Win32 *window class*, not a Smalltalk
one, so it needs an adapter. That is the line: translate what is Smalltalk,
adapt what is Windows. `st/dolphin_compat/10_winmenu.mst` only creates the
HMENU and pushes item state at it.

Win32's menu API here is `InsertMenuItem`/`SetMenuItemInfo` with a
MENUITEMINFOW, not the older `AppendMenu`/`EnableMenuItem` — which is also all
Dolphin's pragma set carries, so it is what the generated floor offers.

### Enablement is read back FROM WINDOWS

`queryCommand:` is Dolphin's hook: a view answers a `CommandQuery` saying
whether a command applies right now. The gate makes `#reset` conditional — it
is only meaningful once the value has moved off its start — so enablement is
*observable* rather than constant, and then asserts the item's state through
`GetMenuItemInfo`. Asking the probe what it thinks it set would agree with
itself whatever happened.

Two assertions worth keeping: the same item's state changes across a command
(greyed → enabled → greyed), and **a disabled command refuses even when its id
is delivered anyway**. Windows greys the item so a user cannot click it, but an
accelerator or a posted message still delivers the id — Dolphin checks, so the
probe checks.

### `intptrAt:put:` was missing from the runtime

`ExternalMemory` had `intptrAt:` and no writer, so **every struct with a
pointer field was read-only** — and `genstructs` emits no setter for one
because the runtime had none to emit. MENUITEMINFOW's `dwTypeData` (the item
text) is the first caller. Added beside its reader.

## The worker mechanism — built (`test/st_worker.dart`)

The doctrine from `docs/WORKERS.md`, now with a transport
(`test/worker_host.dart`) and an image side
(`st/dolphin_compat/11_worker.mst`).

`Worker do: #task with: arg then: aBlock` answers immediately. The block stays
in the image under an id — isolates copy, and a Smalltalk block cannot cross —
so only the id, the task NAME and the argument travel. The Dart host drains
the queue, spawns an isolate per task, and on reply sends
`Worker complete: id with: result`, which **posts** the continuation.

**The run loop is Dart's, and that is forced.** `UiSession pump` drains Win32
through a native call and returns; it never runs Dart's event loop, so an
isolate reply can only be delivered when control is back in Dart. Pump a
slice, `await`, repeat — and the `await` is the load-bearing line. Without it
no reply is ever delivered however long the Win32 pump spins. That belongs in
the record because it is the one thing about this design that is not
negotiable.

The transport lives in ordinary Dart, NOT in the bootstrap `dart:cocoa`
library: isolates are the run loop's business, not the Smalltalk runtime's.

### What the gate proves, and why in three parts

1. Submission returns immediately — ~16ms, including the first
   `Isolate.spawn`.
2. The pump stays LIVE while the isolate burns: **26 real WM_PAINTs** counted
   during the run. The task burns CPU rather than sleeping, deliberately — a
   sleeping isolate proves the reply arrives, not that the UI thread kept
   running while another thread was actually busy.
3. **The continuation is POSTED, not called.** Asserted by observing the GAP:
   at the moment `Worker completed` says the reply arrived, the continuation
   has not run and exactly one action sits in the queue; the next pump runs
   it. This is the assertion that carries the doctrine — calling it inline
   from the reply handler satisfies 1 and 2 and is still wrong.

A failure path too: a task that raises replies with a message rather than an
exception (one cannot cross an isolate), the image rebuilds it as an `Error`,
and it is posted the same way.

### Known limitation, recorded

The task table is a top-level literal. A spawned isolate re-runs the library
from scratch with its own statics, so a task registered by calling a function
from `main` is absent on the other side — tasks must be visible at
library-init time in BOTH isolates. Letting an application supply its own
means a place in that literal, or a generated one.

## COURSE CORRECTION (2026-08-16): the MVP is Dolphin's, in Smalltalk

The project owner caught a real drift, now binding as `DOLPHIN_PORT.md` scope
rules 7 and 8: **the deliverable is Dolphin's own MVP framework — translated
Smalltalk — running.** Dart is an implementation substrate with exactly the
standing C++ has (door/pump, FFI floor, worker transport, harnesses), and
**Workers on isolates replace Dolphin's processes/green threads outright**.
No MVP logic was ever written in Dart — but a parallel HAND-WRITTEN SMALLTALK
mini-framework grew around the translated classes, which is the same failure
in a different coat. This section is the honest ledger.

### Genuinely Dolphin's, already load-bearing

`Model`/`ValueModel`/`ValueHolder`/`ValueBuffer`; `TypeConverter`/
`NumberToText` and the `InvalidFormat` path; `CommandDescription`/
`CommandQuery`/`CommandPolicy`; `BorderLayout`/`LayoutContext`/
`LayoutPlacement` and the `Rectangle`/`Point` geometry; `buildMessageMap`
dispatch. Translated and loaded but NOT yet driven: `Presenter`, `Shell`,
`ValuePresenter`, `TextPresenter`, `Menu`/`MenuItem`/`MenuBar`.

### Substrate — legitimately ours, stays

The door, pump and routed set; the FFI floor with its generated prims and
structs; the worker transport; the accelerator table in the pump
(`TranslateAcceleratorW` needs the MSG and the pump is native); `UiSession`
as the kernel bridge, with an eye on Dolphin's `InputState` for later.

### SCAFFOLDING — named, with what retires each

| Stand-in | Duplicates | Retired by |
|---|---|---|
| `TextField` (text_probe) | **`UI.TextPresenter`'s whole role** — the clearest drift | driving `UI.TextPresenter` + `UI.TextEdit` |
| `WinTextEdit`/`WinButton`/`WinLabel`/`WinControl` | `UI.TextEdit` and the control-view classes | `UI.View` window ownership + the control wave |
| `WinView` | `UI.View` as a layout subject | `UI.View` owning windows (`View>>create` through the door's class) |
| `WinMenu` | `UI.Menu`'s realization | `UI.Menu` realizing its own HMENU through the floor; `WinMenu` shrinks to raw calls or vanishes |
| `WinAccelerators` | `UI.AcceleratorTable`'s realization | translated `AcceleratorTable` driving the pump's table |
| `CounterApp` + `test/st_app.dart` | the acceptance app | the REAL acceptance app, built from Dolphin's `Shell`/`TextPresenter`/`Menu` |

### The DD10 gate is REDEFINED

`CounterApp` is demoted on arrival to a SUBSTRATE DEMONSTRATION. It proves the
substrate carries a whole application — triad, converters, commands,
accelerator, isolate worker — and that is worth keeping. **It does not count
as the DD10 acceptance app**, because its presenter and view layer are
hand-written. DD10 is done when Dolphin's own `TextPresenter`/`Shell`/`Menu`
are the load-bearing classes of the acceptance app.

The next work item is therefore **Dolphin View window ownership** —
`View>>create` running against the door's window class — after which
`UI.TextEdit`/`UI.TextPresenter` replace `WinTextEdit`/`TextField`, and the
scaffolding column above starts emptying.

## UI.VIEW OWNS ITS WINDOW (`test/st_dolphinview.dart`)

**Dolphin's own `View>>create` makes a real window, registers itself, and
receives messages through its own message map.** `ShellView` too. That is the
milestone this sprint's course correction pointed at: the class doing the work
is Dolphin's, not a stand-in.

The path is Dolphin's code end to end — `create` -> `createWindow:` ->
`basicCreateWindow:` -> `CreateWindow>>create:` -> `User32 createWindowEx:` —
with the substrate supplying only what is genuinely its own:

* **The window CLASS.** Its WndProc has to be the door's, so
  `View class >> winClassName` answers the door's class name. Asking for the
  name now REGISTERS it: the door registered lazily and the only path in used
  to be `mvpCreateTopWindow`, so Dolphin's path got an unregistered class and
  CreateWindowExW answered 0 with GetLastError 0 — the least informative
  failure Win32 offers.
* **WM_NCCREATE**, where the door stamps the generation and tells the image.
  That is Dolphin's own binding moment: inside CreateWindowExW, with the view
  still parked in the slot the creating code put it in.
* **THE GREEN-PROCESS SLOT** — scope rule 8 at its smallest. Dolphin's
  `basicCreateWindow:` brackets the call with
  `Processor activeProcess newWindow: self`, using the active process as a
  thread-local holding slot. With one UI thread that is a variable, and
  PROVIDING it rather than rewriting the method is what keeps Dolphin's code
  running verbatim.
* **SessionManager/InputState**, bridged to `UiSession`'s registry rather than
  duplicating it. Two maps would drift and the one the door routes through
  would win silently.
* **DesktopView**, the creation parent — including
  `createShellWindow:withFunction:`, which `ShellView>>createWindow:`
  delegates to because a container may adjust placement first.

### WS_CHILD with no parent — why the first window would not open

`View>>create` calls `parentView: self class desktop` when no parent is set,
and `parentView:` ORs **WS_CHILD** into the creation style. The desktop stood
in as a plain object answering `asParameter` = 0, and a WS_CHILD window with
hWndParent 0 is invalid — so CreateWindowExW failed while the *same arguments
issued by hand succeeded*, because by hand nothing had set WS_CHILD. The
desktop now answers the real `GetDesktopWindow`, which is what Dolphin's own
DesktopView does.

### Three more translator defects, all silent

1. **Qualified CLASS-VARIABLE reads.** `^Point.Zero` reads Graphics.Point's
   class variable; both segments are capitalised, so the namespace flattener
   rsplit it to a bare unbound `Zero` — nil at runtime, no diagnostic.
   **384 sites, 62 distinct**: `Point.Zero` 60, `SessionManager.Current` 49,
   `Color.Black` 29. Now an accessor send, with a reader emitted on every
   class; an untranslated owner gives a loud doesNotUnderstand, not a nil.
2. **Primitive 157 fills slots 1..N of the WHOLE object**, inherited first —
   not offset past the superclass. Settled by evidence:
   `UI.CreateWindowApiCall` holds `rectangle dpi` (1-2), `UI.CreateWindow`
   holds `styles title` (3-4), and Dolphin's `rectangle:dpi:styles:title:`
   takes all four in that order, which an offset reading cannot express with
   two own slots. Every constructor met before had a parent with no ivars, so
   the readings agreed and the difference stayed invisible.
3. **Class CONSTANTS are inherited too.** `ShellView>>defaultExtent` reads
   `CreateWindow.UseDefaultGeometry`, which `CreateWindow` inherits from
   `CreateWindowFunction`; looking only at the named owner left it unfolded
   and the flattener rsplit it to a bare name. The lookup now walks the chain.
   Its value is a POINT — `(-16r80000000 @ -16r80000000)` — so the pool parser
   learned that a point of two literals is a literal, and that a leading sign
   belongs to the whole radix literal.

### Compat added, each a named Dolphin part

`whileMutableDo:` (the pair of the `beImmutableObject` no-op — nothing here is
frozen), `release`, **`free`** (Dolphin's default does nothing, which is what
makes `combinedAcceleratorTable free` safe when none was made; nil needed it
too, and `nil species` already proved nil reaches Object's protocol),
`isNull`/`notNull`, `Signal`, and Dolphin's rectangle PROTOCOL on the
generated `RECT`/`RECTL` — the struct's layout is generated from Win32
metadata, which has no opinion about Smalltalk protocol.

`DolphinBoot` sends the class-side `initialize` that Dolphin's package loader
would, and reports the classes that FAILED rather than aborting: a boot line
that stops half way leaves whatever followed it silently un-run, which is
exactly how this gate first read an empty registry.

### One in the gate itself

`stMvpIsWindow` answers a BOOLEAN, and both assertions compared it to 0.
`true != 0` is true and `false == 0` is false, so the "is a window" check
passed whatever the answer and the "is destroyed" check could never pass. Two
assertions, neither of them measuring anything.

### Scaffolding status

`WinView` is now retired IN PRINCIPLE — a Dolphin View that owns its own HWND
does not need an adapter standing in for one. It stays until the DD9 shell
gate is rebuilt on `UI.View`, which is the next step, followed by
`UI.TextEdit`/`UI.TextPresenter` replacing `WinTextEdit`/`TextField`.

## Rebuilding the shell gate on UI.View — partial, and honestly so

`test/st_dolphinshell.dart` + `st/test/ffi/dolphin_shell.mst`. The DD9 shell
gate with the `WinView` adapter removed: a real `UI.ShellView` subclass built
by Dolphin's own `create`, registering itself through Dolphin's own binding
moment, destroyed cleanly.

**`UI.View` already implements the entire layout protocol** — every method
`WinView` was hand-written to supply (`clientRectangle`, `rectangle:`,
`layoutExtent:`, `subViewsDo:`, `adjustRectangle:`, `hasVisibleStyle`,
`getRect`, `preferredExtent`, `actualInsets:`) exists on Dolphin's class. That
measurement is what makes the adapter retirable at all; nothing in the new
probe re-supplies view protocol.

### Where it stops, and why that is written into the gate

**`ShellView>>show` hangs.** Narrowed by bisection: `create` alone is fine —
every assertion above the stop runs with it — and the hang appears the moment
`show` is sent. `ShowWindow` generates real WM_PAINT/WM_SHOWWINDOW traffic and
the door reflects paint through its named channel whether or not a message map
is installed, so a paint handler that invalidates would spin forever. That is
the shape to look for; `View`'s paint path is where to start.

Child views are therefore not yet covered: `addSubView:` reaches
`View>>subViewsDo:`, which enumerates real child HWNDs and asks
`InputState>>lookupWindow:` for each.

The gate STOPS at that point and says so, rather than carrying a hanging
assertion — a gate that hangs is worse than one that reports where it stopped.
`st_shell.dart` still covers the full BorderLayout arrangement through the
adapter meanwhile, which is exactly why that scaffolding is not deleted yet.

### `--loose`: Dolphin's convenience layer over the generated prims

`OS.UserLibrary` is GENERATED by `genprims` from Dolphin's FFI pragmas, so it
knows nothing about the 177 methods a `.pax` files onto the same class —
Dolphin's own convenience layer, `getWindowText: hWnd` answering a String on
top of the three-argument API call. `UI.View` calls them constantly. The
translator gained `--loose OS.UserLibrary`, which emits them as a reopen.

Of the 177, **16 survive**: only PRAGMA-FREE methods are emitted. The rest are
raw `<stdcall:>` declarations — the same ones `genprims` already generates from
the same pragmas — and emitting them would both duplicate the floor and fail to
parse, since the house dialect has no `<stdcall:>`.

### A `.pax` NEVER emits a class — a regression that taught the rule

Passing `Dolphin MVP Base.pax` in for its loose methods also emitted its
RE-DECLARATION of `OS.MENUITEMINFOW` into `st/mvp`, where it loaded after and
overwrote the struct `genstructs` builds from winkb. `MENUITEMINFOW class >>
sizeInBytes` disappeared and the whole menu gate went red — six assertions,
from one file nobody meant to generate.

A `.pax` is a package MANIFEST: it re-declares every class the package
contains, including ones whose authoritative definition is a `.cls` elsewhere
or, worse, ones this project GENERATES. It now never emits a class at all,
while still contributing its loose methods, its pools and its hierarchy. The
old narrower rule (prefer the `.cls` when a class is in both) only covered the
case where we happened to translate the `.cls` too.

### Compat added on the way

`Utf16String` aliased to `Utf16Buffer` with `newFixed:` (a character count plus
a null, the sizing `GetWindowTextW` expects); `InputState>>lookupWindow:`, the
read half of the registry bridge, answering nil for a handle this image did
not create; and the DESKTOP terminating the parent chain —
`View>>invalidateLayout` walks up via `parent childLayoutInvalidated`, and that
method walks on UNCONDITIONALLY, because in Dolphin the chain always ends at a
DesktopView that answers it.

## REVIEW (2026-08-16, evening): the show hang is root-caused, and it is a family

The review went to name the next work item and found the cause instead —
`View>>subViewsDo:` is readable in the emitted source:

```smalltalk
child := User32 getWindow: handle uCmd: 5.
[child isNil] whileFalse: [
    (inputState lookupWindow: child) ifNotNil: [...].
    child := User32 getWindow: child uCmd: 2]
```

Dolphin's external-call machinery answers **nil** for a NULL handle return.
This port's generated prims answer **0** — every one of UserLibrary's 230
returns is `ret: #g`, an integer. `0 isNil` is false, so the loop never
terminates. The timing evidence closes it: the hang appeared at exactly the
commit that added `InputState>>lookupWindow:`, because before that the FIRST
iteration raised inside the loop and the containment broke it. The paint-spin
guess recorded earlier was wrong — the paint path never calls `lookupWindow:`
— and the gate comment now says so.

**It is a family, not a site.** 6 `whileFalse:` loops and 8 handle-returning
call sites in this wave alone, and every one walks a chain Windows terminates
with NULL: siblings, parents, dialog tab order. The fix is therefore a
CONVENTION, not a patch: a `#h` return type in the floor (NULL → nil), emitted
by genprims wherever winkb says the return is a handle. This joins the
silent-nil family the translator work kept finding — bare unbound names,
offset D157 slots, un-walked constant chains — as the same disease in the FFI
layer: a sentinel of the wrong TYPE, invisible until a loop trusts it.

The rest of the review's outcomes live in the brief's STATUS 2 block: the
remaining-work checklist in retirement order, the ListBox scope call (may ride
with DD11's control wave), the explicit note that everything so far is
HEADLESS-verified and a visible shell is a named acceptance item, and the
tooling ledger — `translate_mvp.py` now cleans its output directory before
emitting (the 93-stale-files incident), with a gate-sweep script and a shared
`test/gate_util.dart` recommended but not yet built.
