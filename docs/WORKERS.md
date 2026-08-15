# Workers — the DolphinDart doctrine

**Status: doctrine settled, mechanism NOT yet built.** 2026-08-15, during DD10.

Dolphin runs long work on green processes (`fork`, `forkAt:`), scheduled inside
one OS thread by its own scheduler. This VM has no green processes and will not
grow any: Dart's concurrency unit is the **isolate**, which has its own heap and
communicates only by copying. That is a different shape, and pretending
otherwise is how a port acquires a scheduler nobody wants to maintain.

So the rule, in one line:

> **Work happens in an isolate. The UI is touched only on the UI thread, and
> only through the posted-action queue.**

## Why the queue, and not just "call back"

The door (`port-win/dart_win32/win_mvp.cpp`) enters the image from inside a
`WndProc`, synchronously, to arbitrary depth. Two consequences settle the
design:

1. **A continuation must not run inside a door entry.** DD7 established this
   for handlers that rebuild the window they are being called from; a worker
   completion is the same hazard arriving from a different direction. The
   posted-action queue (`UiSession postAction:`, drained by `pump`) exists
   precisely so work can be deferred to *outside* the current entry, and the
   DD8 gate already asserts that a self-posting action defers to the NEXT
   pump rather than extending the current drain.

2. **A raise inside a door entry cannot be caught outside it.** Recorded in the
   DD7 notes and still true. A worker continuation that raises must therefore
   install its own handler, or run where the pump's own containment covers it —
   which the queue provides.

## The shape

```
    UI thread                          isolate
    ---------                          -------
    command invoked
      Worker do: #task with: arg
      then: [ :result | ... ]   ──────► task runs, no UI, no shared state
      (returns immediately)
    pump keeps running                      │
    ...                                     │ result copied back
    reply arrives ◄─────────────────────────┘
      UiSession postAction: [ block value: result ]
    ...
    next pump drains it
      the block runs HERE, on the UI thread
      it may touch the ValueModel, and the
      model's #valueChanged reaches the views
```

The continuation updates a **`ValueModel`**, never a view directly. That is
what makes the worker path indistinguishable from any other edit as far as the
view side is concerned — the triad already propagates a model change to every
subscriber (`test/st_triad.dart`), so a worker result reaches the screen by the
same route a keystroke does.

## What must NOT happen

- **No UI call from the isolate.** No HWND crosses the boundary; a handle from
  another isolate is a number that names a window this isolate may not touch.
- **No Smalltalk object crosses.** Isolates copy. What goes over is data —
  numbers, strings, lists, maps — and what comes back is data. A result that
  needs to become an object is rebuilt on the UI side, by the continuation.
- **No blocking wait on the UI thread.** The pump must stay live; that is the
  observable the DD10 gate measures (a counter that keeps painting during a
  ~3-second command).

## `st/world/47_worker.mst` is INERT in this port

The world carries a `Worker` class from the MACVM lineage, with the whole
primary/worker doctrine already written up in its header comment. **It does not
work here**, and the reason is one this project has met before: its methods are
bodied with **numbered primitives** — 220 through 228, plus 250 — and in this
VM a numbered `<primitive: N>` pragma is *intent, not dispatch* (see
`docs/HOUSE_PRIMS.md`, and the DD8 `identityHash` defect that established it).
Every one of those methods compiles to `^self`.

So it is not a starting point to wire up; it is a **specification to
reimplement against Dart isolates**. Its doctrine — copy-passing, no shared
state, no identity across heaps, replies as correlation-id-matched
continuations, worker death delivered as an ordinary message — transfers
wholesale. Only the transport changes.

Nothing should be loaded from it until that is done, and nothing currently is.

## The build order when it lands

1. A Dart-side task registry: named top-level functions an isolate can be
   spawned onto (`Isolate.spawn` needs a top-level entry point).
2. `stWorkerSubmit(task, arg, id)` — spawn, run, reply on a `ReceivePort`.
3. On reply, the main isolate calls `UiSession completeWork: id with: result`,
   which looks the continuation block up by id and **posts** it. The lookup
   lives in Smalltalk so the block never leaves the image.
4. `Worker do:with:then:` as the Smalltalk face of it.
5. The gate: a ~3-second task with a timer-driven paint counter that must keep
   advancing throughout — the pump provably live, not merely assumed to be.

Step 3 is the one that carries the doctrine. Calling the block directly from
the reply handler would work, look correct, and violate every reason above.
