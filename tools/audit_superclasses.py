"""Every class's SUPERCLASS must actually be defined somewhere in `st/`.

    python tools/audit_superclasses.py          # report; exit 1 if any missing

WHY THIS EXISTS. A missing superclass is the quietest failure this port has.
`Foo subclass: Bar [...]` where nothing defines `Foo` does not raise: the
loader auto-vivifies a `Foo` stub rooted at Object, `Bar` loads cleanly, and
what you get is a class that has silently lost

  * every inherited INSTANCE VARIABLE (so `instVarAt:` indices shift, which
    matters enormously to the STx filers — they read `instSize + size` slots
    straight into positions);
  * every inherited METHOD; and
  * its whole CLASS SIDE, because the stub's metaclass shadow is not linked
    into the real chain either.

That last one is how it was found, in DD17: `ReferenceView instSize` raised
`ReferenceView class has no method 'instSize'` while `ContainerView instSize`
answered 15. `instSize` lives on `Object class`; ReferenceView could not reach
it because it stood on a stub of `AbstractDelegatingView`, which had never been
translated. Eight classes were in that state at once — including
`ControlBarAbstract`, the superclass of BOTH Toolbar and StatusBar.

Nothing in the gates caught it because a re-rooted class still LOADS, still
answers its own selectors, and only misbehaves when something reaches for
something inherited.

WHAT COUNTS AS DEFINED. Any `X subclass: Name [`, any `Name extend [`, in any
layer — plus the handful the Dart prelude supplies (Object, Error, Exception,
Signal), which have no `.mst` declaration at all and are therefore listed here
explicitly rather than inferred.
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# Layers searched, in no particular order — this is a name-existence question.
LAYERS = ("st/world", "st/dolphin_compat", "st/prims/rt", "st/prims/structs",
          "st/prims", "st/mvp", "st/mvp_compat", "st/ext")

# Supplied by the Dart prelude, not by any .mst. `Error` is the one that made
# the first version of this audit report a false positive.
PRELUDE = {"Object", "Error", "Exception", "Signal", "nil"}

DECL = re.compile(r"^\s*([A-Za-z][\w.]*|nil)\s+subclass:\s*([A-Za-z]\w*)\s*\[", re.M)
EXTEND = re.compile(r"^([A-Za-z]\w*)\s+extend\s*\[", re.M)


def scan():
    defined = set(PRELUDE)
    declared = []          # (subclass, superclass, path)
    for layer in LAYERS:
        root_dir = os.path.join(REPO, layer)
        if not os.path.isdir(root_dir):
            continue
        for root, _dirs, files in os.walk(root_dir):
            for fn in sorted(files):
                if not fn.endswith(".mst"):
                    continue
                path = os.path.join(root, fn)
                text = io.open(path, encoding="utf-8", errors="replace").read()
                for m in DECL.finditer(text):
                    sup, cls = m.group(1), m.group(2)
                    defined.add(cls)
                    declared.append((cls, sup, path))
                for m in EXTEND.finditer(text):
                    defined.add(m.group(1))
    return defined, declared


def main():
    defined, declared = scan()
    missing = {}
    for cls, sup, path in declared:
        if sup not in defined:
            missing.setdefault(sup, set()).add(cls)

    if not missing:
        print("audit_superclasses: OK — every superclass is defined (%d classes)"
              % len(defined))
        return 0

    print("audit_superclasses: %d SUPERCLASS(ES) REFERENCED BUT NEVER DEFINED\n"
          % len(missing))
    for sup in sorted(missing):
        print("  %-32s <- %s" % (sup, ", ".join(sorted(missing[sup]))))
    print("\nEach subclass above has silently re-rooted at Object: no inherited")
    print("ivars, no inherited methods, and a class side that does not inherit.")
    print("Add the missing class to TARGETS in tools/translate_mvp.py (with its")
    print("own superclass closure) and regenerate.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
