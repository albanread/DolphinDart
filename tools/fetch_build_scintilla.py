"""Fetch and build Scintilla + Lexilla as ARM64 DLLs for this port.

    python tools/fetch_build_scintilla.py            # pinned versions, build
    python tools/fetch_build_scintilla.py --check    # just report what is there

WHY BUILD RATHER THAN COPY. Dolphin ships `Scintilla.dll` and `Lexilla.dll`
and drives them from `UI.Scintilla.ScintillaView` — 438KB of Smalltalk that we
very much do not want to rewrite. But those DLLs are **I386**, and unlike
`DolphinDR8.dll` — whose contents are architecture-neutral DATA that a 64-bit
process can read out of a 32-bit module — these are CODE. An ARM64 process
cannot load them at all. So they are rebuilt from source for ARM64.

VERSIONS. Scintilla is backwards compatible at the message level (the SCI_*
codes are stable and additive), so this tracks the LATEST rather than pinning
to the 5.5.7 / 5.4.5 that Dolphin 8.2.3 happens to ship. A wrapper generated
against an older interface talks to a newer Scintilla fine; the reverse would
not hold.

    Scintilla  scintilla.org  — the GitHub mirror (mirror/scintilla) is STALE,
                                stopping at 5.5.2, so the official site is the
                                source even though GitHub was asked for.
    Lexilla    github.com/ScintillaOrg/lexilla — official, and current.

WHAT 64-BIT CHANGES, since it is mostly message-based. `SendMessage(hSci,
SCI_*, wParam, lParam)` carries pointers and positions in wParam/lParam, which
are 64-bit here and 32-bit in Dolphin — so every Scintilla call site is rule-1
territory, and `SCNotification` (delivered by WM_NOTIFY) grows exactly the way
NMHDR did: 12 bytes to 24 for the header alone. That is the integration risk,
not the DLL itself.
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = r"C:\projects\dolphindart-work\scintilla"

SCINTILLA_VER = "561"          # 5.6.1 — latest at time of writing
LEXILLA_TAG = "rel-5-5-3"      # latest tag
SCINTILLA_URL = "https://www.scintilla.org/scintilla%s.zip" % SCINTILLA_VER
LEXILLA_URL = "https://github.com/ScintillaOrg/lexilla.git"

MACH = {0x14C: "I386", 0x8664: "AMD64", 0xAA64: "ARM64"}


def _rmtree(path):
    """`shutil.rmtree` on a git working tree fails on Windows.

    Git marks objects under `.git` READ-ONLY, and Windows refuses to delete a
    read-only file — `rmtree` raises, the old tree survives, and the next
    `git clone` then fails with exit 128 for what looks like a network or tag
    problem. Clear the bit and retry.
    """
    def on_error(func, p, _exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except Exception:
            pass
    if os.path.exists(path):
        shutil.rmtree(path, onerror=on_error)


def machine_of(path):
    try:
        b = open(path, "rb").read(0x400)
        pe = struct.unpack_from("<I", b, 0x3C)[0]
        return MACH.get(struct.unpack_from("<H", b, pe + 4)[0], "?")
    except Exception:
        return None


def report():
    for rel in (r"scintilla\bin\Scintilla.dll", r"lexilla\bin\lexilla.dll"):
        p = os.path.join(WORK, rel)
        if os.path.exists(p):
            print("  %-44s %-6s %7.2f MB"
                  % (p, machine_of(p), os.path.getsize(p) / 1048576))
        else:
            print("  %-44s MISSING" % p)


def fetch():
    os.makedirs(WORK, exist_ok=True)
    sci_dir = os.path.join(WORK, "scintilla")
    zip_path = os.path.join(WORK, "scintilla%s.zip" % SCINTILLA_VER)
    if not os.path.exists(zip_path):
        print("downloading %s" % SCINTILLA_URL)
        urllib.request.urlretrieve(SCINTILLA_URL, zip_path)
    print("  %s  %d bytes" % (os.path.basename(zip_path),
                              os.path.getsize(zip_path)))
    # The archive contains a top-level `scintilla/`, so a stale tree from a
    # previous version would be merged into rather than replaced.
    _rmtree(sci_dir)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(WORK)
    print("  extracted -> %s" % sci_dir)

    lex_dir = os.path.join(WORK, "lexilla")
    _rmtree(lex_dir)
    print("cloning %s @ %s" % (LEXILLA_URL, LEXILLA_TAG))
    subprocess.check_call(
        ["git", "clone", "--quiet", "--depth", "1", "--branch", LEXILLA_TAG,
         LEXILLA_URL, lex_dir])
    print("  cloned -> %s" % lex_dir)


def build():
    cmd = os.path.join(REPO, "port-win", "build_scintilla.cmd")
    # Driven through PowerShell: invoking a .cmd directly from a POSIX shell
    # on this machine silently produces no output and no build.
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "& cmd.exe /c '%s' 2>&1" % cmd],
        capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()[-6:]
    for line in tail:
        print("  " + line)
    return r.returncode


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        report()
        return 0
    fetch()
    rc = build()
    print("")
    report()
    for rel in (r"scintilla\bin\Scintilla.dll", r"lexilla\bin\lexilla.dll"):
        if machine_of(os.path.join(WORK, rel)) != "ARM64":
            print("NOT ARM64 — refusing to call this a success")
            return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
