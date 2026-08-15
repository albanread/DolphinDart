"""Golden tests, one per rewrite class (DD3).

    python test_rewrites.py

No framework: this runs anywhere Python does, including before anything else in
the toolchain works. Each case is (input, expected) or (input, expected-refusal),
so a rewrite that silently changes behaviour fails here rather than in the image.
"""
from __future__ import annotations

import sys

from chunks import split_chunks
from stlex import strip_code, is_balanced
from parse import parse_pattern, parse_classdef, parse_method
from chunks import Chunk
from emit import rewrite_qq, rewrite_hashhash, flatten_refs, lower_prim157
from parse import ClassDef, Method

FAILS = []


def check(label, got, want):
    if got != want:
        FAILS.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


# --- stlex: the scanner everything else trusts -------------------------------
check("strip: comment blanked",
      strip_code('a "cmt" b').strip(), "a       b".strip())
check("strip: escaped quote inside comment",
      strip_code('x "a""b" y').count('"'), 0)
check("strip: $\" char literal does not open a comment",
      strip_code('a $" b "c" d').count("c"), 0)
check("strip: $' char literal does not open a string",
      strip_code("a $' b 'c' d").count("c"), 0)
check("balanced: plain", is_balanced("a 'b' \"c\" d"), True)
check("balanced: unterminated string", is_balanced("a 'b"), False)

# --- chunks: bang escaping ---------------------------------------------------
cs = split_chunks("one!two!")
check("chunks: simple split", [c.text.strip() for c in cs], ["one", "two"])
cs = split_chunks("a!!b!c!")
check("chunks: !! is an escaped bang, not a terminator",
      [c.text.strip() for c in cs], ["a!b", "c"])

# --- parse: method patterns --------------------------------------------------
check("pattern: unary", parse_pattern("asPoint"), ("asPoint", []))
check("pattern: binary", parse_pattern("+ anArithmeticValue"), ("+", ["anArithmeticValue"]))
check("pattern: keyword", parse_pattern("x: xCoord y: yCoord"),
      ("x:y:", ["xCoord", "yCoord"]))
check("pattern: keyword, one part", parse_pattern("at: anIndex"), ("at:", ["anIndex"]))

# --- parse: class definition (both dialect generations) ----------------------
modern = Chunk("""Core.ArithmeticValue
\tsubclass: #'Graphics.Point'
\tinstanceVariableNames: 'x y'
\tclassVariableNames: 'Zero'
\timports: #()
\tclassInstanceVariableNames: ''
\tclassConstants: {}""", 1)
cd = parse_classdef(modern)
check("classdef: name", cd.name, "Graphics.Point")
check("classdef: super", cd.superclass, "Core.ArithmeticValue")
check("classdef: ivars", cd.ivars, ["x", "y"])
check("classdef: cvars", cd.cvars, ["Zero"])
check("classdef: namespace/base", (cd.namespace, cd.base), ("Graphics", "Point"))
check("classdef: not legacy", cd.legacy, False)

legacy = Chunk("""Object
\tsubclass: #IPAddressView
\tinstanceVariableNames: 'a b'
\tclassVariableNames: ''
\tpoolDictionaries: 'Win32Constants'
\tclassInstanceVariableNames: ''""", 1)
cdl = parse_classdef(legacy)
check("classdef: legacy detected", cdl.legacy, True)
check("classdef: legacy has no namespace", cdl.namespace, "")

# --- parse: a pragma occupies a whole line, `<` is an operator ---------------
m = parse_method(Chunk("""foo: a
\t"doc"

\t<primitive: 157>
\t^self""", 1), False)
check("pragma: recognised on its own line", m.pragmas, ["<primitive: 157>"])
m2 = parse_method(Chunk("""bar: yCorner
\t"doc"

\t^self top < yCorner ifTrue: [1] ifFalse: [2]""", 1), False)
check("pragma: a `<` comparison is NOT a pragma", m2.pragmas, [])

# --- rewrite: ?? -------------------------------------------------------------
out, ref = rewrite_qq("^cause ?? #unknown", "t:1")
check("qq: symbol operand", out.strip(), "^(cause ifNil: [ #unknown ])")
check("qq: no refusal", ref, [])
out, ref = rewrite_qq("^legacyHandlers ?? #()", "t:1")
check("qq: empty-array operand", out.strip(), "^(legacyHandlers ifNil: [ #() ])")
# Binary binds tighter than keyword, so this is `(a ?? b) foo: c`. Spliced bare
# it would read as the single keyword message `ifNil:foo:` — hence the parens.
out, ref = rewrite_qq("^a ?? b foo: c", "t:1")
check("qq: parenthesises so a following keyword cannot merge",
      out.strip(), "^(a ifNil: [ b ]) foo: c")
# And the LEFT operand must not swallow a preceding keyword part.
out, ref = rewrite_qq("^self foo: a ?? b", "t:1")
check("qq: left operand bounded to the primary",
      out.strip(), "^self foo: (a ifNil: [ b ])")
out, ref = rewrite_qq("\"a ?? b\" ^1", "t:1")
check("qq: ignores `??` inside a comment", ref, [])

# --- rewrite: ##( ) ----------------------------------------------------------
out, ref = rewrite_hashhash("^##(3 + 4)", "t:1")
check("hashhash: folds integer arithmetic", out.strip(), "^7")
out, ref = rewrite_hashhash("^##(1 bitShift: 4)", "t:1")
check("hashhash: folds bitShift:", out.strip(), "^16")
out, ref = rewrite_hashhash("^##(16r0F)", "t:1")
check("hashhash: folds radix literal", out.strip(), "^15")
out, ref = rewrite_hashhash("^##('hi')", "t:1")
check("hashhash: folds a string literal", out.strip(), "^'hi'")
out, ref = rewrite_hashhash("^##(Behavior _GetSpecialMask bitOr: 4)", "t:1")
check("hashhash: refuses a non-constant", len(ref), 1)
check("hashhash: leaves the expression parenthesised after refusing",
      out.strip(), "^(Behavior _GetSpecialMask bitOr: 4)")

# --- rewrite: selector spellings ---------------------------------------------
from emit import rewrite_selectors
check("selectors: asUnicodeValue -> value",
      rewrite_selectors("^aChar asUnicodeValue"), "^aChar value")
check("selectors: leaves comments alone",
      rewrite_selectors('"asUnicodeValue here" ^1'), '"asUnicodeValue here" ^1')
check("selectors: leaves strings alone",
      rewrite_selectors("^'asUnicodeValue'"), "^'asUnicodeValue'")
check("selectors: does not touch a keyword part of the same spelling",
      rewrite_selectors("^x asUnicodeValue: 1"), "^x asUnicodeValue: 1")

# --- rewrite: cascades -------------------------------------------------------
from emit import rewrite_cascades
# The case that blocked UI.View: Dolphin allows a whole message chain as a
# cascade part; this dialect allows one message.
out, ref = rewrite_cascades("^self destroy; isOpen not", "t:1")
check("cascade: multi-message part becomes statements",
      out.strip(), "self destroy. ^self isOpen not")
check("cascade: no refusal on a simple receiver", ref, [])
out, ref = rewrite_cascades("Transcript show: 'x'; cr", "t:1")
check("cascade: keyword + unary parts",
      out.strip(), "Transcript show: 'x'. Transcript cr")
out, ref = rewrite_cascades("^self a; b", "t:1")
check("cascade: the last part carries the return", out.strip(), "self a. ^self b")
out, ref = rewrite_cascades("^self foo", "t:1")
check("cascade: untouched when there is no cascade", out, "^self foo")
# THE CASCADE RECEIVER IS THE RECEIVER OF THE LAST MESSAGE, not the first token.
# This is the shape lower_prim157 emits, and reading only `self` made every
# D157 constructor write its fields into the CLASS and answer the class.
out, ref = rewrite_cascades(
    "^self basicNew instVarAt: 1 put: a; instVarAt: 2 put: b; yourself", "t:1")
check("cascade: a `primary unary` receiver is bound to a temp, once",
      out.strip(),
      "| _casc1 | _casc1 := self basicNew. _casc1 instVarAt: 1 put: a. "
      "_casc1 instVarAt: 2 put: b. ^_casc1 yourself")
check("cascade: and that is not a refusal", ref, [])
out, ref = rewrite_cascades("| x | ^x foo bar baz; qux", "t:1")
check("cascade: several unaries all belong to the receiver",
      out.strip(),
      "| x _casc1 | _casc1 := x foo bar. _casc1 baz. ^_casc1 qux")
out, ref = rewrite_cascades("^self basicNew setA: 1; setB: 2; yourself", "t:1")
check("cascade: keyword parts bind the same way", out.strip(),
      "| _casc1 | _casc1 := self basicNew. _casc1 setA: 1. _casc1 setB: 2. "
      "^_casc1 yourself")
# A temp name already in the body must not be reused.
out, ref = rewrite_cascades("| _casc1 | ^self basicNew a; b", "t:1")
check("cascade: the temp name avoids one already present",
      "_casc2 := self basicNew" in out, True)
out, ref = rewrite_cascades('"a ; b" ^1', "t:1")
check("cascade: ignores a `;` inside a comment", out, '"a ; b" ^1')
# A non-primary receiver would be evaluated once PER PART if split, so refuse.
out, ref = rewrite_cascades("^(self viewAt: 1) a; b", "t:1")
check("cascade: refuses a non-primary receiver", len(ref), 1)

# --- temporaries vs. the binary `|` operator ---------------------------------
# The DD9 silent-wrong-answer: a bare `|...|` pair scan reads a bitOr chain as
# a declaration and shadows alternate operands, so they never fold and the
# method answers nil at runtime instead of refusing at translation.
from emit import collect_temps
check("temps: a real method declaration",
      collect_temps("| a b |  ^a + b"), {"a", "b"})
check("temps: a bitOr chain declares NOTHING",
      collect_temps("^(WS_THICKFRAME | WS_CAPTION | WS_SYSMENU | WS_MAXIMIZEBOX)"),
      set())
check("temps: declaration then a bitOr chain",
      collect_temps("| mask | mask := WS_BORDER | WS_CAPTION | WS_SYSMENU. ^mask"),
      {"mask"})
check("temps: block temporaries count",
      collect_temps("^[ | t | t := 1. t ] value"), {"t"})
check("temps: block ARGUMENTS are not temps, and the arg bar is not a decl",
      collect_temps("^coll inject: 0 into: [ :acc :each | acc | each ]"), set())
check("temps: block args followed by real temps",
      collect_temps("^coll do: [ :each | | tmp | tmp := each ]"), {"tmp"})
check("temps: a `|` inside a comment opens nothing",
      collect_temps(strip_code('"a | b |" ^X | Y')), set())

# --- pool imports are INHERITED ----------------------------------------------
# The DD9 case: ContainerView declares `imports: #()` and still writes
# WS_EX_CONTROLPARENT, binding it through View's OS.Win32Constants. Folding only
# a class's own imports left it as a bare name that became a runtime nil.
from cli import inherited_pool_chain
_view = ClassDef(name="UI.View", superclass="Core.Object", ivars=[], cvars=[],
                 civars=[], imports=["OS.Win32Constants", "OS.Win32Errors"],
                 class_constants="{}")
_cont = ClassDef(name="UI.ContainerView", superclass="UI.View", ivars=[],
                 cvars=[], civars=[], imports=[], class_constants="{}")
_shell = ClassDef(name="UI.ShellView", superclass="UI.ContainerView", ivars=[],
                  cvars=[], civars=[], imports=["OS.ButtonConstants"],
                  class_constants="{ 'TransientMask' -> 1 }")
_by = {c.name: c for c in (_view, _cont, _shell)}
# An ancestor OUTSIDE the parsed+reference set contributes nothing — it has no
# ClassDef to read imports from. That is why the kernel classes must be passed
# as `--reference` inputs when a translated class binds through their pools.
check("imports: a class whose parent was never parsed inherits nothing",
      inherited_pool_chain(_by, "UI.View"), [])
check("imports: a class with `imports: #()` still sees its parent's pools",
      inherited_pool_chain(_by, "UI.ContainerView"),
      ["UI.View", "OS.Win32Constants", "OS.Win32Errors"])
check("imports: the chain is walked to the root, nearest ancestor first",
      inherited_pool_chain(_by, "UI.ShellView"),
      ["UI.ContainerView", "UI.View", "OS.Win32Constants", "OS.Win32Errors"])

# --- rewrite: namespace flattening -------------------------------------------
check("flatten: dotted reference",
      flatten_refs("^Graphics.Point x: 1 y: 2", {}), "^Point x: 1 y: 2")
check("flatten: leaves comments alone",
      flatten_refs('"see Graphics.Point" ^1', {}), '"see Graphics.Point" ^1')
check("flatten: honours a rename",
      flatten_refs("^Graphics.Point new", {"Graphics.Point": "DPoint"}), "^DPoint new")

# --- rewrite: primitive 157 --------------------------------------------------
cd157 = ClassDef(name="Graphics.Point", superclass="Core.ArithmeticValue",
                 ivars=["x", "y"], cvars=[], civars=[], imports=[], class_constants="{}")
m157 = Method(selector="x:y:", arg_names=["xc", "yc"], pattern="x: xc y: yc",
              comment="", body="", class_side=True, line=1)
got, ref = lower_prim157(m157, cd157, "t:1", 0)
check("prim157: lowers to basicNew + ivar stores", got,
      "^self basicNew instVarAt: 1 put: xc; instVarAt: 2 put: yc; yourself")
check("prim157: no refusal on the clean case", ref, [])

got, ref = lower_prim157(m157, cd157, "t:1", None)
check("prim157: refuses an unknown superclass ivar count", (got, len(ref)), (None, 1))
# Inherited fields come FIRST in the instVarAt: order, so a superclass with 3
# of its own pushes this class's variables to slots 4 and 5. Off-by-one here
# shifts every field of every instance, so the arithmetic is pinned exactly.
got, ref = lower_prim157(m157, cd157, "t:1", 3)
check("prim157: offsets past the superclass's fields", got,
      "^self basicNew instVarAt: 4 put: xc; instVarAt: 5 put: yc; yourself")
check("prim157: no refusal once the count is known", ref, [])

# FEWER args than ivars is well defined: the first N are set, the rest stay nil.
# Refusing this left LayoutContext unable to make a placement at all.
m_few = Method(selector="x:", arg_names=["only"], pattern="x: only", comment="",
               body="", class_side=True, line=1)
got, ref = lower_prim157(m_few, cd157, "t:1", 0)
check("prim157: fewer args than ivars sets the first ones", got,
      "^self basicNew instVarAt: 1 put: only; yourself")
check("prim157: and is not a refusal", ref, [])
# MORE args than ivars has nowhere to put them.
cd0 = ClassDef(name="Graphics.ARGB", superclass="Graphics.AbstractRGB", ivars=[],
               cvars=[], civars=[], imports=[], class_constants="{}")
got, ref = lower_prim157(m_few, cd0, "t:1", 1)
check("prim157: more args than ivars is still refused", (got, len(ref)), (None, 1))

# --- report ------------------------------------------------------------------
if FAILS:
    print(f"FAIL: {len(FAILS)} golden case(s)\n")
    for f in FAILS:
        print("  " + f)
    sys.exit(1)
print("dolphin2mst golden tests: all pass")
