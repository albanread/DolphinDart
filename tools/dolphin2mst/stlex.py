"""Smalltalk lexical helpers shared by the translator (DD3).

The one rule this file exists to enforce: **never scan Dolphin source with a
plain regex.** Three things break naive scans, and all three cost real time on
this project before they were understood (DD1 mis-read four dependencies from
comments; DD2's counts moved by an order of magnitude for `Symbol`):

* `"..."` comments, with `""` as an escaped quote;
* `'...'` string literals, with `''` as an escaped quote;
* `$x` **character literals** — `$'` and `$"` are perfectly legal and will
  derail any scanner that treats the quote as opening a region.

`strip_code` blanks comments and strings while preserving length and line
structure, so offsets computed on the stripped text address the original.
"""
from __future__ import annotations

from typing import List

NORMAL, IN_COMMENT, IN_STRING = 0, 1, 2


def strip_code(src: str, keep: str = " ") -> str:
    """Blank out comments and string literals, preserving length and newlines."""
    out: List[str] = []
    st = NORMAL
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if st == NORMAL:
            if c == "$" and i + 1 < n:          # character literal: $x, $', $"
                out.append("  ")
                i += 2
                continue
            if c == '"':
                st = IN_COMMENT
                out.append(keep)
            elif c == "'":
                st = IN_STRING
                out.append(keep)
            else:
                out.append(c)
        elif st == IN_COMMENT:
            if c == '"':
                if i + 1 < n and src[i + 1] == '"':   # escaped quote
                    out.append(keep * 2)
                    i += 2
                    continue
                st = NORMAL
            out.append("\n" if c == "\n" else keep)
        else:  # IN_STRING
            if c == "'":
                if i + 1 < n and src[i + 1] == "'":
                    out.append(keep * 2)
                    i += 2
                    continue
                st = NORMAL
            out.append("\n" if c == "\n" else keep)
        i += 1
    return "".join(out)


def is_balanced(src: str) -> bool:
    """True when the source does not end inside a comment or string.

    DD2 ran this over all 1087 corpus files and every one came back balanced,
    which is what makes `strip_code` trustworthy on this corpus. Any future
    file that fails it is malformed (or has found a lexical case this module
    does not model) and must be reported, never silently translated.
    """
    st = NORMAL
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if st == NORMAL:
            if c == "$" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                st = IN_COMMENT
            elif c == "'":
                st = IN_STRING
        elif st == IN_COMMENT:
            if c == '"':
                if i + 1 < n and src[i + 1] == '"':
                    i += 2
                    continue
                st = NORMAL
        else:
            if c == "'":
                if i + 1 < n and src[i + 1] == "'":
                    i += 2
                    continue
                st = NORMAL
        i += 1
    return st == NORMAL


def split_top_level(src: str, sep: str) -> List[str]:
    """Split on `sep` occurrences that are outside comments and strings."""
    blanked = strip_code(src)
    parts: List[str] = []
    start = 0
    idx = blanked.find(sep)
    while idx != -1:
        parts.append(src[start:idx])
        start = idx + len(sep)
        idx = blanked.find(sep, start)
    parts.append(src[start:])
    return parts
