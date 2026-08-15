# DD6c — marshalling automation: NOTES

**Status: DONE.** 2026-08-15. Both arches: marshalling gate green, prims
1,007/1,104 resolved with 0 failures, battery 12 suites / 566 assertions / 0.

## The gate

```smalltalk
UserLibrary getClientRect: (UserLibrary getDesktopWindow) lpRect: aRect
    "-> RECT = 0 0 2560 1440"
```

**Dolphin's own selector, taking an object where the API wants a pointer,
filling real external memory.** DD6 did that shape by hand; this is the
automation of it, and it is generated for all 1,126 external methods.

Every gate answer is checkable against something the OS or the language already
knows, never a constant written into the test:

| Gate | Check |
|---|---|
| `lstrlenW` on a marshalled string | must equal the Smalltalk string's own size (5, 15) |
| UTF-16 round trip | must return what went in (`round trip`) |
| non-BMP character | `'ab'` + one astral char = **4** code units |
| `getClientRect:lpRect:` | desktop client rect must equal the screen |
| `nil` as a pointer | `0` |
| wrong argument type | refused, not coerced |

## Shape

The generator emits a **coercing wrapper** for the 715 of 1,126 methods with a
string or pointer argument:

```smalltalk
UserLibrary class >> primGetClientRect: hwnd lpRect: p [   "raw: words only"
    <primitive: FFI function: #GetClientRect ret: #g args: #( g g )> ]

UserLibrary class >> getClientRect: aWindowHandle lpRect: aRECT [
    ^self primGetClientRect: (FFICoerce word: aWindowHandle)
              lpRect: (FFICoerce pointer: aRECT) ]
```

The raw entry keeps a `primN` name so a caller already holding addresses can
skip the coercion. Where a wrapper allocates a string temporary it runs under
`ensure:`, so a raise cannot leak external memory. **Pure-word methods get no
wrapper** — a forwarding-only wrapper is overhead on the hot path and noise in
1,126 methods of source.

`st/prims/rt` is hand-written and loads first: `ExternalMemory` (LocalAlloc
-backed, addressed by integer, never in the collected heap — no moving-GC hazard
by construction), `Utf16Buffer` (a copy, not a transcode, because Dart strings
are already UTF-16; surrogate pairs survive with no special case), and
`FFICoerce`, which refuses what it cannot convert rather than handing a
plausible number to a real API.

## Two dialect facts, found the honest way

1. **Character's code-point accessor here is `value`**, not Dolphin's
   `asUnicodeValue`. DD8's compat layer should alias it rather than assume it.
2. **`asString` is a universal helper the IL builder rewrites AT THE CALL
   SITE**, so a method of that name is never reached. The read-back method was
   first written as `asString` and silently answered
   `an ExternalMemory(6 bytes @ …)` instead of the string. Renamed
   `stringValue`, with the reason in the source — and it is a trap for anything
   else that wants to override a helper selector.

## Process notes worth keeping

- **An `rm -rf` of the generated tree took uncommitted hand-written runtime with
  it**, which had to be rewritten from scratch. Now committing mid-sprint, not
  just at sprint end.
- **The Bash tool's working directory persists across calls.** A `cd
  tools/dolphin2mst` several commands earlier meant a later `rm -rf st/prims &&
  cp …` operated on a *stray* `tools/dolphin2mst/st/prims`, leaving the repo's
  copy at the previous generation — which then presented as "the raw prim does
  not exist" and cost a debugging detour. Generator invocations now use absolute
  `--out` paths.

## Still open

- **Translator emission.** `dolphin2mst` still refuses external-call pragmas
  (DD3b's 172). The generated `st/prims` surface now covers those functions, so
  the remaining work is for the translator to *call* the generated wrapper
  rather than re-emit a pragma — a resolution question (which library class owns
  this selector?), not a marshalling one.
- **Struct field accessors.** `ExternalMemory` composes widths by hand
  (`int32At:`), which is enough for RECT/POINT/MSG. Generating typed accessors
  from winkb's `struct_fields` (66,708 rows, with byte offsets) is the next
  obvious lever and would serve DD9's View corpus directly.
- **`overlap`/async and COM** remain refused by design.
