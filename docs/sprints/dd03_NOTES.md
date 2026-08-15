# DD3 — dolphin2mst translator core: NOTES

**Status: CORE LANDED.** 2026-08-15. The central claim of the project is now
demonstrated rather than argued.

## The result that matters

**Dolphin's own `Graphics.Rectangle` source, translated mechanically and loaded
into our world, runs on the Dart VM:**

```
(Rectangle origin: 1@2 corner: 5@7) width          -> 4
(Rectangle origin: 1@2 corner: 5@7) height         -> 5
(Rectangle origin: 1@2 corner: 5@7) area           -> 20
(Rectangle origin: 0@0 corner: 10@10) containsPoint: 5@5  -> true
(Rectangle origin: 1@2 corner: 5@7) topLeft        -> 1@2
```

Note what those answers are made of: **translated Dolphin MVP code on top of our
own kernel's `Point`** (`1@2` is `st/world/28_point.mst`). That is the plan's
architecture — translate the MVP layers, bridge to our kernel — working end to
end for the first time.

Point + Rectangle: **155 methods translated, 2 refusals**, output **byte-stable**
across re-runs.

## What was built

`tools/dolphin2mst/` (Python, no dependencies):

| Module | Role |
|---|---|
| `chunks.py` | bang-chunk reader — BOM optional (3 corpus files have none), CRLF→LF, `!!` un-escaping |
| `stlex.py` | the character-level scanner everything trusts: blanks comments/strings while preserving offsets, and `is_balanced` as a precondition |
| `parse.py` | chunk → `ClassDef` / `Method`; both dialect generations (modern `imports:`, legacy `poolDictionaries:`) |
| `emit.py` | the rewrite classes + house-dialect emission |
| `cli.py` | driver, hierarchy resolution, refusal + run reports |
| `test_rewrites.py` | 38 golden cases, one group per rewrite class |

House target shape confirmed against the world: `Super subclass: Name [`,
`<classVars: A B>`, `| ivars |`, `Name class >> sel` for the class side.

## The D157 lowering works

`primitiveNewInitializedObject` — DD2 established it is the only primitive
number in the MVP tree — lowers with no VM work:

```smalltalk
"Dolphin:  Point class >> x: xCoord y: yCoord  <primitive: 157>"
Point class >> x: xCoord y: yCoord [
    ^self basicNew instVarAt: 1 put: xCoord; instVarAt: 2 put: yCoord; yourself
]
```

**The inheritance guard earned its place immediately.** The first run refused
`Graphics.Point>>x:y:` with *"superclass ivar count unknown
(Core.ArithmeticValue)"* — correct behaviour, because field placement depends on
the whole ancestor chain and I had only passed two files. Had it assumed zero, it
would have emitted plausible code that mis-fills every Point. The refusal is what
told me the chain resolver was incomplete.

## Four defects the first corpus runs found

1. **Section headers arrive without their leading bang.** In the file they read
   `!Graphics.Point methodsFor!`, but that opening `!` terminates the *preceding*
   chunk, so the splitter yields `Graphics.Point methodsFor`. Symptom: class
   parsed fine, **0 methods**.
2. **A `<` comparison was parsed as a pragma.** `<[^<>]*>` matched from a
   comparison to a later `>`: `... < yCorner ifTrue: [areas addLast: (self left @ (`
   was reported as an "unhandled pragma" and the method dropped. Pragmas occupy a
   whole line; the matcher is now anchored that way.
3. **`nil` is the hierarchy root.** Dolphin declares `nil subclass: #'Core.Object'`
   (as does our own `st/world/01_object.mst`). Without that case the root resolved
   to "unknown" and poisoned every descendant — surfacing three levels down as the
   `Graphics.Point>>x:y:` refusal above.
4. **`??` cannot be spliced inline.** Two bugs in one:
   - a following keyword part *merges* with the rewrite —
     `a ifNil: [b] foo: c` is the single message `ifNil:foo:`, not
     `(a ifNil: [b]) foo: c`. The result is now always parenthesised.
   - the left operand must be bounded to the primary + unary chain, because
     binary binds tighter than keyword: in `foo: a ?? b` the `??` applies to `a`
     alone, and consuming `foo: a` would emit `foo:ifNil:`.

   Both were caught by a golden case, not by the corpus — the corpus run was
   green while the rewrite was wrong. That is the argument for golden tests per
   rewrite class rather than end-to-end checks only.

## `--reference`: parse for hierarchy, never emit

Resolving field placement needs the ancestor chain, and that chain runs up into
Dolphin's kernel — which this project replaces rather than translates. Passing
`Core.Object` in as an ordinary input dutifully tried to *translate* it and
produced **39 "unmapped primitive" refusals for code we will never ship**. Hence
`--reference`: parsed for the hierarchy, never emitted. It is also a live
demonstration of DD2's finding — the kernel is where the primitives are.

## Refusals are the product

The two survivors on the first corpus are both `#{...}` **variable-binding
literals** (`#{Zero} binding setValue: nil` in class-side `uninitialize`). The
binding protocol has no house equivalent, so they are refused rather than
emitted as something that would parse and mean something else.

Found honestly: the first run emitted `#{Zero} binding setValue: nil` **cleanly**,
because nothing was looking for it. Every rewrite class exists because something
slipped through silently once.

## Not yet done (DD3 remainder)

- **`.pax` reader** — the manifest format carrying shared pools and ~181 loose
  `OS.UserLibrary` methods. Structurally the same chunk format; the work is
  interpreting the manifest, not lexing it.
- **Pool / `classConstants:` folding** beyond literal constants: `##(...)` over
  pool names currently refuses (4 refusals in `Core.Object` alone), which is the
  honest answer until pools are read.
- **Struct-accessor generation** and the `<stdcall:>` binding form — deliberately
  deferred to DD6, which owns the FFI shape. External-call pragmas refuse today
  with a clear message naming DD6.
- **Overlay mechanism** (`overlays/`) — designed, not built; nothing has needed
  it yet.
- **Wider corpus run.** Point + Rectangle is the DD3 gate corpus; the next step
  is the `UI.CreateWindow` / `Graphics.*Initializer` families where the other 30
  D157 sites live.

## Conventions established

- Generated `.mst` is an **artifact**: never hand-edit. Fix the translator or add
  an overlay, so corpus re-runs stay byte-stable (verified: two runs, identical
  output).
- Every refusal carries `file:line` and the rewrite class that refused, so the
  report is directly actionable.
- `is_balanced` runs as a precondition on every input; a file that ends inside a
  comment or string is never translated, only reported.
