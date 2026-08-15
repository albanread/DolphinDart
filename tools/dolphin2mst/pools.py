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
_RADIX = re.compile(r"^(\d+)r(-?[0-9A-Za-z]+)$")


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
            return str(int(m.group(2), int(m.group(1))))
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
    return None


def parse_class_constants(class_constants: str) -> Dict[str, str]:
    """Extract `{'NAME' -> literal. ...}` into a name→house-literal table."""
    table: Dict[str, str] = {}
    for name, raw in _ENTRY.findall(class_constants or ""):
        lit = parse_literal(raw)
        if lit is not None:
            table[name] = lit
    return table


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
