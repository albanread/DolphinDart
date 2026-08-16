"""Regenerate `st/mvp` from the Dolphin corpus.

    python tools/translate_mvp.py [--corpus C:/projects/dsfork] [--out st/mvp]

`st/mvp/*.mst` is a build artifact: never hand-edit it, fix the translator and
re-run this. It exists because the invocation is not obvious — the reference
set is what makes the output correct, and reconstructing it from memory is how
DD9 shipped a wave whose pool constants silently stayed unfolded.

WHAT THE REFERENCE SET IS FOR. `--reference` sources are parsed for the class
hierarchy and never emitted. Two things need them:

  * ivar COUNTS, for the D157 constructor lowering (a field index is wrong by
    exactly the number of ancestor fields you did not know about);
  * POOL IMPORTS, which are INHERITED. `UI.ContainerView` declares
    `imports: #()` and writes `WS_EX_CONTROLPARENT`, binding it through
    `UI.View`'s `OS.Win32Constants`. Without the pool class in the reference
    set the name stays bare and becomes a runtime nil inside a bitOr — never a
    translation refusal, which is the failure mode this project keeps paying
    for.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# The wave itself — translated and emitted.
TARGETS = [
    "Core/Object Arts/Dolphin/MVP/Base/UI.View.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.ContainerView.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.ShellView.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.LayoutManager.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.BorderLayout.cls",
    # The colour wave. `View>>initialize` ends at `backcolor := Color default`,
    # so no view can be constructed without it — and every painting path in the
    # DD9 shell gate needs it next.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Color.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.AbstractRGB.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ColorRef.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ColorDefault.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ColorNone.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ARGB.cls",
    # Geometry + the layout context. `st/world/28_point.mst` deliberately
    # omitted Rectangle and Point's rect protocol — that call was made for
    # MACVM, whose GUI is HTML-rendered and had no use for Smalltalk geometry.
    # This project's goal reverses it: BorderLayout computes in Rectangles and
    # hands them to a LayoutContext, so both are load-bearing here.
    "Core/Object Arts/Dolphin/MVP/Base/Graphics.Rectangle.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.LayoutContext.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.LayoutPlacement.cls",

    # ── DD10: the MVP triad ────────────────────────────────────────────────
    # Dolphin's own Core.Model REPLACES the DD8 compat stand-in: the compat
    # kernel existed so DD8/DD9 had a model side at all, and the moment the
    # real one is translated, having both would mean two Model classes with a
    # silent winner decided by load order.
    "Core/Object Arts/Dolphin/Base/Core.Model.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Value/UI.ValueModel.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Value/UI.ValueHolder.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Value/UI.ValueAdaptor.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Value/UI.ValueAspectAdaptor.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Value/UI.ValueBuffer.cls",
    # Type converters — the acceptance app's bad-input path runs through
    # NumberToText, which is what makes InvalidFormat fire in anger.
    "Core/Object Arts/Dolphin/MVP/Type Converters/UI.TypeConverter.cls",
    "Core/Object Arts/Dolphin/MVP/Type Converters/UI.NullConverter.cls",
    "Core/Object Arts/Dolphin/MVP/Type Converters/UI.AbstractToTextConverter.cls",
    "Core/Object Arts/Dolphin/MVP/Presenters/Number/UI.NumberToText.cls",
    "Core/Object Arts/Dolphin/MVP/Presenters/Number/UI.IntegerToText.cls",
    # The presenter side.
    "Core/Object Arts/Dolphin/MVP/Base/UI.Presenter.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.Shell.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.ValuePresenter.cls",
    "Core/Object Arts/Dolphin/MVP/Presenters/Text/UI.TextPresenter.cls",

    # The Command framework + menus. `Menu` and `AcceleratorTable` hang off
    # `Graphics.GraphicsTool`, which is Object-rooted and small — so the whole
    # tree translates rather than needing an adapter, unlike the CONTROLS
    # (which are Win32 window classes, not Smalltalk ones).
    "Core/Object Arts/Dolphin/MVP/Base/UI.CommandDescription.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.CommandQuery.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.CommandPolicy.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.GraphicsTool.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.MenuItem.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.Menu.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.MenuBar.cls",
]

# Parsed for hierarchy + pools, never emitted. DIRECTORIES, deliberately: a
# hand-listed file set is a running guess at which constants the wave reaches,
# and a wrong guess does not fail — it leaves a bare name that becomes a
# runtime nil. The first version of this script listed four files and silently
# lost `NMHDR._OffsetOf_hwndFrom`, which the wider set had folded.
# cli.py drops any reference that is also a target, so the overlap is free.
REFERENCES = [
    "Core/Object Arts/Dolphin/Base",
    "Core/Object Arts/Dolphin/MVP/Base",
    "Core/Object Arts/Dolphin/MVP/Graphics",
    "Core/Object Arts/Dolphin/MVP/Models/Value",
    "Core/Object Arts/Dolphin/MVP/Type Converters",
    "Core/Object Arts/Dolphin/MVP/Presenters/Number",
    "Core/Object Arts/Dolphin/MVP/Presenters/Text",
]


def existing(corpus, rels, kind):
    out = []
    for r in rels:
        p = os.path.join(corpus, r.replace("/", os.sep))
        if os.path.exists(p):
            out.append(p)
        else:
            print("  (%s missing, skipped): %s" % (kind, r))
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=r"C:\projects\dsfork")
    ap.add_argument("--out", default=os.path.join(REPO, "st", "mvp"))
    args = ap.parse_args(argv)

    targets = existing(args.corpus, TARGETS, "target")
    refs = existing(args.corpus, REFERENCES, "reference")
    if not targets:
        print("translate_mvp: no targets found under %s" % args.corpus)
        return 2

    cmd = [sys.executable, os.path.join(HERE, "dolphin2mst", "cli.py"),
           "--out", args.out]
    for r in refs:
        cmd += ["--reference", r]
    cmd += targets
    print("translate_mvp: %d target(s), %d reference(s) -> %s"
          % (len(targets), len(refs), args.out))
    return subprocess.call(cmd, cwd=os.path.join(HERE, "dolphin2mst"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
