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

> ## STATUS 2 + REVIEW (2026-08-16, evening)
>
> **Done since the morning block:** per-window routing (`st_twowin`), real
> EDIT controls + triad over them (`st_text`), commands + real menus
> (`st_command`), the worker mechanism (`st_worker`), accelerators in the
> pump, the substrate demo app (`st_app`, demoted per the course correction),
> **`UI.View` window ownership** (`st_dolphinview`) and a partial shell-gate
> rebuild on it (`st_dolphinshell`).
>
> **The blocker has a ROOT CAUSE, not a hypothesis.** `ShellView>>show` hangs
> in `View>>subViewsDo:`:
>
> ```smalltalk
> child := User32 getWindow: handle uCmd: 5.
> [child isNil] whileFalse: [ ... child := User32 getWindow: child uCmd: 2 ]
> ```
>
> Dolphin's external-call machinery answers **nil** for a NULL handle return;
> our generated prims answer **0** (`ret: #g` — all 230 of UserLibrary's
> returns are `#g`). `0 isNil` is false, so the loop never terminates. It
> "worked" before `InputState>>lookupWindow:` existed only because the first
> iteration raised inside the loop. This is a FAMILY: 6 `whileFalse:` loops
> and 8 handle-returning call sites in the wave alone, and every one walks a
> chain Windows terminates with NULL.
>
> **Fix direction (next work item):** a handle-return convention in the floor
> — a `#h` return type in genprims/st_natives that answers nil for NULL —
> driven from winkb, which knows which returns are handles. NOT a per-method
> compat patch: the family is the point.
>
> **REMAINING for DD10, in retirement order:**
> 1. ~~The handle-return convention → `show` unhangs → child views under a
>    Dolphin shell → full `st_dolphinshell` gate.~~ **DONE.** It took TWO
>    conventions, not one: `#h` (handle → nil for NULL, 124 returns) as
>    predicted, and `#b` (BOOL → Boolean, 297 returns) which was not — with
>    `isWindow:` answering the integer 1, `View>>isOpen` answered 1,
>    `show`'s `ifFalse:` took the wrong branch and every `show` created
>    ANOTHER window: three live windows per view. Plus five more silent-nil
>    defects behind them (`newBuffer`, `marshal:`, `Object>>asParameter`,
>    inherited pool imports for `.pax` loose methods, and
>    `usePreferredExtent:` being separate from `preferredExtent:`). Gate
>    `st_dolphinshell` is green on the full arrangement including a second
>    resize; 21/21 gates pass. See `dd10_NOTES.md`.
>
>    **`WinView` is NOT yet deletable, and the brief was wrong to pair the
>    two.** `WinControl` (and so `WinTextEdit`/`WinButton`/`WinLabel`) is a
>    `WinView` SUBCLASS, and `text_probe`/`counter_app` build on those — so
>    the adapter cannot go until item 2 retires the controls. What IS
>    retirable now is the DD9 gate `st_shell` + `shell_probe.mst`, whose
>    arrangement coverage `st_dolphinshell` now fully supersedes. Recorded
>    rather than done, so the retirement happens in one piece with item 2.
> 2. Control SUBCLASSING substrate (the known-hard piece, not started): a door
>    trampoline for comctl WndProcs, then translate `UI.TextEdit` and drive
>    `UI.TextPresenter` → **retire `TextField`/`WinTextEdit`**.
> 3. Drive `UI.Menu`'s own realization over the floor → **retire `WinMenu`**;
>    translated `AcceleratorTable` → **retire `WinAccelerators`**.
> 4. The acceptance app on Dolphin's `Shell`/`TextPresenter`/`Menu` — and a
>    **VISIBLE shell**, named explicitly: everything so far is
>    headless-verified, and nothing has yet been put on screen by Dolphin's
>    own `show`.
>
> **Scope call:** `ListBox` may ride with DD11's control wave — `TextEdit`
> alone proves the value-presenter path here, and `ListModel` is not needed by
> the acceptance app. Recorded as a decision, not a slip.
>
> **Tooling, from three incidents this week:** `translate_mvp.py` now CLEANS
> its output directory before emitting (93 stale files from the brief
> .pax-emitting run were invisible to every gate); still recommended but not
> built — a single gate-sweep script to replace the bespoke per-sweep
> one-liners, and a shared `test/gate_util.dart` for `ev`/`must`/paint-liveness
> so the gate-harness defect pattern (boolean-vs-0, coalescing-flaky paint
> counts, temps-less `ev`) stops recurring.

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
