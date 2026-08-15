# DD2 — conformity census + prim map: NOTES

**Status: DONE.** 2026-08-15. Analysis only; no VM or world change.
Deliverables: `docs/HOUSE_PRIMS.md`, `docs/PRIM_MAP.md`, `docs/DIALECT_GAPS.md`.

## The headline: DD5 evaporates

A direct scan of the Dolphin corpus, comments and string literals stripped:

| Tree | `<primitive:` sites | Files | Distinct numbers |
|---|--:|--:|--:|
| **`MVP/**` — what we translate** | **32** | 28 | **1** |
| `Base/**` — the kernel we replace | 354 | 59 | 212 |

**`primitiveNewInitializedObject` (D157) is the only primitive number in the
entire MVP tree.** It needs no VM work: the translator has just parsed the class
definition, so it knows the instance-variable order and lowers the pragma to
`basicNew` + ivar stores. DD5 is rescoped from `L` to `S` and made
demand-driven; its brief carries the correction at the top.

This is the plan's architecture paying off, not a change to it — keeping our own
kernel is precisely what makes Dolphin's kernel primitives moot. The prior-art
215-row worksheet describes *Dolphin's kernel*, and was never this project's
to-do list; DD2's job was to find that out before DD5 spent weeks on it.

## Namespaces: the rename table is empty

**Zero collisions.** No base class name appears in more than one namespace —
and in fact no base name appears twice at all across the 1001 in-scope `.cls`
files, under either reading of the dotted prefix (`UI.Scintilla.ScintillaView`
split at first dot or last). Independently verified: for all 986 files carrying
a `subclass: #'…'` declaration, the declared fully-qualified name is
byte-identical to the filename stem — **0 mismatches**, so filenames are
trustworthy as a rename-table source.

A2's flattening is therefore mechanical, and DD3's `renames.toml` starts empty.
Two riders:

- **6 legacy un-namespaced classes** (Dolphin-7 format, `poolDictionaries:`
  instead of `imports:`) need a namespace *assignment*, not a rename:
  `IPAddressView`, `NMIPADDRESS`, `StyledContainer`, `StyledGradientBrush`,
  `StyledPen`, `StyledShadow`.
- Scope limit, stated plainly: MVP + Base only. `IDE`, `ActiveX`, `System`,
  `Database`, `Sockets` and friends were not measured and could reintroduce
  collisions if ever pulled in.

## Corrections to the prior art and to my own briefs

1. **`<virtual:` and `<overlap>` are not standalone pragmas.** They are
   modifiers inside an external-call pragma: `<virtual stdcall: …>` (6 sites)
   and `<overlap stdcall:/cdecl: …>` (13 sites). Both the prior art and DD6's
   first draft had the syntax wrong; DD6's brief is corrected. Real demand is
   `<stdcall:` **667 sites / 29 files** and `<cdecl:` **77 / 4**.
2. **Mourning is spelled `elementsExpired:`, not `mourn:`.** `mourn`/`mourn:`
   has **zero** sites in scope; the seven raw "mourn" hits are all prose in class
   comments. `makeWeak` likewise: **zero**. Anyone implementing A7 from the
   prior art's vocabulary would have searched for the wrong selector.
3. **Three files have no BOM** (`IPAddressView.cls`, `NMIPADDRESS.cls`, and
   `Dolphin IP Address Control.pax` — the Dolphin-7-era IP-address control).
   DD3's reader must not *assume* a BOM; it must tolerate its absence.

## Confirmations (prior art was right, now measured)

- **`become:` — exactly one site in MVP**, `UI.STBViewProxy>>restoreView`. The
  other 13 real sends are all kernel idioms (collection grow/shrink,
  `ClassBuilder` class mutation, singleton swap). The design-around holds.
- **`thisContext` — zero sites in MVP.** All 3 corpus sites are in `Base`
  (`Core.Exception>>signal`, `Core.Process>>size`/`topFrame`).
- **`Utf16String` dominates** (222 refs / 85 files vs `Utf8String` 71,
  `AnsiString` 34) — and Dart strings *are* UTF-16, so A9 stays nearly free.

## Scale (the real denominator)

1001 `.cls` + 86 `.pax` = 1087 files, **264,734 raw lines / 160,779 code-only**
(22.5% of non-blank lines are comment or string). The plan's v1 target of
150–200 translated classes / 40–60k lines is ~15–20% of that — consistent with
translating MVP+Graphics and bridging the kernel rather than porting it.

## Green processes: the replacement table has 13 MVP customers

A6 is the one row the census made *bigger* rather than smaller. Corpus-wide:
`Processor` 109 sites/35 files, `critical:` 85, `Semaphore` 50/23, `Delay`
25/11, `fork*` family 51. Most is `Base`, but the MVP-side users are real and
are exactly the sites the prior-art G-f/G-g table predicted:
`UI.AbstractSplash`, `UI.ProgressDialog`, `UI.DragDropSession`,
`UI.GuiInputState`, `UI.View`, `UI.ShellView`, `UI.DialogView`,
`UI.MessageBubble`, `UI.MultilineTextEditWithImage`, `UI.RichText`,
`UI.AdvancedFindDialog`, the Prompter family, and Scintilla.

Nothing here changes the doctrine (no green threads; pump native; workers are
Dart isolates). It does mean DD10's worker sprint inherits a concrete,
enumerated work-list rather than a principle.

## Deferred, with the reason

**The two loose suites are not wired.** `st/test/primitive_probes.mst` and
`type_conformance.mst` are probe *libraries* — they answer values; a driver
compares them against expectations. That driver (`primitive_coverage.dart`) was
never vendored, and the expected answers live in trailing comments, which is not
a contract worth parsing. Wiring them means writing expectation tables, which is
real work and belongs where the answers matter: `primitive_probes` → DD5 (it
exercises the `<primitive: N>`-through-noSuchMethod path DD5 cares about),
`type_conformance` → DD4 (it pins where Dart's semantics show through, which is
exactly the resumability question). My DD1 note calling this "cheap" was wrong;
recorded rather than smoothed over.

## Method note

Counts came from a character-level scanner (states: normal / in-comment /
in-string) rather than regex, because `$"` and `$'` character literals derail a
naive scan and `""`/`''` are escapes. Validation: **zero of 1087 files ended in
an unterminated comment or string state.** Raw grep would have been badly wrong
here — `Symbol` alone drops from 270 raw hits to 27 real code references once
prose and symbol literals are removed, and DD1 already showed four of six
"dependencies" were comments.
