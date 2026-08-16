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
