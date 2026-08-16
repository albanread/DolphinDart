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
