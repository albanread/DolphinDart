# Prior art: WINVM's Dolphin port corpus (imported verbatim, 2026-08-15)

Five documents copied byte-for-byte from `C:\projects\WINVM` (branch
`windows-port`, the x64 Rust VM), where the first Dolphin-port attempt ran
2026-07-22 → 2026-08-10 and stopped at sprint G0 step 2 of 4 — VM substrate
only, zero Dolphin code translated. They are imported as **reference, not plan
of record**: the plan of record for this repo is [`../../../DOLPHIN_PORT.md`](../../../DOLPHIN_PORT.md)
and [`../../../DOLPHIN_SPRINTS.md`](../../../DOLPHIN_SPRINTS.md), which say per
document what still binds here and what is superseded by the Dart-VM substrate.

| File | What it is | Standing here |
|---|---|---|
| `dolphin_ui_porting.md` | The design of record for Dolphin MVP → WINVM, grounded in a file-level review of both trees | **§0–§3 (corpus audit, licence, architecture review of Dolphin's GUI) fully stand** — they describe Dolphin, not the target VM. §4–§5 (WINVM specifics) are superseded. Path refs to `e:\dsfork` are now `C:\projects\dsfork`. |
| `dolphin_ui_sprints.md` | V-specs V1–V8, gap register G-a…G-n, sprint ladder G0–G8 | Gap register and decision log largely stand; V1 (re-entrant embed entries) is Rust-substrate-specific and does **not** transfer — the Dart embedder API is designed for host→VM entry. V2 (W5 exceptions) maps to DD3. V4 (UTF-16) mostly dissolves (Dart strings are UTF-16). G2's translator design transfers nearly whole. |
| `dolphin_win_prims.md` | All 215 Dolphin primitives / 424 call sites, cross-referenced against the C++ VM's 256-entry dispatch table, with an untouched Impl/Test worksheet | **Transfers whole** — it describes the Dolphin image source. Becomes DD4's live worksheet. Caution: Dolphin's numbering is NOT this VM's numbering (house: 1=`+`; Dolphin: 1=`^self`) — see the mapping-table decision in `DOLPHIN_PORT.md`. |
| `g0_reentrant_entries.md` | WINVM's G0 spec + as-landed notes (LIFO recovery stack) | Mechanism does not transfer (sigsetjmp/VEH machinery). The *lesson* does: prove nested host→VM entry to depth, with gates, before any GUI work leans on it. |
| `dev_control_channel.md` | TCL-over-net drive-and-snapshot harness spec | Transfers in spirit; this repo's seed already has a working TCL harness (`tcl/`) driving the Windows host. |

The Dolphin source corpus itself lives at **`C:\projects\dsfork`** (clone of
github.com/albanread/dsfork, verified against `dolphin_ui_porting.md` §2 on
2026-08-15: MVP is byte-identical to upstream D8). Binding scope rules for how
this repo may use it are in `DOLPHIN_PORT.md` §1 — in one line: **the fork's
C++ VM does not work and is reading material only; we port the Smalltalk
language layer and the Windows prims, never the bytecode interpreter.**
