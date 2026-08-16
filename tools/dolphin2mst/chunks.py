"""Dolphin bang-chunk reader (DD3).

The `.cls`/`.pax` file format, as measured on the corpus (DD2):

* UTF-8, **usually** with a BOM — 1084 of 1087 files have one, three do not
  (the Dolphin-7-era IP-address control). `utf-8-sig` tolerates both, which is
  why we decode with it rather than checking for a BOM.
* CRLF line endings. Normalised to LF here; emission re-applies whatever the
  writer wants.
* Chunks are terminated by `!`, and a literal bang inside a chunk is written
  `!!`. Un-escaping is therefore part of *reading*, not of parsing — a chunk
  splitter that scans for a bare `!` without honouring the doubling will split
  a method in half at the first `!!` it meets.

Nothing here knows what a chunk *means*; see `parse.py`.
"""
from __future__ import annotations

from typing import Iterator, List, NamedTuple


class Chunk(NamedTuple):
    text: str      # the chunk body, bangs un-escaped
    line: int      # 1-based line where the chunk starts (for reports)


def read_source(path: str) -> str:
    """Decode a Dolphin source file, BOM optional, to LF line endings.

    UTF-8 first, then CP1252. The corpus is not uniformly UTF-8 — parts of it
    predate that being the default, and a single stray 0xB4 (an acute accent
    in CP1252) was enough to abort a whole `genprims` run with a decode error
    pointing at a byte offset. CP1252 is the honest second guess for
    Dolphin-era Windows sources, and it cannot itself fail: every byte maps.

    Deliberately NOT `errors="replace"`. That would substitute U+FFFD into
    source this project then translates — corruption with no diagnostic, which
    is the failure mode the translator exists to avoid.
    """
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_chunks(src: str) -> List[Chunk]:
    """Split bang-chunk source into chunks, un-escaping `!!` to `!`.

    A single `!` ends the chunk; `!!` is a literal bang and does NOT.
    """
    out: List[Chunk] = []
    buf: List[str] = []
    line = 1
    start_line = 1
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == "!":
            if i + 1 < n and src[i + 1] == "!":
                buf.append("!")
                i += 2
                continue
            text = "".join(buf)
            if text.strip():
                out.append(Chunk(text, start_line))
            buf = []
            i += 1
            # a chunk boundary consumes the newline that follows it, if any
            while i < n and src[i] == "\n":
                line += 1
                i += 1
            start_line = line
            continue
        if c == "\n":
            line += 1
        buf.append(c)
        i += 1
    tail = "".join(buf)
    if tail.strip():
        out.append(Chunk(tail, start_line))
    return out


def iter_chunks(path: str) -> Iterator[Chunk]:
    yield from split_chunks(read_source(path))
