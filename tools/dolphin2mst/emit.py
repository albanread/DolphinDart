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
import pools
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


# --- rewrite: selector spellings ---------------------------------------------
# Where Dolphin and the house dialect differ only in the NAME of a method,
# rewrite at ingestion rather than adding a compat method. Two reasons, both
# measured: a compat method on a BRIDGED class (Character, String, Integer) does
# not reach the native receiver's ext-holder from a later file at all; and a
# rewrite costs nothing at runtime.
#
# Only unambiguous, whole-selector renames belong here. Anything whose SEMANTICS
# differ needs a compat method, not a rename.
SELECTOR_RENAMES = {
    "asUnicodeValue": "value",      # Character code point (DD6c/DD8)
}

_SEL = re.compile(r"(?<![\w:])([A-Za-z_]\w*)(?![\w:])")


def rewrite_selectors(src: str, renames=None) -> str:
    table = SELECTOR_RENAMES if renames is None else renames
    if not table:
        return src
    blanked = strip_code(src)
    out, last = [], 0
    for m in _SEL.finditer(blanked):
        name = src[m.start(1):m.end(1)]
        if name not in table:
            continue
        out.append(src[last:m.start(1)])
        out.append(table[name])
        last = m.end(1)
    out.append(src[last:])
    return "".join(out)


# --- rewrite: cascades -> statements -----------------------------------------
# Dolphin writes `^self destroy; isOpen not` (UI.View>>close). A cascade PART may
# be a whole message chain in Dolphin; this dialect's parser accepts only a
# single message per part, so `View.mst` failed to load on exactly that line.
# Measured first: `^self a; b` parses fine here, so the limit is specifically a
# multi-message part.
#
# Splitting into statements is semantically identical WHEN the receiver is a
# simple primary (`self`, a variable, a literal) — it is then evaluated once
# either way. When it is not, the receiver would be evaluated once per part, so
# those are REFUSED rather than rewritten: silently duplicating a side-effecting
# receiver is exactly the class of change this translator must never make.
#
#   ^self destroy; isOpen not      ->   self destroy. ^self isOpen not
#   Transcript show: 'x'; cr       ->   Transcript show: 'x'. Transcript cr

_SIMPLE_RECV = re.compile(r"^(self|super|thisContext|[A-Za-z_]\w*)$")


def _split_top_level(text: str, ch: str) -> List[str]:
    """Split on `ch` at bracket/paren depth 0, ignoring comments and strings."""
    blank = strip_code(text)
    parts, start, depth = [], 0, 0
    for i, c in enumerate(blank):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ch and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def rewrite_cascades(body: str, where: str) -> Tuple[str, List[Refusal]]:
    blank = strip_code(body)
    if ";" not in blank:
        return body, []
    refusals: List[Refusal] = []
    out_lines = []
    temps_added: List[str] = []
    # A leading temporaries declaration is not a statement, and leaving it in
    # front of the first one makes its `^` invisible and its tokens part of the
    # cascade head. Split it off, process the statements, re-attach at the end.
    orig = body
    decl, body = _split_leading_temps(body)
    for stmt in _split_top_level(body, "."):
        sblank = strip_code(stmt)
        if ";" not in sblank:
            out_lines.append(stmt)
            continue
        parts = _split_top_level(stmt, ";")
        # A `;` NESTED inside a block or parens is not this statement's
        # cascade — `MessageMap isNil ifTrue: [x foo; bar]` has one top-level
        # part. Rewriting anyway bound the receiver to a temp for nothing;
        # harmless, but it made `View class >> initialize` unreadable.
        if len(parts) == 1:
            out_lines.append(stmt)
            continue
        head = parts[0]
        ret = head.lstrip().startswith("^")
        head_body = head.lstrip()[1:] if ret else head
        recv, first_msg = _split_cascade_head(head_body)
        if recv is None:
            refusals.append(Refusal(where, "cascade",
                                    "cascade on a receiver this rewriter cannot "
                                    "bound — splitting it could change evaluation"))
            out_lines.append(stmt)
            continue
        stmts = []
        if _SIMPLE_RECV.match(recv):
            # A bare primary is free to repeat: re-evaluating `self` or a
            # temporary has no effect and costs nothing.
            base = recv
        else:
            # ANYTHING ELSE MUST BE BOUND TO A TEMPORARY. `self basicNew
            # instVarAt: 1 put: x; instVarAt: 2 put: y; yourself` — the shape
            # the D157 constructor lowering itself emits — has the cascade
            # receiver `self basicNew`, and repeating it would allocate a fresh
            # object per part.
            base = _fresh_temp(orig, len(temps_added))
            temps_added.append(base)
            stmts.append(f"{base} := {recv.strip()}")
        stmts.append(f"{base} {first_msg.strip()}")
        stmts += [f"{base} {p.strip()}" for p in parts[1:]]
        if ret:
            stmts[-1] = "^" + stmts[-1]
        out_lines.append(" ".join(s + "." for s in stmts[:-1]) + " " + stmts[-1])
    result = ".".join(out_lines)
    if temps_added:
        decl = _merge_temps(decl, temps_added)
    return (decl + result) if decl else result, refusals


def _split_leading_temps(body: str):
    """Split a leading `| a b |` declaration off the front. Answers
    (declaration-including-trailing-space, rest); the declaration is '' when
    there is none. Comments are blanked first, so a `|` inside one cannot be
    mistaken for a declaration."""
    m = re.match(r"\s*\|[^|]*\|", strip_code(body))
    return (body[:m.end()].rstrip() + " ", body[m.end():]) if m else ("", body)


def _merge_temps(decl: str, names: List[str]) -> str:
    if not decl:
        return "| " + " ".join(names) + " | "
    i = decl.rindex("|")
    return decl[:i].rstrip() + " " + " ".join(names) + " | "


def _split_cascade_head(head: str):
    """Split a cascade's first segment into (receiver-expression, first message).

    The cascade re-sends to the receiver of the LAST message in that segment,
    which is NOT the same as its first token. In

        self basicNew instVarAt: 1 put: x; instVarAt: 2 put: y; yourself

    the receiver is `self basicNew`, not `self`. Reading only the first token
    made every D157-lowered constructor in the corpus write its fields into the
    CLASS and answer the class — `Rectangle origin:extent:` raised "class
    'Rectangle' has no class-side method 'instVarAt:put:'", which is the lucky
    case; a class that happened to understand the selector would have corrupted
    itself in silence.

    Answers (None, None) when the segment cannot be split confidently.
    """
    blank = strip_code(head)
    toks = list(re.finditer(r"[^\s]+", blank))
    if len(toks) < 2:
        return None, None
    # A keyword message starts at the first top-level token ending in ':'.
    depth = 0
    kw_at = None
    bin_at = None
    for i, t in enumerate(toks):
        s = blank[t.start():t.end()]
        if i > 0 and depth == 0:
            if s.endswith(":") and re.match(r"^[A-Za-z_]\w*:$", s):
                kw_at = i
                break
            if bin_at is None and re.match(r"^[-+*/~<>=&|@%,?!\\]+$", s):
                bin_at = i
        depth += sum(1 for c in s if c in "([{") - sum(1 for c in s if c in ")]}")
    cut = kw_at if kw_at is not None else bin_at
    if cut is None:
        # All unary: the final message is the last token, the receiver is the
        # rest. `self basicNew yourself` -> receiver `self basicNew`.
        cut = len(toks) - 1
    if cut < 1:
        return None, None
    recv = head[:toks[cut].start()].strip()
    msg = head[toks[cut].start():]
    # The receiver must itself be a primary followed only by unary sends — a
    # parenthesised or bracketed expression is left to the refusal path, since
    # binding it correctly needs real parsing.
    if not re.match(r"^(self|super|thisContext|[A-Za-z_]\w*)"
                    r"(\s+[A-Za-z_]\w*)*$", strip_code(recv).strip()):
        return None, None
    return recv, msg


def _fresh_temp(body: str, n: int) -> str:
    """A temporary name that cannot collide with anything in `body`."""
    name = f"_casc{n + 1}"
    while re.search(r"\b" + name + r"\b", body):
        n += 1
        name = f"_casc{n + 1}"
    return name




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
    # Integer expressions over literals, left-to-right as Smalltalk evaluates
    # binary sends. Multi-term is required, not a nicety: after pool folding the
    # corpus is full of `##(MIIM_STRING | MIIM_ID | MIIM_BITMAP)`, which is three
    # terms. `|` and `&` are Dolphin's bitwise binaries on integers.
    _OPS = {"+": lambda a, b: a + b, "-": lambda a, b: a - b,
            "*": lambda a, b: a * b, "//": lambda a, b: a // b,
            "|": lambda a, b: a | b, "&": lambda a, b: a & b,
            "bitShift:": lambda a, b: a << b if b >= 0 else a >> -b,
            "bitOr:": lambda a, b: a | b, "bitAnd:": lambda a, b: a & b,
            "bitXor:": lambda a, b: a ^ b}
    toks = e.split()
    if len(toks) >= 3 and len(toks) % 2 == 1:
        try:
            acc = int(toks[0], 0) if not toks[0].startswith("-") else int(toks[0])
        except ValueError:
            acc = None
        if acc is not None:
            ok = True
            for i in range(1, len(toks), 2):
                op, rhs = toks[i], toks[i + 1]
                if op not in _OPS:
                    ok = False
                    break
                try:
                    acc = _OPS[op](acc, int(rhs))
                except Exception:
                    ok = False
                    break
            if ok:
                return str(acc)
    m = re.match(r"^(\d+)r([0-9A-Fa-f]+)$", e)
    if m:
        try:
            return str(int(m.group(2), int(m.group(1))))
        except ValueError:
            return None
    return None


# --- rewrite: bare pool constants -------------------------------------------
# A class names its pools in `imports:` and then writes the constants as BARE
# identifiers (`BM_CLICK`, not a qualified reference), so folding needs the
# import list as well as the tables. 928 constants live in `Dolphin MVP Base.pax`
# alone (DD3b).
#
# The guard matters more than the fold: an identifier is only replaced when it
# is NOT a method argument, temporary, instance variable or class variable.
# Shadowing is legal Smalltalk, and folding a shadowed name would substitute a
# constant for a live variable — a wrong answer with no diagnostic.

_TEMP_NAMES = re.compile(r"[A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*\Z")


def collect_temps(blanked: str) -> set:
    """Names declared as method or block TEMPORARIES.

    Deliberately not a `|([^|]*)|` scan. Dolphin writes bit masks with the
    binary operator — `##(WS_THICKFRAME | WS_CAPTION | WS_SYSMENU |
    WS_MINIMIZEBOX | WS_MAXIMIZEBOX)` — and a bare pair-scan reads
    `| WS_CAPTION |` and `| WS_MINIMIZEBOX |` as declarations, shadowing EVERY
    OTHER OPERAND so it never folds. Measured on `UI.ShellView`: three of the
    five folded, two stayed bare, and the method answered nil at runtime
    (`_bitOrFromInteger was called on null`) rather than refusing at
    translation. Alternate operands surviving is the signature of the bug.

    A declaration can only OPEN where one is legal: at the start of a body, or
    just inside a block, after that block's `:arg` list if it has one. `input`
    is the comment/string-blanked body, so quoted text cannot open one either.
    """
    temps: set = set()
    i, n = 0, len(blanked)
    decl_ok = True                       # a method body starts in decl position
    while i < n:
        c = blanked[i]
        if c.isspace():
            i += 1
            continue
        if c == "[":
            i += 1
            j = i
            while j < n and blanked[j].isspace():
                j += 1
            if j < n and blanked[j] == ":":          # `[:a :b | …` — skip args
                k = j
                while k < n and blanked[k] not in "|]":
                    k += 1
                if k < n and blanked[k] == "|":
                    i = k + 1
            decl_ok = True
            continue
        if c == "|" and decl_ok:
            j = blanked.find("|", i + 1)
            if j < 0:
                break
            inner = blanked[i + 1:j].strip()
            if inner and _TEMP_NAMES.match(inner):
                temps.update(inner.split())
                i = j + 1
                decl_ok = False
                continue
        decl_ok = False
        i += 1
    return temps
# Constant names are SHOUT_CASE (`BM_CLICK`, `MIIM_STRING`) or the struct
# classes' leading-underscore offsets (`_OffsetOf_cch`, `_MENUITEMINFOW_Size`).
# The underscore form is not decoration: it is how every generated struct
# accessor addresses its fields, and excluding it left every struct class
# refusing its own `##(_OffsetOf_x + 1)` expressions.
_IDENT = re.compile(r"(?<![\w:#])(_?[A-Za-z][A-Za-z0-9_]*)(?![\w:])")


# `Point.Zero` — a qualified CLASS-VARIABLE read, not a namespaced class name.
#
# Dolphin writes `^Point.Zero` to read Graphics.Point's class variable. BOTH
# segments are capitalised, so the dotted-reference flattener matched it and
# rsplit to the last segment, leaving a bare `Zero` bound to NOTHING — nil at
# runtime, with no diagnostic anywhere. Measured over the corpus: 384 sites,
# 62 distinct, headed by `Point.Zero` (60), `SessionManager.Current` (49),
# `Color.Black` (29). Found when Dolphin's own `View>>defaultPosition`
# (`^Point.Zero`) answered nil and `View>>create` died on `nil extent:`.
#
# Rewritten to an unambiguous accessor send — `Point classVarZero` — and every
# emitted class gets a reader for each of its class variables. When the owner
# is NOT translated (Point comes from the world, not the corpus) the send is a
# loud doesNotUnderstand rather than a silent nil, and the compat layer
# supplies the accessor.
#
# The discriminator against a genuine namespace reference (`Graphics.Point`)
# is whether the second segment is DECLARED as a class variable of the first.
_QUALIFIED_CVAR = re.compile(
    r"(?<![\w.])([A-Z][A-Za-z0-9]*)\.([A-Z][A-Za-z0-9]*)(?![\w])")


def classvar_accessor(name: str) -> str:
    """The accessor spelling for a class variable read from outside."""
    return "classVar" + name


def rewrite_qualified_classvars(body: str, owners) -> str:
    """`Owner.CVar` -> `Owner classVarCVar`, for known class variables only.

    ASSIGNMENT IS A DIFFERENT REWRITE. `Cursor.Current := self` is a WRITE,
    and turning it into `Cursor classVarCurrent := self` is an assignment to a
    message send — not valid Smalltalk, and it took `Graphics.Icon` down at
    load with a parse error pointing at the `:=`.

    A write becomes a keyword send instead: `Cursor classVarCurrent: self`.
    `emit_class` emits the matching setter beside every reader, so the target
    always exists.
    """
    if not owners:
        return body
    blanked = strip_code(body)
    out, last = [], 0
    for m in _QUALIFIED_CVAR.finditer(blanked):
        owner, name = body[m.start(1):m.end(1)], body[m.start(2):m.end(2)]
        if name not in owners.get(owner, ()):
            continue
        # Is an assignment operator next? Look past whitespace in the BLANKED
        # text so a `:=` inside a comment or string cannot fool it.
        tail = blanked[m.end():]
        stripped = tail.lstrip()
        is_write = stripped.startswith(":=")
        out.append(body[last:m.start()])
        if is_write:
            # `Owner.CVar := expr`  ->  `Owner classVarCVar: expr`
            skipped = len(tail) - len(stripped)
            out.append(owner + " " + classvar_accessor(name) + ":")
            last = m.end() + skipped + 2      # consume the `:=` too
        else:
            out.append(owner + " " + classvar_accessor(name))
            last = m.end()
    out.append(body[last:])
    return "".join(out)


# `NMHDR._OffsetOf_hwndFrom` — a class constant read through its OWNING class,
# rather than through an imported pool. The struct classes use this constantly to
# reach each other's field offsets. It is not a namespace reference (the second
# segment starts with `_`), so the flattener leaves it alone, and the bare-name
# folder never sees it — the result reached the parser as `NMHDR` followed by
# `._OffsetOf_…`, which is a syntax error. Measured on UI.View.
_QUALIFIED_CONST = re.compile(r"(?<![\w.])([A-Z][A-Za-z0-9_]*)\.(_?[A-Za-z][A-Za-z0-9_]*)(?![\w])")


# TARGET CONSTANTS — values that describe THIS PORT'S target, not the source.
#
# The corpus carries its own answers for these, and folding them faithfully is
# how a faithful translator produces wrong code: `DolphinClasses.st` says
#
#     'IsWin64' -> false.
#
# because the image it shipped for was 32-bit. DolphinDart builds x64 and
# ARM64, both 64-bit, so the corpus value is a fact about a different machine.
#
# It is not cosmetic. `View>>setWndProc:` is
#
#     ^VMConstants.IsWin64
#         ifTrue: [User32 setWindowULongPtr: handle nIndex: GWL_WNDPROC ...]
#         ifFalse: [User32 setWindowULong: handle nIndex: GWL_WNDPROC ...]
#
# and on 64-bit the false branch calls SetWindowLongW, which TRUNCATES a
# 64-bit window-procedure address to 32 bits. It does not fail: it installs a
# garbage procedure. That method is the one control subclassing runs through,
# so every subclassed control would have taken it.
#
# Deliberately a SHORT, EXPLICIT list rather than a heuristic. Each entry is a
# claim about the target that someone has checked, and anything not listed
# keeps the corpus's own answer.
_TARGET_CONSTANTS = {
    ("VMConstants", "IsWin64"): "true",
}


def rewrite_qualified_constants(body: str, table, chains=None) -> str:
    if table is None:
        return body
    blanked = strip_code(body)
    out, last = [], 0
    for m in _QUALIFIED_CONST.finditer(blanked):
        owner, name = body[m.start(1):m.end(1)], body[m.start(2):m.end(2)]
        # CLASS CONSTANTS ARE INHERITED, so the search follows the owner's
        # chain and not just the owner. `ShellView>>defaultExtent` reads
        # `CreateWindow.UseDefaultGeometry`, which `CreateWindow` inherits from
        # `CreateWindowFunction` — looking only at CreateWindow's own constants
        # left it unfolded, the flattener rsplit it to a bare
        # `UseDefaultGeometry`, and ShellView's default geometry was nil.
        # The target's answer wins over the corpus's, and is applied HERE
        # rather than by patching the pool so it holds whichever pool in the
        # chain happened to supply the name.
        val = _TARGET_CONSTANTS.get((owner.rsplit(".", 1)[-1], name))
        if val is None:
            val = table.lookup((chains or {}).get(owner, [owner]), name)
        if val is None:
            # NOT FOLDABLE — but leaving `Owner.NAME` alone is a SYNTAX ERROR,
            # not a deferral: the parser sees `Owner` followed by `.NAME` and
            # the whole class file fails to load. `UI.IconicListAbstract` read
            # `NMCUSTOMDRAW._OffsetOf_dwDrawStage`, whose constants live in a
            # struct `.cls` this pipeline does not parse (the structs come
            # from winkb), and took the file down.
            #
            # Rewritten to an accessor SEND instead, the same choice and the
            # same reasoning as the class-variable rewrite above: a
            # doesNotUnderstand at the call is loud and locatable, where a
            # parse error is neither about the right thing nor recoverable.
            # `genstructs` emits `_OffsetOf_<field>` class-side for every
            # generated struct, so these resolve.
            #
            # ONLY FOR THINGS THAT LOOK LIKE CONSTANTS. `External.FunctionDescriptor`
            # also matches this pattern and is a NAMESPACED CLASS NAME, not a
            # constant — the flattener turns it into `FunctionDescriptor`, and
            # rewriting it to `External FunctionDescriptor` first made
            # `Menu class >> initialize` send to a nil `External`. The
            # discriminator is the one this file already documents: a constant
            # starts with `_` or is SHOUT_CASE; a class name is CamelCase.
            if not (name.startswith("_") or name.upper() == name):
                continue
            out.append(body[last:m.start()])
            out.append(owner + " " + name)
            last = m.end()
            continue
        out.append(body[last:m.start()])
        out.append(val)
        last = m.end()
    out.append(body[last:])
    return "".join(out)


def rewrite_pool_constants(body: str, where: str, imports, table,
                           shadowed) -> Tuple[str, List[Refusal]]:
    if table is None:
        return body, []
    blanked = strip_code(body)
    local = set(shadowed)
    local.update(collect_temps(blanked))
    out, last, changed = [], 0, False
    for m in _IDENT.finditer(blanked):
        name = body[m.start(1):m.end(1)]
        if name in local:
            continue
        val = table.lookup(imports, name)
        if val is None:
            continue
        out.append(body[last:m.start(1)])
        out.append(val)
        last = m.end(1)
        changed = True
    if not changed:
        return body, []
    out.append(body[last:])
    return "".join(out), []


# BOTH spellings. Dolphin installs a class CONSTANT with `addClassConstant:`
# and a class VARIABLE with `addClassVariable:`; this dialect binds both
# statically, so both dynamic-name calls become the assignment they mean.
# `Graphics.Color class >> initialize` uses the second for `Default` and
# `None`, and `Color default` answering nil is what made every
# `ambientBackcolor` walk fail at the desktop.
_ADD_CLASS_CONST = re.compile(
    r"self\s+addClass(?:Constant|Variable):\s*'([A-Za-z_]\w*)'\s*value:")


def rewrite_add_class_constant(src: str) -> str:
    """`self addClassConstant:/addClassVariable: 'X' value: E`  ->  `X := E`.

    Dolphin installs a class constant by NAME at runtime; this dialect binds
    class variables statically, so the dynamic-name call is turned into the
    assignment it means. `emit_class` declares every `classConstants:` name as
    a class variable, so the target exists.

    Faithful, not a shortcut: `TextEdit class >> initialize` is where Dolphin
    builds `AlignmentMap` and `FormatMap`, and `DolphinBoot` calls that
    `initialize`. The alternative — a runtime installer keyed by string — would
    need a dynamic class-variable API this dialect deliberately does not have.
    """
    return _ADD_CLASS_CONST.sub(lambda m: m.group(1) + " :=", src)


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
                                    f"`##({inner.strip()[:60]})` folded to a runtime block"))
            # A BLOCK, evaluated — not a bare parenthesised expression.
            #
            # `##(...)` is Dolphin evaluating something once at COMPILE time and
            # planting the result as a literal. When we cannot fold it, the
            # honest fallback is to evaluate it at RUNTIME instead: same value,
            # computed per call. That is a performance difference, not a
            # semantic one, for the constant-answering methods this appears in.
            #
            # It must be `[ ... ] value` rather than `( ... )` because the
            # contents are a BLOCK BODY, not necessarily an expression —
            # `ControlView>>commonNotificationMap` is `##(| nmMap | nmMap :=
            # ...)`, and wrapping that in parentheses produced `^(| nmMap | ...`
            # which does not parse. One such method took the WHOLE class file
            # down at load, which is how a refusal on one method became a
            # missing class.
            out = out[:m.start()] + "[" + inner + "] value" + out[i + 1:]
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
    # Primitive 157 copies the argument list into the first N instance
    # variables IN ORDER, so FEWER arguments than variables is well defined —
    # the remainder simply stay nil. `UI.LayoutPlacement class >> view:` is one
    # argument against `| view rectangle show |`, and refusing it left
    # `LayoutContext` unable to make a placement at all, which took the whole
    # layout down. MORE arguments than variables has nowhere to put them and is
    # still refused (`Graphics.ARGB>>fromArgbCode:` — 1 against 0 own — remains
    # a refusal, since its target is an inherited field this lowering does not
    # address).
    # THE ARGUMENTS FILL SLOTS 1..N OF THE WHOLE OBJECT, inherited fields
    # FIRST — they are not offset past the superclass's.
    #
    # Settled by evidence rather than reasoning. `UI.CreateWindowApiCall` holds
    # `rectangle dpi` (slots 1-2) and its subclass `UI.CreateWindow` holds
    # `styles title` (3-4); Dolphin's
    #
    #     CreateWindow class >> rectangle:dpi:styles:title:  <primitive: 157>
    #
    # takes exactly those four in exactly that order. An offset-past-the-parent
    # reading cannot explain it — there are only two own slots for four
    # arguments. Primitive 157 copies the argument list into the new object's
    # instance variables 1..N, full stop.
    #
    # The earlier version offset by the superclass count. Every constructor met
    # before this one had a parent with NO ivars, so the two readings gave the
    # same answer and the difference stayed invisible: `Graphics.Point x:y:`
    # and `Graphics.Rectangle origin:corner:` both sit directly under Object.
    # The first class with an ivar-carrying parent is where it would have
    # written the wrong fields, silently.
    #
    # So the total must cover the WHOLE chain: fewer arguments than slots is
    # fine (the rest stay nil), more has nowhere to go.
    total = super_ivar_count + len(cd.ivars)
    if n_args > total:
        return None, [Refusal(where, "prim157",
                              f"{cd.name}>>{m.selector}: {n_args} args vs {total} "
                              f"instance variables in the whole chain "
                              f"({super_ivar_count} inherited + {len(cd.ivars)} own) "
                              f"— nowhere to put them")]
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


def emit_loose(cls_name: str, cd, methods, renames, pool_table,
               classvar_owners=None, constant_chains=None,
               inherited_imports=None, force_class_side=True) -> EmitResult:
    """Emit LOOSE methods as a reopen of an already-existing class.

    The class itself is not translated — `OS.UserLibrary` is GENERATED from
    Dolphin's own FFI pragmas by `genprims` — but the `.pax` also files 177
    ordinary Smalltalk methods onto it: Dolphin's convenience layer over the
    raw API calls (`getWindowText: hWnd` answering a String on top of the
    three-argument call). `UI.View` uses them constantly, so without this they
    are a doesNotUnderstand in the middle of Dolphin's own code.

    The reopen must load AFTER the generated class, which is a layer-order
    obligation on the caller.
    """
    refusals: List[Refusal] = []
    lines = [
        '"GENERATED by dolphin2mst --loose. Dolphin\'s own convenience methods,',
        f' filed onto `{cls_name}` by a `.pax` rather than declared in a `.cls`.',
        " The class itself is generated from Dolphin's FFI pragmas (genprims), so",
        " this is the layer Dolphin puts ON TOP of the raw API calls. Never",
        ' hand-edit: fix the translator and re-run."',
        f"Object subclass: {cls_name} [",
    ]
    for m in methods:
        where = f"loose:{m.line}"
        body = m.body
        # ONLY PRAGMA-FREE METHODS. The `.pax` files two different kinds of
        # method onto a library class: Dolphin's convenience layer (plain
        # Smalltalk — `getWindowText: hWnd` answering a String) and the RAW
        # API declarations (`<stdcall: handle BeginPaint handle PAINTSTRUCT*>`).
        # The second kind is what `genprims` already generates from the same
        # pragmas, so emitting it here would both duplicate the floor and fail
        # to parse — the house dialect has no `<stdcall:>`.
        if m.pragmas:
            continue
        body = rewrite_qualified_classvars(body, classvar_owners)
        body = rewrite_qualified_constants(body, pool_table, constant_chains)
        # Own imports FIRST, then the inherited chain — the same order and the
        # same reason as the class path: a pool a class names itself wins over
        # one it merely inherits. Without the chain, `GWL_STYLE` in
        # `getWindowStyle:` stayed a bare name and became a runtime nil.
        imports = list(cd.imports) if cd else []
        for p in (inherited_imports or []):
            if p not in imports:
                imports.append(p)
        body, r = rewrite_pool_constants(
            body, where, imports, pool_table, set(m.arg_names))
        refusals.extend(r)
        body = rewrite_selectors(body)
        body, r = rewrite_cascades(body, where); refusals.extend(r)
        body = rewrite_add_class_constant(body)
        body, r = rewrite_hashhash(body, where); refusals.extend(r)
        body, r = rewrite_qq(body, where); refusals.extend(r)
        body = flatten_refs(body, renames)
        if m.comment:
            body = '"' + m.comment.replace('"', '""') + '"\n' + body
        # WHICH SIDE. For a LIBRARY facade every method goes class-side
        # whichever side the `.pax` filed it on: the corpus sends them to the
        # library itself — `User32 getWindowText: h`, where `User32` is an
        # alias for the class (DD9's census: the bare global is the idiom, 434
        # sites for User32 alone) — and `genprims` already put every generated
        # prim class-side for the same reason.
        #
        # For anything else the `.pax`'s own side is the answer, and forcing
        # was a silent bug: `Dolphin Value Models.pax` files `asValue` onto
        # `Core.Object` as an INSTANCE method, and
        # `ValueConvertingControlView class >> defaultModel` is `^nil asValue`.
        # Emitted class-side, `nil asValue` was a doesNotUnderstand and every
        # TextEdit failed to initialize.
        #
        # `_house_pattern` adds the prefix itself for a method the `.pax`
        # declared class-side, so it is always asked for the bare pattern.
        bare = Method(selector=m.selector, arg_names=m.arg_names,
                      pattern=m.pattern, comment=m.comment, body=m.body,
                      class_side=False, line=m.line)
        pattern = _house_pattern(bare, cls_name)
        if force_class_side or m.class_side:
            lines.append(f"    {cls_name} class >> {pattern} [")
        else:
            lines.append(f"    {pattern} [")
        lines.append(_indent(body.strip("\n")))
        lines.append("    ]")
    lines.append("]")
    return EmitResult("\n".join(lines) + "\n", refusals)


def emit_class(pf: ParsedFile, renames: Dict[str, str],
               super_ivars: Dict[str, Optional[int]],
               pool_table=None, extra_methods: Optional[List[Method]] = None,
               classdef: Optional[ClassDef] = None,
               inherited_imports: Optional[List[str]] = None,
               classvar_owners: Optional[Dict[str, set]] = None,
               constant_chains: Optional[Dict[str, List[str]]] = None) -> EmitResult:
    cd = classdef or pf.classdef
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
    # Class VARIABLES plus every `classConstants:` NAME. A class constant whose
    # value is a literal is folded at translation time and the declaration is
    # then unused; one whose value is an EXPRESSION is installed at runtime by
    # the class's own `initialize` (`self addClassConstant: 'AlignmentMap'
    # value: (IdentityDictionary withAll: ...)`, rewritten to an assignment),
    # and its code reads the bare name. Without the declaration that read was
    # an unbound global — a runtime nil, in `UI.TextEdit>>alignment`.
    cvars = list(cd.cvars)
    for _cc in pools.class_constant_names(cd.class_constants):
        if _cc not in cvars:
            cvars.append(_cc)
    if cvars:
        lines.append(f"    <classVars: {' '.join(cvars)}>")
        # READERS for every class variable. `Point.Zero` in another class is
        # rewritten to `Point classVarZero`, and this is what it lands on —
        # emitted for all of them rather than only the referenced ones, so the
        # rewrite is always resolvable for a translated owner without tracking
        # cross-file usage. One line each.
        for _cv in cvars:
            lines.append(f"    {name} class >> {classvar_accessor(_cv)} "
                         f"[ ^{_cv} ]")
            # AND THE SETTER. A qualified class-variable WRITE from another
            # class (`Cursor.Current := self` in `Graphics.Icon>>showWhile:`)
            # rewrites to `Cursor classVarCurrent: self`, so the pair must be
            # emitted together — a reader without a writer just moves the
            # failure from the parser to the first send.
            lines.append(f"    {name} class >> {classvar_accessor(_cv)}: v "
                         f"[ ^{_cv} := v ]")
    if cd.ivars:
        lines.append(f"    | {' '.join(cd.ivars)} |")
    if cd.cvars or cd.ivars:
        lines.append("")

    # Loose methods filed onto this class from a `.pax` land here alongside the
    # class's own — the User32 binding is 177 such methods on `OS.UserLibrary`.
    all_methods = list(pf.methods if classdef is None or classdef is pf.classdef else [])
    all_methods.extend(extra_methods or [])
    shadowed = set(cd.ivars) | set(cd.cvars) | set(cd.civars)

    # A class's OWN `classConstants:` is an implicit pool for its own methods.
    # The struct classes lean on this heavily — `OS.DTBGOPTS` computes field
    # offsets as `##(_OffsetOf_rcClip + 1)`, where `_OffsetOf_rcClip` is its own
    # class constant, not an imported one. Without this, every struct accessor
    # refused as "not a foldable constant".
    own_imports = list(cd.imports)
    if pool_table is not None and cd.class_constants and cd.class_constants != "{}":
        if pool_table.add(cd.name, cd.class_constants):
            own_imports.insert(0, cd.name)
    # POOL IMPORTS ARE INHERITED. A class binds a bare constant name through its
    # own pools first, then its superclass's, on up the chain — so `imports: #()`
    # does not mean "no pools". Measured on the DD9 wave: `UI.ContainerView`
    # declares no imports and still writes `WS_EX_CONTROLPARENT`, inheriting
    # `OS.Win32Constants` from `UI.View`; `UI.ShellView` declares only
    # `OS.ButtonConstants` and writes `WS_SYSMENU`. Folding only the OWN imports
    # left both unfolded, and each surfaced at RUNTIME as a nil in a bitOr
    # (`_bitOrFromInteger was called on null`) — never as a translation refusal.
    # The ancestors' own class constants ride along for the same reason.
    for p in (inherited_imports or []):
        if p not in own_imports:
            own_imports.append(p)

    for m in all_methods:
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
            # Pools fold BEFORE `##()`, so a compile-time expression written
            # over pool names (`##(BM_CLICK bitOr: 4)`) has literals to fold.
            body = rewrite_qualified_classvars(body, classvar_owners)
            body = rewrite_qualified_constants(body, pool_table,
                                               constant_chains)
            body, r = rewrite_pool_constants(
                body, where, own_imports, pool_table, shadowed | set(m.arg_names))
            refusals.extend(r)
            body = rewrite_selectors(body)
            body, r = rewrite_cascades(body, where); refusals.extend(r)
            body = rewrite_add_class_constant(body)
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
