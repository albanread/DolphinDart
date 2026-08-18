"""Ask REAL Dolphin 8 what an expression evaluates to.

    from tools.oracle import ask
    ask(["OS.MONITORINFOEXW byteSize", "16r7FFF lowPartSigned"])
        -> ["104", "32767"]

    python tools/oracle.py "OS.MONITORINFOEXW byteSize"   # one-off from the shell

WHY THIS EXISTS. Every DD-series fix until now was made by READING the corpus
and reasoning about what it must evaluate to. That works and it is slow, and it
is wrong exactly where the reasoning has an unstated premise — the 32-bit
assumption being the standing example. A booted Dolphin 8 image answers the
question instead of inferring it, which turns "I believe MONITORINFOEXW is 104
bytes" into "Dolphin says 104".

HOW IT DRIVES DOLPHIN. `Dolphin8.exe <image> -u -q -f <chunkfile> -x` is the
invocation Dolphin's own `TestDPRO.cmd` uses, and the option table in
`Tools.DevelopmentSessionManager class >> commandLineParser` is what it means:

    -u  unattended: an unhandled error is logged, not shown in a dialog
    -q  no splash screen
    -f  QUEUE A DEFERRED ACTION that files in the named chunk file
    -x  QUEUE A DEFERRED ACTION that quits

Both -f and -x are DEFERRED, and they run in the order the option table
declares ($f before $x), which is why the image files in the script and only
then quits. Dropping -x leaves the IDE running.

FOUR THINGS THAT COST A RUN EACH, recorded so they are not rediscovered:

  * A GUI-subsystem exe launched from bash does not always block, and reading
    `$?` through a pipe reports the pipe's status. This runs the exe directly
    with `subprocess.run` and reads the real return code.
  * A chunk that fails part-way leaves the file it opened EMPTY, because
    `close` never runs. An empty results file therefore means the script died,
    not that the expressions answered nothing.
  * Dolphin writes UTF-8 WITH A BOM. It is stripped here.
  * A compile failure signals a CompilerNotification (a Notification, not an
    Error) and `evaluate:` answers nil, so `on: Error do:` does not see it.
    The script traps both, and a compile failure is reported as such rather
    than silently answering 'nil'.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import List, Optional

ORACLE_DIR = r"C:\projects\dolphin-oracle"
EXE = os.path.join(ORACLE_DIR, "Dolphin8.exe")
IMAGE = "DPRO.img8"

# The runner, as a chunk. One chunk, so a failure anywhere is visible as a
# short results file rather than a silently truncated batch.
RUNNER = r"""| exprs out lf |
lf := Character lf.
exprs := ((Core.FileStream read: '%(exprs)s' text: true) contents)
    subStrings: (String with: lf).
out := Core.FileStream write: '%(results)s' text: true.
exprs keysAndValuesDo: [ :i :each |
    | e r |
    e := each trimBlanks.
    e isEmpty ifFalse: [
        r := [ | v failed |
               failed := false.
               v := [ Compiler evaluate: e ]
                        on: Kernel.CompilerErrorNotification
                        do: [ :n | failed := true. n return: nil ].
               failed ifTrue: [ 'NOCOMPILE' ] ifFalse: [ v printString ] ]
                 on: Error
                 do: [ :ex |
                       'RAISED: ' , ex class name , ': ' ,
                       (ex messageText ifNil: [ '<none>' ]) ].
        out nextPutAll: i printString.
        out nextPut: Character tab.
        out nextPutAll: (r copyReplaceAll: (String with: lf) with: ' | ').
        out nextPut: lf ] ].
out close!
"""


def _strip_bom(s: str) -> str:
    return s[1:] if s.startswith("\ufeff") else s


def ask(exprs: List[str], timeout: int = 180) -> List[Optional[str]]:
    """Evaluate each expression in real Dolphin 8; answer the printStrings.

    The answer is positional and the same length as `exprs`. An entry is None
    only if the image never reported that line at all — which means the run
    died partway, not that the expression answered nothing.
    """
    if not os.path.exists(EXE):
        raise RuntimeError(
            "no Dolphin oracle at %s — see tools/oracle.py header" % EXE)
    work = tempfile.mkdtemp(prefix="oracle_", dir=ORACLE_DIR)
    exprs_path = os.path.join(work, "exprs.txt")
    results_path = os.path.join(work, "results.txt")
    script_path = os.path.join(work, "run.st")
    # No BOM, LF endings: the script splits on LF and trims, so a stray CR
    # would ride along into the expression and break the compile.
    with open(exprs_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(e.replace("\n", " ") for e in exprs) + "\n")
    with open(script_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(RUNNER % {"exprs": exprs_path.replace("\\", "\\\\"),
                           "results": results_path.replace("\\", "\\\\")})
    # Chunk-file paths inside Smalltalk string literals: a single backslash is
    # literal in Smalltalk, so undo the escaping done above.
    with open(script_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(RUNNER % {"exprs": exprs_path, "results": results_path})

    subprocess.run([EXE, IMAGE, "-u", "-q", "-f", script_path, "-x"],
                   cwd=ORACLE_DIR, timeout=timeout,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out: List[Optional[str]] = [None] * len(exprs)
    if os.path.exists(results_path):
        with open(results_path, encoding="utf-8", errors="replace") as fh:
            for line in _strip_bom(fh.read()).splitlines():
                if "\t" not in line:
                    continue
                idx, _, val = line.partition("\t")
                try:
                    i = int(idx) - 1          # Smalltalk is 1-based
                except ValueError:
                    continue
                if 0 <= i < len(out):
                    out[i] = val
    return out


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for e, r in zip(argv, ask(argv)):
        print("%-50s -> %s" % (e, r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
