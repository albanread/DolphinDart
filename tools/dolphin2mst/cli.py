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


def inherited_pool_chain(by_name: Dict[str, parse.ClassDef],
                         name: str) -> List[str]:
    """The pools an ancestor of `name` contributes, nearest ancestor first.

    Smalltalk resolves a bare constant through the class's own pools, then its
    superclass's, on up — `imports:` is not the whole story for any class with
    a parent. Each ancestor contributes its own `classConstants:` (keyed by
    class name in the PoolTable) followed by its declared imports, which is the
    order the binding search visits them in.
    """
    out: List[str] = []
    seen = set()
    cd = by_name.get(name)
    guard = 0
    while cd is not None and guard < 64:
        cd = by_name.get(cd.superclass)
        guard += 1
        if cd is None:
            break
        for p in [cd.name] + list(cd.imports):
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


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
    ap.add_argument("--loose", action="append", default=[],
                    help="emit this class's LOOSE methods as a reopen, even "
                         "though the class itself is not translated "
                         "(OS.UserLibrary: Dolphin's convenience layer over "
                         "the generated prims)")
    ap.add_argument("--reopen", action="append", default=[],
                    help="translate this class's OWN methods as a reopen "
                         "rather than a definition, because this project "
                         "GENERATES the class (OS.LVCOLUMNW: genstructs "
                         "builds the layout, the .cls carries the methods)")
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

    # Class BASE name -> its declared class variables, over BOTH sets. This is
    # what tells a qualified class-variable read (`Point.Zero`) apart from a
    # namespaced class reference (`Graphics.Point`) — the second segment is
    # only a class variable if its owner actually declares it.
    classvar_owners: Dict[str, set] = {}
    for pf in list(reference.values()) + list(parsed.values()):
        for cd in (pf.classdefs or ([pf.classdef] if pf.classdef else [])):
            if cd.cvars:
                base = cd.name.rsplit(".", 1)[-1]
                classvar_owners.setdefault(base, set()).update(cd.cvars)

    by_name_all_early = {cd.name: cd
                         for pf in list(reference.values()) + list(parsed.values())
                         for cd in (pf.classdefs or ([pf.classdef] if pf.classdef else []))}
    # Class BASE name -> the pool keys to search for one of ITS constants,
    # nearest first: itself, then every ancestor. Class constants are
    # inherited, so `CreateWindow.UseDefaultGeometry` must find the one
    # `CreateWindowFunction` declares.
    constant_chains: Dict[str, List[str]] = {}
    for full, cd in by_name_all_early.items():
        base = full.rsplit(".", 1)[-1]
        chain = [full]
        walk, guard = cd.superclass, 0
        while walk and walk != "nil" and guard < 64:
            chain.append(walk)
            parent = by_name_all_early.get(walk)
            if parent is None:
                break
            walk, guard = parent.superclass, guard + 1
        constant_chains[base] = chain

    by_name_all = {cd.name: cd
                   for pf in list(reference.values()) + list(parsed.values())
                   for cd in (pf.classdefs or ([pf.classdef] if pf.classdef else []))}

    # Loose methods, keyed by the class they are filed onto.
    reopen_targets = set(args.reopen or [])
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
        # A `.pax` NEVER emits a class. It is a package MANIFEST: it
        # re-declares every class the package contains, including ones whose
        # authoritative definition is a `.cls` elsewhere — or, worse, ones this
        # project GENERATES. Passing `Dolphin MVP Base.pax` in for its loose
        # methods emitted its re-declaration of `OS.MENUITEMINFOW` into the
        # output, where it loaded after and overwrote the struct genstructs
        # builds from winkb — and `MENUITEMINFOW class >> sizeInBytes`
        # disappeared, taking the menu gate with it.
        #
        # Its loose methods are still adopted (that is the whole reason to
        # pass one), and its pools and hierarchy still inform the run.
        if f.endswith(".pax"):
            continue
        for cd in pf.classdefs or ([pf.classdef] if pf.classdef else []):
            if cd.superclass.endswith("SharedPool"):
                continue          # folded into constants; never emitted as a class
            extra = loose.pop(cd.name, [])
            adopted += len(extra)
            # REOPEN, not define. `OS.LVCOLUMNW` is a class this project
            # GENERATES — genstructs builds it from winkb with typed accessors
            # at real offsets — but its `.cls` also carries ordinary Smalltalk
            # methods that nothing else can supply: `LVCOLUMNW class >>
            # fromColumn:` is how `UI.ListView` fills a column structure
            # before SendMessage, and without it the ListView cannot be
            # created at all.
            #
            # Emitting it as a DEFINITION would redefine the class after
            # genstructs and drop the layout, which is the failure the `.pax`
            # guard above records for `OS.MENUITEMINFOW`. So the same
            # `emit_loose` path the `OS.UserLibrary` convenience layer uses is
            # taken, with the class's own methods instead of loose ones.
            if cd.name in reopen_targets:
                own = list(pf.methods) if cd is pf.classdef else []
                # `ExternalMemory` because that is what genstructs gives
                # every struct it emits; the `.cls` says `External.Structure`,
                # which is Dolphin's name for the same role and does not exist
                # here.
                res = emit.emit_loose(
                    emit.flatten_name(cd.name, renames), cd, own + extra,
                    renames, pool_table, classvar_owners, constant_chains,
                    inherited_pool_chain(by_name_all, cd.name),
                    force_class_side=False, reopen_super="ExternalMemory")
                refusals.extend(res.refusals)
                notes.extend(res.notes)
                nm = emit.flatten_name(cd.name, renames)
                fname = f"91_{nm}_reopen.mst"
                with open(os.path.join(args.out, fname), "w",
                          encoding="utf-8", newline="\n") as fh:
                    fh.write(res.text)
                written += 1
                per_file.append((nm + " (reopen)", len(own) + len(extra),
                                 len(res.refusals)))
                continue
            res = emit.emit_class(pf, renames, ivars, pool_table, extra, cd,
                                  inherited_pool_chain(by_name_all, cd.name),
                                  classvar_owners, constant_chains)
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

    # Loose methods whose target class was never translated are either EMITTED
    # AS A REOPEN (when the caller names the class with --loose) or REPORTED.
    #
    # `OS.UserLibrary` is the case that matters: 177 loose methods in the
    # `.pax` are Dolphin's own CONVENIENCE layer over the raw prims —
    # `getWindowText: hWnd` answering a String on top of the three-argument
    # API call, and its kin. `genprims` builds UserLibrary from the pragmas
    # and so knows nothing about them, and `UI.View` calls them constantly.
    # Emitting them as a reopen puts Dolphin's own convenience code back on
    # top of the generated floor, which is where it belongs.
    for target in (args.loose or []):
        ms = loose.pop(target, None)
        if not ms:
            notes.append(f"--loose {target}: no loose methods found")
            continue
        cls_name = emit.flatten_name(target, renames)
        cd = by_name_all.get(target)
        # The INHERITED pool chain, exactly as the class path above gets it.
        # Loose methods are ordinary methods of this class and resolve bare
        # constants the same way it does — `OS.UserLibrary` declares only
        # `imports: #(#{OS.MessageBoxConstants private})`, and its
        # `getWindowStyle:` writes `GWL_STYLE`, which it inherits. Folding only
        # the declared imports left that name bare, and a bare name is nil at
        # runtime, and nil reached the FFI floor as `non-integer argument` from
        # inside Dolphin's layout code — three layers from the cause.
        # A LIBRARY facade takes every loose method class-side, because this
        # port's `default` answers the class itself (see emit_loose). Any
        # other target keeps the side the `.pax` filed it on — `Core.Object`
        # gets `asValue` as an instance method, which is the only way `nil
        # asValue` can work.
        is_library = cls_name.endswith("Library")
        res = emit.emit_loose(cls_name, cd, ms, renames, pool_table,
                              classvar_owners, constant_chains,
                              inherited_pool_chain(by_name_all, target),
                              force_class_side=is_library)
        refusals.extend(res.refusals)
        fname = f"90_{cls_name}_loose.mst"
        with open(os.path.join(args.out, fname), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(res.text)
        written += 1
        per_file.append((cls_name + " (loose)", len(ms), len(res.refusals)))

    # The rest are REPORTED, not dropped.
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
