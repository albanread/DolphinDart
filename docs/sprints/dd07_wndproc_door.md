# DD7 — The wndproc door + the re-entry spike `M/L`

**Objective:** Windows calls Smalltalk. A registered class + shared wndproc in
the natives layer reflects every message synchronously into the image, sound
to nesting depth — the seam WINVM spent G0 on. Here the bet (DOLPHIN_PORT §2)
is that the Dart embedder API makes this cheap; **this sprint's first
deliverable is the measurement, not the belief.**

**Read first:** prior-art `g0_reentrant_entries.md` (the *lesson*: prove depth
with gates before anything leans on it), prior-art V3/G1 (the skeleton +
torture gates — transfer as gates), `port-win/dart_win32/` view-server (the
existing native→VM event path — the precedent to imitate or consciously
depart from), Dart embedder docs in the quarry (`Dart_Invoke`, error
propagation, scopes).

## Work

1. **The spike (gate before build):** a native test hook that re-enters the
   image N deep — handler doit → native call → callback → nested doit — with,
   at each depth, an allocation (GC-eligible). Measure and record:
   - depth-5 nesting: five distinct values land, in LIFO order;
   - ST DNU at depth 3: depth-3 entry answers its default, depths 2/1
     continue and return their own values (containment, not unwind-to-top);
   - a native fault in nested marshalling: contained the same way;
   - an ST exception (DD4) signalled at depth 2 and handled at depth 2: outer
     entries unaffected;
   - what Dart's error propagation does across the native frames in each case
     (`Dart_PropagateError` unwinds through native scopes — where do C++
     destructors NOT run? Document the discipline this imposes on the wndproc
     trampoline's locals — the setjmp lesson's Dart-shaped cousin).
2. **The door** (`port-win/dart_win32/win_mvp.cc`, new — the view-server stays
   untouched as the interim gamepane host): `RegisterClassW` +
   the shared wndproc; hwnd→generation map (stale generation →
   `DefWindowProcW` — prior-art G-i); window↔object association via
   `lpParam`/`WM_NCCREATE` with the CBT hook as the flagged fallback
   (prior-art G-j — their doubt, our chance to simplify);
   **WM_PAINT backstop:** if the image-side paint handler faults, the native
   arm calls `ValidateRect` (prior-art G-b — the infinite-WM_PAINT storm);
   a message-only window + posted-action queue for "run this on the UI
   thread"; pump-empty idle hook.
3. **The spike world file** (`st/world/xx_uisession_spike.mst`, ~200 lines,
   hand-written house dialect — *not* Dolphin code, deleted in DD8): register
   class, create top-level window + native BUTTON child via DD6 bindings,
   `TextOutW` hello from a paint handler, click → Transcript, clean close.
4. TCL harness extension: drive + snapshot the spike window (the seed's
   harness already snapshots the host — reuse).

## Gate (the prior-art G1 tortures, verbatim, plus ours)

- Spike matrix from step 1 all green, **measured on arm64**, written up with
  numbers in `dd07_NOTES.md`.
- From the image: window + BUTTON child created; hello painted; click →
  Transcript round trip; clean close, registry empty.
- Window created from inside a `WM_CREATE` handler **5 levels deep**.
- A DNU in a handler: the pump survives, the next message dispatches
  normally, `ValidateRect` backstop proven by a paint-handler fault test.

## Traps

- `CreateWindowExW`/`SetWindowPos`/`DestroyWindow` **send synchronously** —
  the nesting is not exotic, it is the first `openMain`. (WINARM measured
  busy-depth 2 during open, 30 during a 10-cycle run.)
- The UI thread owns the pump AND the isolate entry — decide and document
  which thread the VM's UI isolate lives on; never `Dart_Invoke` from a
  second thread into it (isolate = one mutator).
- Storm messages (`WM_MOUSEMOVE`, `WM_NCHITTEST`, `WM_SETCURSOR`) must be
  measurable before they're routable: count-per-second probe first, then an
  allowlist for image dispatch, `DefWindowProcW` for the rest (WINARM's door
  cost 154× DefWindowProc — assume ours is nonzero too and measure it).
