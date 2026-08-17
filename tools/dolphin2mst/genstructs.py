"""Generate Win32 struct classes with typed accessors (DD6c).

    python genstructs.py --out <dir> --corpus <dolphin-root> [--winkb <db>]

The structs the Dolphin corpus actually passes — taken from the `X*` argument
types in its own external-call pragmas — emitted as `ExternalMemory` subclasses
whose accessors read and write real fields at real offsets.

**The offsets come from winkb, not from arithmetic here.** Its `struct_fields`
table carries 66,708 rows with `byte_offset` already resolved for 64-bit
alignment — `MSG.lParam` at 24, `NMHDR.idFrom` at 8 — which is exactly the part
a hand-written binding gets wrong. Computing them here would mean re-deriving
alignment rules that the metadata already knows.

    ExternalMemory subclass: RECT [
        RECT class >> sizeInBytes [ ^16 ]
        RECT class >> new [ ^self new: 16 ]
        left [ ^self int32At: 1 ]
        left: v [ ^self uint32At: 1 put: v ]
        ...
    ]
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import parse
from stlex import strip_code

PRAGMA = re.compile(r"<\s*(?:(?:virtual|overlap)\s+)?(?:stdcall|cdecl)\s*:\s*([^<>]*)>")

# Field type -> (accessor, width). Handles and pointers are 8 bytes on the only
# targets this port has (x64, ARM64); a 32-bit target would need this widened,
# and would also need different offsets, which is why the width is not guessed
# from the name.
_SCALARS = {
    "i8": ("int8At", 1), "u8": ("byteAt", 1),
    "i16": ("int16At", 2), "u16": ("uint16At", 2),
    "i32": ("int32At", 4), "u32": ("uint32At", 4),
    "i64": ("intptrAt", 8), "u64": ("intptrAt", 8),
    "isize": ("intptrAt", 8), "usize": ("intptrAt", 8),
    "f32": (None, 4), "f64": (None, 8),
}
_PTR_WIDTH = 8


_ENUM_ACCESSOR = {8: ("byteAt", 1), 16: ("uint16At", 2),
                  32: ("uint32At", 4), 64: ("intptrAt", 8)}


def field_accessor(type_name: str, structs: Dict[str, int],
                   enums: Optional[Dict[str, int]] = None,
                   handles: Optional[set] = None
                   ) -> Tuple[Optional[str], int]:
    """(accessor-or-None, width). None accessor => emit a view or skip."""
    t = type_name.rsplit(".", 1)[-1]
    if type_name in _SCALARS:
        return _SCALARS[type_name]
    if t in ("BOOL", "BOOLEAN"):
        return "int32At", 4
    if t in ("HWND", "HDC", "HANDLE", "HMENU", "HICON", "HCURSOR", "HBRUSH",
             "HINSTANCE", "HBITMAP", "HFONT", "HPEN", "HRGN", "WPARAM", "LPARAM",
             "LRESULT", "WNDPROC", "PWSTR", "PCWSTR", "PSTR", "PCSTR"):
        return "intptrAt", _PTR_WIDTH
    # A HANDLE TYPEDEF, derived rather than listed. Win32Metadata models every
    # opaque handle as a struct with exactly one pointer-sized field named
    # `Value` — `HWND` is one, and so is `HTREEITEM`, which the list above does
    # not name. Treated as a nested struct it came out as a read-only VIEW with
    # no setter at all, so `TVINSERTSTRUCTW>>hParent:` did not exist and a tree
    # item could not be given a parent.
    #
    # Deriving it also stops the list above from having to grow once per
    # control family: HIMAGELIST, HDWP and the rest match the same shape.
    if handles and t in handles:
        return "intptrAt", _PTR_WIDTH
    if t in structs:                       # a nested struct: a view, not a copy
        return None, structs[t]
    # AN ENUM-TYPED FIELD is an integer of the enum's own width, and winkb
    # records that width — `LIST_VIEW_ITEM_STATE_FLAGS` is `kind='enum'`,
    # `size_bits=32`. Not following the type left every such field with no
    # accessor at all: `LVITEMW>>stateMask:` and `MENUINFO>>dwStyle:` among
    # them, which is why `03_struct_accessors.mst` exists and hand-supplies
    # two of them. Unsigned, because a Win32 flags enum is a bit set.
    if enums and t in enums and enums[t] in _ENUM_ACCESSOR:
        return _ENUM_ACCESSOR[enums[t]]
    return None, 0                         # unknown: reported, never guessed


# Any `<Super>\n subclass: #'<Namespace.Name>'` header, with the instance
# variables that follow it. The SUPERCLASS is captured because struct-ness is
# INHERITED and the chain is often more than one link: `OS.LVITEMW` is a
# subclass of `OS.CCITEM`, which is the `External.Structure` — matching only
# the direct children found `LVCOLUMNW` and missed `LVITEMW`, and the ListView
# needs both (one per column, one to clear the selection).
CLASS_DECL = re.compile(
    r"^\s*([\w.]+)\s*\n\s*subclass:\s*#'([\w.]+)'"
    r"(?:\s*\n\s*instanceVariableNames:\s*'([^']*)')?",
    re.M)

# The root of struct-ness: `External.Structure`, `OS.ExternalStructure`, and
# anything else the corpus spells with a `Structure` suffix.
STRUCT_ROOT = re.compile(r"(?:^|\.)\w*Structure$")

# Instance variables the corpus declares on a struct class it also defines
# methods for. Filled by `corpus_struct_names`, read by the emitter.
DECLARED_IVARS: Dict[str, List[str]] = {}

# Struct base name -> its corpus superclass base name. Filled by
# `corpus_struct_names`, read by the emitter so the GENERATED hierarchy matches
# the corpus's. Flattening every struct to `ExternalMemory` silently drops the
# inherited Smalltalk protocol: `OS.TVITEMEXW` is a subclass of `OS.TVITEMW`,
# which is a subclass of `OS.CCITEM`, and `maskIn:`/`children:`/
# `beStateExpandedOnce` live up that chain. TreeView's notify handlers are
# written entirely over those, so a flat TVITEMEXW meant the control asked for
# a node's child count, got nothing, decided the node was childless, and never
# sent TVN_ITEMEXPANDING — an empty tree with no error anywhere.
DECLARED_SUPER: Dict[str, str] = {}


# Struct bases this PORT supplies, which winkb therefore knows nothing about.
# `OS.CCITEM` is the case it exists for: Dolphin's abstract parent of every
# common-control item structure (TVITEM, LVITEM, TCITEM), carrying the shared
# `mask`/`maskIn:`/`textInBuffer:` protocol those structs are driven through.
# It is not a Win32 struct, so `load()` can never find a layout for it — but it
# IS translated (see translate_mvp) into `st/prims/rt`, which loads first.
#
# Filled from `--supplied`, so the dependency is explicit and greppable rather
# than a name this file happens to know.
SUPPLIED_BASES: set = set()


def _struct_super(name, fields) -> str:
    """The corpus superclass when it is available here, else `ExternalMemory`.

    Available means: generated from winkb like any other struct, OR named by
    `--supplied` because this port provides it. A parent that is neither must
    NOT be emitted — the class reference would be nil at load and every
    inherited send would go to nothing.
    """
    sup = DECLARED_SUPER.get(name)
    if sup and sup != name and (sup in fields or sup in SUPPLIED_BASES):
        return sup
    return "ExternalMemory"


def corpus_struct_names(root: str) -> collections.Counter:
    """Struct names the corpus needs, by two independent rules.

    RULE 1 — passed by pointer to an external call, e.g. `RECTL*` -> RECTL.
    This was the only rule, and it misses an entire category.

    RULE 2 — DECLARED by the corpus as an `External.Structure` subclass and
    named from some OTHER file. A struct reaches Windows two ways in Dolphin,
    and only one of them is an FFI pragma: the common controls are driven by
    `SendMessage`, so `UI.ListView>>insertColumn:atIndex:` builds an
    `LVCOLUMNW` and passes its ADDRESS as an LPARAM. No pragma ever names the
    type, so rule 1 could not see it and `LVCOLUMNW fromColumn:` was a send to
    nil — the ListView half of the DD11 gate, while the TreeView half passed.

    The second condition (named elsewhere) is what keeps this from emitting
    every struct class in the corpus: a declaration nothing references is a
    struct this port has no caller for.
    """
    names = collections.Counter()
    supers: Dict[str, str] = {}       # class base name -> superclass, qualified
    decl_path: Dict[str, str] = {}    # class base name -> file that declares it
    sources: List[Tuple[str, str]] = []

    for dp, dn, fn in os.walk(root):
        if set(dp.replace("\\", "/").split("/")) & {"Tests", "Deprecated", "Gdiplus"}:
            continue
        for f in fn:
            if not f.endswith((".cls", ".pax")):
                continue
            path = os.path.join(dp, f)
            raw = open(path, encoding="utf-8", errors="replace").read()
            src = strip_code(raw)
            sources.append((path, src))
            for body in PRAGMA.findall(src):
                for tok in body.split()[2:]:
                    if tok.endswith("*") and tok[:1].isupper():
                        names[tok[:-1]] += 1
            # RAW, not stripped: the class name lives in a SYMBOL literal
            # (`subclass: #'OS.LVCOLUMNW'`) and `strip_code` blanks literals,
            # so the stripped text has the superclass and nothing after it.
            # The reference scan below still uses the stripped text, so a name
            # that appears only in a comment does not count as a caller.
            for m in CLASS_DECL.finditer(raw):
                base = m.group(2).rsplit(".", 1)[-1]
                supers.setdefault(base, m.group(1))
                DECLARED_SUPER.setdefault(base, m.group(1).rsplit(".", 1)[-1])
                decl_path.setdefault(base, path)
                # The class's OWN instance variables have to be part of the
                # GENERATED class, not added later by the `--reopen` that
                # brings its methods: in this dialect a class header that
                # states an ivar list REDEFINES the class, so a reopen
                # declaring `| text |` silently dropped `sizeInBytes` and
                # every accessor, and `newBuffer` then allocated nothing.
                # `OS.LVCOLUMNW`'s `text` is a real field — it holds the UTF-16
                # buffer alive while the struct points at it.
                if m.group(3):
                    DECLARED_IVARS.setdefault(base, m.group(3).split())

    def is_struct(base: str, seen=None) -> bool:
        """Does this class's ancestry reach an `External.Structure`?"""
        seen = seen or set()
        if base in seen:
            return False
        sup = supers.get(base)
        if sup is None:
            return False
        if STRUCT_ROOT.search(sup):
            return True
        return is_struct(sup.rsplit(".", 1)[-1], seen | {base})

    for base, path_of_decl in decl_path.items():
        if base in names or not is_struct(base):
            continue
        word = re.compile(r"\b%s\b" % re.escape(base))
        for path, src in sources:
            if path != path_of_decl and word.search(src):
                names[base] += 1
                break
    return names


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="genstructs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--winkb", default=r"C:\projects\windows_api\windows_api.db")
    ap.add_argument("--supplied", action="append", default=[],
                    help="a struct base this port supplies rather than winkb "
                         "(OS.CCITEM); see SUPPLIED_BASES")
    args = ap.parse_args(argv)

    SUPPLIED_BASES.update(n.rsplit(".", 1)[-1] for n in (args.supplied or []))
    if not os.path.exists(args.winkb):
        print("genstructs: winkb database not found — offsets come from there, "
              "so there is nothing to generate", file=sys.stderr)
        return 2
    import sqlite3
    db = sqlite3.connect(args.winkb)
    # ENUM WIDTHS, once. A struct field typed as a Win32 enum is an integer of
    # the enum's size, and winkb records it; see `field_accessor`.
    enum_bits: Dict[str, int] = {
        n: b for n, b in db.execute(
            "select type_name, size_bits from types where kind='enum' "
            "and size_bits is not null")}
    # HANDLE TYPEDEFS, derived: a struct whose ONLY field is a pointer-sized
    # `Value`. See `field_accessor`.
    handle_types = {n for (n,) in db.execute(
        "select t.type_name from types t join struct_fields f "
        "  on f.struct_type_id = t.type_id "
        "where t.kind='struct' "
        "group by t.type_id "
        "having count(*) = 1 "
        "   and max(f.field_name) = 'Value' "
        "   and max(f.type_name) in ('isize','usize','i64','u64')")}

    wanted = corpus_struct_names(args.corpus)
    # Dolphin spells several structs with the GDI `L` suffix (RECTL/POINTL/SIZEL)
    # where the metadata carries the plain name; try both before giving up.
    alias = {"RECTL": "RECT", "POINTL": "POINT", "SIZEL": "SIZE"}

    sizes: Dict[str, int] = {}
    fields: Dict[str, List[Tuple[int, str, str, int]]] = {}
    unknown: List[str] = []
    # winkb's name for a struct is not always the corpus's: Dolphin spells the
    # GDI variants RECTL/POINTL/SIZEL. Nested fields are typed with the WINKB
    # name, so resolving them needs the reverse map — without it, PAINTSTRUCT's
    # `rcPaint` (a `RECT`) failed to match the generated `RECTL` and no accessor
    # was emitted at all.
    winkb_to_corpus: Dict[str, str] = {}

    def load(name: str) -> bool:
        for candidate in (name, alias.get(name, name)):
            rows = list(db.execute(
                "select f.ordinal, f.field_name, f.type_name, f.byte_offset "
                "from struct_fields f join types t on t.type_id=f.struct_type_id "
                "where t.type_name=? order by f.ordinal", (candidate,)))
            if rows:
                fields[name] = rows
                winkb_to_corpus[candidate] = name
                return True
        return False

    for name in sorted(wanted):
        if not load(name):
            unknown.append(name)

    # TRANSITIVE CLOSURE over nested struct fields. The corpus passes `RECTL*`
    # but never `RECT*`, while PAINTSTRUCT's `rcPaint` field is typed `RECT` —
    # so generating only what the corpus names leaves nested accessors
    # unresolvable, and PAINTSTRUCT came out with no `rcPaint` at all.
    pending = list(fields)
    while pending:
        name = pending.pop()
        for _, _, ftype, _ in fields.get(name, []):
            t = ftype.rsplit(".", 1)[-1]
            acc, _w = field_accessor(ftype, {}, enum_bits, handle_types)
            if acc is not None or t in fields or t in winkb_to_corpus:
                continue
            if load(t):
                pending.append(t)

    # Size = last field's offset + its width. Nested struct fields need their
    # own size known first, so this iterates to a fixed point rather than
    # assuming one pass is enough (PAINTSTRUCT contains a RECT; MSG ends with a
    # POINT, and getting that wrong made MSG 44 bytes instead of 48).
    def width_of(ftype: str) -> int:
        acc, w = field_accessor(ftype, {}, enum_bits, handle_types)
        if acc is not None:
            return w
        t = ftype.rsplit(".", 1)[-1]
        corpus = winkb_to_corpus.get(t, t)
        return sizes.get(corpus, 0)

    def alignment_of(rows) -> int:
        """The struct's alignment: the widest scalar it contains, capped at 8."""
        a = 1
        for _, _, ftype, _ in rows:
            acc, w = field_accessor(ftype, {}, enum_bits, handle_types)
            if acc is not None:
                a = max(a, min(w, 8))
            else:
                t = ftype.rsplit(".", 1)[-1]
                nested = winkb_to_corpus.get(t, t)
                if nested in fields:
                    a = max(a, alignment_of(fields[nested]))
        return a

    for _ in range(8):
        changed = False
        for name, rows in fields.items():
            last = rows[-1]
            w = width_of(last[2])
            if w == 0:
                continue
            # sizeof includes TRAILING PADDING to the struct's alignment. Using
            # "last field end" under-allocates: MSG's `pt` (a POINT) ends at 44
            # but sizeof(MSG) is 48 on x64, and a 44-byte buffer handed to
            # GetMessage is four bytes of someone else's memory.
            end = last[3] + w
            align = alignment_of(rows)
            new = ((end + align - 1) // align) * align
            if sizes.get(name) != new:
                sizes[name] = new
                changed = True
        if not changed:
            break
    # Anything still unsized ends in a field of unknown width; fall back to the
    # pointer width and say so in the report rather than emitting a wrong size.
    unsized = [n for n in fields if n not in sizes]
    for n in unsized:
        sizes[n] = fields[n][-1][3] + _PTR_WIDTH

    os.makedirs(args.out, exist_ok=True)
    written = 0
    skipped: List[str] = []
    for name, rows in sorted(fields.items()):
        lines = [f'"GENERATED by tools/dolphin2mst/genstructs.py — field offsets from',
                 f' winkb (Win32Metadata), not computed here. Do not hand-edit."',
                 "",
                 f"{_struct_super(name, fields)} subclass: {name} [",
                 f"    {name} class >> sizeInBytes [ ^{sizes[name]} ]",
                 # `byteSize` is DOLPHIN'S spelling for the same number, and
                 # its own code uses it: `SystemMetrics>>nonClientMetrics`
                 # sizes a NONCLIENTMETRICSW with `byteSize` before calling
                 # SystemParametersInfo.
                 #
                 # Emitted PER STRUCT rather than aliased on `ExternalMemory`,
                 # because a `self` send inside an inherited CLASS-side method
                 # binds to the DEFINING class — `ExternalMemory class >>
                 # byteSize [ ^self sizeInBytes ]` would look for
                 # ExternalMemory's own, not the subclass's. That trap already
                 # cost a Win32 ERROR_INVALID_PARAMETER once (LOOSE_ENDS 3.12).
                 f"    {name} class >> byteSize [ ^{sizes[name]} ]",
                 # AND INSTANCE-SIDE. Dolphin sends it to both:
                 # `SystemMetrics>>getSysParamForDpi:type:ifError:` does
                 # `struct := aClass new. ... uiParam: struct byteSize`.
                 # A literal rather than `^self size` — `size` is a universal
                 # helper the IL builder rewrites at the call site, so a
                 # method body relying on it is not reliably reached.
                 f"    byteSize [ ^{sizes[name]} ]",
                 f"    {name} class >> new [ ^self new: {sizes[name]} ]",
                 ""]
        # The corpus's OWN instance variables for this struct, if it declares
        # any. They belong on the generated class because a `--reopen` cannot
        # add them without redefining the class — see DECLARED_IVARS above.
        if DECLARED_IVARS.get(name):
            lines.insert(4, f"    | {' '.join(DECLARED_IVARS[name])} |")
        # THE `_OffsetOf_` FAMILY, class-side.
        #
        # Dolphin's own code reads a field offset through its owning struct
        # class — `pNMHDR uint32AtOffset: NMCUSTOMDRAW._OffsetOf_dwDrawStage`
        # in `IconicListAbstract>>nmCustomDraw:` — because a WM_NOTIFY handler
        # gets a raw pointer and has to index into it by hand.
        #
        # Those constants live in Dolphin's `.cls` for the struct, which this
        # generator does not read: it reads winkb. So they are emitted here,
        # from the same offsets the accessors use, and the translator rewrites
        # `Owner._OffsetOf_x` to the send `Owner _OffsetOf_x`.
        #
        # ZERO-BASED, matching Dolphin: `_OffsetOf_` is the C offset, which is
        # why the accessors above add 1 for this dialect's 1-based indexing.
        # Emitting the 1-based number here would be off by one everywhere it
        # is used, silently.
        for _ord, _fname, _ftype, _off in rows:
            lines.append(f"    {name} class >> _OffsetOf_{_fname} [ ^{_off} ]")
        lines.append(f"    {name} class >> _{name}_Size [ ^{sizes[name]} ]")
        lines.append("")
        for ordinal, fname, ftype, off in rows:
            acc, width = field_accessor(ftype, sizes, enum_bits, handle_types)
            sel = fname[0].lower() + fname[1:]
            nested = winkb_to_corpus.get(ftype.rsplit(".", 1)[-1])
            if acc is None and nested and nested in sizes:
                # A TYPED view: an instance of the nested struct's own class, so
                # its accessors are reachable. A generic view would answer raw
                # bytes and `rcPaint right: 77` would be a doesNotUnderstand.
                lines.append(f"    {sel} [ ^{nested} viewOn: self at: {off} "
                             f"size: {sizes[nested]} ]")
            elif acc is None:
                skipped.append(f"{name}.{fname} ({ftype})")
                lines.append(f"    \"{sel}: {ftype} at {off} — no accessor "
                             f"(width unknown); use byteAt: directly\"")
            else:
                lines.append(f"    {sel} [ ^self {acc}: {off + 1} ]")
                # A SETTER FOR EVERY WIDTH, through the accessor's own `put:`
                # form. This used to be 32-bit-only, which left a getter with
                # no setter on every pointer and every 8/16-bit field —
                # `MENUITEMINFOW>>dwTypeData:`, the field a menu item's text
                # pointer goes in, was one, and it had to be hand-written in
                # `st/mvp_compat/03_struct_accessors.mst` to make menus work
                # at all. A struct you can read and not write is half a
                # binding.
                #
                # The put form matches the get form now that `int32At:put:`
                # and `int16At:put:` exist; before, the 32-bit setter went
                # through `uint32At:put:` regardless of signedness, which
                # happens to write the same bytes but reads as a mismatch.
                lines.append(f"    {sel}: v [ ^self {acc}: {off + 1} put: v ]")
        lines.append("]")
        with open(os.path.join(args.out, name + ".mst"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        written += 1

    with open(os.path.join(args.out, "_structs.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("# Generated Win32 structs\n\n")
        fh.write(f"- struct pointer types used by the corpus: **{len(wanted)}**\n")
        fh.write(f"- **generated: {written}** (offsets from winkb `struct_fields`)\n")
        fh.write(f"- not in winkb: **{len(unknown)}**\n")
        fh.write(f"- fields without an accessor: **{len(skipped)}**\n\n")
        fh.write("## Generated\n\n| Struct | Bytes | Fields | Corpus uses |\n|---|--:|--:|--:|\n")
        for n in sorted(fields):
            fh.write(f"| `{n}` | {sizes[n]} | {len(fields[n])} | {wanted[n]} |\n")
        if unknown:
            fh.write(f"\n## Not in winkb ({len(unknown)})\n\n")
            for n in unknown:
                fh.write(f"- `{n}` (used {wanted[n]}x)\n")
        if skipped:
            fh.write(f"\n## Fields without an accessor ({len(skipped)})\n\n")
            for s in skipped[:60]:
                fh.write(f"- {s}\n")

    print(f"genstructs: {written} structs -> {args.out} "
          f"({len(unknown)} unknown, {len(skipped)} fields skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
