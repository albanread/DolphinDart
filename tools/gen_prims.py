"""Regenerate the `st/prims` FFI floor from the Dolphin corpus.

    python tools/gen_prims.py [--corpus ...] [--out st/prims]

`st/prims/*.mst` is a build artifact: never hand-edit it, fix the generator
(`tools/dolphin2mst/genprims.py` + `ffitypes.py`) and re-run this.

WHY THIS SCRIPT EXISTS — the same reason `translate_mvp.py` does, learned the
same way. `genprims.py --corpus` is required with no default, so the ONE root
that produces a correct floor lived only in whoever last typed it. Guessing it
wrong is not a failure: pointing at the dsfork ROOT instead of the Dolphin
package root regenerated a floor with **1** external method in `UserLibrary`
instead of 232, and wrote it straight over the good one. The generator cleans
and rewrites in place, so a wrong root is a silent demolition — caught here
only because 232→1 is too big to miss. A subtler wrong root would not have
been.

WHY THE NARROW ROOT. `Core/Object Arts/Dolphin` is the package tree: the
`.cls` files whose `<stdcall:>` pragmas ARE the floor. Above it, dsfork also
holds sample and fork material that declares same-named classes, and
`collect_decls` walks whatever it is given — last writer wins, with no
diagnostic. The narrow root is not a performance choice; it is the correctness
boundary.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# The Dolphin PACKAGE root, not the dsfork checkout root. See the header.
DEFAULT_CORPUS = r"C:\projects\dsfork\Core\Object Arts\Dolphin"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=os.path.join(REPO, "st", "prims"))
    ap.add_argument("--winkb", default=r"C:\projects\windows_api\windows_api.db")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.corpus):
        print("gen_prims: corpus root not found: %s" % args.corpus)
        return 2
    # A root that does not contain the Base package is not the package root,
    # whatever else it is. Cheap check, and it is exactly the mistake made:
    # dsfork's own root passes `isdir` and produces a near-empty floor.
    if not os.path.isdir(os.path.join(args.corpus, "Base")):
        print("gen_prims: %s has no Base/ — that is not the Dolphin package "
              "root (see this script's header)" % args.corpus)
        return 2

    print("gen_prims: %s -> %s" % (args.corpus, args.out))
    rc = subprocess.call(
        [sys.executable, os.path.join(HERE, "dolphin2mst", "genprims.py"),
         "--out", args.out, "--corpus", args.corpus, "--winkb", args.winkb])
    if rc != 0:
        return rc

    # THE STRUCTS TOO. They share this corpus root and this winkb, they land
    # inside the same generated tree (`st/prims/structs`), and the prims call
    # into them — regenerating one without the other is how a field offset and
    # the call that reads it drift apart.
    #
    # Recorded here for the same reason the prims invocation is: `genstructs`
    # also takes a required `--corpus` with no default.
    structs_out = os.path.join(args.out, "structs")
    print("gen_prims: structs -> %s" % structs_out)
    return subprocess.call(
        [sys.executable, os.path.join(HERE, "dolphin2mst", "genstructs.py"),
         "--out", structs_out, "--corpus", args.corpus, "--winkb", args.winkb])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
