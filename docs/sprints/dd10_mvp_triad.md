# DD10 — The MVP triad (= milestone UI-3) `L` — needs DD4

> ## STATUS + DIRECTION (2026-08-16, mid-sprint review)
>
> **Done:** the model side. `Core.Model`, `UI.ValueModel`, `ValueHolder`,
> `ValueAdaptor`, `ValueAspectAdaptor`, `ValueBuffer`, the type-converter
> chain (`TypeConverter` → `NumberToText`/`IntegerToText`), `Presenter` and
> `Shell` are translated and load — 27 classes in `st/mvp`. Gate
> `test/st_triad.dart` is green, including the bad-input path: Dolphin's own
> `NumberToText` signals `InvalidFormat` through `Number class >> fromString:`.
> The DD8 `Model`/`ValueModel` stand-ins are DELETED; their contracts moved to
> the triad gate and passed against the real classes unchanged. The worker
> DOCTRINE is settled (`docs/WORKERS.md`); the mechanism is not built, and
> `st/world/47_worker.mst` is recorded as inert (numbered-primitive bodies).
>
> **The review found one structural prerequisite the brief did not name:**
>
> **PER-WINDOW ROUTING.** The door's funnel carries `(kind, msg, wParam,
> lParam)` — no HWND — and `UiSession dispatch:`/`dispatchMessage:` route to
> `LastWindow`. One window, fine; the moment a shell owns an EDIT control,
> `WM_COMMAND` must find the control's OWNER, and DD12's stacked modals are
> impossible without it. The `viewFor:` registry already exists and is already
> maintained — it is simply not consulted by dispatch. The fix is mechanical
> and should land BEFORE the view side, not be retrofitted under it: widen the
> funnel to `(kind, hwnd, a, b, c)` (the named kinds zero-fill, the spike
> two-arg forwarder stays), route by `viewFor:` with `LastWindow` as the
> fallback for the spike suites.
>
> Two smaller direction points:
> - **Real controls come through the generated floor.** `UserLibrary class >>
>   createWindowEx:…` exists and marshals (verified). The door's
>   `mvpCreateButton` was a DD7 spike convenience — the TextEdit/ListBox wave
>   creates real `EDIT`/`LISTBOX` windows through the prim, parented to the
>   shell, and only the top-level window class stays door-owned.
> - **The `Graphics.Canvas` wave carried from DD9 lands here or DD11**, at the
>   first gate that needs drawn text beyond the DD9 pixel probe.
>
> Per-CLASS message maps (the global `MessageMap` on `UiSession`) can wait for
> DD11, when different view classes first coexist with different maps.

**Objective:** Model–View–Presenter in anger: the framework wave plus the
first app that exercises exceptions, converters, commands, and the
long-command doctrine. Prior-art G5 transfers as scope + gate; the worker
mechanism is Dart-native here.

**Read first:** prior-art G5 + the design's §5.8 green-process replacement
table (G-f/G-g — every `ProgressDialog`/splash/autoscroll fork site and its
replacement); DD2's process census (the measured version of that table for
our closure); Dart isolate docs in the quarry (`Isolate.spawn` works in the
seed — the README lists it as verified).

## The wave

`Presenter`, `Shell`, value models (`ValueHolder`/`ValueBuffer`/aspect
plumbing), `ListModel`, type converters (`NumberToText` and kin), the
Command framework (`queryCommand:`, `CommandDescription`), `Menu`/`MenuBar` +
accelerators, `TextEdit`, `ListBox`.

## Work

1. Translate the wave; burn the refusal report down (as DD9).
2. **The worker doctrine lands here:** a demo command ships work to a Dart
   isolate (`Isolate.spawn` + a reply port), the continuation updates a
   `ValueModel` **on the UI thread via the DD7 posted-action queue** — never
   from the worker. Document the pattern in `docs/WORKERS.md` (this is the
   MULTIVM doctrine, Dart edition — decision log #5).
3. The acceptance app (hand-written doit): a model object edited through two
   `TextPresenter`s with a `NumberToText` converter; menu commands with
   `queryCommand:` enablement; one accelerator; one long-running command
   (~3 s of isolate work) that visibly does not freeze the pump.
4. Bad-input path: converter failure → `InvalidFormat` (DD8 class on DD4
   hierarchy) → beep-and-revert — **exceptions in anger**, the reason DD4
   gates this sprint.

## Gate (prior-art G5, carried)

- The acceptance app runs: edits round-trip model↔both presenters;
  bad input beeps and reverts via the `InvalidFormat` path (test asserts the
  exception class, the beep native call, and the reverted text);
  `queryCommand:` enables/disables observably; the accelerator fires;
  the long command completes with the pump provably live (a timer-driven
  counter keeps painting during it — snapshot pair proves motion).
- Suite green vs baseline; corpus checkpoint recorded (≈ +60 classes band).

## Traps

- Nothing in the translated wave may still carry a green-process idiom the
  census missed — a `fork` surviving translation is a hard error at load,
  not a runtime surprise (add the loader/translator check if DD3 doesn't
  already refuse it).
- Modal-ish waits inside commands (`MessageBox` in a command handler) are
  fine — they pump (DD12 formalizes); `Processor sleep:`-style waits are not.
- Converter classes touch locale (`decimalSeparator`) — pin the tests to an
  explicit locale or the gate flakes on machines with `,` decimals.
