"""Differential struct-layout check: OUR generated structs vs REAL Dolphin 8.

    python tools/conform_structs.py            # summary + anything to review
    python tools/conform_structs.py -v         # every struct, including matches

WHAT IT PROVES, AND WHAT IT CANNOT. The oracle image is **32-bit Dolphin
8.2.3** (`VMConstants.IntPtrMask` answers 16rFFFFFFFF, `HalfPtrBits` 16), and
this port targets ARM64. A size difference is therefore only interesting when
the struct cannot legitimately differ, and this tool draws that line for you
instead of leaving 40-odd rows to be triaged by hand every run.

THREE OPINIONS, not two. Dolphin says what its own `defineFields` built,
winkb says what the 64-bit SDK ABI is, and the generator says what we emitted.
Printing all three is what makes a disagreement diagnosable:

  POINTER-BEARING (transitively)  contains, at any depth, a pointer, a handle,
      or a pointer-sized integer. MUST differ between 32- and 64-bit; a match
      would be the suspicious result. Transitivity is the whole game here —
      every `NM*` notification struct embeds `NMHDR`, whose `hwndFrom` is a
      pointer, so a top-level-only scan calls nine of them pointer-free and
      files nine false alarms. (`NMHDR` is 12 bytes on Win32 and 24 on x64;
      one literal `8` for its `code` offset silently disabled every WM_NOTIFY
      handler in this port once already.)

  POINTER-FREE AND EQUAL  the common case, and the one that carries the
      evidence: 140-odd structs where a 32-bit image and a 64-bit port agree
      to the byte.

  POINTER-FREE AND DIFFERENT  the only bucket worth reading. Either the SDK
      changed the struct since Dolphin wrapped it (Dolphin's `LVHITTESTINFO`
      predates `iGroup`), or one of the two is wrong about packing — which is
      a real finding in both directions, because winkb does not model
      `#pragma pack` and Dolphin does.

Dolphin answering `byteSize` 0 means the class exists but defines no fields —
`OS.POINT` is one, because Dolphin uses `POINTL` — so it is counted as not
defined rather than as a zero-sized mismatch.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from oracle import ask                                    # noqa: E402

STRUCTS = os.path.join(REPO, "st", "prims", "structs")
WINKB = r"C:\projects\windows_api\windows_api.db"

SIZE_RE = re.compile(r"class >> sizeInBytes \[ \^(\d+) \]")
# Dolphin spells three GDI structs with an `L`; winkb carries the plain name.
ALIAS = {"RECTL": "RECT", "POINTL": "POINT", "SIZEL": "SIZE"}


def scan():
    """name -> our emitted sizeInBytes."""
    out = {}
    for fn in sorted(os.listdir(STRUCTS)):
        if not fn.endswith(".mst"):
            continue
        with open(os.path.join(STRUCTS, fn), encoding="utf-8",
                  errors="replace") as fh:
            m = SIZE_RE.search(fh.read())
        if m:
            out[fn[:-4]] = int(m.group(1))
    return out


class Kb:
    """winkb, with transitive pointer-bearing memoised."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self._ptr = {}
        self._size = {}

    def size(self, name):
        if name not in self._size:
            row = self.db.execute(
                "select size_bits from types where type_name=? and kind='struct'"
                " and size_bits is not null", (ALIAS.get(name, name),)).fetchone()
            self._size[name] = row[0] // 8 if row else None
        return self._size[name]

    def fields(self, name):
        return [r[0] for r in self.db.execute(
            "select f.type_name from struct_fields f "
            "join types t on t.type_id=f.struct_type_id "
            "where t.type_name=? order by f.ordinal",
            (ALIAS.get(name, name),))]

    def has_pointer(self, name, seen=None):
        key = ALIAS.get(name, name)
        if key in self._ptr:
            return self._ptr[key]
        seen = seen or set()
        if key in seen:
            return False
        seen.add(key)
        self._ptr[key] = False                 # break cycles while recursing
        found = False
        for ft in self.fields(key):
            if not ft:
                continue
            bare = ft.rsplit(".", 1)[-1]
            if ft.endswith("*") or bare in ("isize", "usize", "i64", "u64"):
                found = True
                break
            # A nested struct, a handle typedef (one pointer-sized `Value`
            # field), or a callback — all reached by the same recursion.
            if self.fields(bare) and self.has_pointer(bare, seen):
                found = True
                break
        self._ptr[key] = found
        return found


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--only", help="check just this struct")
    args = ap.parse_args(argv)

    ours = scan()
    if args.only:
        ours = {k: v for k, v in ours.items() if k == args.only}
    names = sorted(ours)
    kb = Kb(WINKB)

    print("asking Dolphin 8 for %d struct sizes ..." % len(names))
    answers = ask(["OS.%s byteSize" % n for n in names], timeout=900)

    agree, ptr_differ, review, absent, unknown = [], [], [], [], []
    for name, ans in zip(names, answers):
        mine = ours[name]
        if ans is None:
            unknown.append(name)
            continue
        try:
            theirs = int(ans)
        except (TypeError, ValueError):
            absent.append(name)
            continue
        if theirs == 0:                        # declared, but no fields
            absent.append(name)
        elif theirs == mine:
            agree.append((name, mine))
        elif kb.has_pointer(name):
            ptr_differ.append((name, theirs, mine))
        else:
            review.append((name, theirs, mine, kb.size(name)))

    print("")
    print("  agree, byte for byte ......................... %d" % len(agree))
    print("  differ, POINTER-BEARING (expected 32 vs 64) .. %d" % len(ptr_differ))
    print("  differ, pointer-free — REVIEW ................ %d" % len(review))
    print("  not defined by Dolphin ....................... %d" % len(absent))
    if unknown:
        print("  NO ANSWER (run died?) ........................ %d" % len(unknown))

    if review:
        print("")
        print("REVIEW — pointer-free yet different. winkb is the 64-bit SDK ABI;")
        print("where ours == winkb the disagreement is Dolphin's struct being")
        print("older or packed, which is a finding about the corpus, not a bug here.")
        print("  %-28s %9s %9s %9s" % ("struct", "dolphin", "ours", "winkb"))
        for name, theirs, mine, kbs in sorted(review):
            flag = "" if kbs == mine else "   <-- ours disagrees with winkb too"
            print("  %-28s %9d %9d %9s%s"
                  % (name, theirs, mine, kbs if kbs is not None else "-", flag))
    if args.verbose:
        print("")
        print("POINTER-BEARING (difference expected):")
        for name, theirs, mine in sorted(ptr_differ):
            print("  %-28s dolphin32=%-7d ours64=%d" % (name, theirs, mine))
        print("")
        print("AGREE (%d):" % len(agree))
        for name, size in agree:
            print("  %-28s %d" % (name, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
