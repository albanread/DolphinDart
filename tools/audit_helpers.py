"""Find .mst method definitions whose selector is a UNIVERSAL HELPER.

    python tools/audit_helpers.py [--quiet]

THE TRAP, which has now cost three separate debugging sessions: the IL builder
rewrites ~55 selectors AT THE CALL SITE (`{"asInteger", "stTruncated", 0}` and
friends in st_flow_graph_builder.cc). A send of one of these never performs a
Smalltalk lookup — it calls the Dart helper directly. So a method of that name
defined in an .mst file loads without complaint and is reached ONLY if the
helper's slow path happens to fall through to ST dispatch for that receiver.

  * `Object>>value [ ^self ]` in the compat kernel recursed through stValue0
    and took out every MVP gate with a blown stack.
  * `ExternalMemory>>asInteger [ ^address ]` was simply never called; the
    helper routed to `.truncated()` and every WM_NOTIFY handler died.

The severity depends on the receiver: an ST-class receiver usually reaches the
method through the helper's slow-path NSM fallback; a Dart-primitive or bridged
receiver (num, String, List, Map, Character) is answered by the helper's fast
path and the method is DEAD. This tool cannot always know the receiver, so it
REPORTS rather than judges — the rule is in CLAUDE.md: before defining any
method, check its selector against this list, and if it collides, either pick
the helper's slow path as the home for the behaviour (cocoa.dart) or prove the
fallback reaches your class.

The table is parsed from the builder source, so a helper added tomorrow is
audited tomorrow — no second list to keep in sync.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDER = os.path.join(REPO, "port-win", "dart_st", "st_flow_graph_builder.cc")

ENTRY = re.compile(r'\{"([a-zA-Z:_]+)",\s*"st[A-Za-z0-9_]+",\s*\d+\}')

# Layers worth scanning. `st/attic` is dead by definition; `st/test` probes are
# included because a probe whose helper-named method is never reached asserts
# nothing while looking like it does.
SCAN_DIRS = ["st/world", "st/dolphin_compat", "st/prims", "st/mvp",
             "st/mvp_compat", "st/ext", "st/test"]

GENERATED = ("st/mvp/", "st/prims/structs/")   # fix the translator, not the file

# ALIASED selectors — always DEAD as .mst definitions. When two selectors map
# to one helper, the slow path re-dispatches under only ONE of them (read from
# the _st*Slow bodies in cocoa.dart), so a method defined under the alias name
# is unreachable on EVERY receiver. `ExternalMemory>>asInteger` was exactly
# this: the helper's slow path calls `.truncated()`, never `.asInteger()`.
DEAD_ALIASES = {
    "asInteger": "truncated",     # _stTruncSlow -> r.truncated()
    "asString": "displayString",  # stDisplayOf -> displayOn:/displayString
    "asFloat": "asDouble",        # _stAsDoubleSlow -> r.asDouble()
    "arcTan": "atan",             # _stAtanSlow -> r.atan()
}


def helper_selectors():
    src = open(BUILDER, encoding="utf-8", errors="replace").read()
    return sorted({m.group(1) for m in ENTRY.finditer(src)})


def def_pattern(sel: str) -> re.Pattern:
    """A house-dialect definition of `sel`, either side, with optional type
    annotations: `truncated ^ <Integer> [`, `at: i <Integer> put: v [`,
    `Foo class >> value [`."""
    prefix = r"^\s+(?:[A-Za-z_]\w*\s+class\s*>>\s*)?"
    if ":" not in sel:
        body = re.escape(sel) + r"(?:\s*\^\s*<[^>]+>)?\s*\["
    else:
        parts = sel.split(":")[:-1]
        body = r"\s+".join(
            re.escape(p) + r":\s+\w+(?:\s*<[^>]+>)?" for p in parts)
        body += r"(?:\s*\^\s*<[^>]+>)?\s*\["
    return re.compile(prefix + body)


def main(argv):
    ap = argparse.ArgumentParser(prog="audit_helpers")
    ap.add_argument("--quiet", action="store_true",
                    help="print only the summary line")
    args = ap.parse_args(argv)

    sels = helper_selectors()
    pats = {s: def_pattern(s) for s in sels}
    hits = []
    for d in SCAN_DIRS:
        root = os.path.join(REPO, d)
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            for f in fn:
                if not f.endswith(".mst"):
                    continue
                path = os.path.join(dp, f)
                rel = os.path.relpath(path, REPO).replace("\\", "/")
                for lineno, line in enumerate(
                        open(path, encoding="utf-8", errors="replace"), 1):
                    if line.lstrip().startswith('"'):
                        continue
                    for s, pat in pats.items():
                        if pat.match(line):
                            hits.append((s, rel, lineno))

    print("audit_helpers: %d call-site-rewritten selectors; "
          "%d colliding definition(s)\n" % (len(sels), len(hits)))
    if not args.quiet:
        for s, rel, lineno in sorted(hits):
            tags = []
            if s in DEAD_ALIASES:
                tags.append("DEAD ALIAS: slow path calls `%s`, never this"
                            % DEAD_ALIASES[s])
            if any(rel.startswith(g) for g in GENERATED):
                tags.append("GENERATED: fix the translator")
            tag = ("  [" + "; ".join(tags) + "]") if tags else ""
            print("  %-24s %s:%d%s" % (s, rel, lineno, tag))
        dead = [h for h in hits if h[0] in DEAD_ALIASES]
        if dead:
            print("\n%d definition(s) are DEAD ALIASES, unreachable on every "
                  "receiver." % len(dead))
        if hits:
            print("\nEach is reached only if the helper's slow path falls")
            print("through to ST dispatch for its receivers. If the receiver")
            print("can be a Dart primitive or bridged class, the method is")
            print("DEAD and the behaviour belongs in the helper (cocoa.dart).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
