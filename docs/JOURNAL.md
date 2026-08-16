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

## The bad-input path — DD4's exceptions in anger

`st_dolphinapp` now drives Dolphin's own `updateModel`, which carries the
whole policy:

```smalltalk
[self model value: (self typeconverter convertFromRightToLeft: self displayValue)]
    on: InvalidFormat
    do: [:e | e beep.
              self value: self typeconverter leftNullValue; refreshContents]
```

The probe catches NOTHING. Wrapping it would replace Dolphin's policy with
the test's, and the policy is what is under test.

Three things had to be right for it to run at all, and each was silent:

1. **The converter must be installed BEFORE the presenter connects.**
   Connecting pushes the model's value through the view's converter
   immediately; installing it afterwards re-ran that path against whatever
   text the control held and wrote nil back into the model. The app started
   empty and every later assertion blamed the model.

2. **`setWindowText:` does not set the modify flag.** `TextEdit>>updateModel`
   opens with `self isTextModified ifFalse: [^self]` — Windows' EM_GETMODIFY,
   which real typing sets and a programmatic WM_SETTEXT deliberately does not.
   Without `isTextModified: true` the update returned immediately: the probe
   looked like it had typed and nothing had happened.

3. **`Boolean>>asParameter`.** `isTextModified:` sends
   `aBoolean asParameter` and `Object>>asParameter` answers self, so a Boolean
   reached the FFI floor and was refused. Added Dolphin's own method AND made
   the floor accept true/false as 1/0 — the mirror of `#b`, exactly as nil is
   the mirror of `#h`: a BOOL-returning call ANSWERS a Boolean, so Booleans
   are values the floor produces and must take back.

Plus `Exception>>beep` — the audible half, and not decoration: it is the only
feedback a user gets that what they typed was rejected.

**21/21.** DD10's acceptance items are now all covered on Dolphin's own
classes: two fields one model, converters and the bad-input revert, commands
with `queryCommand:` enablement, menus, a worker-backed long command, and
accelerators via `UI.AcceleratorTable`.

**Still owed for DD10: a VISIBLE shell, and the first attempt did not count.**

`demos/dolphin_app.dart` puts a window on screen with a menu and two fields
attached, and that is all it proves. Judged as a demo it is not interesting:
it has no real event loop of its own beyond a `UiSession pump` slice in a
Dart `while`, nothing was driven through it by hand, and a screenshot of a
window is not evidence that anything in it works. Keeping it as "done" would
have been the same self-deception this project keeps writing gates to avoid.

The demo file stays — it is a harness worth having — but **the item is still
open**, and what it actually needs is: a shell that owns its own message loop,
keyboard input reaching a control, a menu opened and clicked by a person, and
the accelerator firing. None of that is shown yet.
