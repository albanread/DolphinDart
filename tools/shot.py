"""Convert the door's BMP captures to PNG so they can be looked at.

    python tools/shot.py <in.bmp> [out.png]

WHY THIS EXISTS. `Win32 mvpCapture:path:clientOnly:` writes a 24-bit BMP
because a BMP needs no encoder — a 14-byte file header, a 40-byte info header,
and bottom-up BGR rows. Nothing that displays an image reads BMP, though, so
this re-wraps the same pixels as a PNG.

NO DEPENDENCIES, deliberately. `zlib` and `struct` are in the standard library
and a PNG is four chunks; requiring Pillow would make looking at a window
contingent on a package install, which is exactly the friction this is meant
to remove.
"""
from __future__ import annotations

import os
import struct
import sys
import zlib


def bmp_to_png(src: str, dst: str) -> tuple:
    with open(src, "rb") as fh:
        data = fh.read()
    if len(data) < 54 or data[:2] != b"BM":
        raise SystemExit("shot: %s is not a BMP" % src)

    offbits = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp != 24:
        raise SystemExit("shot: expected 24-bit, got %d" % bpp)

    # BMP rows are bottom-up (positive height) and padded to 4 bytes; PNG wants
    # top-down rows each prefixed with a filter byte. BGR -> RGB as we go.
    stride = ((width * 3) + 3) & ~3
    rows = []
    for y in range(height - 1, -1, -1):
        off = offbits + y * stride
        row = bytearray(b"\x00")
        for x in range(width):
            b, g, r = data[off + x * 3: off + x * 3 + 3]
            row += bytes((r, g, b))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    with open(dst, "wb") as fh:
        fh.write(png)
    return width, height


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    src = argv[0]
    dst = argv[1] if len(argv) > 1 else os.path.splitext(src)[0] + ".png"
    w, h = bmp_to_png(src, dst)
    print("shot: %dx%d -> %s" % (w, h, dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
