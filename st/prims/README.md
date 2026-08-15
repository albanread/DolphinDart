# `st/prims` — the generated Win32 binding surface

**GENERATED. Do not hand-edit — re-run the generator.**

```bash
python tools\dolphin2mst\genprims.py --out st\prims --corpus "C:\projects\dsfork\Core\Object Arts\Dolphin"
```

**1,126 external methods across 37 library classes**, generated from Dolphin's
own `<stdcall:`/`<cdecl:>` pragmas. The corpus is the specification: each pragma
names the function, its return type and its argument types in the order the
image will call them, so the generator reads those and emits a house external
method per declaration. winkb (`C:\projects\windows_api\windows_api.db`) is used
to *validate* — does the function exist, does the arity agree — not to enumerate;
it holds 18,271 functions and the port needs the ones Dolphin declares.

Largest classes: `UserLibrary` 231, `KernelLibrary` ~200, `GDILibrary`, plus the
networking/CRT/shell libraries. Full table and the refusal report:
[`_generated.md`](_generated.md).

## Running the harness

```bash
C:\projects\dolphindart-work\build-arm64\dart.exe test\st_prims.dart st\world st\prims
```

Two tiers, because "test every prim" means different things for different prims:

- **Tier A — resolve all.** Every generated prim must resolve to a real address
  through the floor's *own* resolver, so a pass means the floor could call it.
  This is the tier that scales to four figures, and it catches the failure mode
  a generator actually has: emitting a plausible name that is not there. It
  cannot prove a signature is right.
- **Tier B — call and check.** A curated set called for real, each with an answer
  that is independently checkable (a metric queried twice, a live HWND that
  `IsWindow` accepts). Small by necessity: blind-calling `CreateWindowExW` or
  `CloseHandle` in a test teaches you nothing good.

Current: **1,007 of 1,104 resolve**, 0 failures, identically on arm64 and x64.

## The 97 that do not resolve, and why that is correct

They are not defects; they name DLLs that are not present, or not present under
that name, on a stock machine:

| Library | Count | Why |
|---|--:|---|
| `ICULibrary` | 21 | Windows ships ICU version-suffixed (`icuuc*.dll`), not as a plain `icu.dll` |
| `WebView2Loader` | 4 | third-party, shipped with the Edge WebView2 SDK |
| `ScintillaLibrary`, `HTMLHelpLibrary`, `AXHostLibrary` | 3 | optional components Dolphin loads on demand |
| `CommCtrlLibrary`, `KernelLibrary`, `NTLibrary`, `IPHlpApiLibrary`, `SHCoreLibrary` | ~8 | individually absent exports — worth a look before the corpus reaches them |
| remainder | | version- or SKU-dependent |

Tier A reports these **by library class** rather than as a bare count, which is
what makes them actionable: the first run showed 371 unresolved and the
breakdown named the missing DLLs (ws2_32 68, iphlpapi 57, the CRT 49, httpapi
34, ICU 21, pathcch 18…). Adding those to the floor's search set took it to
1,007. A count alone would have said "a third of your bindings are broken"
without saying which, or why.

## What is refused, and why

3,385 declarations in the wider Dolphin tree do **not** generate:

| Reason | Count |
|---|--:|
| `virtual` — a COM vtable call (v1 non-goal) | 3,333 |
| `overlap` — an asynchronous call (v1 is synchronous) | 35 |
| struct passed **by value** (`POINTL`, `REFGUID`) | 6 |
| Dolphin VM object references (`oop`, `ote`) | 2 |
| ordinal export (the floor resolves by name only) | 1 |

The COM bulk comes from ActiveX packages outside this port's MVP+Base scope; the
generator refuses them wherever it meets them. Every refusal is written to
`_refusals.txt` with file:line, the class, the selector and the reason.
