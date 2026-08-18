"""Extract Dolphin's ICON / BITMAP / CURSOR resources from DolphinDR8.dll.

    python tools/extract_resources.py                 # list what is in there
    python tools/extract_resources.py --write         # write them to resources/

WHY EXTRACT AT ALL. Dolphin's UI artwork is not in the source repo — a
`git ls-files Core/DolphinVM/Res` answers four files, none of them images,
while `devres.rc` references dozens of `Res\\*.ico`. They exist only compiled
into `DolphinDR8.dll`, which IS committed. So the DLL is the source of truth,
and this reads it rather than anyone re-drawing icons.

LICENCE. Dolphin Smalltalk is MIT, Copyright (c) 2015 Object Arts. The licence
permits copying and redistribution provided the copyright and permission
notice travel with it, so `--write` also writes `resources/LICENSE.dolphin`
and a `PROVENANCE.md` naming the exact DLL and its build date. That is a
condition of the licence, not decoration — do not delete them.

HOW. Windows' own resource loader does the parsing, via
`LoadLibraryEx(..., LOAD_LIBRARY_AS_IMAGE_RESOURCE | LOAD_LIBRARY_AS_DATAFILE)`
— which maps the file WITHOUT executing anything, so an x86 DLL can be read
from an ARM64 process. That matters here: DolphinDR8.dll is 32-bit and this
port is not.

RECONSTRUCTING A .ico. A PE stores an icon as N separate `RT_ICON` images plus
one `RT_GROUP_ICON` directory that names them. A `.ico` FILE is the same
directory followed by the images, with one field changed: the group entry
holds a 2-byte resource ID where the file format wants a 4-byte offset. So the
header is rewritten rather than copied. Cursors are the same shape with a
2-byte hotspot prefix on each image, which is stripped for the `.cur` file.

A .bmp needs the opposite: `RT_BITMAP` stores a BITMAPINFOHEADER with no
14-byte BITMAPFILEHEADER, so one is synthesised. Note that header is
`#pragma pack(2)` and therefore **14 bytes, not 16** — see LOOSE_ENDS 3.22,
where our generated struct has it wrong for exactly this reason. It is built
here with `struct.pack('<2sIHHI')`, which packs without padding.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as w
import os
import struct
import sys

DLL = r"C:\projects\dolphin8\DolphinDR8.dll"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "resources")

RT_CURSOR, RT_BITMAP, RT_ICON = 1, 2, 3
RT_GROUP_CURSOR, RT_GROUP_ICON = 12, 14

_k = ctypes.WinDLL("kernel32", use_last_error=True)
_k.LoadLibraryExW.restype = w.HMODULE
_k.LoadLibraryExW.argtypes = [w.LPCWSTR, w.HANDLE, w.DWORD]
_k.FindResourceW.restype = w.HANDLE
_k.FindResourceW.argtypes = [w.HMODULE, ctypes.c_void_p, ctypes.c_void_p]
_k.LoadResource.restype = w.HANDLE
_k.LoadResource.argtypes = [w.HMODULE, w.HANDLE]
_k.LockResource.restype = ctypes.c_void_p
_k.LockResource.argtypes = [w.HANDLE]
_k.SizeofResource.restype = w.DWORD
_k.SizeofResource.argtypes = [w.HMODULE, w.HANDLE]

# The callbacks hand back either a small integer ID or a wide-string pointer,
# in the same parameter. Declared as c_void_p so a 64-bit pointer survives the
# trip — typed as LPWSTR, ctypes tries to build a string from an integer ID and
# raises `OverflowError: int too long to convert`.
ENUMTYPES = ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_void_p)
ENUMNAMES = ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.c_void_p)

# The module handle needs declaring too. `LoadLibraryEx` with
# AS_IMAGE_RESOURCE tags the low bits of the returned pointer, so the value is
# a full 64-bit quantity; left undeclared, ctypes guesses a C int for it and
# raises `OverflowError: int too long to convert` before the call is made.
_k.EnumResourceNamesW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                  ENUMNAMES, ctypes.c_void_p]
_k.EnumResourceNamesW.restype = w.BOOL
_k.EnumResourceTypesW.argtypes = [ctypes.c_void_p, ENUMTYPES, ctypes.c_void_p]
_k.EnumResourceTypesW.restype = w.BOOL
_k.FindResourceW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_k.LoadResource.argtypes = [ctypes.c_void_p, w.HANDLE]
_k.SizeofResource.argtypes = [ctypes.c_void_p, w.HANDLE]


def _ident(v):
    """A resource type/name is an integer ID below 0x10000, else a string."""
    if v is None:
        return 0
    if v < 0x10000:
        return int(v)
    return ctypes.wstring_at(v)


def _as_param(ident):
    return ctypes.c_void_p(ident) if isinstance(ident, int) else \
        ctypes.c_wchar_p(ident)


class Res:
    def __init__(self, path=DLL):
        self.path = path
        flags = 0x20 | 0x02          # AS_IMAGE_RESOURCE | AS_DATAFILE
        self.h = _k.LoadLibraryExW(path, None, flags)
        if not self.h:
            raise RuntimeError("LoadLibraryEx failed on %s (err %d)"
                               % (path, ctypes.get_last_error()))

    def names(self, rtype):
        out = []

        def cb(mod, typ, name, lp):
            out.append(_ident(name))
            return True
        _k.EnumResourceNamesW(self.h, _as_param(rtype), ENUMNAMES(cb), None)
        return out

    def data(self, rtype, name):
        hres = _k.FindResourceW(self.h, _as_param(name), _as_param(rtype))
        if not hres:
            return None
        size = _k.SizeofResource(self.h, hres)
        ptr = _k.LockResource(_k.LoadResource(self.h, hres))
        if not ptr or not size:
            return None
        return ctypes.string_at(ptr, size)


def build_icon_file(res, group_bytes, is_cursor):
    """GROUP_ICON/GROUP_CURSOR directory + its images -> a .ico/.cur file."""
    reserved, rtype, count = struct.unpack_from("<HHH", group_bytes, 0)
    entries, images = [], []
    # File entries are 16 bytes; group entries are 14 (a 2-byte id where the
    # file wants a 4-byte offset), so the header size differs from the group's.
    offset = 6 + count * 16
    for i in range(count):
        base = 6 + i * 14
        if is_cursor:
            # GRPCURSORDIRENTRY: width, height(2x), planes, bits, bytes, id
            cw, ch, planes, bits, nbytes, rid = struct.unpack_from(
                "<HHHHIH", group_bytes, base)
            cw, ch = cw & 0xFF, (ch // 2) & 0xFF
        else:
            cw, ch, colors, rsv, planes, bits, nbytes, rid = \
                struct.unpack_from("<BBBBHHIH", group_bytes, base)
        img = res.data(RT_CURSOR if is_cursor else RT_ICON, rid)
        if img is None:
            continue
        hotspot = b""
        if is_cursor:
            # RT_CURSOR prefixes each image with its 4-byte hotspot; the .cur
            # file carries the hotspot in the DIRECTORY instead.
            hx, hy = struct.unpack_from("<HH", img, 0)
            hotspot = struct.pack("<HH", hx, hy)
            img = img[4:]
        if is_cursor:
            entries.append(struct.pack("<BBBBIII" if False else "<BBBB",
                                       cw or 0, ch or 0, 0, 0)
                           + hotspot + struct.pack("<II", len(img), offset))
        else:
            entries.append(struct.pack("<BBBBHHII", cw, ch, colors, rsv,
                                       planes, bits, len(img), offset))
        images.append(img)
        offset += len(img)
    if not images:
        return None
    head = struct.pack("<HHH", 0, 2 if is_cursor else 1, len(images))
    return head + b"".join(entries) + b"".join(images)


def build_bmp_file(dib):
    """RT_BITMAP is a DIB with no file header; synthesise the 14-byte one."""
    if len(dib) < 40:
        return None
    hdr_size, _wid, _hgt, _planes, bits, _comp, _sz, _xp, _yp, used, _imp = \
        struct.unpack_from("<IiiHHIIiiII", dib, 0)
    if used == 0 and bits <= 8:
        used = 1 << bits
    palette = used * 4 if bits <= 8 else 0
    offbits = 14 + hdr_size + palette
    # '<2sIHHI' packs to exactly 14 bytes -- BITMAPFILEHEADER is pack(2).
    return struct.pack("<2sIHHI", b"BM", 14 + len(dib), 0, 0, offbits) + dib


def safe(name):
    s = str(name)
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, "_")
    return s


DOLPHIN_MIT = """The MIT License (MIT)

Copyright (c) 2015 Object Arts

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _write_licence(out, dll, n_ico, n_cur, n_bmp):
    """The MIT notice and where these files came from.

    The licence REQUIRES the copyright and permission notice to travel with
    any substantial portion of the work, and 295 icons is a substantial
    portion. This is a condition of using them, not a courtesy — leave both
    files in place.
    """
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "LICENSE.dolphin"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(DOLPHIN_MIT)
    try:
        import datetime
        stamp = datetime.datetime.utcfromtimestamp(
            os.path.getmtime(dll)).strftime("%Y-%m-%d")
        size = os.path.getsize(dll)
    except OSError:
        stamp, size = "unknown", 0
    with open(os.path.join(out, "PROVENANCE.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(
            "# Where these came from\n\n"
            "Dolphin Smalltalk 8's own UI artwork, extracted verbatim from its\n"
            "resource DLL by `tools/extract_resources.py`. Nothing here was\n"
            "redrawn, resized or recoloured.\n\n"
            "| | |\n|---|---|\n"
            "| source | `%s` |\n| size | %d bytes |\n| dated | %s |\n"
            "| icons | %d |\n| cursors | %d |\n| bitmaps | %d |\n\n"
            "**Why extracted rather than copied from source.** They are not in\n"
            "the Dolphin source repository: `git ls-files Core/DolphinVM/Res`\n"
            "answers four files, none of them images, while `devres.rc`\n"
            "references dozens of `Res\\\\*.ico`. The compiled DLL is the only\n"
            "place they exist, and it is committed upstream.\n\n"
            "**Licence.** Dolphin Smalltalk is MIT, Copyright (c) 2015 Object\n"
            "Arts — see `LICENSE.dolphin` beside this file, which is kept here\n"
            "because the licence requires the notice to accompany substantial\n"
            "portions of the work.\n\n"
            "Regenerate with:\n\n    python tools/extract_resources.py --write\n"
            % (dll, size, stamp, n_ico, n_cur, n_bmp))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", default=DLL)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    res = Res(args.dll)
    icons = res.names(RT_GROUP_ICON)
    cursors = res.names(RT_GROUP_CURSOR)
    bitmaps = res.names(RT_BITMAP)
    print("%s" % args.dll)
    print("  GROUP_ICON   %4d" % len(icons))
    print("  GROUP_CURSOR %4d" % len(cursors))
    print("  BITMAP       %4d" % len(bitmaps))
    if not args.write:
        print("\n  sample icons: %s" % ", ".join(safe(n) for n in icons[:10]))
        print("\n  (re-run with --write to extract)")
        return 0

    written = 0
    for sub, kind in (("icons", "ico"), ("cursors", "cur"), ("bitmaps", "bmp")):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
    _write_licence(args.out, args.dll, len(icons), len(cursors), len(bitmaps))
    # THE MANIFEST IS NOT OPTIONAL. A resource NAME cannot be recovered from
    # the filename it was written to: `CLASSBROWSERSHELL.ICO` is a name that
    # ends in `.ICO`, while `!APPLICATION` is a name with no extension that
    # had `.ico` appended to make a usable filename. Stripping the extension
    # to rebuild the .rc got the first kind wrong, and every FindResource for
    # it missed with ERROR_RESOURCE_NAME_NOT_FOUND while the resources were
    # demonstrably in the DLL. So the mapping is RECORDED here.
    manifest = []
    for n in icons:
        blob = res.data(RT_GROUP_ICON, n)
        data = build_icon_file(res, blob, False) if blob else None
        if data:
            fn = os.path.join(args.out, "icons", safe(n))
            if not fn.lower().endswith(".ico"):
                fn += ".ico"
            open(fn, "wb").write(data)
            manifest.append(("ICON", n, os.path.relpath(fn, args.out)))
            written += 1
    for n in cursors:
        blob = res.data(RT_GROUP_CURSOR, n)
        data = build_icon_file(res, blob, True) if blob else None
        if data:
            fn = os.path.join(args.out, "cursors", safe(n))
            if not fn.lower().endswith(".cur"):
                fn += ".cur"
            open(fn, "wb").write(data)
            manifest.append(("CURSOR", n, os.path.relpath(fn, args.out)))
            written += 1
    for n in bitmaps:
        blob = res.data(RT_BITMAP, n)
        data = build_bmp_file(blob) if blob else None
        if data:
            fn = os.path.join(args.out, "bitmaps", safe(n))
            if not fn.lower().endswith(".bmp"):
                fn += ".bmp"
            open(fn, "wb").write(data)
            manifest.append(("BITMAP", n, os.path.relpath(fn, args.out)))
            written += 1

    with open(os.path.join(args.out, "MANIFEST.tsv"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("# type\tresource name (VERBATIM)\tfile\n")
        for kind, name, rel in manifest:
            fh.write("%s\t%s\t%s\n" % (kind, name, rel.replace(os.sep, "/")))
    print("\n  wrote %d file(s) + MANIFEST.tsv to %s" % (written, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
