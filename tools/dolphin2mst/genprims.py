"""Generate Win32 prim bindings from Dolphin's own external methods (DD6b).

    python genprims.py --out <dir> --corpus <dolphin-root> [--winkb <db>]

**Corpus-driven, not catalogue-driven.** winkb holds 18,271 functions; the port
needs the ones Dolphin actually declares. Every `<stdcall:`/`<cdecl:>` pragma in
the corpus IS the specification — function name, return type, argument types, in
the order the image will call them — so the generator reads those and emits a
house external method per declaration. winkb is used to *validate* (does the
function exist, does the arity agree), not to enumerate.

Emits, per Dolphin library class:

    Object subclass: UserLibrary [
        UserLibrary class >> getSystemMetrics: nIndex [
            <primitive: FFI function: #GetSystemMetrics ret: #g args: #( g )>
        ]
        ...
    ]

plus `_generated.md` (what was emitted, what refused and why) and
`prim_manifest.mst` — the harness's input, listing every generated function so
the resolve-all tier can prove each one is really callable.
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
import ffitypes

PRAGMA = re.compile(r"<\s*(?:(virtual|overlap)\s+)?(stdcall|cdecl)\s*:\s*([^<>]*)>")


class Decl:
    __slots__ = ("cls", "selector", "args", "func", "ret", "argtypes", "modifier",
                 "conv", "where")

    def __init__(self, cls, selector, args, func, ret, argtypes, modifier, conv, where):
        self.cls, self.selector, self.args = cls, selector, args
        self.func, self.ret, self.argtypes = func, ret, argtypes
        self.modifier, self.conv, self.where = modifier, conv, where


def collect_decls(root: str) -> Tuple[List[Decl], List[str]]:
    """Every external method in the corpus, with the class it is filed onto."""
    decls: List[Decl] = []
    notes: List[str] = []
    for dp, dn, fn in os.walk(root):
        if set(dp.replace("\\", "/").split("/")) & {"Tests", "Deprecated", "Gdiplus"}:
            continue
        for f in sorted(fn):
            if not f.endswith((".cls", ".pax")):
                continue
            path = os.path.join(dp, f)
            pf = parse.parse_file(path)
            groups = []
            if pf.classdef:
                groups.append((pf.classdef.name, pf.methods))
            for target, ms in pf.loose.items():
                groups.append((target, ms))
            for cls, methods in groups:
                for m in methods:
                    for pg in m.pragmas:
                        mm = PRAGMA.match(pg)
                        if not mm:
                            continue
                        toks = mm.group(3).split()
                        if len(toks) < 2:
                            notes.append(f"{path}:{m.line}: malformed pragma {pg[:50]}")
                            continue
                        decls.append(Decl(cls, m.selector, m.arg_names, toks[1],
                                          toks[0], toks[2:], mm.group(1),
                                          mm.group(2), f"{path}:{m.line}"))
    return decls, notes


def winkb_index(db_path: str) -> Optional[Dict[str, Tuple[str, int, int, int]]]:
    """function_name -> (dll, argc, set_last_error, is_variadic). None if absent."""
    if not db_path or not os.path.exists(db_path):
        return None
    import sqlite3
    c = sqlite3.connect(db_path)
    idx: Dict[str, Tuple[str, int, int, int]] = {}
    q = ("select f.function_name, f.dll_name, f.set_last_error, f.is_variadic, "
         "(select count(*) from function_params p where p.function_id=f.function_id) "
         "from functions f")
    for name, dll, sle, var, argc in c.execute(q):
        # First definition wins; the DB carries per-source duplicates.
        idx.setdefault(name, (dll, argc, sle, var))
    return idx


def house_pattern(selector: str, args: List[str]) -> str:
    if args and ":" in selector:
        parts = selector.split(":")[:-1]
        return " ".join(f"{k}: {a}" for k, a in zip(parts, args))
    if args:
        return f"{selector} {args[0]}"
    return selector


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="genprims")
    ap.add_argument("--out", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--winkb", default=r"C:\projects\windows_api\windows_api.db")
    args = ap.parse_args(argv)

    decls, notes = collect_decls(args.corpus)
    kb = winkb_index(args.winkb)
    os.makedirs(args.out, exist_ok=True)

    by_class: Dict[str, List[Tuple[Decl, str, str]]] = collections.defaultdict(list)
    refused: List[Tuple[Decl, str]] = []
    kb_missing: List[Decl] = []
    kb_arity: List[Tuple[Decl, int]] = []
    seen = set()

    for d in decls:
        if d.modifier == "overlap":
            refused.append((d, "`overlap` is an asynchronous call — v1 is synchronous"))
            continue
        if d.modifier == "virtual":
            refused.append((d, "`virtual` is a COM vtable call — a v1 non-goal"))
            continue
        if not re.match(r"^[A-Za-z_]\w*$", d.func):
            # Dolphin can bind an ORDINAL export (`<stdcall: ... 12 ...>`), which
            # our floor resolves by name only. Emitting a call to a "function"
            # named `12` would fail at runtime with a confusing message; refuse
            # it here with the real reason. One site in the corpus
            # (OS.ShlwapiLibrary), found by the winkb cross-check.
            refused.append((d, f"ordinal export '{d.func}' — the floor resolves "
                               f"by name only"))
            continue
        rc, why = ffitypes.ret_code(d.ret)
        if rc is None:
            refused.append((d, f"return {why}"))
            continue
        codes: List[str] = []
        bad = None
        for t in d.argtypes:
            c, w = ffitypes.arg_code(t)
            if c is None:
                bad = w
                break
            codes.append(c)
        if bad:
            refused.append((d, f"argument {bad}"))
            continue
        if len(codes) != len(d.args):
            refused.append((d, f"pragma declares {len(codes)} argument types but the "
                               f"selector takes {len(d.args)}"))
            continue
        if kb is not None:
            info = kb.get(d.func)
            if info is None:
                kb_missing.append(d)
            else:
                dll, argc, sle, var = info
                if var:
                    refused.append((d, "winkb says variadic — the ARM64 register/stack "
                                       "split differs from the fixed case"))
                    continue
                if argc != len(codes):
                    kb_arity.append((d, argc))
        key = (d.cls, d.selector)
        if key in seen:
            continue
        seen.add(key)
        by_class[d.cls].append((d, rc, "".join(codes)))

    written = 0
    total_methods = 0
    manifest: List[Tuple[str, str, int]] = []
    for cls, items in sorted(by_class.items()):
        base = cls.rsplit(".", 1)[-1]
        lines = [f'"GENERATED by tools/dolphin2mst/genprims.py from the Dolphin corpus.',
                 f' Do not hand-edit: re-run the generator. {len(items)} external methods."',
                 "",
                 f"Object subclass: {base} ["]
        for d, rc, codes in sorted(items, key=lambda x: x[0].selector):
            argspec = " ".join(codes) if codes else ""
            lines.append(f"    {base} class >> {house_pattern(d.selector, d.args)} [")
            lines.append(f"        <primitive: FFI function: #{d.func} ret: #{rc} "
                         f"args: #( {argspec} )>")
            lines.append("    ]")
            manifest.append((d.func, base, len(codes)))
            total_methods += 1
        lines.append("]")
        with open(os.path.join(args.out, base + ".mst"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        written += 1

    # The harness input: every generated function, so the resolve-all tier can
    # prove each is really present in the system DLLs.
    with open(os.path.join(args.out, "prim_manifest.mst"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write('"GENERATED — every prim this build binds, for the resolve-all\n'
                 ' tier of the harness. Each entry is #(functionName class argc)."\n\n')
        fh.write("Object subclass: PrimManifest [\n")
        fh.write("    PrimManifest class >> all [\n        ^#(\n")
        for func, base, argc in sorted(set(manifest)):
            fh.write(f"            #(#{func} #{base} {argc})\n")
        fh.write("        )\n    ]\n]\n")

    hist = collections.Counter(r for _, r in refused)
    with open(os.path.join(args.out, "_generated.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("# Generated Win32 prims\n\n")
        fh.write(f"- external methods found in the corpus: **{len(decls)}**\n")
        fh.write(f"- **generated: {total_methods}** across **{written}** library classes\n")
        fh.write(f"- refused: **{len(refused)}**\n")
        if kb is not None:
            fh.write(f"- winkb cross-check: **{len(kb_missing)}** not found, "
                     f"**{len(kb_arity)}** arity disagreements\n")
        else:
            fh.write("- winkb cross-check: **skipped** (database not found)\n")
        fh.write("\n## Refusals by reason\n\n| Reason | Count |\n|---|--:|\n")
        for r, n in hist.most_common():
            fh.write(f"| {r} | {n} |\n")
        if kb_arity:
            fh.write("\n## winkb arity disagreements (pragma vs metadata)\n\n")
            for d, argc in kb_arity[:40]:
                fh.write(f"- `{d.func}`: pragma {len(d.argtypes)}, winkb {argc} "
                         f"— `{d.where}`\n")
        if kb_missing:
            fh.write(f"\n## Not in winkb ({len(kb_missing)})\n\n")
            for d in kb_missing[:40]:
                fh.write(f"- `{d.func}` (`{d.cls}`)\n")
        fh.write("\n## Per class\n\n| Class | Methods |\n|---|--:|\n")
        for cls, items in sorted(by_class.items()):
            fh.write(f"| `{cls}` | {len(items)} |\n")

    with open(os.path.join(args.out, "_refusals.txt"), "w",
              encoding="utf-8", newline="\n") as fh:
        for d, r in refused:
            fh.write(f"{d.where}: {d.cls}>>{d.selector} [{d.func}] {r}\n")

    print(f"genprims: {total_methods} prims in {written} classes, "
          f"{len(refused)} refused -> {args.out}")
    for r, n in hist.most_common(6):
        print(f"    {n:4d}  {r[:66]}")
    if kb is not None:
        print(f"    winkb: {len(kb_missing)} unknown, {len(kb_arity)} arity mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
