# `st/attic/ide` — the seed's IDE world layers (not loaded)

Fourteen `.mst` files from the WINDART seed's Cocoa/IDE surface: the workspace
pad, editor, class browsers, outliner, find, canvas, help, debugger, delegate
and app-UI layers.

**They are not part of DolphinDart's default world and are never loaded.** The
project's UI story is Dolphin's MVP framework (sprints DD7–DD12); this surface
would be a second, parallel GUI with no path into that.

They are **kept, not deleted**, because they are the only worked examples in
this tree of Smalltalk driving a live native UI through the ST↔host seam —
which is exactly what DD7's wndproc door and DD8's `UiSession` have to do, in
Win32 terms. Read them as reference, port nothing from them wholesale.

Nothing in `st/world` or `st/ext/gamepane` references any class defined here
(verified by census with comments and string literals stripped — DD1; the two
apparent hits, `NewClass` in `34_tools.mst` and `CocoaHelp` in
`49a_cocoafile.mst`, are a doc string and a comment).

If you want them loaded for study, they are just another layer:

```bash
dart.exe test\st_world_run.dart "st\world;st\attic\ide"
```

— though several expect Cocoa host services that do not exist on Windows, so
expect misses. `63_cocoaui_stub.mst` is the file that documents that seam.
