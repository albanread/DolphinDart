"""Dolphin external-call types → house FFI argument codes (DD6b).

Built from a survey of every `<stdcall:`/`<cdecl:` pragma in the MVP+Base
corpus: 763 external methods, 88 distinct argument types. The mapping is
deliberately a WHITELIST — an unknown type refuses rather than defaulting to a
word, because defaulting is how a pointer-sized assumption silently corrupts a
call whose argument was really a struct.

Codes match the existing floor (`st_flow_graph_builder.cc` FFI pragma):
  'g' — a word: integer, handle, pointer, BOOL
  'h' — a HANDLE return: the same word, but NULL answers nil (return only)
  'v' — void (return only)
"""
from __future__ import annotations

from typing import Optional, Tuple

# Word-sized scalars and handles. `hresult`/`errno` are status codes, `char32`
# et al are code units, `oop`/`ote` are DELIBERATELY absent — see below.
_WORD = {
    "bool", "bool8", "int8", "uint8", "int16", "int32", "int64",
    "uint16", "uint32", "uint64", "intptr", "uintptr",
    "handle", "dword", "sdword", "word", "errno", "hresult",
    "char8", "char16", "char32",
    "lpvoid", "void*", "lpwstr", "lpstr", "char*",
    # Pointer-shaped typedefs the corpus uses that do not end in `*`.
    "lppvoid",      # void** — an out-parameter for a pointer
    "bstr",         # a BSTR is a pointer to the string body
}

# Scalar typedefs whose NAME is capitalised, so the "uppercase means struct"
# heuristic would refuse them wrongly. Each is a word-sized status/handle code.
# Measured from the corpus: NTSTATUS accounts for 10 returns on its own.
_SCALAR_TYPEDEFS = {
    "NTSTATUS", "HRESULT", "LRESULT", "LPARAM", "WPARAM", "COLORREF",
    "HANDLE", "HWND", "HDC", "HMENU", "HICON", "HCURSOR", "HBRUSH", "HPEN",
    "HFONT", "HBITMAP", "HRGN", "HINSTANCE", "HMODULE", "HGLOBAL", "HLOCAL",
    "ATOM", "BOOL", "DWORD", "UINT", "INT", "LONG", "ULONG", "WORD", "BYTE",
    "SIZE_T", "DWORD_PTR", "UINT_PTR", "INT_PTR", "LONG_PTR", "ULONG_PTR",
}

# Dolphin VM object references. These pass a live Smalltalk object (or its
# object-table entry) straight to C, which only means anything inside Dolphin's
# own VM. There is no honest translation, so they refuse.
_VM_REFS = {"oop", "ote"}

# Floating point: refused by the floor itself (a float travels in a different
# register class), so refuse at generation time with a better message.
_FLOAT = {"double", "float", "single"}


def arg_code(t: str) -> Tuple[Optional[str], str]:
    """(code, reason). code None => refuse, with the reason for the report."""
    ty = t.strip()
    if not ty:
        return None, "empty type"
    if ty in _VM_REFS:
        return None, f"'{ty}' is a Dolphin VM object reference — no translation"
    if ty in _FLOAT:
        return None, f"'{ty}' is floating point — the floor takes word arguments only"
    if ty in _WORD or ty in _SCALAR_TYPEDEFS:
        return "g", ""
    if ty.endswith("*"):
        # Any pointer is a word. This is the RECT*/POINTL*/MSG* family: the
        # caller allocates and passes the address (see the DD6 RECT gate).
        return "g", ""
    if ty and ty[0].isupper():
        # A bare struct name with no `*` is BY VALUE. Win32 passes small structs
        # in registers by a rule that depends on size and architecture, so this
        # cannot be faked with a word. POINTL appears 5 times in the corpus.
        return None, f"'{ty}' is a struct passed BY VALUE — not representable as a word"
    return None, f"unknown type '{ty}'"


# --- marshalling kinds (DD6c) ------------------------------------------------
# The generated prim takes words; real callers pass objects. `coerce_kind` says
# which runtime helper an argument needs, from the type Dolphin itself declared.

_STRING_TYPES = {"lpwstr", "lpstr", "char*", "char16*", "char8*", "bstr"}
_POINTER_ISH = {"lpvoid", "void*", "lppvoid"}


def coerce_kind(t: str) -> str:
    """'string' (allocates a temp), 'pointer', or 'word' (identity + nil/bool)."""
    ty = t.strip()
    if ty in _STRING_TYPES:
        return "string"
    if ty in _POINTER_ISH or ty.endswith("*"):
        return "pointer"
    return "word"


def needs_wrapper(argtypes) -> bool:
    """True when at least one argument is not a plain word.

    Pure-word methods get NO wrapper: a wrapper that only forwards is overhead
    on the hot path and noise in the source. 1,126 methods is enough surface
    without doubling it for nothing.
    """
    return any(coerce_kind(t) != "word" for t in argtypes)


# HANDLE RETURNS. Dolphin declares these `handle` in its own pragmas — 129
# returns across the corpus — and its external-call machinery answers NIL when
# one comes back NULL. Its code depends on that: `View>>subViewsDo:` walks the
# sibling chain with `[child isNil] whileFalse:`, and Windows ends the chain
# with NULL. Answering 0 made the loop infinite and `ShellView>>show` hang.
#
# So a handle return gets its own code. Deliberately NARROW:
#
#   * only Dolphin's declared `handle` (plus the H-prefixed typedefs, which the
#     corpus does not currently use as returns but genprims would accept);
#   * NOT pointers. `lpvoid`/`void*` also use NULL for absence, but the
#     marshalling runtime does address ARITHMETIC on them (ExternalMemory), and
#     nil does not add. A pointer stays a word.
#   * NOT every zero. `GetWindowLong` answering 0 is a legitimate empty style
#     bitmask, not an absence — which is exactly why this is keyed off the
#     declared TYPE rather than off the value.
_HANDLE_RETURNS = {"handle"} | {
    "HANDLE", "HWND", "HDC", "HMENU", "HICON", "HCURSOR", "HBRUSH", "HPEN",
    "HFONT", "HBITMAP", "HRGN", "HINSTANCE", "HMODULE", "HGLOBAL", "HLOCAL",
}


# BOOL RETURNS — the same lesson as handles, found the same way, one layer up.
#
# Dolphin declares these `bool` (`<stdcall: bool IsWindow handle>`) and its
# external-call machinery answers a real Boolean. Answering the integer 1
# instead does not fail: it flows into Smalltalk control flow and quietly
# takes the wrong branch. `View>>isOpen` is
#
#     ^handle notNil and: [User32 isWindow: handle]
#
# and `View>>show` is `self isOpen ifFalse: [self create]`. With an integer
# answer, every `show` re-created a window that already existed — the shell
# ended up with three windows per child view, all of them real, all leaked.
#
# NARROW, for the same reason `#h` is: only the types Dolphin itself declares
# boolean. A `dword` that happens to hold 0 or 1 is a NUMBER, and the caller
# is entitled to do arithmetic on it.
_BOOL_RETURNS = {"bool", "bool8", "BOOL"}


def ret_code(t: str) -> Tuple[Optional[str], str]:
    ty = t.strip()
    if ty == "void":
        return "v", ""
    if ty in _HANDLE_RETURNS:
        return "h", ""
    if ty in _BOOL_RETURNS:
        return "b", ""
    return arg_code(ty)
