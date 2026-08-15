"""dolphin2mst — translate Dolphin 8 sources into house `.mst` (DD3).

    python cli.py --out <dir> <file-or-dir>...

Reports are the product, not a side effect. Two are written next to the output:

  * `_refusals.txt` — every construct the translator would not translate, with
    file:line and the rewrite class that refused. **Silence is the failure
    mode this project keeps paying for**, so a refusal is a first-class result:
    it means "a human must decide", never "skipped".
  * `_report.md` — per-file counts, class/method totals, and the refusal
    histogram, so a corpus re-run is diffable.

Generated `.mst` is an artifact: never hand-edit it. Fix the translator, or add
an overlay under `overlays/`.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from typing import Dict, List, Optional

import parse
import emit
import pools
from stlex import is_balanced
from chunks import read_source


def collect(paths: List[str], exts=(".cls", ".pax")) -> List[str]:
    """Gather sources. `.pax` counts: it is load-bearing source, not metadata —
    it carries the shared pools AND 177 loose `OS.UserLibrary` methods, so a
    `.cls`-only ingester silently loses the entire User32 binding."""
    out: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                parts = set(dp.replace("\\", "/").split("/"))
                if parts & {"Tests", "Deprecated", "Gdiplus"}:
                    continue
                out.extend(os.path.join(dp, f) for f in fn if f.endswith(exts))
        elif p.endswith(exts):
            out.append(p)
    return sorted(out)


def superclass_ivar_counts(parsed: Dict[str, parse.ParsedFile]) -> Dict[str, Optional[int]]:
    """Total declared ivars for each class, including its ancestors.

    `None` means "chain not fully known" — the caller must then refuse anything
    that depends on field placement, rather than assume zero.
    """
    by_name = {cd.name: cd for pf in parsed.values() for cd in
               (pf.classdefs or ([pf.classdef] if pf.classdef else []))}
    memo: Dict[str, Optional[int]] = {}

    def count(name: str, seen: Optional[set] = None) -> Optional[int]:
        if name in memo:
            return memo[name]
        seen = seen or set()
        if name in seen:                      # cycle: refuse rather than loop
            return None
        # `nil` is the hierarchy root: Dolphin declares Object as
        # `nil subclass: #'Core.Object'`, and the house dialect writes the same
        # thing (`nil subclass: Object [` in st/world/01_object.mst). Without
        # this case the root resolves to "unknown" and poisons every descendant
        # — measured: the first corpus run refused Graphics.Point>>x:y: with
        # "superclass ivar count unknown (Core.ArithmeticValue)" three levels
        # further down.
        if name == "nil":
            memo[name] = 0
            return 0
        cd = by_name.get(name)
        if cd is None:
            # A class outside the parsed set contributes an unknown number of
            # fields. Unknown is NOT zero: rewrites that depend on field
            # placement must refuse rather than assume. Pass the ancestors in
            # as reference inputs to resolve it.
            memo[name] = None
            return None
        up = count(cd.superclass, seen | {name})
        memo[name] = None if up is None else up + len(cd.ivars)
        return memo[name]

    for n in list(by_name):
        count(n)
    return memo


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="dolphin2mst")
    ap.add_argument("--out", required=True)
    # Reference inputs are PARSED but never EMITTED. They exist because field
    # placement (the D157 lowering) needs the whole superclass chain, and that
    # chain runs up into Dolphin's kernel — which this project replaces rather
    # than translates. Without the distinction, pulling `Core.Object` in to
    # resolve `Graphics.Point`'s ancestry also tried to translate it and
    # produced 39 "unmapped primitive" refusals for code we will never ship.
    ap.add_argument("--reference", action="append", default=[],
                    help="parse for the class hierarchy only; never emit")
    ap.add_argument("inputs", nargs="+")
    args = ap.parse_args(argv)

    files = collect(args.inputs)
    ref_files = collect(args.reference)
    if not files:
        print("dolphin2mst: no .cls inputs found", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)

    parsed: Dict[str, parse.ParsedFile] = {}
    reference: Dict[str, parse.ParsedFile] = {}
    unbalanced: List[str] = []
    for f in files + [r for r in ref_files if r not in files]:
        src = read_source(f)
        if not is_balanced(src):
            unbalanced.append(f)          # malformed, or a lexical case we do not model
            continue
        pf = parse.parse_file(f)
        (parsed if f in files else reference)[f] = pf

    # The hierarchy is resolved over BOTH sets; only `parsed` is emitted.
    ivars = superclass_ivar_counts({**reference, **parsed})
    renames: Dict[str, str] = {}           # DD2: zero collisions, so empty by measurement

    # Shared pools, gathered from EVERY parsed file (reference sources included:
    # the pools live in `.pax` manifests that are usually not translation
    # targets themselves).
    pool_table = pools.PoolTable()
    n_consts = 0
    for pf in list(reference.values()) + list(parsed.values()):
        for cd in pf.classdefs or ([pf.classdef] if pf.classdef else []):
            # EVERY class's own `classConstants:`, not just SharedPool subclasses.
            # The struct classes reach each other's field offsets as
            # `NMHDR._OffsetOf_hwndFrom`, so a class whose constants are not in
            # the table leaves that qualified reference unfolded — and it then
            # reaches the parser as `NMHDR` followed by `._OffsetOf_…`, which is
            # a syntax error. Measured on UI.View.
            if cd.class_constants and cd.class_constants != "{}":
                n_consts += pool_table.add(cd.name, cd.class_constants)

    by_name_all = {cd.name: cd
                   for pf in list(reference.values()) + list(parsed.values())
                   for cd in (pf.classdefs or ([pf.classdef] if pf.classdef else []))}

    # Loose methods, keyed by the class they are filed onto.
    loose: Dict[str, List[parse.Method]] = collections.defaultdict(list)
    for pf in parsed.values():
        for target, ms in pf.loose.items():
            loose[target].extend(ms)

    refusals: List[emit.Refusal] = []
    notes: List[str] = []
    written = 0
    adopted = 0
    per_file = []
    emitted_names = set()
    # `.cls` files first. A `.pax` manifest RE-DECLARES the classes its package
    # contains, so a class present in both must be emitted from its own `.cls` —
    # the authoritative source. Measured: a run over MVP/Base + MVP/Graphics with
    # the package manifest as an input produced 211 duplicate refusals, one per
    # class, purely from that overlap.
    for f, pf in sorted(parsed.items(), key=lambda kv: kv[0].endswith(".pax")):
        for cd in pf.classdefs or ([pf.classdef] if pf.classdef else []):
            if cd.superclass.endswith("SharedPool"):
                continue          # folded into constants; never emitted as a class
            extra = loose.pop(cd.name, [])
            adopted += len(extra)
            res = emit.emit_class(pf, renames, ivars, pool_table, extra, cd)
            refusals.extend(res.refusals)
            notes.extend(res.notes)
            name = emit.flatten_name(cd.name, renames)
            # LOAD ORDER IS DEPENDENCY ORDER. The layer loader takes a directory
            # and sorts by filename, so a class must sort AFTER its superclass or
            # it loads against a forward-reference stub and the hierarchy never
            # links. Measured: emitted alphabetically, ContainerView arrived
            # before View existed and `ShellView inheritsFrom: View` was false.
            # A zero-padded depth prefix makes alphabetical order correct.
            depth = 0
            walk, guard = cd.superclass, 0
            while walk and walk != "nil" and guard < 64:
                parent = by_name_all.get(walk)
                if parent is None:
                    break
                depth += 1
                walk, guard = parent.superclass, guard + 1
            fname = f"{depth:02d}_{name}.mst"
            if name in emitted_names:
                # Not a refusal when the loser is a `.pax` re-declaration of a
                # class that has its own `.cls` — that is the format working as
                # designed. Any other collision IS a refusal.
                if f.endswith(".pax"):
                    notes.append(f"{cd.name}: package re-declaration, "
                                 f"emitted from its own .cls")
                else:
                    refusals.append(emit.Refusal(f, "duplicate",
                                                 f"{cd.name} would overwrite {name}.mst"))
                continue
            emitted_names.add(name)
            with open(os.path.join(args.out, fname), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(res.text)
            written += 1
            n_methods = (len(pf.methods) if cd is pf.classdef else 0) + len(extra)
            per_file.append((name, n_methods, len(res.refusals)))

    # Loose methods whose target class was never translated are REPORTED, not
    # dropped: they are the User32 binding when the target is `OS.UserLibrary`.
    for target, ms in sorted(loose.items()):
        refusals.append(emit.Refusal(target, "orphan-loose-methods",
                                     f"{len(ms)} loose method(s) filed onto "
                                     f"'{target}', which was not translated"))

    with open(os.path.join(args.out, "_refusals.txt"), "w",
              encoding="utf-8", newline="\n") as fh:
        for r in refusals:
            fh.write(str(r) + "\n")

    hist = collections.Counter(r.rewrite for r in refusals)
    with open(os.path.join(args.out, "_report.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("# dolphin2mst run report\n\n")
        fh.write(f"- inputs: **{len(files)}** source files (`.cls` + `.pax`)\n")
        fh.write(f"- shared-pool constants available: **{n_consts}** "
                 f"from **{len(pool_table)}** pools\n")
        fh.write(f"- loose methods adopted from `.pax`: **{adopted}**\n")
        fh.write(f"- parsed: **{len(parsed)}**  (unbalanced/skipped: {len(unbalanced)})\n")
        fh.write(f"- emitted: **{written}** `.mst`\n")
        fh.write(f"- methods: **{sum(p[1] for p in per_file)}**\n")
        fh.write(f"- refusals: **{len(refusals)}**\n\n")
        if unbalanced:
            fh.write("## Unbalanced sources (never translated)\n\n")
            for u in unbalanced:
                fh.write(f"- `{u}`\n")
            fh.write("\n")
        fh.write("## Refusals by rewrite class\n\n| Rewrite | Count |\n|---|--:|\n")
        for k, v in hist.most_common():
            fh.write(f"| `{k}` | {v} |\n")
        if notes:
            fh.write("\n## Notes\n\n")
            for n in sorted(set(notes)):
                fh.write(f"- {n}\n")
        fh.write("\n## Per class\n\n| Class | Methods | Refusals |\n|---|--:|--:|\n")
        for name, nm, nr in sorted(per_file):
            fh.write(f"| `{name}` | {nm} | {nr} |\n")

    print(f"dolphin2mst: {written} classes, {sum(p[1] for p in per_file)} methods, "
          f"{len(refusals)} refusals -> {args.out}")
    for k, v in hist.most_common(8):
        print(f"    {k:18s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
