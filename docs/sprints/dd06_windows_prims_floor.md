# DD6 — The Windows-prims floor: `<stdcall:>` → natives `L`

> **OUTCOME (2026-08-15): DONE, differently than planned — see
> `dd06_NOTES.md` + `dd06c_NOTES.md`.** The generator-vs-trampoline choice
> below turned out to be false: `ST_ffiCall`'s Windows branch casts the
> resolved address to a function-pointer of the right ARITY and the C++
> compiler emits the call, correct on both arches with no `.asm` (~120 lines).
> The winkb DB validates rather than enumerates; `genprims.py` reads Dolphin's
> own pragmas. Kept below unedited as the record of what was planned.

**Objective:** translated Dolphin external methods call real Win32. This is
the sprint that builds what WINVM already had (a working FFI + winkb) and we
don't: **`ST_ffiCall` is stubbed on Windows** ("Win64 trampoline pending",
`st_natives.cc:14-18`); the working precedent is per-function C++ natives
(`port-win/dart_win32/`). Gates DD7.

> **DD2 correction (measured 2026-08-15): `<virtual:` and `<overlap>` are NOT
> standalone pragmas.** They are *modifiers inside* an external-call pragma:
> `<virtual stdcall: …>` (6 sites, 2 COM print-dialog callback classes) and
> `<overlap stdcall:/cdecl: …>` (13 sites, 3 files — `OS.KernelLibrary`,
> `OS.CRTLibraryNonBlocking`, `OS.UserLibrary`). The prior art and this brief's
> first draft both had the syntax wrong. Corpus demand: `<stdcall:` 667 sites in
> 29 files, `<cdecl:` 77 in 4 — so the generator's real workload is the stdcall
> surface, and `overlap` (async, non-blocking) is a v1 refusal, not a feature.

**Read first:** `st_natives.cc` (the POSIX dlsym floor + the stub),
`st_flow_graph_builder.cc:3058` (the existing `"primitive: FFI "` pragma —
the house binding form), `port-win/dart_win32/` (natives precedent),
prior-art V5 (coercions/sign/last-error — transfers), the `.pax` UserLibrary
loose methods (the demand side), and the winkb DB
(`C:\projects\windows_api\windows_api.db`: 18,271 functions, 66,708 struct
fields, typed params — schema self-describing; WINVM/WINARM validated it).

## The decision this sprint opens with

**Generated per-function natives vs finishing the generic Win64 trampoline.**
Recommendation baked into the plan (DOLPHIN_PORT §8): ship the *generator*
first — winkb gives typed signatures, so emitting a C++ native per needed
function is mechanical, debuggable, and arch-uniform; the generic trampoline
(x64 + arm64 asm, variadic/HFA cases) is backlog unless the generator proves
insufficient. Decide with a one-day cost probe, record in `dd06_NOTES.md`.

## Work

1. **Fix the binding form** the translator emits (`--ffi-form` flip in DD3):
   the house `"primitive: FFI …"` pragma extended (or a sibling pragma) to
   name library/function/ret/args in winkb terms. Document in
   `docs/DIALECT_GAPS.md` A11.
2. **The generator** (`tools/winkb_natives/`, Python + the DB): input = a
   function allowlist; output = (a) a `.cc` of natives (LoadLibrary/
   GetProcAddress once, typed marshalling, `GetLastError` captured
   immediately after the call into a TLS slot), (b) the world-side decl file.
   Idempotent, diff-stable.
3. **Struct model:** external bytes with generated typed accessors (Alien
   shape — sidesteps any moving-GC question by construction; audit what
   `11_bytearray`/`07a_largeint_bytes` already give, extend minimally).
   Core set: RECT, POINT, MSG, WNDCLASSW, PAINTSTRUCT, NMHDR, SCROLLINFO.
4. **Marshalling:** Dart strings are UTF-16 — `String` → `LPCWSTR` is a
   length+copy (pin/copy discipline documented); out-params via the struct
   model; HANDLE as opaque integer; BOOL sign discipline per prior-art V5.
5. **Last-error:** a prim reading the TLS-captured value; `KernelLibrary
   getLastError` conformance; the capture-immediately rule is load-bearing
   (any intervening native call clobbers it).
6. **First allowlist:** the MVP-base demand set — the 181 `.pax` UserLibrary
   loose methods + the GDILibrary/KernelLibrary subset the DD3 refusal
   reports name (measure, don't guess), landed in winkb-generated form.
7. Conformance micro-suite: `GetSystemMetrics`, `MessageBeep`,
   `GetClientRect` into a RECT, `GetLastError` after a forced failure
   (`CreateFileW` on an invalid path), a UTF-16 round trip
   (`GetWindowTextW` on a created window — may defer to DD7 if no window
   exists yet; note it).

## Gate

- From the image, headless: `UserLibrary getClientRect:` fills a live RECT
  (values sane for a real window or the desktop); `GetSystemMetrics` matches
  a C++-side check; forced-failure last-error surfaces the right code.
- Generator re-run is byte-stable; allowlist + generated files committed.
- Both arches: the natives build and the micro-suite passes on arm64 and x64.

## Traps

- **Never capture `GetLastError` after any intervening call** — including a
  Dart re-entry or an allocation that faults in a native.
- winkb's DB default path story: pass the path explicitly; never assume
  `E:\` (that was WINVM's machine).
- arm64 variadic ABI differs from x64 (variadics in registers on Windows
  AAPCS64) — the generator sidesteps this for fixed-arity Win32, but refuse
  variadic functions loudly rather than emitting wrong marshalling
  (`wsprintfW` is in UserLibrary — refusal is correct v1 behavior).
