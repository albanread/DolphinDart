# DD7 — the wndproc door + re-entry spike: NOTES

**Status: SPIKE PASSED, door landed.** 2026-08-15. Identical on arm64 and x64.

## The measurement

Every recursion below goes through a **real message-only window and a real
`SendMessageW`** — the production re-entry path, not a test double. That
distinction is the whole point: WINVM's G0 proved nesting with Rust doubles that
called the handle directly, and the production seam (crossing the FFI stub) was
still unbuilt when the work stopped.

| Probe | Result | Reading |
|---|---|---|
| depth-5 answer | **104** | 100 at the base, +1 per level × 4 |
| depth-5 trace | **(5 4 3 2 1)** | all five image entries ran |
| max depth reached | **5** | five genuinely nested entries, measured in C++ |
| depth unwound | **0** | the stack came back to zero |
| dnu@3: answer | **2** | the depth-3 entry answered its default; 4 and 5 completed normally |
| dnu@3: trace | **(5 4 3)** | levels 5 and 4 ran, 3 raised, 2 and 1 correctly never happened |
| dnu@3: contained | **1** | exactly one containment — not a cascade |
| door alive after faults | **102** | the pump survives; the next message dispatches normally |

## The finding that was NOT predicted

**A raise inside a nested entry is contained AT THE DOOR — it does not
propagate to an enclosing Smalltalk handler across the native frames.**

`guardedAt2` wraps the whole send in `on: Error do: [ #caught ]` and signals at
depth 2. That handler **does not fire**: the depth-2 entry answers its default
(0), the entries above complete, and the answer is `0+1+1 = 2`.

This is correct — Windows owns that stack and there is no Smalltalk exception it
could carry across it — but it is a real semantic the MVP layer has to know: **a
handler installed outside a door entry cannot catch a raise from inside one.**
The test now asserts this behaviour explicitly rather than the `#caught` I had
assumed when writing it.

## Why the door is a separate file from the view-server

`win_view.h` documents that the existing view-server's callback dispatcher
**skips re-entrant dispatch**, because *"re-entering Dart (`Dart_EnterScope`)
while Apply holds Dart handles corrupts the scope stack"*.

Read carefully, that is a constraint on **holding handles across a re-entry**,
not on nesting as such. `ViewServer::Apply` is mid-materialize with live handles
when a control fires `EN_CHANGE` synchronously; the door is entered from the OS
message pump with no enclosing native frame of ours holding anything. So the
door can nest where Apply cannot, and keeping it in `win_mvp.cpp` keeps that
distinction visible instead of encoding it as a flag someone later flips.

The discipline is one line, stated at the top of the file: **enter a scope,
invoke, exit the scope, and hold no Dart handle across the invoke.**

That reading is what the spike tested, and it held to depth 5 with allocation at
every level.

## Containment, deliberately

The WndProc drops a `Dart_IsError` result rather than calling
`Dart_PropagateError`, which would unwind through the WndProc's own C++ frame
and out through Windows' dispatch. The count (`mvpStats` element 3) exists so
that *contained* can never be mistaken for *did not happen* — the dnu probe
asserts it is exactly 1.

## What exists now

- `port-win/dart_win32/win_mvp.cpp` — window class, shared WndProc, the image
  funnel, and the depth/containment instrument.
- Natives `ST_mvp{RegisterDispatch,CreateWindow,DestroyWindow,Send,Stats,ResetStats}`,
  a `Win32 mvp*` prelude surface, and a single Dart closure funnel that forwards
  to `MvpDoor class >> wndProc:with:` — the same one-funnel shape the
  view-server uses.
- `st/test/ffi/mvp_door_spike.mst` + `test/st_door.dart`, pinned.

## The visible window (second half, landed)

A real top-level window with a real BUTTON child, carrying real Win32 messages
into the image:

| Probe | Result |
|---|---|
| window opens, `ShowWindow` paints | yes |
| live window: click delivered | **1** (a delta, not a raw count) |
| live window: paint delivered | yes |
| **paint fault contained** | `ValidateRect` backstop fired |
| **pump does not spin after a paint fault** | budget not exhausted |
| window survives the paint fault | yes |
| **stale window: no paint delivered** | **0** |
| **stale window: no click delivered** | **0** |
| destroys cleanly | yes |

**The `ValidateRect` backstop** (prior-art G-b) is the one that would otherwise
be found in production: if a paint handler raises, the update region is still
invalid, Windows re-posts `WM_PAINT` immediately, and the pump burns 100% CPU
forever. `EndPaint` only validates the region `BeginPaint` was given, so the
backstop validates the whole window — a partially-painted failure cannot re-arm
itself. The test bounds the pump with a budget so this fails rather than hangs.

**The generation guard** (prior-art G-i) stamps each window with the generation
that made it; after a bump, a stale window's messages never reach the image. A
world reload leaves real HWNDs alive whose image-side owners are gone.

## Two mistakes worth recording

**1. The channel was overloaded onto the payload.** Routing the funnel on
`wParam` meant the spike's depth-3 recursion probe was read as a `WM_DESTROY`.
Channel and payload are now separate arguments. The test *passed* while this was
broken, because the probe asserted a raw value with no expectation.

**2. Three assertions proved nothing.** `stale window stops dispatching` was
literally a tautology (`x = (y - y + x)`), and the click probes asserted a raw
counter that reads the same whether the guard works or not. Replaced with
before/after **deltas**, and paired with live-window probes so the guard is
proven by contrast: live delivers 1, stale delivers 0. This is the exact trap
the sprint briefs warn about — "passes numerically but wasn't observed" — caught
here in my own test.

## Still open

- **Posted-action queue + idle hook** — the "run this on the UI thread" path.
- **The storm-message probe**: measure `WM_MOUSEMOVE`/`WM_NCHITTEST` rates
  *before* routing them to the image. WINARM measured its door at ~154×
  `DefWindowProcW`, which is why an allowlist exists at all.
- **`TextOutW` from the paint handler** — the door carries `WM_PAINT` and hands
  the image its HDC; drawing through it is DD9's `Graphics.Canvas` work.
