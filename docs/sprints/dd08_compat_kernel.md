# DD8 — The compat kernel (`world/dolphin_compat`) `M`

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
