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
                                                  (DD5 keeps rolling through DD12)
```

DD4 (exceptions) gates DD10, not DD9. DD5 (prims) is a rolling campaign with
per-wave checkpoints. DD6 (Windows prims) gates DD7. Nothing before DD10 may
use `on:do:` in translated code (prior-art rule, carried).

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

**Corpus checkpoints** (carried from the prior-art calibration): DD9 ≈ 30–40
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
