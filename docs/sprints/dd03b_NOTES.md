# DD3b — `.pax`, pools, wider corpus: NOTES

**Status: DONE.** 2026-08-15. Translator now reads the whole source format and
scales to a real corpus.

## Numbers

| | |
|---|---|
| Wide run | `MVP/Base` + `MVP/Graphics`, `Base` as reference |
| Inputs | 220 source files (`.cls` **and** `.pax`) |
| **Emitted** | **211 classes, 5,441 methods** |
| Refusals | 382, all classified (below) |
| Pools available | **3,873 constants from 17 shared pools** |
| Byte-stable | yes — two runs over all 211 classes, identical output |
| Regression | translated `Graphics.Rectangle` still runs (4 / 5 / 20 / true / 1@2) |

## `.pax` is source, and it changes the shape of a "parsed file"

A `.cls` holds one class. A **`.pax` holds many** — `Dolphin MVP Base.pax` alone
declares **117 classes**, three shared pools (**928 constants**), and **198 loose
methods**, of which **177 are filed onto `OS.UserLibrary`**: the User32 binding
the prior-art design warned a `.cls`-only ingester would silently lose.

So `ParsedFile` gained `classdefs` (every definition in the file) and `loose`
(target class → methods filed onto it), and each `methodsFor` section is
attributed to **the class its own header names** rather than to the file.

Loose methods whose target was not translated are **reported, not dropped** —
`orphan-loose-methods`, 15 in the wide run. Dropping them is exactly how you
lose a Win32 binding without noticing.

## Pools

`Kernel.SharedPool` subclasses carry `classConstants: { 'BM_CLICK' -> 16rF5. … }`.
Two folding sources, both needed:

1. **Imported pools** — a class lists them in `imports:` and then writes the
   constants as bare identifiers.
2. **The class's own `classConstants:`** — the struct classes lean on this
   entirely: `OS.MENUITEMINFOW` has 49 of its own (`_OffsetOf_cch` → 40), and
   every generated accessor addresses fields as `##(_OffsetOf_x + 1)`.

The guard is the important half: a name is folded only when it is not a method
argument, temporary, instance variable or class variable. Shadowing is legal
Smalltalk, and folding a shadowed name would swap a constant for a live variable
with no diagnostic.

## Four defects the wide run found

1. **`imports:` kept its braces.** Entries are `{OS.Win32Constants}` — a
   brace-wrapped binding reference — and stripping only `#'` left every pool
   import unmatchable, so nothing folded and `##(MIIM_STRING | MIIM_ID)` refused
   as "not constant".
2. **`##()` could not fold multi-term or `|`.** After pool folding the corpus is
   full of `##(A | B | C)`. Now folds left-to-right over `+ - * // | & bitOr:
   bitAnd: bitXor: bitShift:`.
3. **Constant names may start with an underscore.** `_IDENT` required an
   uppercase first letter, so every struct class refused its own `_OffsetOf_*`
   expressions.
4. **211 spurious "duplicate" refusals.** A `.pax` re-declares the classes its
   package contains, so every class in scope appeared twice. `.cls` files are now
   emitted first and a losing `.pax` re-declaration is a *note*, not a refusal —
   that is the format working as designed. Any other collision is still a refusal.

## The inherited-offset case is implemented

DD3 refused D157 when the superclass contributed fields. That refusal was
blocking real MVP classes (`UI.CreateWindow`, `UI.CreateInDpiAwarenessContext`),
and the fix was available once the chain resolver worked: inherited fields come
first in `instVarAt:` order, so this class's variables start at
`super_count + 1`. Pinned by a golden case that asserts the exact arithmetic —
an off-by-one here shifts every field of every instance.

12 `prim157` refusals remain and are **correct**: cases like
`UI.LayoutPlacement>>view:` with 1 argument against 3 instance variables, where
there is no mapping to infer.

## The remaining 382 refusals, classified

| Class | Count | Verdict |
|---|--:|---|
| `external-call` | 172 | **By design** — `<stdcall:>`/`<cdecl:>` belong to DD6, which owns the FFI form |
| `hashhash` | 161 | ~36 are `##(self …)` and object constructions (`IdentityDictionary new …`) that genuinely need image evaluation — out of scope by design; the rest name pools **absent from the input set** (`MIIM_STRING`, `SWP_NOZORDER`, `MK_LBUTTON`), which is a corpus-scoping question for DD9, not a translator defect |
| `binding-literal` | 19 | `#{...}` has no house equivalent |
| `orphan-loose-methods` | 15 | target class not in this run's scope |
| `prim157` | 12 | genuinely ambiguous arg/ivar mappings |
| `pragma` | 3 | unrecognised pragmas, listed individually |

**None of these is a silent failure.** Every one names a file, a line and the
rewrite class that refused.

## Still open

- **Overlay mechanism** (`overlays/`) — designed, still unbuilt; nothing has
  needed it yet, and inventing a use for it would be worse than waiting.
- **Struct-accessor generation** — the `_OffsetOf_*` constants now fold, but
  turning a Dolphin `External.Structure` subclass into a house Alien-backed
  struct is DD6's job, with the FFI form.
- **A pool-completeness pass** for DD9: decide whether the corpus scope grows to
  cover `MIIM_*`/`SWP_*`/`MK_*` or whether those classes are trimmed.
