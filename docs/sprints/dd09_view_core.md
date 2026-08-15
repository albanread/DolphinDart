# DD9 — View core vertical slice (= milestone UI-2) `L`

> ## DIRECTION UPDATE (2026-08-15) — the external-call story changed under this brief
>
> The brief below predates DD6b/c. What now exists and replaces its "DD5 W3 +
> DD6 allowlist extensions" plan:
>
> - **`st/prims/`** — 1,126 generated external methods across 37 library
>   classes (from Dolphin's own pragmas; regenerate with `genprims.py`), with
>   the tiered harness `test/st_prims.dart` (1,007/1,104 resolve, Tier B green).
> - **`st/prims/structs/`** — 148 struct classes with typed accessors, offsets
>   from winkb (`genstructs.py`); nested structs are typed views; sizes include
>   trailing padding.
> - **`st/prims/rt/`** — `ExternalMemory`/`Utf16Buffer`/`FFICoerce`; generated
>   wrappers coerce objects and free string temps under `ensure:`.
>
> So the translator does NOT emit FFI pragmas for the View wave; **translated
> sends must route to the generated library classes.** The corpus's dominant
> idiom (measured): **`User32 beginPaint: h lpPaint: ps` — a bare global name —
> 212 refs in MVP/Base**, vs `UserLibrary default …` at only 5. Two small
> pre-tasks before translation starts:
>
> 1. **Alias globals**: a tiny `st/prims/rt/02_aliases.mst` binding the global
>    names the corpus uses to the generated classes (`User32 :=
>    UserLibrary.` etc. — globals live on STGlobals; class names win reads, and
>    no class is named `User32`, so the read resolves to the global). Census the
>    exact alias list from the corpus first (`\w+32` style names + `Gdi32`,
>    `Kernel32`, `ComCtl32`…), don't guess it.
> 2. **`default` bridge**: add class-side `default [ ^self ]` to the generated
>    libraries (one line in `genprims.py`) for the 5 `XxxLibrary default` sends.
>
> Also landing here from DD7's open list: the **storm-message probe** (measure
> `WM_MOUSEMOVE`/`WM_NCHITTEST`/`WM_SIZE` rates BEFORE routing them to the
> image — WINARM measured its door at ~154× `DefWindowProcW`), because resize
> relayout is this sprint's gate and storms are where it bites; and **drawing
> through the WM_PAINT HDC** (the door already delivers it) — `TextOutW` first,
> then the translated `Graphics.Canvas` wave.
>
> Reminder from the DD7 notes: **a handler installed outside a door entry
> cannot catch a raise from inside one** — containment is at the door. View
> code that wants `on:do:` protection must install it INSIDE the entry.

**Objective:** the first translated MVP corpus wave: a real window tree built
from Dolphin's own `UI.View` code running on our substrate. The prior-art G4
sprint transfers as scope + gate, with one correction: **the canvas class is
`Graphics.Canvas`** (there is no `GdiCanvas` anywhere in the corpus —
verified 2026-08-15).

**Read first:** prior-art G4; the DD3 translator's refusal report over this
wave's class list (drives the DD5 W3 prim wave and any new DD6 allowlist
entries); `C:\projects\dsfork\...\MVP\Base\UI.View.cls` (the real thing —
5,000+ lines; the trim list below is what keeps this sprint L and not XL).

## The wave

Translated via DD3 (+ overlays, never hand-edits): `UI.View` (trimmed per
prior-art §5.6: dpi ^96, no drag-drop, no theme — the three funnels stay
stubbed), `ContainerView`, `ShellView`, the `CreateWindow*` creation
protocol, `BorderLayout` + `LayoutContext`, `PushButton`/`CheckBox`/
`StaticText`/`GroupBox`, `Graphics.Canvas` + `Pen`/`Brush`/`Font`/`Color`
basics, MessageMap dispatch, `WindowsEvent`/`PaintEvent`/`KeyEvent`/
`MouseEvent`. Supervisor respawn arm lands here (generation teardown demo —
kill the UI world mid-run, `UiSession startUp` rebuilds the shell; the seed's
`74_supervisor.mst` is the house precedent to lean on).

## Work

1. Translate the wave; burn down the refusal report (each refusal → translator
   fix, overlay entry, or a recorded trim).
2. DD5 W3 + DD6 allowlist extensions as the report demands (measured demand,
   not speculative bindings).
3. The acceptance shell (a hand-written doit, not Dolphin code): caption,
   BorderLayout with a label + two buttons, wired handlers.
4. TCL-driven proof with snapshots at each gate item.

## Gate (prior-art G4, carried)

- Code-built shell shows: caption, BorderLayout label + two buttons.
- **Live resize relayout** (drive a size change; snapshot before/after;
  layout positions assert, then pixels).
- WM_PAINT via `Graphics.Canvas` (a drawn rectangle/text visible in the
  snapshot).
- Focus/tab traversal between the buttons.
- Clean destroy with registry hygiene (empty registry assert).
- Kill the VM world mid-run → supervisor rebuilds the shell (generation
  respawn demo).
- Suite green vs baseline; corpus checkpoint recorded (~30–40 translated
  classes expected — count and record the real number).

## Traps

- `UI.View` is the biggest single translation target in the project — expect
  the translator to meet D8 constructs it hasn't seen (class-instance
  variables, aspect pragmas, resource refs). Refusals are the mechanism;
  a day of translator fixes here is normal, silence is not.
- Resize storms: `WM_SIZE` during a drag arrives per-tick — the DD7 storm
  probe + allowlist discipline applies before wiring `onResize` to layout
  (WINARM's lesson: commands queue, resizes coalesce — an event may not be
  dropped, a state may).
- Stub honestly: dpi ^96 and no-theme are *recorded* trims (prior-art §5.6),
  not silent ones — each stub carries a comment naming the backlog item.
