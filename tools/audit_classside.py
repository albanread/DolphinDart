"""Find class-side selectors that are SELF-SENT by an ancestor and OVERRIDDEN
by a descendant — the pattern the class-side `self` fast path resolves with CHA.

    python tools/audit_classside.py [--quiet] [--dirs st/mvp st/world ...]

THE TRAP this guards. `self <sel>` inside a class-side method compiles to a
direct StaticCall when class-hierarchy analysis proves nothing below the
defining class overrides `<sel>` (see the class-side `self` path in
st_flow_graph_builder.cc). CHA is decided at COMPILE time and ST functions are
compiled lazily on FIRST CALL, so the analysis sees only the classes finalized
by then. That leaves exactly one hole:

    a method is CALLED DURING LOADING (from a top-level statement), and a
    subclass that OVERRIDES a selector it self-sends loads LATER.

Such a call would keep the stale direct binding to the ancestor's method. Every
other ordering is safe, because by the time anything else runs, the whole wave
is loaded.

Before CHA the fast path had no check at all, and the divergence was dismissed
in a comment as "a rare pattern, absent from the corpus". It was not absent:
`STxFiler class >> classForVersion:` self-sends `versions`, `STLInFiler`
overrides it, and the whole STB/STL view-resource reader dead-ended on
`nil lookup:` because the inherited send reached STxFiler's abstract instead.
That is the bug class this audit keeps closed.

WHAT IT REPORTS. Each overridden class-side selector that some ancestor
self-sends, with the load order of the definers. A pair is FLAGGED only when
the ancestor's file also runs a load-time statement that could reach the send
before the override's file loads; everything else is listed as ok.

This parses the .mst wave, not the builder, so it audits what actually loads.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "dolphin2mst"))
from stlex import strip_code  # noqa: E402  (comments/strings blanked, offsets kept)

DEFAULT_DIRS = ["st/world", "st/dolphin_compat", "st/prims/rt", "st/prims",
                "st/mvp", "st/mvp_compat"]

# `Super subclass: Name [`
CLASSDEF = re.compile(r"^\s*([A-Za-z_][\w.]*)\s+subclass:\s+([A-Za-z_][\w.]*)\s*\[")
# `Name class >> selector [`  (unary, keyword or binary head)
CLASSMETH = re.compile(r"^\s*([A-Za-z_][\w.]*)\s+class\s*>>\s*(.+?)\s*\[")
# a top-level statement like `Foo initialize.` / `Foo initializeClassConstants.`
TOPLEVEL = re.compile(r"^([A-Za-z_][\w.]*)\s+([A-Za-z_]\w*)\s*\.\s*$")


def selector_name(head: str) -> str:
    """`at: k put: v` -> `at:put:`; `foo` -> `foo`; `= other` -> `=`."""
    head = head.strip()
    if ":" not in head:
        return head.split()[0] if head.split() else head
    parts = re.findall(r"([A-Za-z_]\w*:)", head)
    return "".join(parts) if parts else head


def scan(paths):
    """-> (supers, methods, bodies, toplevels, order)"""
    supers = {}       # class -> superclass
    methods = {}      # class -> {selector: file}
    bodies = {}       # (class, selector) -> body text
    toplevels = {}    # file -> [(receiver, selector)]
    order = {}        # class -> load index (by file order, then position)
    for idx, path in enumerate(paths):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        cur_cls = None
        cur_sel = None
        buf = []
        depth = 0
        for ln in lines:
            m = CLASSDEF.match(ln)
            if m:
                sup, name = m.group(1), m.group(2)
                supers.setdefault(name, sup)
                order.setdefault(name, idx)
                cur_cls = name
            mm = CLASSMETH.match(ln)
            if mm:
                if cur_sel is not None:
                    bodies[cur_sel] = "".join(buf)
                owner, head = mm.group(1), mm.group(2)
                sel = selector_name(head)
                methods.setdefault(owner, {}).setdefault(sel, path)
                order.setdefault(owner, idx)
                cur_sel = (owner, sel)
                buf = []
                depth = 1
                continue
            if cur_sel is not None:
                buf.append(ln)
            t = TOPLEVEL.match(ln)
            if t:
                toplevels.setdefault(path, []).append((t.group(1), t.group(2)))
        if cur_sel is not None:
            bodies[cur_sel] = "".join(buf)
    return supers, methods, bodies, toplevels, order


def ancestors(cls, supers):
    seen = []
    cur = supers.get(cls)
    while cur and cur not in seen:
        seen.append(cur)
        cur = supers.get(cur)
    return seen


def self_sends(body: str, sel: str) -> bool:
    """Does `body` contain a `self <sel>` send? Comments and string literals are
    blanked first — `CommandButton class >> initialize` documents itself with
    the literal text "self initialize" in its comment, which read as a real
    send and produced a false RISK."""
    if not body:
        return False
    body = strip_code(body)
    if sel.endswith(":"):
        first = sel.split(":")[0] + ":"
        return re.search(r"\bself\s+" + re.escape(first), body) is not None
    return re.search(r"\bself\s+" + re.escape(sel) + r"\b(?!\s*:)", body) is not None


def self_sent_selectors(body: str) -> set:
    """Every `self <sel>` selector in a method body (comments/strings blanked)."""
    if not body:
        return set()
    body = strip_code(body)
    out = set()
    for m in re.finditer(r"\bself\s+([A-Za-z_]\w*:?)", body):
        out.add(m.group(1))
    return out


def load_reachable(top, methods, bodies, supers):
    """Class-side methods reachable from the load-time statements `top`, by
    following `self` sends. This is what decides RISK: a stale direct call can
    only be baked in if the ancestor's method is actually COMPILED during
    loading, i.e. reached from a top-level statement.

    `IconicListAbstract initializeClassConstants.` only assigns its constants —
    it never reaches `viewModeNames`, whose `self viewModes` send is called from
    an instance method at GUI time, with the whole wave long since loaded."""
    seen = set()
    work = list(top)
    while work:
        cls, sel = work.pop()
        if (cls, sel) in seen:
            continue
        seen.add((cls, sel))
        # Resolve the definition up the ancestor chain, as ST lookup would.
        owner = cls if sel in methods.get(cls, {}) else None
        if owner is None:
            for anc in ancestors(cls, supers):
                if sel in methods.get(anc, {}):
                    owner = anc
                    break
        if owner is None:
            continue
        for nxt in self_sent_selectors(bodies.get((owner, sel), "")):
            # `self` keeps the RECEIVING class, so keep dispatching from `cls`.
            work.append((cls, nxt))
    return seen


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--dirs", nargs="*", default=DEFAULT_DIRS)
    args = ap.parse_args(argv)

    paths = []
    for d in args.dirs:
        full = os.path.join(REPO, d.replace("/", os.sep))
        if not os.path.isdir(full):
            continue
        paths.extend(sorted(os.path.join(full, f) for f in os.listdir(full)
                            if f.endswith(".mst")))
    supers, methods, bodies, toplevels, order = scan(paths)

    # Every class-side method compiled during LOADING, from every top-level
    # statement in the wave.
    top = [(recv, sel) for stmts in toplevels.values() for (recv, sel) in stmts]
    reachable = load_reachable(top, methods, bodies, supers)

    findings = []   # (ancestor, sub, sel, risky, why)
    for sub, sels in sorted(methods.items()):
        for sel, sub_file in sorted(sels.items()):
            for anc in ancestors(sub, supers):
                if sel not in methods.get(anc, {}):
                    continue
                # `anc` defines `sel` and `sub` overrides it. Does any class-side
                # method visible from `anc` self-send `sel`?
                senders = [(o, s) for (o, s), b in bodies.items()
                           if (o == anc or o in ancestors(anc, supers) or o == sub)
                           and self_sends(b, sel)]
                if not senders:
                    continue
                anc_file = methods[anc][sel]
                # Risky only if a method that self-sends `sel` is actually
                # REACHED from a load-time statement, and the override loads
                # later — the one ordering CHA cannot see (see the module
                # docstring). Reachability is computed from every load-time
                # statement in the wave, not just the definer's own file.
                later = order.get(sub, 0) > order.get(anc, 0)
                risky = later and any(
                    (o, s) in reachable for (o, s) in senders)
                findings.append((anc, sub, sel, risky,
                                 os.path.relpath(anc_file, REPO),
                                 os.path.relpath(sub_file, REPO),
                                 len(senders)))

    risky = [f for f in findings if f[3]]
    if not args.quiet:
        print(f"audit_classside: {len(paths)} files, "
              f"{len(findings)} self-sent class-side override(s)")
        for anc, sub, sel, is_risky, af, sf, n in findings:
            tag = "RISK" if is_risky else "ok  "
            print(f"  {tag}  {anc} class >> {sel}  overridden by {sub}")
            print(f"        definer {af}")
            print(f"        override {sf}  ({n} self-send site(s))")
        if not risky:
            print("\nno load-order risk: every override loads before anything "
                  "can compile a stale direct call to it")
    if risky:
        print(f"\n{len(risky)} RISKY pair(s): an override that loads after a "
              f"load-time call could keep a stale direct binding.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
