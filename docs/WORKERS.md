# Workers — the DolphinDart doctrine

**Status: BUILT and gated.** 2026-08-16, DD10. Gate `test/st_worker.dart`;
transport `test/worker_host.dart`; image side
`st/dolphin_compat/11_worker.mst`.

**Workers REPLACE Dolphin's processes/green threads — outright, as binding
scope rule 7/8 of `DOLPHIN_PORT.md` records.** Every `fork`/`forkAt:`/
`Process` site in the corpus maps to a `Worker do:with:then:` submission with
a posted continuation. There is no green-thread scheduler in this port and
there never will be one. The transport being Dart is the same statement as a
primitive being C++: an implementation substrate under Smalltalk, never a
second home for application logic.

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

## How it is built

`Worker do: #task with: arg then: aBlock` answers immediately. The block stays
in the image under an id; only the id, the task NAME and the argument travel.
The Dart host drains the submission queue (`Worker takePending`), spawns an
isolate per task, and on reply sends `Worker complete: id with: result` —
which **posts** the continuation rather than calling it.

**The run loop is Dart's, and that is forced rather than chosen.** `UiSession
pump` drains Win32 messages through a native call and returns; it never runs
Dart's event loop, so an isolate reply can only be delivered when control is
back in Dart. The loop is: pump a slice of Win32, `await`, repeat. The `await`
is load-bearing — without it no reply is ever delivered, however long the
Win32 pump spins.

**Failures cross as data.** An exception cannot leave an isolate, so a task
that raises replies with a message and the image rebuilds it as an `Error` —
posted through the same queue, so the continuation's own handler deals with it.

### What the gate proves

Three things, because the first two can be true while the third is not:

1. Submission returns immediately (measured at ~16ms, including the first
   `Isolate.spawn`).
2. The pump stays LIVE while the isolate burns CPU — 26 real WM_PAINTs
   counted during the run. The task burns rather than sleeps, deliberately: a
   sleeping isolate proves the reply arrives, not that the UI thread kept
   running while another thread was actually busy.
3. **The continuation is POSTED, not called.** Asserted by observing the gap:
   at the moment the reply is known to have arrived, the continuation has NOT
   run and exactly one action sits in the queue; the next pump runs it.
   Calling it inline from the reply handler would satisfy 1 and 2 and still
   be wrong.

### Known limitation

The task table is a top-level literal in `worker_host.dart`. A spawned isolate
re-runs the library from scratch with its own copy of every static, so a task
registered by calling a function from `main` is absent on the other side;
tasks must be visible at library-init time in BOTH isolates. Letting an
application supply its own means a place in that literal, or a generated one.
Recorded, not yet designed around.
