# DolphinDart — working rules

Dolphin Smalltalk 8's language layer + Windows prims on the Dart 1.24.3 VM
(ARM64). Corpus: `C:\projects\dsfork`. Work tree: `C:\projects\dolphindart-work`.
Build: `powershell -File port-win/build.ps1 -Arch arm64 -Config Release
-WorkRoot C:/projects/dolphindart-work -Tree C:/projects/dolphindart-work/tree`.

**`-Config` DEFAULTS TO `Debug`, and the default is a trap.** `build.ps1`
declares `[string]$Config = "Debug"`, so the command with no `-Config` builds
an unoptimised Dart VM with assertions on — and it is hopelessly slow to
drive, which reads as "the port is slow" rather than "the build is a debug
build". Both configurations write to the SAME `build-$Arch` directory, so
whichever was built last is what the gates and demos run; there is no way to
tell from the binary's path which one you have. Check `build.log`, whose
first line records `[arm64/Release]` or `[arm64/Debug]`.
Tests: `python tools/gates.py [name]`. Status goes in `docs/JOURNAL.md`, not chat.

These rules exist because each one was paid for. They are ordered by how much
they cost.

## 1. Dolphin is a 32-BIT system — every byte number in the corpus is suspect

Assume any literal offset, struct size, or pointer-width assumption from the
corpus is WRONG here until re-derived from the generated `_OffsetOf_*` /
`sizeInBytes` constants (winkb-sourced, per target). These never raise: a wrong
offset reads the neighbouring field and the code keeps running. One such
literal (`nmNotify:` reading the code at 8 instead of 16) silently disabled
every WM_NOTIFY handler in the port.

- **Check:** `python tools/audit_offsets.py` after touching anything near a
  struct.
- **Fix in the translator** (`rewrite_nmhdr_code` is the model), not by
  overriding — the corpus's own logic stays intact that way.

## 1b. There is an ORACLE — ask it instead of inferring

A booted **Dolphin Professional 8.2.3** lives at `C:\projects\dolphin-oracle`
(isolated, so running it dirties no repo). `tools/oracle.py` evaluates
expressions in it:

    python tools/oracle.py "OS.MONITORINFOEXW byteSize" "16rFFFE lowPartSigned"

Reading the corpus and reasoning about what it must evaluate to has now
produced a confident WRONG conclusion twice — most recently a whole sitting
spent on `fromHandle:`, which was never broken; `printString` on its result
was. Where a question has a factual answer, ask.

- **Authoritative about SEMANTICS always** — what a method answers, whether a
  selector exists, what Dolphin's own flow permits (`parentView:` on an
  uncreated view is legal; `addSubView:` is what realizes it).
- **32-BIT** (`IntPtrMask` = `16rFFFFFFFF`, `HalfPtrBits` = 16), so for
  LAYOUT it is authoritative only where no pointer is involved — which is
  exactly the split `tools/conform_structs.py` automates. Run that after
  touching `genstructs.py`.
- It sees what winkb cannot: `#pragma pack` (LOOSE_ENDS 3.22).

## 2. Universal helpers — a method with one of these names may be DEAD

The IL builder rewrites ~51 selectors AT THE CALL SITE (`at:`, `size`, `do:`,
`value`, `printOn:`, `asInteger`, …). A send never reaches Smalltalk lookup; it
calls a Dart helper. A method you define under such a name loads silently and
runs only if the helper's slow path falls through to your class. Aliased
selectors (`asInteger`, `asString`, `asFloat`, `arcTan`) are dead on EVERY
receiver.

- **Check BEFORE defining any method:**
  `python tools/audit_helpers.py` — it parses the builder's table, so it is
  always current.
- **Fix in the helper's slow path** (cocoa.dart), by protocol probe, not class
  name. `Object>>value` written in Smalltalk blew the stack on every gate;
  `ExternalMemory>>asInteger` written in Smalltalk did nothing at all.

## 3. Silent nil is the house failure mode — hunt it, don't wait for it

An unbound global is nil. A class-side method on a bridged core name
(Array, String, Integer, …) may be unreachable. `initialize` /
`initializeClassConstants` are never called by a file-in loader unless emitted
as top-level statements. Each of these presents far from its cause, usually as
`doesNotUnderstand` on nil inside a contained handler.

- After adding corpus classes, probe the CONSTRUCTION path immediately
  (`Foo new`, `Foo defaultModel`) via `test/st_one.dart` — it needs no rebuild.
- A class must load AFTER its superclass; a same-name declaration carrying
  ivars REPLACES rather than reopens (this is why `CCITEM` lives in
  `st/prims/rt`, two layers before the structs that subclass it).

## 4. Handler errors are contained TWICE — instrument, don't read

An exception inside a WM_NOTIFY/wndproc handler is caught by the image's
`on: Error do:` and again by the door. No stack, no receiver ever reaches the
log; removing the image-side guard just moves the silence. The door prints the
first 8 contained errors — read them.

- **Localize by counters, not by reading code:** the `NotifyTrace bump:`
  pattern (st/mvp_compat) names the exact failing send in one run.
  `gdi_cls->183, gdi_addr->0` found in minutes what code-reading missed twice.

## 5. LOOK at the window — assertions cannot see pixels

`listItemCount` answered 33 while zero rows drew. Handles, class names and
counts all pass on an invisible failure. Gates pump once and exit, so any
window seen during a suite run is an unpainted frame — that is expected.

- **The camera:** `test/st_demo.dart` runs a real loop (`UiSession runFor:`)
  and captures via `Win32 mvpCapture:path:clientOnly:`; convert with
  `python tools/shot.py x.bmp` and READ the PNG.
- Any change intended to affect what draws is not done until a screenshot
  shows it.

## 6. Tooling hygiene (self-inflicted, three times each)

- **Never edit source through bash heredocs** — `\n` in the payload corrupts
  the file. Use the Edit/Write tools for anything containing backslashes.
- **Never read an exit code through a pipe** — `cmd | tail; echo $?` reports
  tail's status. A Smart App Control block reports as "Segmentation fault"
  under git-bash; a loader error is not a crash.
- `st/mvp/*` and `st/prims/*` (except `rt/`) are GENERATED — fix
  `tools/translate_mvp.py` / `tools/gen_prims.py` and regenerate. Hand-edits
  are silently destroyed by the next run.
- Narrow gates between changes; full `tools/gates.py` sweep before commit.

## 7. Work cadence — batch the discovery

Bugs here hide behind each other, but a rebuild costs minutes. Do not fix one
missing method per cycle:

1. Run the demo once; collect ALL door-contained errors and probe failures.
2. Fix the batch. Prefer one class-level fix (translator rewrite, helper,
   audit rule) over N instance fixes.
3. One rebuild, one gate run, one screenshot.

When a fix closes a bug CLASS, add or extend an audit under `tools/` so the
class stays closed.

## 8. Subagents — at most 2, task in / review out

Default is solo. When work splits cleanly (e.g. "ListView rows" vs "tree
expansion"), dispatch at most two agents, each with: this file, the exact task,
acceptance criteria (a named gate green AND a screenshot showing the change),
and the counters technique. Review their diff and their screenshot before
anything is committed. Never fan out exploratory reading — these bugs are
serial, and a swarm mostly duplicates the same dead end.
