# DD4 — exceptions: NOTES

**Status: DONE.** 2026-08-15. Battery 12 suites / 566 assertions / 0 failures
throughout.

## The sprint was much smaller than the brief assumed

The brief said "build the ANSI hierarchy". **Most of it already existed** in
`st_prelude.h`: `Exception` (with `messageText`, `description`, `signal`,
`signal:`, and the handler actions `return:`, `return`, `retry`, `pass`),
`Error`, `ArithmeticError`, `ZeroDivide`, `MessageNotUnderstood`, `Warning`.
DD0's grep found no `subclass: Exception` in `st/world` and concluded there was
no hierarchy — true of the world, wrong about the substrate, because the
hierarchy lives in the prelude. `test_exceptions`' 21 green assertions were the
clue, and they were in the DD0 notes unread.

## The resumability spike — decided by measurement

**Probe 1 — where does the handler run?**

```smalltalk
[[ Error signal: 'x' ] ensure: [ t nextPutAll: 'E' ]] on: Error do: [:e | t nextPutAll: 'H' ]
```
→ **`EH`**. The protected block's `ensure:` fires *before* the handler, so the
handler runs **after unwinding**. Confirmed by probe 2: code after the signal
never runs. This is Dart `try`/`catch` semantics showing through, exactly as
`DOLPHIN_PORT.md` risk #1 predicted.

**Probe 2 — does the corpus care?** The deciding measurement:

| Construct | Sites, corpus-wide | Sites **in MVP** |
|---|--:|--:|
| `resume:` | 14 | **0** |
| `resume` (unary) | 18 | **0** |
| `outer` | 47 | **0** |
| `retryUsing:` | 12 | **0** |
| `signalOn:` | 6 | **0** |
| `ExceptionSet` (`on: A, B do:`) | **0** | **0** |
| `MessageNotUnderstood` | 4 | **0** |
| **`Notification`** | **83** | **41** (39 files) |

All 14 `resume:` sites are inside Dolphin's own kernel exception classes
(`Core.Error`, `Core.Exception`, `Core.Notification`, `Core.Warning`,
`Core.ZeroDivide`, …) — the classes this project **replaces**. The MVP corpus
never resumes.

**Decision: option (b), v1 non-resumable — and it is not a compromise.** A
raise-time handler search in the front-end would buy conformity the corpus does
not use. What the corpus *does* use is `Notification`, and Notification's real
requirement is not frame resumption but *"an unhandled signal answers its
default instead of terminating"* — which is implementable at the signal point.

Recorded as an explicit divergence rather than hidden: `resume:` exists and
**raises a message naming the limitation**, so a future class that needs it
fails loudly instead of receiving something plausible.

## What landed

**`Notification` and the resumable-default rule.** `stOnDo` now publishes the
type it handles for the dynamic extent of its protected block, and `stSignal`
consults that stack: a resumable exception with no handler in scope answers
`defaultAction` instead of throwing. The pop is by identity, not `removeLast` —
`retry` re-enters the loop and a non-local return can leave through the same
`finally`, so a positional pop could discard someone else's entry.

**The hierarchy now matches Dolphin's, verified from source** rather than from
memory (`Core.Warning.cls` etc. parsed directly):

```
Exception ─┬─ Error ─┬─ ArithmeticError ── ZeroDivide
           │         └─ MessageNotUnderstood
           └─ Notification ── Warning
```

`Warning` moved from `Exception` to `Notification`, making it resumable — which
is what Dolphin does, and why `Warning signal:` may be ignored safely.

**DNU is now catchable as `MessageNotUnderstood`** on both paths, which needed
two changes because there are two:

- an ST-object receiver reaches the world's `Object>>doesNotUnderstand:`
  (now signals `MessageNotUnderstood` rather than `self error:`);
- a **native** receiver (`nil fooBar`) never gets that far — Dart raises
  `NoSuchMethodError` first — so `_stWrapNativeError` reifies that as
  `MessageNotUnderstood`.

Only fixing the first would have left the ANSI idiom silently unreachable for
exactly the receivers proxy code cares about. `MessageNotUnderstood` is a
subclass of `Error`, so every existing `on: Error do:` still matches.

## Gates

| Gate | Result |
|---|---|
| Unhandled `Notification signal` / `signal:` | `nil` |
| Handled `Notification` reaches its handler | yes |
| Unhandled `Warning signal:` | `nil` |
| Handled `Warning` still works | yes |
| `on: Error do:` does **not** catch a `Notification` | correct |
| Hierarchy `isKindOf:` checks | all correct |
| `resume:` refuses loudly | yes |
| `ensure:` runs exactly once — normal exit / raise | `E` / `E` |
| Nested handlers are LIFO | innermost wins |
| `retry` re-runs the protected block | yes |
| `pass` reaches the enclosing handler | yes |
| **A `Notification` signalled inside a running handler** | answers `nil` — the handler-stack pop is correct under nesting |
| DNU catchable as `MessageNotUnderstood` and as `Error` | both, on native and ST receivers |
| Full battery | 12 suites / 566 assertions / 0 failures |

## Deliberately not built

- **`outer`, `retryUsing:`, `signalOn:`, `ExceptionSet`** — zero MVP sites each
  (`ExceptionSet` has zero sites *anywhere*). Adding them now would be
  speculative surface with no test that means anything.
- **`MessageNotUnderstood>>message`** (the reified `Message`) — zero MVP sites.
- **True resumption.** If DD9+ pulls in a class that needs it, the raise-time
  handler search is the design, and `resume:`'s refusal message is where the
  next person will start.

## Correction to DD0's notes

DD0 recorded *"no ANSI Exception hierarchy in the world"* and carried it into
`DIALECT_GAPS.md` row A5. Accurate about `st/world`, misleading as a gap: the
hierarchy is in the prelude, and A5's real content was always the four missing
pieces above, not the hierarchy. `DIALECT_GAPS.md` is corrected.
