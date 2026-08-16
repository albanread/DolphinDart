"""Shared pools and `classConstants:` tables (DD3b).

Dolphin keeps its Win32 constants in `Kernel.SharedPool` subclasses whose whole
content is a `classConstants:` literal:

    Kernel.SharedPool
        subclass: #'OS.ButtonConstants'
        ...
        classConstants: {
            'BCM_GETIDEALSIZE' -> 16r1601.
            'BM_CLICK' -> 16rF5.
            ...
        }

A class names the pools it uses in `imports:`, and then refers to the constants
as **bare identifiers** in method bodies (`BM_CLICK`, not `ButtonConstants::BM_CLICK`).
So folding needs two things: the tables, and the import list.

**These live in `.pax` files, not `.cls` files** — the trap the prior-art design
flagged and DD2 confirmed: `Dolphin MVP Base.pax` alone carries three pools
(`OS.ButtonConstants`, `OS.CommCtrlConstants`, `OS.ThemeConstants`) plus 181
loose `OS.UserLibrary` methods. An ingester that reads only `.cls` silently
loses the entire User32 binding.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

# 'NAME' -> <literal> .   (the trailing period separates entries)
_ENTRY = re.compile(r"'([^']+)'\s*->\s*([^.\n}]+?)\s*(?:\.|(?=\})|$)", re.M)
_RADIX = re.compile(r"^(-?)(\d+)r(-?[0-9A-Za-z]+)$")
_POINT = re.compile(r"^\(?\s*([^@()]+?)\s*@\s*([^@()]+?)\s*\)?$")
_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def parse_literal(text: str) -> Optional[str]:
    """Normalise a Dolphin literal to house form, or None if not a literal.

    Radix literals (`16rF5`) are the common case and have no house spelling, so
    they are converted to decimal. Anything that is not provably a literal
    returns None and the caller refuses — a pool entry that is really an
    expression must not be silently folded to something plausible.
    """
    t = text.strip()
    if not t:
        return None
    m = _RADIX.match(t)
    if m:
        try:
            # A LEADING sign belongs to the whole literal: `-16r80000000` is
            # negative two-to-the-31, not radix -16.
            v = int(m.group(3), int(m.group(2)))
            return str(-v if m.group(1) == "-" else v)
        except ValueError:
            return None
    if re.match(r"^-?\d+$", t):
        return t
    if re.match(r"^-?\d+\.\d+(?:e-?\d+)?$", t):
        return t
    if re.match(r"^'(?:[^']|'')*'$", t):
        return t
    if re.match(r"^#\w+$", t) or t in ("true", "false", "nil"):
        return t
    if re.match(r"^\$.$", t):
        return t
    # A POINT constant: `(-16r80000000 @ -16r80000000)`. Both operands are
    # literals, so the whole thing is one — Dolphin writes geometry constants
    # this way and `UI.CreateWindowFunction`'s `UseDefaultGeometry` is the one
    # the View creation path needs. Refused as "not a literal", it left
    # `ShellView>>defaultExtent` answering nil and `create` dying on
    # `nil extent:`.
    m = _POINT.match(t)
    if m:
        x, y = parse_literal(m.group(1)), parse_literal(m.group(2))
        if x is not None and y is not None and _NUMERIC.match(x) and _NUMERIC.match(y):
            return "(%s @ %s)" % (x, y)
    return None


def parse_class_constants(class_constants: str) -> Dict[str, str]:
    """Extract `{'NAME' -> literal. ...}` into a name→house-literal table."""
    table: Dict[str, str] = {}
    for name, raw in class_constant_entries(class_constants):
        lit = parse_literal(raw)
        if lit is not None:
            table[name] = lit
    return table


def class_constant_entries(class_constants: str):
    """Every `'NAME' -> value` entry, with the value RAW and whole.

    `_ENTRY` cannot do this. It stops the value at the first `.`, newline or
    `}`, which is right for the scalar entries it was written for and wrong for
    every entry whose value is a multi-line expression:

        'UpdateModes'
            -> (IdentityDictionary withAll: {
                            #dynamic -> TreeViewDynamicUpdateMode.
                            #lazy -> TreeViewLazyUpdateMode.
                            #static -> TreeViewStaticUpdateMode
                        })

    Those matched as an empty or truncated value, so the name was declared as a
    class variable and NOTHING ever assigned it. That is not a translation gap
    that shows up at load — it is a nil that surfaces at the first read, which
    for `UI.TreeView` was `UpdateModes at: #dynamic` inside `initialize`, i.e.
    `TreeView new` could not complete; and for `UI.IconicListAbstract` it was
    `ViewModes at: self viewMode` during window creation. Three classes on the
    common-controls path were affected (`UpdateModes`, `LvModes`, `ViewModes`)
    and each presented only as `at:` sent to nil.

    So this walks the brace group instead of matching it, tracking nesting of
    `(`, `[`, `{` and skipping over `'...'` strings (with `''` escapes) and
    `#'...'` symbols, and splits on TOP-LEVEL periods only.
    """
    text = (class_constants or "").strip()
    if text.startswith("{"):
        text = text[1:]
    if text.endswith("}"):
        text = text[:-1]

    entries = []
    depth = 0
    i = 0
    start = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        i += 2
                        continue
                    break
                i += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "." and depth == 0:
            entries.append(text[start:i])
            start = i + 1
        i += 1
    entries.append(text[start:])

    out = []
    for chunk in entries:
        chunk = chunk.strip()
        if not chunk.startswith("'"):
            continue
        end = chunk.index("'", 1)
        while end + 1 < len(chunk) and chunk[end + 1] == "'":
            end = chunk.index("'", end + 2)
        name = chunk[1:end]
        rest = chunk[end + 1:].lstrip()
        if not rest.startswith("->"):
            continue
        out.append((name, rest[2:].strip()))
    return out


def class_constant_names(class_constants: str) -> list:
    """EVERY name in a `classConstants:` declaration, foldable or not.

    `parse_class_constants` keeps only entries whose value is a literal,
    because those are what can be folded at translation time. The rest are
    real class constants too — `UI.TextEdit` declares

        'AlignmentMap' -> (IdentityDictionary withAll: { ... })

    and its code reads the bare name at runtime. Dropping them left
    `AlignmentMap` as an unbound global, which is a runtime nil.
    """
    return [name for name, _ in class_constant_entries(class_constants)]


class PoolTable:
    """All known pools, keyed by fully-qualified and by base name."""

    def __init__(self) -> None:
        self.pools: Dict[str, Dict[str, str]] = {}

    def add(self, qualified_name: str, class_constants: str) -> int:
        table = parse_class_constants(class_constants)
        if not table:
            return 0
        self.pools[qualified_name] = table
        self.pools.setdefault(qualified_name.rsplit(".", 1)[-1], table)
        return len(table)

    def lookup(self, imports, name: str) -> Optional[str]:
        """Resolve a bare constant against the pools a class imports."""
        for imp in imports:
            t = self.pools.get(imp) or self.pools.get(imp.rsplit(".", 1)[-1])
            if t and name in t:
                return t[name]
        return None

    def any_lookup(self, name: str) -> Optional[str]:
        for t in self.pools.values():
            if name in t:
                return t[name]
        return None

    def __len__(self) -> int:
        # fully-qualified keys only, so aliases are not double counted
        return len([k for k in self.pools if "." in k])
