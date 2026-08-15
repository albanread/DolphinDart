# DD8 — the compat kernel: NOTES

**Status: DONE.** 2026-08-15. Both arches: battery **15 suites / 0 failures**,
uisession 0, door 0, prims 0.

## What landed

| File | What |
|---|---|
| `st/dolphin_compat/01_events.mst` | the event system, semantics-first |
| `st/dolphin_compat/02_uisession.mst` | `UiSession` + a minimal `UiWindow` |
| `st/dolphin_compat/03_kernel.mst` | `Model`, `ValueModel`, `SearchPolicy`, `DeafObject`, `GUID`, properties, `expandMacrosWith:`, the exception compat classes |
| `st/test/features/test_events.mst` | 14 assertions, all six rules read from D8 source |
| `st/test/features/test_compat_kernel.mst` | 25 assertions on the bridge classes |
| `st/test/features/test_bare_prims.mst` | 28 assertions pinning the audit |
| `test/st_uisession.dart` | the session gate — DD7's door behaviour re-run through the registry |

## The blocker, and what it really was

`Object>>identityHash` answered **itself**, so every identity collection keyed by
a plain object raised `does not understand &`.

Root cause was structural, not a typo: **a numbered `<primitive: N>` pragma is
not dispatch in this front-end.** Only `"primitive: FFI "` is handled, so a
method whose body is only the pragma compiles to an empty body. Most world prims
work anyway because their *selector* is separately special-cased; `identityHash`
had no such handling.

Fixed with a named `<stprim: stIdentityHash>` over dart:core's
`identityHashCode` — no C++ native needed. **Deliberately not `^self hash`**:
String and Integer hash *by value*, which would conflate identity with equality
exactly where the distinction is the point.

**The audit found no others.** All 53 bare-primitive methods in the world were
scanned and each selector tested empirically rather than reasoned about;
`identityHash` was the only one. `test_bare_prims.mst` keeps it that way.

## Four helper-selector collisions, all the same shape

The IL builder rewrites certain selectors **at the call site**, so defining a
method of that name means it is never reached — the send lands elsewhere, often
on a class value, surfacing as `_Type has no instance method …`. Hit four times
in one file:

| Named | Collided with | Renamed to |
|---|---|---|
| `at:` / `at:put:` / `removeKey:` on `EventRegistry` | the universal collection helpers | `eventsFor:` / `eventsFor:put:` / `removeEventsFor:` |
| `valueWithArguments:` on `EventHandler` | `BlockClosure`'s | `evaluateWith:` |
| `trigger:withArguments:` on `EventsCollection` | the protocol this file adds to **Object** — EventsCollection is an Object too | `triggerEvent:withArguments:` (Dolphin's own name) |
| `copyFrom:to:` for the trigger snapshot | died inside the collection's internals | no copy at all — Dolphin reads the size once and indexes the live list |

That last one is the good outcome: matching Dolphin exactly is both faithful
*and* cheaper, and it is what makes an add-during-trigger invisible to that
trigger.

**Rule for DD9+: before naming a compat method, check the selector is not a
universal helper.** Each occurrence cost a debugging round.

## Spelling differences belong in the translator, not in compat

`Character>>asUnicodeValue` could not be added as a compat method at all: a
character literal is a native `StChar` whose ST protocol lives on the bridged
`Character ext` holder, and a **cross-file reopen of a bridged class does not
reach it** (measured under both `nil subclass:` and `Magnitude subclass:`).

So it moved to the translator as a `SELECTOR_RENAMES` rewrite, with golden
tests. The general rule, now written into `03_kernel.mst`: **when Dolphin and
the house dialect differ only in spelling, rewrite at ingestion; compat classes
are for missing behaviour.**

## UiSession

Carries Dolphin's own responsibilities — registry (`hwnd → view`, `lastWindow`),
routing from the door's channels, deferred actions, `onIdle`.

Two design points worth keeping:

1. **Protection is installed inside the entry.** DD7 measured that containment
   is at the door, so a raise inside an entry never reaches a handler outside
   it. `dispatch:arg:` therefore wraps the view send itself — the only place it
   can work.
2. **`drainActions` drains a snapshot.** An action that posts another action
   must not extend the current drain, or a self-posting action spins the UI
   thread forever. The gate proves it: after one pump the counter is 1, after
   the next it is 2.

The door funnel routes window messages to `UiSession` and **falls back** to the
DD7 spikes, so the raw re-entry tortures still run against the bare door.

## Carried into DD9

- The spikes (`MvpDoor`, `MvpWindow`) stay until DD9 no longer needs them as the
  door's own regression; `test/st_door.dart` is that regression.
- `ValueModel setValue:` updates **without** notifying — DD10's `AspectBuffer`
  ok/cancel semantics need exactly that, and the suite pins it now.
- `GUID newUnique` is a v1 shortcut (clock + counter, no `CoCreateGuid`),
  recorded in the source rather than left to be discovered.
