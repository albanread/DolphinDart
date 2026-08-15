# DD6 — the Windows prims floor: NOTES

**Status: FLOOR LANDED** (translator emission still open — see below).
2026-08-15. Battery 12 suites / 566 assertions / 0 failures on both arches.

## The gates, measured

From the image, **identical on arm64 and x64**:

| Call | Result | Independent check |
|---|---|---|
| `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)` | 2560 / 1440 | `PrimaryMonitorSize = 2560 x 1440` |
| `GetCurrentThreadId`, `GetTickCount` | live values | — |
| `GetDesktopWindow` → `IsWindow` | HWND 65548 → 1; `IsWindow(0)` → 0 | — |
| `MessageBeep(0xFFFFFFFF)` | 1 | — |
| `CloseHandle(1)` then `Win32 lastError` | **6** | `ERROR_INVALID_HANDLE` = 6 |
| **`GetClientRect(desktop, lpRect)`** | ok=1, RECT = **(0 0 2560 1440)** | matches the screen size above |

## The decision the brief asked for: no generator, no trampoline

The brief framed a choice between generating per-function C++ natives from winkb
and finishing a generic Win64 trampoline, recommending the generator. **Neither
was necessary**, and the cost probe is why.

`ST_ffiCall` had been stubbed on Windows since the port began, its comment
waiting for a "Win64 (GetProcAddress + MS-x64 ABI) trampoline". The POSIX side
hand-rolls an AAPCS64 trampoline because it sorts arguments into registers
*itself*. Here the resolved address is cast to a function-pointer type of the
right **arity** and the C++ compiler emits the call — correct by construction on
**both** architectures, because the compiler knows each ABI. Hence the identical
results above from one source file with no arch-specific code and no `.asm`.

Roughly 120 lines, versus a generator plus a build step plus a per-function
allowlist to maintain. The winkb database stays useful — it is how DD9 will
decide *which* functions the corpus needs and with what signatures — but it is
not needed to make the calls happen.

## What the floor refuses, and why that is the point

Word-sized arguments and returns only (integer, pointer, handle, BOOL) — which
is exactly the Win32 window/GDI surface DD2 measured (`<stdcall:` at 667 sites
across 29 files).

- **Doubles are refused, not approximated.** On x64 a float argument travels in
  XMM by position; casting it through a word would be silently wrong.
- **Variadics are refused** — the register/stack split for variadic arguments
  differs from the fixed case on ARM64 (`wsprintfW` is the corpus's one case).
- **Unresolved symbols raise**, naming the symbol and the search set.
- **Non-integer arguments raise** rather than being coerced: that is a
  marshalling bug at the call site, not something to paper over.

All four are catchable ST errors and are covered by gate tests. Verified:
`unresolved -> FFI: unresolved symbol 'ThisFuncti…'`,
`float arg -> FFI: argument code 'f' is unsupported…`.

## Structs came free

The struct/out-param gate needed **no new native**. `LocalAlloc`/`LocalFree` are
kernel32 functions, so the FFI floor allocates its own external memory *through
itself*; the existing Alien-shaped `stPeekByte`/`stPokeByte` read the fields
back. `GetClientRect` filling a 16-byte RECT is the proof, and it is a good gate
precisely because the answer is independently checkable — the desktop window's
client rect must equal the screen size.

This also settles the representation question the plan left open: external bytes
addressed by integer, with typed accessors composed in Smalltalk. No moving-GC
hazard by construction, because the memory is never in the Dart heap.

## Symbol resolution

A fixed system-DLL set — user32, gdi32, kernel32, comctl32, shell32, ole32,
oleaut32, comdlg32, advapi32, uxtheme, msimg32 — searched in order,
`GetModuleHandle` before `LoadLibrary`, with negative results cached so a miss
stays a miss.

**Loading an arbitrary caller-named DLL is deliberately not offered.** Dolphin's
pragmas do name their library, and honouring that would mean image code could
pull any binary on the machine into the process. Widening the surface is an edit
to `kWinFfiModules`, which is a review point rather than a runtime capability.

## `GetLastError`: immediately, and thread-local

Captured on the line after the call returns. *Immediately* is load-bearing — any
allocation, Dart transition or intervening native clobbers it, and a stale code
is worse than none because it reads as authoritative. Thread-local because
`GetLastError` is per-thread and the UI thread must never see a worker isolate's
code. Exposed as `Win32 lastError`.

## Still open (the rest of DD6)

**Translator emission.** DD3b's 172 `external-call` refusals still refuse. The
floor they would target now exists, but emitting the pragma needs the *marshalling*
model as well as the call: Dolphin writes `<stdcall: BOOL GetClientRect HWND
RECT*>`, and turning `RECT*` into "allocate, pass the address, read fields back"
is a code-generation problem on top of the ABI one. `GetClientRect` above is that
shape done by hand — the pattern is proven, the automation is not written.

**UTF-16 string arguments.** Dart strings are UTF-16 already (DIALECT_GAPS A9),
so `LPCWSTR` is a pin-and-pass rather than a conversion, but the pinning
discipline needs writing down before `SetWindowTextW` is called in anger.

**Pinned probes:** `st/test/ffi/win32_probe.mst` + `test/win32_ffi_probe.dart`,
`st/test/ffi/win32_rect.mst` + `test/win32_rect_probe.dart`.
