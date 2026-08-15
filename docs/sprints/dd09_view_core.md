# DD9 — View core vertical slice (= milestone UI-2) `L`

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
