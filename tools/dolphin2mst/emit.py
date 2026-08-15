"""Rewrite Dolphin constructs into house dialect, and emit `.mst` (DD3).

Each rewrite is a named *rewrite class* so it can be golden-tested in isolation
and named in a refusal report. The governing rule for all of them: **when a
construct cannot be translated faithfully, refuse it loudly** — emit nothing and
record file:line. A guess here becomes a runtime surprise arbitrarily far from
its cause, which is the failure mode this project has already paid for twice
(DD0's silent class-side nil; DD1's comment-vs-code census).

House target shape:

    Super subclass: Name [
        <classVars: A B>
        | ivar1 ivar2 |

        selector: arg [
            body
        ]
        Name class >> selector: arg [
            body
        ]
    ]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from parse import ClassDef, Method, ParsedFile
from stlex import strip_code


@dataclass
class Refusal:
    where: str            # file:line
    rewrite: str          # which rewrite class refused
    detail: str

    def __str__(self) -> str:
        return f"{self.where}: [{self.rewrite}] {self.detail}"


@dataclass
class EmitResult:
    text: str
    refusals: List[Refusal] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# --- rewrite: namespace flattening ------------------------------------------
# DD2 measured ZERO base-name collisions across the 1001-file MVP+Base closure
# (and no base name repeated at all), so flattening is mechanical and the rename
# table starts empty. It exists anyway because that guarantee is scoped to
# MVP+Base; pulling in IDE/ActiveX/System could reintroduce collisions.

_DOTTED = re.compile(r"(?<![\w.])([A-Z][A-Za-z0-9]*(?:\.[A-Z][A-Za-z0-9]*)+)(?![\w])")


def flatten_name(qualified: str, renames: Dict[str, str]) -> str:
    base = qualified.rsplit(".", 1)[-1]
    return renames.get(qualified, renames.get(base, base))


def flatten_refs(src: str, renames: Dict[str, str]) -> str:
    """Flatten dotted class references in code, leaving comments/strings alone."""
    blanked = strip_code(src)
    out = []
    last = 0
    for m in _DOTTED.finditer(blanked):
        out.append(src[last:m.start()])
        out.append(flatten_name(src[m.start():m.end()], renames))
        last = m.end()
    out.append(src[last:])
    return "".join(out)


# --- rewrite: `??` -> ifNil: -------------------------------------------------
# Dolphin's binary `??` answers the receiver unless it is nil, in which case it
# answers the argument: `^cause ?? #unknown`. 133 sites / 65 files (DD2).

_QQ = re.compile(r"\?\?")


def rewrite_qq(src: str, where: str) -> Tuple[str, List[Refusal]]:
    blanked = strip_code(src)
    if "??" not in blanked:
        return src, []
    refusals: List[Refusal] = []
    out = src
    # Rewrite right-to-left so earlier offsets stay valid.
    for m in reversed(list(_QQ.finditer(blanked))):
        rhs = out[m.end():].lstrip()
        pad = len(out[m.end():]) - len(rhs)
        # RIGHT operand: a binary operator takes a primary plus any unary chain
        # (`a ?? b foo bar`), and stops at the first keyword part.
        prim = re.match(r"(#?\w+|#\([^()]*\)|'(?:[^']|'')*'|\$.|\([^()]*\)|-?\d+(?:\.\d+)?)"
                        r"((?:\s+[a-z]\w*(?![\w:]))*)\s*", rhs)
        if not prim:
            refusals.append(Refusal(where, "qq", "`??` with a non-primary right operand"))
            continue
        value = (prim.group(1) + prim.group(2)).strip()
        rest = rhs[prim.end():]

        # LEFT operand: bounded to the primary + unary chain immediately before
        # the operator — NOT everything to its left. Smalltalk binds binary
        # tighter than keyword, so in `foo: a ?? b` the `??` applies to `a`
        # alone; consuming `foo: a` would emit `foo: a ifNil: [b]`, which is the
        # single keyword message `foo:ifNil:` and means something else entirely.
        left_all = out[:m.start()]
        lm = re.search(r"((?:\([^()]*\)|#?\w+|'(?:[^']|'')*'|\$.)"
                       r"(?:\s+[a-z]\w*(?![\w:]))*)\s*$", left_all)
        if not lm:
            refusals.append(Refusal(where, "qq", "`??` with an unbounded left operand"))
            continue
        head, lhs = left_all[:lm.start(1)], lm.group(1)

        # The result is ALWAYS parenthesised. Spliced bare, a following keyword
        # part merges with ours: `a ifNil: [b] foo: c` is `ifNil:foo:`, not
        # `(a ifNil: [b]) foo: c`. Redundant parens are harmless; a merged
        # selector is a silent behaviour change.
        out = f"{head}({lhs} ifNil: [ {value} ]){' ' * pad if pad else ''}{rest}"
    return out, refusals


# --- rewrite: `##( ... )` compile-time literal --------------------------------
# 978 sites / 283 files (DD2) — the single most common Dolphin-ism in the corpus.
# Only a closed set of provably-constant expressions is folded; everything else
# is refused. Evaluating arbitrary Smalltalk at translation time is out of scope
# and would need the very image we are building.

_HASHHASH = re.compile(r"##\(")
_CONST_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")


def _fold_constant(expr: str) -> Optional[str]:
    e = expr.strip()
    if _CONST_NUM.match(e):
        return e
    if re.match(r"^'(?:[^']|'')*'$", e) or re.match(r"^#\w+$", e) or re.match(r"^\$.$", e):
        return e
    if e in ("true", "false", "nil"):
        return e
    # Integer arithmetic over literals: 16r0F, 1 bitShift: 4, 3 + 4 ...
    m = re.match(r"^(-?\d+)\s*(\+|-|\*|//|bitShift:|bitOr:|bitAnd:)\s*(-?\d+)$", e)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        try:
            return str({"+": a + b, "-": a - b, "*": a * b, "//": a // b,
                        "bitShift:": a << b if b >= 0 else a >> -b,
                        "bitOr:": a | b, "bitAnd:": a & b}[op])
        except Exception:
            return None
    m = re.match(r"^(\d+)r([0-9A-Fa-f]+)$", e)
    if m:
        try:
            return str(int(m.group(2), int(m.group(1))))
        except ValueError:
            return None
    return None


def rewrite_hashhash(src: str, where: str) -> Tuple[str, List[Refusal]]:
    refusals: List[Refusal] = []
    out = src
    while True:
        blanked = strip_code(out)
        m = _HASHHASH.search(blanked)
        if not m:
            return out, refusals
        depth = 0
        i = m.end() - 1
        while i < len(blanked):
            if blanked[i] == "(":
                depth += 1
            elif blanked[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if i >= len(blanked):
            refusals.append(Refusal(where, "hashhash", "unbalanced `##(`"))
            return out, refusals
        inner = out[m.end():i]
        folded = _fold_constant(inner)
        if folded is None:
            refusals.append(Refusal(where, "hashhash",
                                    f"`##({inner.strip()[:60]})` is not a foldable constant"))
            # Leave it as a plain parenthesised expression so the rest of the
            # method still translates; the refusal is what gets acted on.
            out = out[:m.start()] + "(" + inner + ")" + out[i + 1:]
        else:
            out = out[:m.start()] + folded + out[i + 1:]


# --- rewrite: primitive 157 --------------------------------------------------
# DD2: D157 is the ONLY primitive number in the whole MVP tree (32 sites / 28
# files). `primitiveNewInitializedObject` allocates an instance of the receiver
# class and fills its instance variables from the arguments, in declaration
# order. No VM work is needed — we know the ivar order, having just parsed it.
#
# The fill order is the class's FULL instance-variable order INCLUDING
# inherited variables. We only know the declared ones, so a class whose
# superclass contributes ivars is REFUSED rather than mis-filled: getting the
# inheritance offset wrong shifts every field by one, and the damage surfaces
# arbitrarily far from the cause.

def lower_prim157(m: Method, cd: ClassDef, where: str,
                  super_ivar_count: Optional[int]) -> Tuple[Optional[str], List[Refusal]]:
    n_args = len(m.arg_names)
    if super_ivar_count is None:
        return None, [Refusal(where, "prim157",
                              f"{cd.name}>>{m.selector}: superclass ivar count unknown "
                              f"({cd.superclass}); cannot place fields safely")]
    if super_ivar_count != 0:
        return None, [Refusal(where, "prim157",
                              f"{cd.name}>>{m.selector}: superclass {cd.superclass} contributes "
                              f"{super_ivar_count} ivars; inherited-offset case not implemented")]
    if n_args != len(cd.ivars):
        return None, [Refusal(where, "prim157",
                              f"{cd.name}>>{m.selector}: {n_args} args vs {len(cd.ivars)} "
                              f"instance variables — refusing to guess the mapping")]
    stores = " ".join(f"instVarAt: {i + 1} put: {a};"
                      for i, a in enumerate(m.arg_names))
    return f"^self basicNew {stores} yourself", []


# --- emission ----------------------------------------------------------------

def _indent(text: str, pad: str = "        ") -> str:
    return "\n".join(pad + ln if ln.strip() else "" for ln in text.split("\n"))


def _house_pattern(m: Method, cls_name: str) -> str:
    if m.arg_names and ":" in m.selector:
        parts = m.selector.split(":")[:-1]
        pat = " ".join(f"{k}: {a}" for k, a in zip(parts, m.arg_names))
    elif m.arg_names:
        pat = f"{m.selector} {m.arg_names[0]}"
    else:
        pat = m.selector
    return f"{cls_name} class >> {pat}" if m.class_side else pat


def emit_class(pf: ParsedFile, renames: Dict[str, str],
               super_ivars: Dict[str, Optional[int]]) -> EmitResult:
    cd = pf.classdef
    if cd is None:
        return EmitResult("", [Refusal(pf.path, "classdef", "no class-definition chunk")])
    refusals: List[Refusal] = []
    notes: List[str] = []
    if cd.legacy:
        notes.append(f"{cd.name}: Dolphin-7 legacy form (poolDictionaries:, no namespace)")

    name = flatten_name(cd.name, renames)
    sup = flatten_name(cd.superclass, renames)
    lines: List[str] = []
    if cd.comment:
        lines.append('"' + cd.comment.replace('"', '""').strip() + '"')
        lines.append("")
    lines.append(f"{sup} subclass: {name} [")
    if cd.cvars:
        lines.append(f"    <classVars: {' '.join(cd.cvars)}>")
    if cd.ivars:
        lines.append(f"    | {' '.join(cd.ivars)} |")
    if cd.cvars or cd.ivars:
        lines.append("")

    for m in pf.methods:
        where = f"{pf.path}:{m.line}"
        body = m.body
        prim = next((p for p in m.pragmas if p.startswith("<primitive:")), None)
        if prim:
            num = re.search(r"<primitive:\s*(\d+)", prim)
            n = int(num.group(1)) if num else -1
            if n == 157:
                lowered, r = lower_prim157(m, cd, where, super_ivars.get(cd.superclass))
                refusals.extend(r)
                if lowered is None:
                    continue
                body = lowered
            else:
                refusals.append(Refusal(where, "primitive",
                                        f"unmapped Dolphin primitive {n} — see docs/PRIM_MAP.md"))
                continue
        else:
            body = re.sub(re.escape(prim) if prim else r"(?!x)x", "", body)

        for pg in m.pragmas:
            if pg.startswith("<primitive:"):
                continue
            if pg.startswith(("<stdcall:", "<cdecl:", "<virtual", "<overlap")):
                refusals.append(Refusal(where, "external-call",
                                        f"{pg[:60]} — external-call pragma (DD6 owns the form)"))
                break
            if pg.startswith("<namespace:"):
                body = body.replace(pg, "")
                continue
            refusals.append(Refusal(where, "pragma", f"unhandled pragma {pg[:50]}"))
            break
        else:
            # `#{Namespace.Name}` — Dolphin's VARIABLE BINDING literal. It
            # denotes the binding (an association), not the value, and its
            # protocol (`binding value`, `setValue:`, `isDefined`) has no house
            # equivalent. Silently emitting it would produce source that parses
            # and means something else, so it is refused. Found the honest way:
            # Graphics.Point's class-side `uninitialize` emitted
            # `#{Zero} binding setValue: nil` cleanly in the first run.
            if "#{" in strip_code(body):
                refusals.append(Refusal(where, "binding-literal",
                                        "`#{...}` variable-binding literal has no house equivalent"))
                continue
            body, r = rewrite_hashhash(body, where); refusals.extend(r)
            body, r = rewrite_qq(body, where); refusals.extend(r)
            body = flatten_refs(body, renames)
            if m.comment:
                body = '"' + m.comment.replace('"', '""') + '"\n' + body
            lines.append(f"    {_house_pattern(m, name)} [")
            lines.append(_indent(body.strip("\n")))
            lines.append("    ]")
            continue
        # a `break` above landed here: the method was refused, emit nothing
    lines.append("]")
    return EmitResult("\n".join(lines) + "\n", refusals, notes)
