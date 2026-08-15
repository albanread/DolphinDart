"""Which corpus IVAR names collide with a unary method our Object carries?

    python tools/check_ivar_collisions.py "st/world;st/dolphin_compat" C:/projects/dsfork

A Dart field may not shadow an INHERITED method — class_finalizer.cc's
FindSuperOwnerOfFunction rejects it — but Smalltalk allows it and Dolphin
depends on it. The VM handles the collision (st_loader.cc gives such a field a
synthetic `name$iv` spelling; st_flow_graph_builder.cc's IvarOffset resolves
both), so this script is not a gate on correctness.

It is a gate on SURPRISE. Every unary method added to `Object` in the compat
kernel silently widens the set of corpus ivars that must be renamed, and the
failure mode without the VM fix was a class that would not finalize — reported
against the CLASS, not against the compat method that caused it. Run this after
touching Object's protocol; the numbers belong in the sprint notes.

Only UNARY selectors can collide: a keyword method's mangled name carries an
underscore, and no ivar is spelled that way.
"""
from __future__ import annotations

import collections
import os
import re
import sys


def object_unary_methods(world_dirs):
    """Every unary selector our reopened `Object` carries, across the layers."""
    found = {}
    for d in world_dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".mst"):
                continue
            path = os.path.join(d, f)
            src = open(path, encoding="utf-8").read()
            for m in re.finditer(r"nil subclass: Object \[", src):
                i = m.end() - 1
                depth = 0
                for j in range(i, len(src)):
                    if src[j] == "[":
                        depth += 1
                    elif src[j] == "]":
                        depth -= 1
                        if depth == 0:
                            break
                body = src[i + 1:j]
                for mm in re.finditer(r"^\s{0,8}([a-z][A-Za-z0-9]*)\s*\[", body, re.M):
                    found.setdefault(mm.group(1), path)
    return found


def corpus_ivars(root):
    """ivar name -> the classes declaring it, across `.cls` and `.pax`."""
    owner = collections.defaultdict(set)
    for dp, dn, fn in os.walk(root):
        if ".git" in dp.replace(os.sep, "/").split("/"):
            continue
        for f in fn:
            if not f.endswith((".cls", ".pax")):
                continue
            try:
                src = open(os.path.join(dp, f), encoding="utf-8",
                           errors="replace").read()
            except OSError:
                continue
            for m in re.finditer(
                    r"subclass:\s*#?'?([\w.]+)'?\s*\n?\s*"
                    r"instanceVariableNames:\s*'([^']*)'", src):
                for iv in m.group(2).split():
                    owner[iv].add(m.group(1))
    return owner


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    world_dirs = [d.strip() for d in argv[0].replace("\\", "/").split(";")]
    methods = object_unary_methods(world_dirs)
    ivars = corpus_ivars(argv[1])
    print("unary methods our Object carries: %d" % len(methods))
    for n in sorted(methods):
        print("   %-28s %s" % (n, methods[n]))
    hits = sorted(n for n in ivars if n in methods)
    print("\ncolliding ivar names: %d" % len(hits))
    for n in hits:
        cs = sorted(ivars[n])
        print("   %-16s %2d class(es): %s%s"
              % (n, len(cs), ", ".join(cs[:6]), " ..." if len(cs) > 6 else ""))
    if hits:
        print("\nEach of these gets a synthetic `name$iv` field (st_loader.cc).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
