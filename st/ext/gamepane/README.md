# `st/ext/gamepane` — the GamePane extension package

**The games-with-sound story for DolphinDart.** A Smalltalk package layered on
top of the default world (`st/world`): a Direct3D 11 pane with sprites, an
indexed/direct framebuffer, keyboard input, and XAudio2 sound, plus the games
built on it. Kept deliberately (project scope rule #4) while the rest of the
seed's UI surface went to `st/attic/ide` — the Dolphin MVP framework is the
application-GUI story, and this is the games story beside it.

## Contents (10 files, 11 classes)

| File | What |
|---|---|
| `43_gamepane.mst` | `GamePane`, `Sprite`, `Sound`, `Tune` — the package's API |
| `80_gamepane_wiring.mst` | binds the `stGp*` / `primPlay:` / `primPlayTune:` natives |
| `83_gamepane_direct.mst`, `84_gamepane_buffers.mst` | direct-framebuffer + buffer paths |
| `44_breakout.mst`, `48a_worms.mst`, `45_mandelzoom.mst`, `46_mandelvm.mst` | games/demos |
| `48_parallelmandel.mst` | isolate-parallel Mandelbrot driving the pane |
| `61b_fftscope.mst` | live FFT scope (`GamePane new`, `GamePane keyLeft/keyRight`) |

`48_parallelmandel` and `61b_fftscope` live here rather than in the kernel
because they issue real `GamePane` sends — the DD1 census separated genuine
sends from the many comment mentions.

## Loading it

The world is a **layer stack**, semicolon-separated:

```bash
C:\projects\dolphindart-work\build-arm64\dart.exe test\st_world_run.dart "st\world;st\ext\gamepane"
```

The package depends on the default world and nothing else; nothing in
`st/world` references any class defined here (verified by census with comments
and string literals stripped — DD1).

## What it needs from the host

The `stGp*` natives (sprites, framebuffer, key state), `primPlay:` (XAudio2
presets) and `primPlayTune:` (ABC-notation chiptunes), all provided by
`port-win/dart_win32` and shimmed through `port-win/dart_st/cocoa.dart`.
**Headless, `play` is a documented no-op** — the call chain succeeds and returns
self, but nothing is audible; a real device needs a hosted pane.

Shader bodies in this package are **Metal (MSL)**, a MACDART inheritance;
`GpShaderPane::compile` translates MSL→HLSL at compile time, so they run on
D3D11 unchanged.

## Host status

Until **DD13**, the pane is hosted by `dartui.exe` (the seed's IDE), which is
retained solely as the *interim GamePane host* and is otherwise deprecated —
nothing new may depend on it. DD13 re-homes the pane into a Dolphin MVP
`ShellView` as a `GamePaneView`, at which point the interim host can go.
