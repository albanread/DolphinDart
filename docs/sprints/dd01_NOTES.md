# DD1 — scope surgery: NOTES

**Status: DONE.** 2026-08-15. Gate green on arm64 and x64.

## The split

| Tree | Files | What |
|---|---|---|
| `st/world` | **73** (was 97) | the default load — kernel, collections, numerics, streams, reflection, io/net, workers, supervisor |
| `st/ext/gamepane` | **10** | the games-with-sound extension (kept per scope rule #4) |
| `st/attic/ide` | **14** | the seed's Cocoa/IDE surface — kept for reference, never loaded |

Boot: 73 files → **137 classes**; the extension adds 10 files → **11 classes**.

## The census (what actually drove the split)

Class definitions were extracted per file (267 `subclass:` sites), then every
cross-group reference was checked **with ST comments and string literals
stripped** — which turned out to be the whole trick. Raw grep reported six
kept-files depending on the groups being moved; four were false:

| Apparent dependency | Reality |
|---|---|
| `34_tools.mst` → `NewClass` | inside an HTML string literal (a doc example) |
| `49a_cocoafile.mst` → `CocoaHelp` | a comment |
| `35_mandelbrot.mst` → `MandelZoom` | a comment |
| `47_worker.mst` → `GamePane` | a comment ("the GamePane posture") |
| `48_parallelmandel.mst` → `GamePane new` | **real** — moved to the extension |
| `61b_fftscope.mst` → `GamePane new`, `GamePane keyLeft` | **real** — moved to the extension |

After the moves the three trees have **zero code-level cross-references** in
either direction (verified in both directions, not just outward).

Had the census been run on raw text, `48_parallelmandel` and `61b_fftscope`
would have stayed in the kernel and broken the default world's boot, while four
files would have been moved for no reason.

## Layered worlds

The world is now a **layer stack**, not a directory. `st_world_run.dart` and
`st_battery.dart` take a semicolon-separated list, each directory sorted
internally and applied in order:

```bash
dart.exe test\st_world_run.dart "st\world;st\ext\gamepane"
```

This is the mechanism DD8's `dolphin_compat` and DD9+'s translated MVP corpus
will arrive through, so it is worth having early and worth keeping simple.

## The extension proof

The gate asked for a GamePane demo still running with sound. Delivered at three
levels, weakest to strongest:

1. **Headless:** layered world boots (83 files); `Sound coin play`,
   `Sound zap play` and `Tune fromAbc: 'C C G G'` all answer without error.
   (`play` is a documented no-op headless — the call chain is what this proves.)
2. **Wiring:** a hosted capture pass installs `GamePane >> primDefineSprite:rows:`,
   `primSpriteColor:index:r:g:b:`, `primMoveSprite:x:y:`, **`Sound >> primPlay:`**
   and **`Tune >> primPlayTune:`**, and reports
   `ST-EXT gamepane: imported 11 classes from 10 files`.
3. **Pixels:** `SNAP: tab_game OK` — COIN DASH rendering live in the D3D11 pane,
   with all five Smalltalk games from the extension enumerated in the game list
   (Breakout, Worms, MandelZoom, MandelVM, FFT). Dimensions prove framing; only
   a pixel proves content, and this is the pixel.

*Method note:* the first capture pass returned `ERR:window has no client area`
for every snapshot because the host was launched minimized. A minimized window
has no client area to `PrintWindow`. Re-run un-minimized, all captures OK. Worth
remembering for DD7/DD9, whose gates are all snapshot-based.

## Host status

`dartui.exe` is now **deprecated and documented as such** in
`port-win/CMakeLists.txt`: retained solely as the interim GamePane host until
DD13 re-homes the pane into an MVP `ShellView`. Nothing new may depend on it.

Worth recording plainly: `dart` and `dartui` link **the same libraries**,
including `dart_win32`; they differ only in `main.cc`'s `DART_UI_HOST`. So "the
IDE" is a Dart script (`test/workspace.dart`) plus an entry point — there was no
IDE C++ to excise from `dart.exe`, and the brief's "measure the target's source
list" item resolves to that fact. `dart_win32` staying linked is not scope creep;
it is the foundation DD6/DD7 build the Windows prims and wndproc door on.

## Also fixed

**Generated output was escaping the work area.** A capture pass wrote
`C:\projects\shots\*.png` — `workspace.dart` derived its output root as the
repo's parent, the same wrong assumption DD0 fixed in `extract.py` and
`build.ps1`. It now honours `WINDART_WORKROOT` first. The stray directory was
removed.

## Carried forward

- `st/attic/ide` is reference material for DD7/DD8: it is the only worked example
  in this tree of Smalltalk driving a live native UI across the ST↔host seam.
  `63_cocoaui_stub.mst` documents that seam explicitly.
- `demos/galaxigans.mst` still loads separately in the host (after the world and
  the extension). It is a game, not kernel; folding it into `st/ext/gamepane`
  is a tidy-up DD13 can take.
- The three loose suites in `st/test` (`primitive_probes`, `type_conformance`,
  `galaxigans_smoke`) remain unwired — DD2 picks up the first two.
