# DD4 — Exceptions: the ANSI hierarchy on `stOnDo`/`stEnsure` `M/L`

**Objective:** Dolphin's exception surface, conformant enough for the MVP
corpus: the class hierarchy, the handler protocol, DNU → catchable
`MessageNotUnderstood`. The *mechanism* exists (measured:
`on:do:` → `stOnDo(protected, type, handler)`, `ensure:`/`ifCurtailed:` →
`stEnsure` = Dart try/finally, running during NLR unwind —
`st_flow_graph_builder.cc:1250-1258`); this sprint builds Dolphin's *protocol*
on it. Gates DD10; **nothing translated before DD10 may use `on:do:`**.

**Read first:** the builder's stOnDo/stEnsure lowering + whatever Dart-side
`stOnDo` resolves to (`port-win/dart_st/cocoa.dart` or prelude), prior-art V2
(the W5 spec — the class list and MVP-facing surface transfer), D8's own
`Core.Exception.cls` family + `Kernel.MessageNotUnderstood` in dsfork, and the
D8 tests (`ExceptionTest`, `ZeroDivideTest`).

## Work

1. **The resumability spike — decision before code.** Dolphin `resume:`
   returns control to the *signal point*; Dart try/catch unwinds frames before
   the handler runs. Measure what `stOnDo` does today (where does the handler
   execute relative to the protected frames?). Then choose, and record in
   `docs/DIALECT_GAPS.md` A5 + `dd04_NOTES.md`:
   - **(a) Raise-time handler search** (the conformant fix): `signal` walks a
     handler chain and runs the handler as a closure *before* any unwind;
     unwind (via the existing NLR/ensure machinery) only on fall-through /
     `return:` / `pass`. This is front-end + in-image work — the expected
     dialect change of owner rule #5.
   - **(b) v1 non-resumable:** handlers run post-unwind (today's shape);
     `resume:` on a non-Notification raises; `Notification signal` answers its
     default without running resumption-dependent code. An explicit, tested
     divergence — acceptable only if the DD2 census shows the MVP corpus
     doesn't lean on resumption beyond Notification defaults.
2. **The hierarchy, in-image** (new world file `st/world/xx_exceptions.mst`):
   `Exception`, `Error`, `Warning`, `Notification`, `ZeroDivide`, `Halt`,
   `MessageNotUnderstood`, `ExceptionSet`, plus the handler protocol:
   `signal`/`signal:`, `on:do:` (class + ExceptionSet filters), `pass`,
   `outer`, `retry`, `retryUsing:`, `return:`, `resume`/`resume:` per the
   spike decision, `description`/`messageText`.
3. **Wiring:** DNU raises `MessageNotUnderstood` through the chain first,
   falling through to the existing DNU behavior when unhandled (byte-identical
   unhandled path — existing world tests must not notice this sprint).
   `error:` → `Error signal:`. `ZeroDivide` raised from the division prims'
   fallbacks.
4. **Conformance corpus:** translate (DD3) the D8 ExceptionTest/ZeroDivideTest
   subset consistent with the spike decision; excluded cases listed by name
   with reasons in `dd04_NOTES.md`.

## Gate

- Spike decision recorded with the measurement that justified it.
- Translated exception-test subset green (headless, arm64).
- `[nil foo] on: MessageNotUnderstood do: [:e | …]` catches; the unhandled
  path is unchanged (existing world suite green, count vs DD0 baseline).
- `ensure:` runs exactly once under: normal return, NLR past it, signal
  through it, `retry` re-entry (four explicit tests).
- ExceptionSet ordering + nested-handler LIFO tests (a handler installed in an
  inner `on:do:` never fires for an outer protect after its block returns).

## Traps

- `stEnsure` during NLR already works (measured claim from the builder
  comment) — still write the test; a comment is not a measurement.
- Dolphin's `Signal description:` idiom and `Win32Error`/`InvalidFormat`/
  `OperationAborted` are **DD8 compat classes**, not this sprint (prior-art
  V2 made the same cut).
- Handler-in-handler (a signal raised inside a handler) must find the *next
  outer* handler — the classic infinite-regress trap; test it explicitly.
