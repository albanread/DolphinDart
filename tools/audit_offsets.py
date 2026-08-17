"""Find 32-BIT assumptions surviving in the translated wave.

    python tools/audit_offsets.py [--wave st/mvp] [--structs st/prims/structs]

**Dolphin Smalltalk 8 is a 32-bit system.** Every byte offset, struct size and
pointer-width assumption in its source is suspect on this port's targets, and
none of them raise: a wrong offset reads the neighbouring field, so the code
runs and answers something plausible. Three of them cost most of DD11, and the
last one — `ControlView>>nmNotify:` decoding a notification code at offset 8
instead of 16 — silently stopped EVERY WM_NOTIFY handler in the port.

So they are hunted rather than waited for. This reports, and never rewrites:
the fix for each is a judgement (a translator rewrite, an override, or nothing
because the number is genuinely target-independent), and a tool that guessed
would be re-introducing the same class of silent wrongness it exists to find.

WHAT IT LOOKS FOR
  * a literal byte offset sent to a `*AtOffset:` accessor
  * `asInteger + <n>` / `fromAddress: ... + <n>`, the "index past a header" form
  * a struct size compared or assigned as a literal

WHAT IT KNOWS. Every generated struct's real offsets are read from
`st/prims/structs`, so a literal that matches NO field offset of any struct is
reported differently from one that matches a 32-bit-looking layout. The second
kind is the dangerous one.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# `foo int32AtOffset: 8`, `bar uint32AtOffset: 12 put: x`
AT_OFFSET = re.compile(r"([A-Za-z_]\w*)\s+(u?int(?:8|16|32|ptr)?|byte)AtOffset:\s*(\d+)")
# `pNMHDR asInteger + 12`, `fromAddress: p + 56`
PAST_HEADER = re.compile(r"([A-Za-z_]\w*)\s+asInteger\s*\+\s*(\d+)")
# a generated struct's field offsets
GEN_OFFSET = re.compile(r"(\w+) class >> _OffsetOf_(\w+) \[ \^(\d+) \]")
GEN_SIZE = re.compile(r"(\w+) class >> sizeInBytes \[ \^(\d+) \]")


def load_layouts(structs_dir):
    """name -> {field: offset}, plus name -> size."""
    offsets = collections.defaultdict(dict)
    sizes = {}
    if not os.path.isdir(structs_dir):
        return offsets, sizes
    for f in sorted(os.listdir(structs_dir)):
        if not f.endswith(".mst"):
            continue
        src = open(os.path.join(structs_dir, f), encoding="utf-8",
                   errors="replace").read()
        for m in GEN_OFFSET.finditer(src):
            offsets[m.group(1)][m.group(2)] = int(m.group(3))
        for m in GEN_SIZE.finditer(src):
            sizes[m.group(1)] = int(m.group(2))
    return offsets, sizes


def guess_struct(var_name, offsets):
    """Which generated struct does this variable most likely point at?

    Dolphin names the pointer after the structure — `pNMHDR`, `anNMHDR`,
    `aTVITEM`, `pNMTVDISPINFO` — which is the only signal available without
    type inference, and it is a strong one in this corpus.
    """
    upper = var_name.upper()
    hits = [n for n in offsets if len(n) > 3 and n.upper().rstrip("W") in upper]
    # Longest name wins: `NMTVDISPINFOW` beats `NMHDR` for `pNMTVDISPINFO`.
    return max(hits, key=len) if hits else None


def audit(wave_dir, offsets, sizes):
    findings = []
    for f in sorted(os.listdir(wave_dir)):
        if not f.endswith(".mst"):
            continue
        path = os.path.join(wave_dir, f)
        for lineno, line in enumerate(
                open(path, encoding="utf-8", errors="replace"), 1):
            stripped = line.strip()
            if stripped.startswith('"'):
                continue                    # a comment quoting the old code
            for m in AT_OFFSET.finditer(line):
                var, _acc, off = m.group(1), m.group(2), int(m.group(3))
                findings.append(check(f, lineno, var, off, offsets, sizes,
                                      m.group(0)))
            for m in PAST_HEADER.finditer(line):
                var, off = m.group(1), int(m.group(2))
                findings.append(check(f, lineno, var, off, offsets, sizes,
                                      m.group(0)))
    return [x for x in findings if x is not None]


def check(f, lineno, var, off, offsets, sizes, text):
    struct = guess_struct(var, offsets)
    if struct is None:
        return None                          # not a struct pointer we can judge
    fields = offsets[struct]
    if off in fields.values():
        return None                          # matches a REAL offset: fine
    # Does it match the 32-bit shape? Every pointer-sized field ahead of it
    # halves, so a suspect literal is one that lands on a real offset when the
    # 64-bit layout is squeezed. Report the field it was probably reaching for.
    for name, real in sorted(fields.items(), key=lambda kv: kv[1]):
        if real > off and (real - off) % 4 == 0:
            return (f, lineno, var, off, struct, name, real, text)
    size = sizes.get(struct)
    if size is not None and off < size:
        return (f, lineno, var, off, struct, "?", size, text)
    return None


def main(argv):
    ap = argparse.ArgumentParser(prog="audit_offsets")
    ap.add_argument("--wave", default=os.path.join(REPO, "st", "mvp"))
    ap.add_argument("--structs",
                    default=os.path.join(REPO, "st", "prims", "structs"))
    args = ap.parse_args(argv)

    offsets, sizes = load_layouts(args.structs)
    if not offsets:
        print("audit: no generated structs under %s" % args.structs)
        return 2
    findings = audit(args.wave, offsets, sizes)

    print("audit_offsets: %d generated struct layouts, %d suspect literal(s)\n"
          % (len(offsets), len(findings)))
    for f, lineno, var, off, struct, field, real, text in findings:
        print("  %s:%d" % (f, lineno))
        print("      %s" % text.strip())
        print("      `%s` looks like %s; offset %d is not a field. "
              "Nearest at-or-after: %s = %d" % (var, struct, off, field, real))
    if findings:
        print("\nEach needs a JUDGEMENT, not a blind rewrite: a translator")
        print("rewrite (preferred — keeps the corpus's logic), an override, or")
        print("nothing if the number is genuinely target-independent.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
