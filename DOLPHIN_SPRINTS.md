# DolphinDart — the sprint ladder

**Plan of record:** [DOLPHIN_PORT.md](DOLPHIN_PORT.md). Per-sprint detail for
implementing agents: [docs/sprints/](docs/sprints/) — one `ddNN_*.md` per
sprint; an agent takes exactly one sprint, reads its detail doc first, and the
sprint is done only when its **gate** is green on top of everything already
green. House conventions: every sprint ends green; sizing S (a focused day or
two) / M (up to a week) / L (1–2 weeks); no `#[ignore]`-style gating of
failures without a written reason; narrow filtered tests between changes, one
full release-mode sweep at sprint end ([test cadence](docs/prior_art/winvm/README.md)).

**Dependency spine:**

```
DD0 → DD1 → DD2 → DD3 → { DD4, DD5, DD6 in parallel } → DD7 → DD8 → DD9 → DD10 → DD11 → DD12 → DD13
                                                  (DD5 absorbed into DD3's translator — see Status)
```

DD4 (exceptions) gates DD10, not DD9. DD5 (prims) is a rolling campaign with
per-wave checkpoints. DD6 (Windows prims) gates DD7. Nothing before DD10 may
use `on:do:` in translated code (prior-art rule, carried).

## Status (updated 2026-08-15, after the DD9 gate went green)

| # | Status | Outcome in one line |
|---|---|---|
| DD0 | ✅ DONE | Both arches build from the new home; battery vendored — **and found 4 inherited defects, all fixed**; baseline 12 suites / 566 assertions / 0 |
| DD1 | ✅ DONE | World split 73/10/14 (kernel / gamepane ext / IDE attic); worlds became **layer stacks**; GamePane proven to pixels |
| DD2 | ✅ DONE | **D157 is the only primitive number in the MVP tree**; zero namespace collisions; `<virtual`/`<overlap` are pragma *modifiers* |
| DD3+3b | ✅ DONE | `dolphin2mst`: 211 classes / 5,441 methods, byte-stable; translated `Rectangle` **runs** on our kernel; `.pax` loose methods + pools ingested |
| DD4 | ✅ DONE | Resumability settled by measurement (0 MVP `resume:` sites → v1 non-resumable, refuses loudly); `Notification` + resumable-default; DNU → catchable MNU on both paths |
| DD5 | ✅ ABSORBED | The 215-row campaign evaporated (DD2); D157 lowering lives in the translator; nothing left to do |
| DD6 (a/b/c) | ✅ DONE | FFI floor with **no assembly** (arity-cast); **1,126 prims generated from the corpus** + tiered harness (1,007/1,104 resolve); marshalling runtime; **148 structs, offsets from winkb** |
| DD7 | ✅ DONE | Door proven to depth 5 through real `SendMessageW`; visible window with real WM_PAINT/WM_COMMAND; `ValidateRect` backstop; generation guard — all falsifiably tested |
| DD8 | ✅ DONE | Compat kernel: events, `UiSession`, Model/ValueModel, SearchPolicy, GUID, properties |
| DD9 | ✅ DONE | **Gate green.** Dolphin's `BorderLayout` arranges real Win32 windows; live WM_SIZE relayout via Dolphin's own `buildMessageMap`; paint through the HDC proved by pixel readback; focus/tab; clean destroy. Class-side `super` implemented in the front-end. Carried forward: `Graphics.Canvas` wave, supervisor respawn demo |
| DD10 | 🚧 IN PROGRESS | `UI.View` OWNS ITS WINDOW (Dolphin's own create path, end to end); shell-gate rebuild partial. Blocker root-caused: NULL handle returns are 0 here, nil in Dolphin — `subViewsDo:`'s `[child isNil] whileFalse:` never ends. NEXT: a `#h` handle-return convention in the floor, then child views → retire WinView → control subclassing → `UI.TextEdit`/`TextPresenter` → acceptance app. See the brief's STATUS 2 block |
| DD11–DD13 | ⬜ PENDING | DD11 needs per-class message maps; DD12 (goal gate) hard-depends on DD10's per-window routing |

Two standing corrections the ladder should be read with:

1. **Numbered `<primitive: N>` pragmas are intent, not dispatch** (DD8 finding,
   recorded in `docs/HOUSE_PRIMS.md`): the front-end special-cases *selectors*;
   a bare numbered-primitive body compiles to `^self`. Anything gated on "the
   primitive number works" is really gated on the selector being handled.
2. **The external-call story is `st/prims/`, not translator-emitted pragmas.**
   The generated libraries + structs + marshalling runtime are the binding
   surface; the translator's job is to *route sends to them* (DD9 brief).

| # | Sprint | Size | Gate (one line — the detail doc is authoritative) |
|---|---|---|---|
| DD0 | Toolchain + baseline from the new home | S | Both arches build from `C:\projects\DolphinDart` against the external quarry; headless world boot + PROVENANCE functional checks green; baseline counts recorded |
| DD1 | Scope surgery: IDE out, GamePane stays | M | Default world/build carries no IDE/cocoa-UI surface; world boots green; a GamePane demo still runs with sound (the extension proof) |
| DD2 | Conformity census + prim map | M | `docs/DIALECT_GAPS.md` final, `docs/PRIM_MAP.md` v1 (all 215 rows dispositioned), MVP-closure census numbers for processes/weak/ansi/become |
| DD3 | `dolphin2mst` translator core | L | Translated Basic Geometry green in the world; golden-file tests per rewrite class; re-run over the corpus byte-stable; `.pax` loose methods + pools ingested |
| DD4 | Exceptions: ANSI hierarchy on `stOnDo`/`stEnsure` | M/L | Resumability decision spiked + recorded; translated ExceptionTest/ZeroDivideTest subset green; DNU catchable; unhandled path unchanged |
| DD5 | Primitive campaign (rolling) | L | Worksheet rows ticked with per-prim + fallback tests; each wave's dependent translated tests green |
| DD6 | Windows-prims floor: `<stdcall:>` → natives | L | From the image: `UserLibrary getClientRect:` fills a live RECT; last-error surfaced; winkb-generated bindings for the MVP-base subset; struct/UTF-16 marshalling proven |
| DD7 | The wndproc door + re-entry spike | M/L | Depth-5 nested entry, DNU-in-handler, fault-in-marshalling all contained (prior-art torture gates); click → Transcript round trip; WM_PAINT backstop |
| DD8 | Compat kernel (`world/dolphin_compat/`) | M | Event-system semantics suite green (written before porting consumers); UiSession drives the DD7 spike windows; spike code deleted |
| DD9 | View core vertical slice (= UI-2) | L | Code-built shell: caption, BorderLayout, live resize relayout, paint via Canvas, focus/tab, clean destroy with registry hygiene |
| DD10 | MVP triad (= UI-3; needs DD4) | L | Real MVP app: two TextPresenters + converter, `InvalidFormat` beep-and-revert, `queryCommand:` menus, accelerator, non-freezing long command via isolate worker |
| DD11 | Common controls (= UI-4) | L | Two-pane class browser (tree + list + text) over live reflection data |
| DD12 | Dialogs & polish (= UI-5) — **THE GOAL GATE** | M | Modal prompter with buffered OK/Cancel from the browser; two stacked modals; file-open round trip; clipboard paste — *the Dolphin MVP GUI running* |
| DD13 | GamePane extension in the MVP world | M | A game runs **inside a Dolphin MVP shell** with XAudio2 sound, TCL-driven, snapshot-proven |

**Backlog (pull-based, after DD12/DD13):** weak refs + finalization (mourning
semantics mined from Dolphin's C++, on Dart weak persistent handles); the
image-format decision (owner TBD — options in DOLPHIN_PORT.md §1.3, decide end
of DD10); ListView virtual mode/custom draw; per-monitor DPI; themes;
RichEdit; drag-drop; COM story; generic `ST_ffiCall` Win64 trampoline if DD6
shipped generated natives first.

**Corpus checkpoints — deliberately undershot (recorded 2026-08-16).** The
bands below were calibrated for translating whole packages. The DD9/DD10 runs
settled a different strategy: translate ON DEMAND, cut each wave to what the
next gate exercises, and let the refusal report name what was left out. DD9
closed at 14 classes against a 30–40 band and DD10's model side at 27 total —
and every one of those classes is exercised by a gate, which the band never
guaranteed. The bands stay as a rough total-effort forecast for DD12's
150–200-class endpoint, not as per-sprint targets.

Original calibration: DD9 ≈ 30–40
translated classes · DD10 ≈ +60 · DD11 ≈ +40 · DD12 ≈ +30 — the 150–200-class
v1 band. DD3 and DD8 are the long poles before visible progress; DD0–DD2 are
small but gate everything.

**Standing rules for implementing agents**

1. Read your sprint's `docs/sprints/ddNN_*.md` **and** the prior-art documents
   it names before writing code. The prior art is reference; your detail doc
   says what stands.
2. The dsfork VM is never run and never trusted; semantics come from image
   source, `PrimitivesTable.cpp` reading, and our own tests.
3. Measured claims only: "it passes" means the command, the count, and the
   arch are written in the sprint notes. A gate that passes numerically but
   wasn't *observed* (screenshot/snapshot for GUI gates) is not passed —
   dimensions prove framing, only a pixel proves content.
4. Translator output is generated artifact: never hand-edit a generated `.mst`
   — fix the translator or add a patch-overlay entry, so corpus re-runs stay
   byte-stable.
5. Windows-only work carries no POSIX risk by construction (the front-end is
   shared, the natives are per-platform); do not gate shared-file behavior on
   `_WIN32` without a written reason.
6. Every sprint ends with its notes file (`docs/sprints/ddNN_NOTES.md`):
   what landed, measured numbers, surprises, and anything the next sprint
   inherits. The seed's `port-win/*_NOTES.md` files are the house exemplar.
