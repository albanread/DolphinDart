"""Dolphin external-call types → house FFI argument codes (DD6b).

Built from a survey of every `<stdcall:`/`<cdecl:` pragma in the MVP+Base
corpus: 763 external methods, 88 distinct argument types. The mapping is
deliberately a WHITELIST — an unknown type refuses rather than defaulting to a
word, because defaulting is how a pointer-sized assumption silently corrupts a
call whose argument was really a struct.

Codes match the existing floor (`st_flow_graph_builder.cc` FFI pragma):
  'g' — a word: integer, handle, pointer, BOOL
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


def ret_code(t: str) -> Tuple[Optional[str], str]:
    ty = t.strip()
    if ty == "void":
        return "v", ""
    return arg_code(ty)
