# Journal

Running log of what changed and why, newest last. Status lives HERE, not in
chat. `docs/LOOSE_ENDS.md` holds what is still owed; this holds what happened.

---

## Retiring the `WinView` adapter family

**Goal:** delete `WinView`, `WinControl`/`WinTextEdit`/`WinButton`/`WinLabel`,
`WinMenu`/`WinAccelerators` and `TextField` — the DD8/DD9 stand-ins that
answered Dolphin's view protocol over raw HWNDs before the real classes were
reachable.

**They cannot go one at a time.** `WinControl` is a `WinView` subclass and the
probes build on both, so the family is one commit.

### What depends on them, measured rather than assumed

Code references (mentions in the surviving gates are all COMMENTS):

| probe | uses | gate |
|---|---|---|
| `shell_probe.mst` | WinView | `st_shell` |
| `text_probe.mst` | WinView, WinTextEdit, TextField | `st_text` |
| `command_probe.mst` | WinMenu | `st_command` |
| `counter_app.mst` | all of them | `st_app` |

### The decision: MIGRATE, not delete

`docs/LOOSE_ENDS.md` said `st_shell` was "fully superseded by
`st_dolphinshell`". **That was wrong**, and checking the assertion lists
rather than trusting the note is what caught it. Each old gate carries
coverage its Dolphin-side successor does not:

- **`st_shell`** — FOCUS: focus moves between controls, and a relayout does
  not steal it. `st_dolphinshell` asserts arrangement only.
- **`st_text`** — TWO fields sharing ONE model, both directions. `st_textedit`
  has a single field.
- **`st_command`** — command ENABLEMENT (`queryCommand:` greying an item).
  `st_menu` asserts routing only.
- **`st_app`** — the acceptance app: bad-input revert, long command, worker.

Deleting them would have retired the scaffolding and quietly dropped four
distinct behaviours from the suite. So the probes move to Dolphin's own
classes and the assertions come with them.

### Done — the family is gone, 21/21

Deleted: `06_winview.mst`, `09_wincontrol.mst`, `10_winmenu.mst`,
`shell_probe.mst`, `text_probe.mst`, `command_probe.mst`, `counter_app.mst`,
and the four gates that drove them.

Coverage moved first, then the deletion:

| was | now | on |
|---|---|---|
| `st_shell` focus | `st_dolphinshell` | `UI.View setFocus/hasFocus` |
| `st_text` two fields one model | `st_textedit` | two `UI.TextEdit` + `TextPresenter` |
| `st_command` enablement | `st_menu` | `queryCommand:` + `CommandQuery` |
| `st_app` acceptance app | `st_dolphinapp` | `UI.ShellView`/`TextEdit`/`MenuBar` |

**The deletion broke the layout, and the reason is worth keeping.**
`06_winview.mst` also contained `Dictionary>>lookup:` — nothing to do with
the adapter, it just lived there because `WinView` and the `LayoutContext`
work were written at the same time. `LayoutContext` asks
`(placements lookup: aView)` on every pass, so with it gone the whole
BorderLayout arrangement silently reverted to the 100x100 creation default:
every view still laid out, none at the size it asked for.

**When deleting a scaffolding file, what it HOSTS is not what it is FOR.**
The gates caught it on the first sweep after the delete, which is the only
reason it is a footnote rather than an incident.

### What the migration cost, in substrate

Each of these was found by the app failing, not by inspection:

- `DesktopView` needed three more walk terminators — `nameOf:`,
  `ambientBackcolor`, `backcolor`. `View>>name` and `View>>actualBackcolor`
  both walk the parent chain to the desktop, and Dolphin's DesktopView ends
  both walks. Ours ended neither.
- `Color class >> initialize` was failing, so `Color default` was nil and
  every WM_ERASEBKGND raised. Behind it: `Graphics.RGB` untranslated
  (`Color>>asRGB` needs it), `asSortedArray:`/`asArrayCopy` missing, and
  `addClassVariable:` — the same dynamic-name shape as `addClassConstant:`,
  so the translator rewrite was widened to cover both.
- `Color`'s `Window`/`WindowText`/`Face3d` class variables are only ever READ
  in `Color.cls`; the system-colour package that assigns them is not in the
  wave. Supplied from `GetSysColor` so a themed desktop gets its real colour.
- `View>>onEraseRequired:` now answers nil — declining the message, which is
  Dolphin's own documented way to accept default window processing. It needs
  `Graphics.Canvas` (DD11). **Cost: a view's `backcolor` is not honoured when
  erasing.** Recorded in LOOSE_ENDS with the gate that will prove its
  retirement.
- A multi-statement `stRun` abandons the rest of the string on a raise, so
  `App create. App show. App build.` left `model` nil and every later
  assertion blamed the model. Setup sends are separate now.
