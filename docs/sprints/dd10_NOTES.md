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
