"""Give Dolphin chunks their meaning (DD3).

A `.cls` file is a sequence of chunks whose *shapes* are:

    Core.ArithmeticValue
        subclass: #'Graphics.Point'
        instanceVariableNames: 'x y'
        classVariableNames: 'Zero'
        imports: #()
        classInstanceVariableNames: ''
        classConstants: {}

    Graphics.Point guid: (Core.GUID fromString: '{...}')
    Graphics.Point comment: '...'
    !Graphics.Point categoriesForClass!Graphics-Geometry! !
    !Graphics.Point methodsFor!            <- a SECTION header; method chunks follow
    !Graphics.Point class methodsFor!      <- the class side
    !Graphics.Point categoriesForMethods!  <- metadata we drop

Legacy (Dolphin 7) files use `poolDictionaries:` instead of `imports:`, carry an
unquoted `#Name` symbol, and have no namespace — six such classes exist in the
corpus (DD2). They are parsed, flagged, and given a namespace by the caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from chunks import Chunk, split_chunks, read_source
from stlex import strip_code

# --- shapes -----------------------------------------------------------------


@dataclass
class Method:
    selector: str                 # 'x:y:' / '+' / 'asPoint'
    arg_names: List[str]
    pattern: str                  # the raw first line, for reports
    comment: str                  # the leading "..." comment, un-quoted
    body: str                     # source after the comment
    class_side: bool
    line: int
    pragmas: List[str] = field(default_factory=list)


@dataclass
class ClassDef:
    name: str                     # fully-qualified: 'Graphics.Point'
    superclass: str               # fully-qualified: 'Core.ArithmeticValue'
    ivars: List[str]
    cvars: List[str]
    civars: List[str]
    imports: List[str]
    class_constants: str
    comment: str = ""
    legacy: bool = False          # Dolphin-7 form (poolDictionaries:, no namespace)
    line: int = 0

    @property
    def namespace(self) -> str:
        return self.name.rsplit(".", 1)[0] if "." in self.name else ""

    @property
    def base(self) -> str:
        return self.name.rsplit(".", 1)[-1]


@dataclass
class ParsedFile:
    path: str
    classdef: Optional[ClassDef]
    methods: List[Method]
    refusals: List[str] = field(default_factory=list)
    # DD3b: a `.pax` holds MANY class definitions and files LOOSE METHODS onto
    # classes defined elsewhere — `Dolphin MVP Base.pax` alone carries three
    # shared pools and 181 `OS.UserLibrary` methods. So a parsed file is not
    # "one class": `classdefs` holds every definition it declares, and
    # `loose` maps target-class-name -> methods filed onto it.
    classdefs: List[ClassDef] = field(default_factory=list)
    loose: Dict[str, List[Method]] = field(default_factory=dict)


# --- the class-definition chunk ---------------------------------------------

_SUBCLASS_RE = re.compile(
    r"^\s*(?P<super>[A-Za-z][\w.]*)\s*\n?\s*subclass:\s*#'?(?P<name>[\w.]+)'?",
    re.S,
)


def _kw_string(chunk: str, keyword: str) -> Optional[str]:
    """Value of `keyword: '...'` in a class-definition chunk."""
    m = re.search(keyword + r":\s*'((?:[^']|'')*)'", chunk)
    return m.group(1).replace("''", "'") if m else None


def _kw_array(chunk: str, keyword: str) -> Optional[List[str]]:
    m = re.search(keyword + r":\s*#\((.*?)\)", chunk, re.S)
    if not m:
        return None
    # Entries look like `{OS.Win32Constants}` — a brace-wrapped binding
    # reference — or a bare/quoted symbol. Strip both wrappers: leaving the
    # braces on made every pool import unmatchable, so no bare pool constant
    # folded and `##(MIIM_STRING | MIIM_ID)` refused as "not constant".
    return [t.strip().strip("#'").strip("{}") for t in m.group(1).split() if t.strip()]


def parse_classdef(chunk: Chunk) -> Optional[ClassDef]:
    m = _SUBCLASS_RE.match(chunk.text)
    if not m:
        return None
    body = chunk.text
    legacy = "poolDictionaries:" in body and "imports:" not in body
    imports = _kw_array(body, "imports")
    if imports is None:
        imports = _kw_array(body, "poolDictionaries") or []
    cc = re.search(r"classConstants:\s*(\{.*?\})", body, re.S)
    return ClassDef(
        name=m.group("name"),
        superclass=m.group("super"),
        ivars=(_kw_string(body, "instanceVariableNames") or "").split(),
        cvars=(_kw_string(body, "classVariableNames") or "").split(),
        civars=(_kw_string(body, "classInstanceVariableNames") or "").split(),
        imports=imports,
        class_constants=cc.group(1).strip() if cc else "{}",
        legacy=legacy,
        line=chunk.line,
    )


# --- method chunks ----------------------------------------------------------

# Section headers arrive WITHOUT their leading bang. In the file they read
# `!Graphics.Point methodsFor!`, but that opening `!` terminates the preceding
# chunk, so the splitter hands us `Graphics.Point methodsFor`. The `what` is
# whitelisted rather than left open (`\w+`) so an ordinary unary method cannot
# be mistaken for a section header; an unrecognised header still becomes a
# refusal via the fall-through in `parse_file`.
_SECTION_RE = re.compile(
    r"^(?P<name>[A-Z][\w.]*)(?P<side>\s+class)?\s+"
    r"(?P<what>methodsFor|categoriesForClass|categoriesForMethods|methodProtocol\w*)\s*$"
)
_COMMENT_RE = re.compile(r"^\s*\"((?:[^\"]|\"\")*)\"\s*", re.S)
# A pragma occupies a WHOLE LINE of its own (after the method comment). It must
# be anchored that way: Smalltalk's binary `<` and `>` are ordinary selectors, so
# an unanchored `<[^<>]*>` happily matches from a comparison to a later `>` and
# swallows real code. Measured on the first corpus run: Graphics.Rectangle:59
# `... < yCorner ifTrue: [areas addLast: (self left @ (` was reported as a
# "pragma" and the method dropped.
_PRAGMA_RE = re.compile(r"^[ \t]*(<[^<>\n]*>)[ \t]*$", re.M)

_BINARY_CHARS = set("+-*/\\~<>=@%|&?,")


def parse_pattern(first_line: str):
    """Return (selector, arg_names) for a Smalltalk method pattern line."""
    s = first_line.strip()
    kw = re.findall(r"([A-Za-z_]\w*:)\s*([A-Za-z_]\w*)", s)
    if kw and s.split()[0].endswith(":"):
        return "".join(k for k, _ in kw), [a for _, a in kw]
    m = re.match(r"^([" + re.escape("".join(_BINARY_CHARS)) + r"]+)\s+([A-Za-z_]\w*)", s)
    if m:
        return m.group(1), [m.group(2)]
    m = re.match(r"^([A-Za-z_]\w*)\s*$", s)
    if m:
        return m.group(1), []
    m = re.match(r"^([A-Za-z_]\w*)", s)
    return (m.group(1), []) if m else (s, [])


def parse_method(chunk: Chunk, class_side: bool) -> Optional[Method]:
    text = chunk.text.strip("\n")
    if not text.strip():
        return None
    nl = text.find("\n")
    first, rest = (text, "") if nl < 0 else (text[:nl], text[nl + 1:])
    selector, args = parse_pattern(first)
    comment = ""
    cm = _COMMENT_RE.match(rest)
    if cm:
        comment = cm.group(1).replace('""', '"').strip()
        rest = rest[cm.end():]
    pragmas = _PRAGMA_RE.findall(strip_code(rest))
    return Method(
        selector=selector, arg_names=args, pattern=first.strip(), comment=comment,
        body=rest.strip("\n"), class_side=class_side, line=chunk.line,
        pragmas=[p.strip() for p in pragmas],
    )


# --- whole file -------------------------------------------------------------

# Section headers we understand. Anything else becomes a refusal rather than
# being silently skipped — the corpus is 25 years old and full of surprises,
# and silence is the failure mode this project keeps paying for.
_DROP_SECTIONS = {"categoriesForMethods", "categoriesForClass", "methodProtocol"}


def parse_file(path: str) -> ParsedFile:
    src = read_source(path)
    chunks = split_chunks(src)
    cd: Optional[ClassDef] = None
    classdefs: List[ClassDef] = []
    by_name: Dict[str, ClassDef] = {}
    methods: List[Method] = []
    loose: Dict[str, List[Method]] = {}
    refusals: List[str] = []
    mode: Optional[bool] = None      # None = not in a methods section; else class_side
    target: Optional[str] = None     # which class the current section files onto

    for ch in chunks:
        head = ch.text.strip()
        sm = _SECTION_RE.match(head) if "\n" not in head else None
        if sm:
            if sm.group("what") == "methodsFor":
                mode = bool(sm.group("side"))
                target = sm.group("name")
            else:
                mode, target = None, None
            continue
        if mode is None:
            maybe = parse_classdef(ch)
            if maybe:
                classdefs.append(maybe)
                by_name[maybe.name] = maybe
                if cd is None:
                    cd = maybe          # the first definition is the file's own
                continue
            cm = re.match(r"^\s*([\w.]+)\s+comment:\s*'((?:[^']|'')*)'", ch.text, re.S)
            if cm:
                owner = by_name.get(cm.group(1))
                if owner is not None:
                    owner.comment = cm.group(2).replace("''", "'")
                continue
            # guid:, categoriesFor..., binary metadata: all droppable
            continue
        m = parse_method(ch, mode)
        if m:
            # A method belongs to the class its SECTION names. In a `.cls` that
            # is always the file's own class; in a `.pax` it is usually not.
            if target and cd is not None and target == cd.name:
                methods.append(m)
            elif target:
                loose.setdefault(target, []).append(m)
            else:
                methods.append(m)
    return ParsedFile(path=path, classdef=cd, methods=methods, refusals=refusals,
                      classdefs=classdefs, loose=loose)
