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
    # `Color>>asRGB` is `^RGB fromRgbCode: self rgbCode`, and
    # `Color class >> initializeCommonColors` builds every named colour
    # through it — so an untranslated RGB made `Color class >> initialize`
    # raise, `Color default` stay nil, and every `ambientBackcolor` walk fail
    # at the desktop.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.RGB.cls",
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
    # `CommandPolicy class >> defaultClass` answers this, and `View>>
    # commandPolicy` is `self topShell commandPolicyWithSource: ...` ->
    # `self commandPolicyClass commandSource: sourceView`. Untranslated it was
    # an unbound global, so `defaultClass` answered nil and every command
    # route died on `nil commandSource:` — inside the contained handler-error
    # path, so it showed only as a diagnostic line.
    "Core/Object Arts/Dolphin/MVP/Base/UI.DelegatingCommandPolicy.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.GraphicsTool.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.MenuItem.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.Menu.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.MenuBar.cls",
    # The two concrete MenuItem subclasses. `MenuItem class >> new` is
    # `subclassResponsibility` — it is abstract — and `fromString:` answers a
    # `CommandMenuItem` or, for '-', the shared `DividerMenuItem` flyweight.
    "Core/Object Arts/Dolphin/MVP/Base/UI.CommandMenuItem.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.DividerMenuItem.cls",
    # Accelerators. `ShellView` already holds `acceleratorTable` and
    # `combinedAcceleratorTable` ivars and calls `registerAcceleratorKeyIn:`
    # on its menu bar, so the shell side is already translated and waiting —
    # this is the class it was waiting for. Retires `WinAccelerators`.
    "Core/Object Arts/Dolphin/MVP/Base/UI.AcceleratorTable.cls",

    # ── DD11: the GRAPHICS wave ────────────────────────────────────────────
    # Three DD10 stand-ins wait on exactly these classes, and each is recorded
    # in docs/LOOSE_ENDS.md with this as its retirement:
    #
    #   * `View>>onEraseRequired:` answers nil because `ColorEvent>>canvas`
    #     needs a Canvas — so a view's backcolor is not honoured when erasing.
    #   * `SystemFont` terminates the font walk because `Graphics.Font` is
    #     absent — so a control cannot be given the font it asks for.
    #   * `Cursor` is a hand-written stand-in; `showWhile:` is `Icon`'s.
    #
    # Ordered by dependency: GraphicsTool is already in the wave (Menu needs
    # it), then the tools that hang off it, then Canvas which uses them all.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.AbstractPen.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Pen.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Brush.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.AbstractFont.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Font.cls",
    # The STOCK tools. `AbstractFont class >> reset` is
    # `System := self fromId: 13`, and `fromId:` answers `StockFont newId:` —
    # so without StockFont the font class initializes to nil and every
    # `Font system` is nil. Its superclass `SystemFont` comes with it.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.SystemFont.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.StockFont.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.StockPen.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.StockBrush.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Image.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Icon.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Cursor.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.Canvas.cls",

    # THE IMAGE INITIALIZERS. An `Image` in Dolphin does not hold its own
    # construction recipe — it delegates to an <imageInitializer>, and every
    # class-side constructor builds one: `Icon class >> fromSystemId:` is
    # `^self initializer: (IconFromSystemInitializer identifier: anInteger)`.
    # So `Cursor wait`, `Icon question` and every stock image were sends of
    # `identifier:` to nil, which is how it reached the DD11 gate — the
    # ListView's `applyImageLists` asks for a system cursor.
    #
    # `ImageInitializer` is the abstract parent; the three below are the ones
    # the stock-image constructors reach. The bitmap and file/resource
    # initializers are NOT taken: nothing constructed in this port loads an
    # image from a file or a resource, and each drags in the DIB and stream
    # machinery behind it.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ImageInitializer.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.IconFromSystemInitializer.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ImageFromHandleInitializer.cls",
    # `IconicListAbstract` — the shared parent of ListView, TreeView and
    # TabView — holds the image-list plumbing, so no common control can be
    # constructed without this one.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ImageList.cls",
    # `IconicListAbstract>>initialize` ends `imageManager := self
    # defaultImageManager`, which is `^IconImageManager current` — so the
    # manager pair comes with the image list.
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.ImageManager.cls",
    "Core/Object Arts/Dolphin/MVP/Graphics/Graphics.IconImageManager.cls",

    # ── DD11: the COMMON CONTROLS ──────────────────────────────────────────
    # comctl32's window classes, reached the same way `UI.TextEdit` reaches
    # EDIT: Dolphin SUBCLASSES them, and the substrate for that is the
    # trampoline `st_subclass` proved. `InitCommonControlsEx` now runs on the
    # door's class-registration path — the DD11 brief's named trap, because
    # the first control created decides whether the whole wave works and a
    # lazily-hit call can land on the wrong thread.
    #
    # The chain, ListControlView -> IconicListAbstract -> ListView/TreeView,
    # is taken whole: `IconicListAbstract` is where the image-list and
    # get-text plumbing lives, so neither leaf works without it.
    # `ListControlView class >> defaultModel` is `^ListModel new`, so every
    # list-shaped control needs it before it can be constructed at all.
    "Core/Object Arts/Dolphin/MVP/Models/List/UI.ListModel.cls",
    "Core/Object Arts/Dolphin/MVP/Presenters/List/UI.ListControlView.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.IconicListAbstract.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.ListView.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.TreeView.cls",

    # The TREE model, for the same reason `ListModel` is here and by the same
    # mechanism: `TreeView class >> defaultModel` is `^TreeModel new`, and
    # `defaultModel` runs from `initialize`, so an untranslated `TreeModel` is
    # not a missing feature — `TreeView new` cannot complete. It reached the
    # gate as "the method 'new' was called on null" with nothing naming the
    # class, because an unbound global IS nil here.
    #
    # `TreeModelAbstract` carries the protocol and `TreeNode` is the storage
    # `TreeModel` allocates per element, so the three come together or not at
    # all. `VirtualTreeModel` and the Folder pair are deliberately NOT taken:
    # nothing in the DD11 gate constructs them, and the folder models drag in
    # the shell-namespace file classes.
    "Core/Object Arts/Dolphin/MVP/Models/Tree/UI.TreeModelAbstract.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Tree/UI.TreeNode.cls",
    "Core/Object Arts/Dolphin/MVP/Models/Tree/UI.TreeModel.cls",

    # The UPDATE MODES. `IconicListAbstract` does not talk to its control
    # directly — it delegates every add/remove/refresh to a strategy object,
    # and `initialize` installs one immediately:
    # `updateMode := TreeViewDynamicUpdateMode forIconicList: self`. So this
    # is not an optional performance knob, it is on the construction path;
    # untranslated it reached the gate as "the method 'forIconicList_' was
    # called on null".
    #
    # The WHOLE family is taken, not just the two defaults. `TreeView` keeps
    # a class-variable `UpdateModes` mapping #dynamic/#lazy/#static/#virtual
    # to these classes, and a missing entry does not fail at load — it fails
    # later as a nil, at whatever `updateMode` is first sent.
    # `ListView>>initialize` builds its first column immediately —
    # `columns := OrderedCollection with: (self columnClass text: 'Column 1')`
    # — so the column class is on the construction path too, and untranslated
    # it read as `text:` sent to nil with the string 'Column 1' in the error.
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.ListViewColumn.cls",
    # Its Win32 counterpart, REOPENED onto the generated struct (see --reopen
    # in the cli invocation below).
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/OS.LVCOLUMNW.cls",

    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.IconicListUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.ListViewUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.ListViewStaticUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.ListViewVirtualUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.TreeViewUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.TreeViewDynamicUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.TreeViewLazyUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.TreeViewStaticUpdateMode.cls",
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls/UI.TreeViewVirtualUpdateMode.cls",

    # ── DD10: the EVENT family ─────────────────────────────────────────────
    # Once Dolphin's own `buildMessageMap` is installed as the routed set, its
    # mouse and key handlers run — and every one of them builds an event
    # object: `wmMouseMove:` answers `MouseEvent window: self message: ...`,
    # `wmContextMenu:` a PointEvent, `wmChar:` a KeyEvent. Untranslated those
    # were unbound globals, so each handler sent to nil.
    #
    # Small classes, and the whole chain is needed because the constructor is
    # `WindowsEvent class >> window:message:wParam:lParam:`, two levels up.
    "Core/Object Arts/Dolphin/MVP/Base/UI.Event.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.WindowsEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.PointEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.MouseEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.KeyEvent.cls",
    # The REST of the family, added together rather than one per failure.
    # `UI.View` names ten event classes and its message map reaches all of
    # them, so translating them piecemeal just means one more contained
    # handler error per message that happens to arrive first. Grepped from
    # View's own source rather than guessed:
    #   ColorEvent DpiChangedEvent KeyEvent MouseEvent MouseWheelEvent
    #   PaintEvent PointEvent PositionEvent ScrollEvent WindowsEvent
    # (`TrackMouseEvent` is named but has no class file — it is a STRUCT,
    #  TRACKMOUSEEVENT, which the generated floor already has.)
    "Core/Object Arts/Dolphin/MVP/Base/UI.ColorEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.DpiChangedEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.MouseWheelEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.PaintEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.PositionEvent.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.ScrollEvent.cls",

    # ── DD10: CONTROLS ─────────────────────────────────────────────────────
    # A control is a window of a class COMCTL registered, so Dolphin gets into
    # its message stream by SUBCLASSING it — `ControlView>>subclassWindow`
    # swaps the WndProc and chains to the original through
    # `defaultWindowProcessing:wParam:lParam:`. The substrate for that is
    # proven by `st_subclass` (the door's trampoline + `VM getWndProc`), so
    # these translate onto something that already works rather than being the
    # thing that discovers whether it does.
    # `View>>metrics` is `^SystemMetrics forDpi: self dpi`, and `TextEdit`
    # asks it `hasTextBoxMargins` on the create path. Dolphin's own class,
    # translated rather than stubbed: it wraps GetSystemMetrics and
    # SystemParametersInfo, both of which the generated floor already has.
    "Core/Object Arts/Dolphin/MVP/Graphics/OS.SystemMetrics.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.ControlView.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.ValueConvertingControlView.cls",
    "Core/Object Arts/Dolphin/MVP/Presenters/Text/UI.TextEdit.cls",

    # WINDOW CREATION — Dolphin's own CreateWindowExW call, so `View>>create`
    # is Dolphin's code all the way down to the API. The substrate supplies
    # only what is genuinely ours: the window CLASS (its WndProc has to be the
    # door's) and the module handle.
    "Core/Object Arts/Dolphin/MVP/Base/UI.CreateWindowFunction.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.CreateWindowApiCall.cls",
    "Core/Object Arts/Dolphin/MVP/Base/UI.CreateWindow.cls",

    # The PACKAGE MANIFEST, as a target rather than a reference: `.pax` files
    # carry LOOSE METHODS, and this one files 177 of them onto
    # `OS.UserLibrary` — Dolphin's convenience layer over the raw API calls,
    # which `UI.View` uses constantly. `--loose OS.UserLibrary` emits them as
    # a reopen of the generated class. The manifest's class re-declarations
    # are ignored: cli.py emits a class from its own `.cls` and notes the
    # duplicate.
    "Core/Object Arts/Dolphin/MVP/Base/Dolphin MVP Base.pax",

    # The VALUE-MODEL package manifest, for its LOOSE METHODS ON `Core.Object`
    # — `asValue`, `aspectValue:`, `aspectValue:triggers:`. Dolphin files them
    # onto Object from this `.pax` rather than declaring them in a `.cls`,
    # which is why translating the value-model classes did not bring them.
    #
    # `asValue` is not optional decoration:
    # `ValueConvertingControlView class >> defaultModel` is `^nil asValue`, so
    # EVERY TextEdit fails to initialize without it — and it fails as
    # `doesNotUnderstand` on nil, three frames inside Dolphin's own code.
    "Core/Object Arts/Dolphin/MVP/Models/Value/Dolphin Value Models.pax",
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
    # DD11: the common-controls tree, for its POOLS above all. `OS.ListViewConstants`
    # and the `Dolphin Common Controls.pax` live here, and the ListView/TreeView
    # code writes LVIF_TEXT, TVS_HASBUTTONS and ~200 others as BARE NAMES. An
    # unfolded one is not a refusal — it is a runtime nil, and the first thing
    # it reaches is a `bitOr:`, which is how `TreeView>>defaultWindowStyle`
    # failed with "the method '|' was called on null".
    "Core/Object Arts/Dolphin/MVP/Views/Common Controls",
    "Core/Object Arts/Dolphin/MVP/Presenters/List",
    "Core/Object Arts/Dolphin/MVP/Models/List",
    "Core/Object Arts/Dolphin/MVP/Models/Tree",
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

    # CLEAN FIRST. The generator owns this directory: anything it did not
    # emit on THIS run is stale, and stale generated files are invisible to
    # every gate — measured, when a brief .pax-emitting run left 93 files
    # behind and the whole suite stayed green over them.
    if os.path.isdir(args.out):
        for f in os.listdir(args.out):
            if f.endswith(".mst") or f in ("_refusals.txt", "_report.md"):
                os.remove(os.path.join(args.out, f))

    cmd = [sys.executable, os.path.join(HERE, "dolphin2mst", "cli.py"),
           "--out", args.out,
           # Dolphin's convenience layer over the generated prims: 177 methods
           # filed onto OS.UserLibrary by a .pax, which UI.View calls
           # constantly (`User32 getWindowText: hWnd` and its kin).
           "--loose", "OS.UserLibrary",
           # `Core.Object` — see the value-models `.pax` in TARGETS.
           "--loose", "Core.Object",
           # `Core.String` carries `setTextInto:`, one half of Dolphin's
           # DOUBLE DISPATCH for setting a view's text: `View>>text:` sends
           # `aString setTextInto: self`, and the String sends `plainText:`
           # back. `UI.RichText` is the other half, which is the whole point
           # of the dispatch — the view does not have to know which it got.
           "--loose", "Core.String",
           # REOPENED, not defined: `genstructs` builds `LVCOLUMNW` from
           # winkb with typed accessors at real offsets, and the `.cls` adds
           # the Smalltalk on top — `LVCOLUMNW class >> fromColumn:` is what
           # `UI.ListView>>insertColumn:atIndex:` fills before SendMessage.
           # Defining it here instead would load after genstructs and drop the
           # layout. The generated class lands in `st/prims/structs`, so the
           # reopen is moved to the late layer alongside the UserLibrary one.
           "--reopen", "OS.LVCOLUMNW"]
    for r in refs:
        cmd += ["--reference", r]
    cmd += targets
    print("translate_mvp: %d target(s), %d reference(s) -> %s"
          % (len(targets), len(refs), args.out))
    rc = subprocess.call(cmd, cwd=os.path.join(HERE, "dolphin2mst"))
    if rc != 0:
        return rc

    # The loose-method reopen must load AFTER the class it reopens, and
    # `UserLibrary` is generated into `st/prims` — so it belongs in the LATE
    # layer, not beside the translated classes. Moved rather than emitted
    # there directly, because the translator has one output directory and the
    # layer split is the caller's concern.
    loose = os.path.join(args.out, "90_UserLibrary_loose.mst")
    if os.path.exists(loose):
        late_dir = os.path.join(REPO, "st", "mvp_compat")
        os.makedirs(late_dir, exist_ok=True)
        late = os.path.join(late_dir, "02_userlibrary_loose.mst")
        with open(loose, encoding="utf-8") as fh:
            body = fh.read()
        with open(late, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        os.remove(loose)
        print("translate_mvp: loose UserLibrary methods -> %s" % late)

    # Same relocation, same reason, for every `--reopen` class: it reopens
    # something `st/prims/structs` defines, so it must load after that layer.
    for f in sorted(os.listdir(args.out)):
        if not (f.startswith("91_") and f.endswith("_reopen.mst")):
            continue
        late_dir = os.path.join(REPO, "st", "mvp_compat")
        os.makedirs(late_dir, exist_ok=True)
        late = os.path.join(late_dir, "04_" + f[3:])
        with open(os.path.join(args.out, f), encoding="utf-8") as fh:
            body = fh.read()
        with open(late, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        os.remove(os.path.join(args.out, f))
        print("translate_mvp: struct reopen -> %s" % late)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
