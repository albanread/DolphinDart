# DD8 — The compat kernel (`world/dolphin_compat`) `M`

> ## STATUS (2026-08-15) — in progress, blocked; read this before the brief
>
> **Done:** `st/dolphin_compat/01_events.mst` (the event system, hand-written)
> and `st/test/features/test_events.mst` (the semantics suite, written FIRST
> from the D8 source — six cited rules: last-handler value; keyed-by-receiver
> replace; safe no-handler trigger; size-snapshotted trigger loop; remove-by-
> receiver; `noEventsDo:` restores under `ensure:`).
>
> **Blocker 1 — `Object>>identityHash` answers SELF** (inherited, on the bare
> world). Root cause is structural: a numbered `<primitive: N>` pragma is NOT
> dispatch in this front-end — only the `"primitive: FFI "` form is handled, so
> a bare numbered body compiles to `^self`. Most world prims work because their
> SELECTORS are special-cased; `identityHash` has no such handling, so every
> identity collection keyed by a plain object dies (`IdentityDictionary at:
> Object new` → "does not understand &", via `identityHash bitAnd:`).
> **Fix design:** a named `<stprim: stIdentityHash>` backed by Dart's
> `identityHashCode()` (present in 1.24) wired through cocoa.dart + a one-line
> body change in `01_object.mst`. Do NOT use `^self hash` — String/Integer hash
> by value, which would conflate identity with equality exactly where the
> distinction matters. Then re-run the FULL battery for regressions.
>
> **Blocker 2 — gate layering.** The suite lives in `st/test/features` but needs
> `st/dolphin_compat` loaded; the standard battery invocation loads `st/world`
> alone, so TestEvents aborts on `EventRegistry` before it even reaches the
> identityHash wall. From DD8 on, the gate is
> `st_battery.dart "st/world;st/dolphin_compat" st/test/features` — update
> `docs/TOOLCHAIN.md` when closing the sprint.
>
> **New sub-task — the bare-primitive audit.** `identityHash` is unlikely to be
> the only silent-`^self` method: scan the world for methods whose body is ONLY
> a `<primitive: N>` line (no fallback code after it) and cross-check each
> selector against the front-end's special-casing. Anything unhandled is a
> latent identityHash-class defect. Small script, big hazard.
>
> **Inherited from DD7 (build here, not there):** the posted-action queue and
> idle hook are UiSession's deferred-actions/`onIdle` machinery — they were DD7
> leftovers precisely because they belong to this sprint's `UiSession`. The DD7
> spike classes (`MvpDoor`, `MvpWindow`) are the seed UiSession replaces; the
> door tortures in `test/st_door.dart` must be re-run green under UiSession
> routing before the spikes are deleted.
>
> **Two compat items measured in DD6c, add to the class list below:**
> `Character>>asUnicodeValue` (alias of house `value`); and note that `asString`
> is a helper selector the IL builder rewrites AT THE CALL SITE — compat must
> route Dolphin's `asString` uses, never define a method of that name and expect
> it to be reached.

**Objective:** the hand-written bridge classes Dolphin's MVP corpus assumes,
per the prior-art G3 inventory — **which transfers nearly verbatim**; this doc
records only deltas. Home: `st/world/dolphin_compat/` (loaded after the core
world, before any translated corpus).

**Read first:** prior-art G3 (the inventory + the event-semantics test list),
D8 `Core.Object` events + `Kernel.Events*` sources in dsfork (the semantics
being ported), DD4's hierarchy (the exception-compat classes subclass it).

## Work

1. **The event system, semantics-first** (the risk item): a dedicated test
   file written from the D8-source-derived semantics table **before** porting
   consumers — trigger return value, argument merge from the left,
   add-during-trigger exclusion, idempotent registration,
   `removeEventsTriggeredFor:`, `noEventsDo:`. Strong storage v1 (weak is
   backlog; explicit `free` discipline per prior-art).
2. The compat classes: `Model`, `SearchPolicy`, `DeafObject`/`DeadObject`,
   `LookupTable` alias, `GUID newUnique`, `expandMacros`/`<<`,
   `propertyAt:`, `Cursor showWhile:` shim, `Win32Error`/`InvalidFormat`/
   `OperationAborted` on DD4's hierarchy.
3. **`UiSession` proper**, replacing the DD7 spike: window registry +
   `lastWindow` cache, `windowCreated:`, `wndProc:message:wParam:lParam:`
   routing on the ported `dispatchMessage:` shape, deferred actions
   (DD7's posted-action queue), `onIdle`, startup/shutdown +
   generation-respawn arm (`UiSession startUp` re-runs on a fresh
   generation — prior-art G-i).
4. `perform:` arity note (prior-art G-k): `dispatchMessage:` uses the
   array form (`perform:withArguments:` — a DD5 W1 row) where D8 used
   fixed-arity `perform:with:with:with:` if the fixed form is absent.
5. Delete `st/world/xx_uisession_spike.mst`; the compat `UiSession` drives
   the same windows.

## Gate

- Event-semantics suite green — written first, commit order proves it.
- `UiSession` drives the DD7 spike scenario (window, button, click →
  Transcript, clean close) with the spike file deleted.
- Registry hygiene: after a create/destroy cycle, the registry is empty
  (`purgeDeadWindows`-equivalent asserts).
- Full suite green vs baseline; DD7's torture gates re-run green under
  `UiSession` routing.

## Traps

- The event-semantics tests are the sprint's whole value — porting consumers
  against a misremembered trigger contract is how GUI heisenbugs are born.
  Every rule in the table cites the D8 source line it came from.
- `LookupTable` in Dolphin is not `Dictionary` in edge semantics (nil keys,
  identity) — alias only what the census says the corpus uses; test what you
  alias.
