# DD1 — Scope surgery: IDE out, GamePane stays `M`

**Objective:** the default world and default build carry no IDE surface; the
GamePane + XAudio2 stack survives as the games extension and is proven still
green. (Owner rules #4: dartui IDE not needed; GamePane kept, with sound.)

**Read first:** `st/PROVENANCE.md` (which world files exist and why),
`st/world/` file headers 43–84, `port-win/CMakeLists.txt` (targets),
`test/workspace.dart` (what only the IDE uses), `DOLPHIN_PORT.md` §1.4.

## Work

1. **Census before surgery.** For each candidate world file, grep who sends
   into it. Candidates OUT (IDE/cocoa-UI): `50_cocoapad`, `60_editor`,
   `63_cocoaui_stub`, `64_cocoaui`, `65_cocoadelegate`, `66_cocoabrowser`,
   `67_cocoafind`, `68_cocoaeditor`, `69_cocoaoutliner`, `70_cocoacanvas`,
   `71_cocoahelp`, `72_cocoabrowser2`, `73_cocoadebugger`, `81_appui`.
   Candidates KEEP: kernel 01–42, `43_gamepane`, games `44/45/46/48a`,
   workers `47/48`, host hooks `49/49a` (**verify** — gamepane/io may depend
   on them), `51–59`, io/net `61*/62*`, `74_supervisor`, `75_dns`,
   `76–79/82`, gamepane wiring `80/83/84`. The census, not this list, is
   authoritative — record deltas.
2. **Split the world tree:** `st/world/` = default load (kernel + io +
   supervisor); `st/ext/gamepane/` = the gamepane package + game demos +
   whatever `49*` hooks the census pins to it; `st/attic/ide/` = the IDE
   layers (kept in-tree, never loaded by default). Update the loader
   invocation/`WINDART_ST_WORLD` docs accordingly.
3. **Build targets:** `dart.exe` stays the default target. `dartui.exe`
   remains buildable but is demoted to *interim GamePane host* (DD13 re-homes
   GamePane into the MVP shell) — mark it deprecated in `port-win/CMakeLists`
   comments and `docs/TOOLCHAIN.md`; nothing new may depend on it.
4. Re-run the DD0 gate on the shrunken default world; run one gamepane demo
   with sound via the TCL harness and capture a snapshot + an audible-path
   assertion (the XAudio2 native invoked without error is acceptable proof).
5. `dd01_NOTES.md`: files moved, census table, anything that resisted.

## Out of scope

Deleting anything (moves only); touching the C++ front-end; starting the
extension's MVP re-home (that is DD13).

## Gate

- Default world boots green with the DD0 functional checks; loaded-file list
  contains no attic/IDE file.
- GamePane demo runs from `st/ext/gamepane` with sound, TCL-driven, snapshot
  captured.
- `dart.exe` builds without the IDE sources in its link (measure the target's
  source list, not just "it links").

## Traps

- `49_cocoa.mst` is host-hooks, not IDE — PROVENANCE says its primitives route
  through pluggable Dart hooks and `80_gamepane_wiring`/`63_cocoaui_stub`
  needed 16 shims. Do not attic it without the census proving nothing kept
  depends on it.
- The shots/ evidence convention: dimensions prove framing, only a pixel
  proves content — snapshot the gamepane, don't just assert the window size.
