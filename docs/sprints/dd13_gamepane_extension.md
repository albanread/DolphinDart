# DD13 — The GamePane extension in the MVP world `M`

**Objective:** the owner's second commitment: **our own GamePane as a
supported extension for games, including sound** — re-homed from the interim
dartui host into the Dolphin MVP world, so a game runs inside an MVP shell
with XAudio2 audio.

**Read first:** `st/ext/gamepane/` (DD1's package: `43_gamepane`, wiring
`80/83/84`, the games), `port-win/dart_win32/` game engine + XAudio2 natives
(working today), `port-win/GAMEPANE_DESIGN.md` + `gamepane-design/`,
DD9's `ContainerView`/creation protocol (the host side).

## Work

1. **`GamePaneView`:** an MVP `View` subclass (hand-written in the extension
   package, house dialect — this is our code, not Dolphin's) whose HWND hosts
   the existing D3D11 swapchain: the engine renders into a child window
   created through the MVP creation protocol. The engine's window-handle
   seam is the only native change expected — it already renders into a
   window; parent it.
2. **Lifecycle:** create/size/destroy wired to MVP view events (`onResize` →
   swapchain resize — the engine has this path for the dartui tab); the
   generation-respawn arm covers the pane (kill mid-game → supervisor
   rebuilds the shell, pane included, engine reinitialized).
3. **Sound:** the XAudio2 natives exposed to the extension package as-is; a
   game sound effect fires from Smalltalk.
4. **The shader story carries:** world shader bodies are MSL, translated
   MSL→HLSL at compile (`GpShaderPane::compile`) — unchanged; note it in the
   extension README.
5. A game (`44_breakout` or the invaders demo) launched from an MVP **menu
   command** in a shell that also contains normal MVP controls (StatusBar
   showing score via the event system — the integration proof).
6. Retire the interim host: `dartui.exe` loses its "interim GamePane host"
   status (DD1's deprecation completes); it may be atticked from the default
   build entirely.
7. `st/ext/gamepane/README.md`: the extension's contract (what it needs from
   the world, what natives it binds, how sound is reached).

## Gate

- A game runs **inside a Dolphin MVP ShellView** — playable input, animating
  D3D11 output, a sound effect on a game event — TCL-driven, snapshot pair
  proving animation (two frames differ), the sound native's success asserted.
- Resize the shell: the pane resizes live without device loss (or recreates
  cleanly — either is a pass if deliberate and noted).
- The MVP StatusBar updates from game events (score) — GamePane and MVP
  share one event world.
- DD12's goal gate re-run green with the extension loaded (the extension
  must not destabilize the GUI it extends).

## Traps

- Two paint worlds share one thread: WM_PAINT (GDI, MVP) and the D3D present
  loop must not fight — the engine's existing present cadence with the pane
  excluded from GDI painting (`CS_OWNDC`-style discipline / paint-handler
  ValidateRect on the pane's HWND) — measure for flicker, don't assume.
- Unified-memory arm64 vs discrete x64 differences already handled by the
  engine (the ARM64 port's own sprint) — don't re-litigate; test both arches.
- Sound-path CI: no audio device on a headless session — the gate asserts
  the native call chain succeeds, not that a human heard it; say so in the
  test comment.
