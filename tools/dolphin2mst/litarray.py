"""Lower Dolphin `#{Namespace.Name}` variable-binding literals.

A binding literal denotes the BINDING, not the value — Dolphin's compiler
creates a `VariableBinding` at compile time and `#{Core.Array} value` answers
the class. The house dialect has no such literal, so every method containing
one was refused outright (45 of them), and that single refusal is what kept
`resource_Default_view` — the literal array that IS a Dolphin window — out of
the translated image.

TWO PLACES THEY APPEAR, needing different treatment:

  * **In ordinary code** — `#{Graphics.Icon} value fromId: ...`. A direct
    textual substitution works: the binding becomes an expression.

  * **Inside a LITERAL ARRAY** — `^#(#'!STL' 6 ... #{UI.STBViewProxy} ...)`.
    A literal array cannot hold a runtime expression, so the whole array is
    rewritten as a BRACE array `{ ... }` whose elements are expressions. That
    is sound here because the filer only WALKS the array; nothing depends on
    it being a compile-time literal.

THE TRAP IN THAT REWRITE, and the reason this is a parser and not a regex:
inside a literal array a BARE WORD IS A SYMBOL. `#(foo bar)` is two symbols,
while `{ foo. bar }` is two variable references. Every bare identifier must
therefore be emitted as an explicit `#symbol` — except `nil`, `true` and
`false`, which denote themselves in both forms. Getting that wrong produces
source that compiles and means something else, which is exactly what the
original blanket refusal was protecting against.

Nested arrays, byte arrays (`#[1 2 3]`), scaled/negative numbers, character
literals and quoted symbols all have to survive intact, so the scanner is a
real tokeniser.
"""
from __future__ import annotations

import re
from typing import List, Tuple

BINDING = re.compile(r"#\{\s*([A-Za-z_][\w.]*)\s*\}")


def binding_expr(path: str) -> str:
    """`#{UI.STBViewProxy}` -> the expression that answers that binding."""
    return "(VariableBinding path: '%s')" % path


class _Scan:
    """Minimal Smalltalk literal scanner, positioned inside a literal array."""

    def __init__(self, s: str, i: int):
        self.s = s
        self.i = i

    def skip_ws(self):
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == '"':                      # a comment, even in an array
                j = s.find('"', self.i + 1)
                self.i = n if j < 0 else j + 1
            else:
                return

    def element(self) -> Tuple[str, bool]:
        """Answer (source-for-brace-array, contains_binding)."""
        self.skip_ws()
        s, n = self.s, len(self.s)
        if self.i >= n:
            return "", False
        c = s[self.i]

        # #{Binding}
        m = BINDING.match(s, self.i)
        if m:
            self.i = m.end()
            return binding_expr(m.group(1)), True

        # Nested literal array, with or without the '#'
        if c == "#" and self.i + 1 < n and s[self.i + 1] == "(":
            self.i += 1
            return self.array()
        if c == "(":
            return self.array()

        # Byte array #[...] — no bindings possible inside
        if c == "#" and self.i + 1 < n and s[self.i + 1] == "[":
            j = s.find("]", self.i)
            j = n if j < 0 else j + 1
            out = s[self.i:j]
            self.i = j
            return out, False

        # String or quoted symbol
        if c == "'" or (c == "#" and self.i + 1 < n and s[self.i + 1] == "'"):
            start = self.i
            self.i += 2 if c == "#" else 1
            while self.i < n:
                if s[self.i] == "'":
                    if self.i + 1 < n and s[self.i + 1] == "'":
                        self.i += 2
                        continue
                    self.i += 1
                    break
                self.i += 1
            return s[start:self.i], False

        # Character literal
        if c == "$" and self.i + 1 < n:
            out = s[self.i:self.i + 2]
            self.i += 2
            return out, False

        # #symbol (including #foo:bar:)
        if c == "#":
            start = self.i
            self.i += 1
            while self.i < n and (s[self.i].isalnum() or s[self.i] in "_:."):
                self.i += 1
            return s[start:self.i], False

        # Anything else: a run up to whitespace or a delimiter.
        start = self.i
        while self.i < n and s[self.i] not in " \t\r\n()":
            self.i += 1
        tok = s[start:self.i]
        # BARE WORD IN A LITERAL ARRAY IS A SYMBOL — but nil/true/false are
        # themselves. This is the whole reason for parsing rather than
        # substituting.
        if re.match(r"^[A-Za-z_][\w:.]*$", tok) and tok not in ("nil", "true",
                                                                "false"):
            return "#" + tok, False
        return tok, False

    def array(self) -> Tuple[str, bool]:
        """At '(' — consume the array, answer (source, contains_binding)."""
        assert self.s[self.i] == "("
        self.i += 1
        raw_start = self.i
        parts: List[str] = []
        found = False
        n = len(self.s)
        while True:
            self.skip_ws()
            if self.i >= n:
                break
            if self.s[self.i] == ")":
                raw_end = self.i
                self.i += 1
                break
            src, has = self.element()
            if src == "":
                break
            parts.append(src)
            found = found or has
        else:
            raw_end = self.i
        if found:
            return "{" + ". ".join(parts) + "}", True
        # No binding anywhere inside: keep the ORIGINAL literal text, so a
        # method that merely contains arrays is not needlessly rewritten.
        return "#(" + self.s[raw_start:raw_end] + ")", False


def lower(body: str) -> str:
    """Rewrite every binding literal in `body`, arrays included."""
    if "#{" not in body:
        return body
    out = []
    i = 0
    n = len(body)
    while i < n:
        # `##(` IS NOT `#(`. A compile-time expression contains the literal
        # array marker at offset 1, so scanning for `#(` naively treats
        # `##({ ... })` as an array and mangles everything after it —
        # `STBInFiler class >> predefinedClasses` is `^##({#{AnsiString}.
        # Array. ...})` and came out as unparseable soup. Copy both `#`s and
        # let the `##()` rewriter downstream deal with it; the binding inside
        # is still lowered by the ordinary substitution below.
        if body[i] == "#" and i + 1 < n and body[i + 1] == "#":
            out.append("##")
            i += 2
            continue
        # A literal array that CONTAINS a binding becomes a brace array.
        if body[i] == "#" and i + 1 < n and body[i + 1] == "(":
            sc = _Scan(body, i + 1)
            src, _has = sc.array()
            out.append(src)
            i = sc.i
            continue
        m = BINDING.match(body, i)
        if m:
            out.append(binding_expr(m.group(1)))
            i = m.end()
            continue
        # Skip over string literals so a `#{` inside one is left alone.
        if body[i] == "'":
            j = i + 1
            while j < n:
                if body[j] == "'":
                    if j + 1 < n and body[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(body[i:j])
            i = j
            continue
        out.append(body[i])
        i += 1
    return "".join(out)


if __name__ == "__main__":
    # Self-test: run `python litarray.py` — no framework, deliberately.
    cases = [
        # plain code
        ("^#{Graphics.Icon} value fromId: x",
         "^(VariableBinding path: 'Graphics.Icon') value fromId: x"),
        # array with no binding is untouched
        ("^#(1 2 3)", "^#(1 2 3)"),
        # bare words in an untouched array stay bare
        ("^#(foo bar)", "^#(foo bar)"),
        # array WITH a binding becomes a brace array, bare words become symbols
        ("^#(foo #{Core.Array} nil 7)",
         "^{#foo. (VariableBinding path: 'Core.Array'). nil. 7}"),
        # quoted symbol and string survive
        ("^#(#'!STL' 'hi' #{A.B})",
         "^{#'!STL'. 'hi'. (VariableBinding path: 'A.B')}"),
        # byte array survives
        ("^#(#{A.B} #[1 2 3])",
         "^{(VariableBinding path: 'A.B'). #[1 2 3]}"),
        # nested array containing a binding
        ("^#(1 #(2 #{X.Y}))",
         "^{1. {2. (VariableBinding path: 'X.Y')}}"),
        # nested array WITHOUT a binding keeps literal form
        ("^#(#{X.Y} #(2 3))",
         "^{(VariableBinding path: 'X.Y'). #(2 3)}"),
        # true/false/nil are not symbols
        ("^#(true false nil #{Q.R})",
         "^{true. false. nil. (VariableBinding path: 'Q.R')}"),
        # `##(` IS NOT `#(` — the compile-time marker must survive, and the
        # BRACE array inside it keeps bare words as VARIABLES, not symbols.
        # This is `STBInFiler class >> predefinedClasses`, which the first
        # version turned into unparseable soup.
        ("^##({#{AnsiString}. Array. ByteArray})",
         "^##({(VariableBinding path: 'AnsiString'). Array. ByteArray})"),
        # a `##()` with no binding at all is left completely alone
        ("^##(350 @ 250)", "^##(350 @ 250)"),
        # a binding inside a string literal is NOT a binding
        ("^'see #{Foo} here'", "^'see #{Foo} here'"),
    ]
    bad = 0
    for src, want in cases:
        got = lower(src)
        if got != want:
            bad += 1
            print("FAIL  %s\n  got  %s\n  want %s" % (src, got, want))
    print("litarray self-test: %d/%d" % (len(cases) - bad, len(cases)))
    raise SystemExit(1 if bad else 0)
