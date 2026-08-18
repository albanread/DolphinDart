"""Run the DolphinDart gates.

    python tools/gates.py                # every gate
    python tools/gates.py dolphinshell   # one gate (prefix match, `st_` optional)
    python tools/gates.py view shell     # several
    python tools/gates.py --list

WHY THIS EXISTS. Every gate takes its layer list and probe file as ARGV, and
until now each invocation lived in a shell one-liner that was retyped from
memory per run. Three failures in a single afternoon came from that and
nothing else: a prims regeneration pointed at the wrong corpus root that
silently rewrote `UserLibrary` down to one method; a gate run with no
arguments that died on `a[0]`; a gate run with relative paths from a working
directory that was not the repo root. None of those were bugs in the thing
under test. They were the invocation being unrecorded, which is a defect in
the harness, not in whoever typed it.

So the invocation lives HERE, once, per gate — the same call
`translate_mvp.py` and `gen_prims.py` make for their generators.

TWO THINGS THE TABLE ENCODES that a one-liner kept getting wrong:

  * **cwd is the repo root.** Some gates hard-code a relative probe path
    (`st_app` loads `st/test/ffi/text_probe.mst` itself), so every gate is run
    from the repo root and every path here is repo-relative.
  * **BOOT stops before `st/mvp`.** The layer ORDER is load-bearing and has
    been rediscovered four times, but the gates that take a `st/mvp` argument
    load it themselves — putting it in BOOT too would double-load the wave,
    and a class reopened by a second load of its own file is a silent
    redefinition, not an error.

WHICH HOST each gate needs is part of the invocation too, and the least
obvious part. `dartui.exe` runs a real Windows message pump, which is what the
window gates need and what keeps the process alive after `main` returns — so a
CONSOLE gate that simply ends, with no `exit()`, hangs there forever while
having printed every one of its correct answers. `st_structs` did exactly
that: four right answers, then a timeout. Those gates run under `dart.exe`.

A gate that hangs is a RESULT, not a reason to wait: each runs under a
timeout and reports TIMEOUT, because the failure this harness was built during
(`ShellView>>show` spinning in `subViewsDo:`) presented exactly that way.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# WHICH BUILD, SAID OUT LOUD.
#
# Debug and Release used to land in the same `build-arm64`, so whichever was
# built last is what ran and nothing reported which that was. `-Config`
# defaults to Debug, so the documented build command produced an unoptimised
# VM with assertions on, and a whole session's timings were taken from it
# without anyone — including the person taking them — knowing.
#
# Release is PREFERRED when both exist, because a timing taken from a debug
# build is worse than no timing. The chosen directory is printed on every run
# (see `main`), and `WINDART_BUILD` overrides the choice outright.
WORK = r"C:\projects\dolphindart-work"


def _pick_build():
    override = os.environ.get("WINDART_BUILD")
    if override:
        return override, "WINDART_BUILD"
    for suffix, why in (("-Release", "Release"), ("-Debug", "Debug"),
                        ("", "legacy untagged dir — config UNKNOWN")):
        cand = os.path.join(WORK, "build-arm64" + suffix)
        if os.path.exists(os.path.join(cand, "dartui.exe")):
            return cand, why
    return os.path.join(WORK, "build-arm64-Release"), "MISSING"


BUILD, BUILD_KIND = _pick_build()
DARTUI = os.path.join(BUILD, "dartui.exe")   # GUI host: runs a real message pump
DARTC = os.path.join(BUILD, "dart.exe")      # console host: exits when main returns

# The pre-MVP layers, in the order that works. Not alphabetical, not
# arbitrary: `rt` defines the marshalling helpers the generated prims call,
# `structs` the record layouts they take addresses of, and `aliases` renames
# over the top of both — so each must be loaded after what it depends on.
BOOT = ";".join([
    "st/world",
    "st/dolphin_compat",
    "st/prims/rt",
    "st/prims/structs",
    "st/prims",
    "st/prims/aliases",
])

MVP = "st/mvp"
MVP_COMPAT = "st/mvp_compat"
FFI = "st/test/ffi"

# gate -> the arguments after BOOT. BOOT is always argv[0].
GATES = {
    # Floor and substrate.
    #
    # `st_prims` and `st_battery` name their parameter `args`, not `a` — which
    # is why the first version of this table gave them BOOT alone and they
    # died on `args[1]`. The arity of a gate is not guessable from a grep for
    # one spelling; it is read from the gate.
    "st_prims": ["st/prims"],
    "st_battery": ["st/test/features"],
    "st_aliases": [],
    "st_marshal": [],
    "st_structs": [],
    # ── console gates: no window, no pump, so `dart.exe` (see CONSOLE below)
    "st_storm": [],
    "st_uisession": [],
    # Door-level gates: BOOT + a probe.
    "st_door": [FFI + "/mvp_door_spike.mst"],
    "st_paint": [FFI + "/paint_probe.mst"],
    "st_routed": [FFI + "/routed_probe.mst"],
    # The translated wave, loaded by the gate itself.
    "st_triad": [MVP],
    "st_worker": [MVP],
    "st_viewwave": [MVP],
    # Wave + a probe.
    #
    # `st_shell`, `st_text`, `st_command` and `st_app` were REMOVED with the
    # WinView adapter family they drove. Their coverage was not: focus moved
    # to `st_dolphinshell`, two-fields-one-model to `st_textedit`, command
    # enablement to `st_menu`, and the acceptance app to `st_dolphinapp` —
    # each on Dolphin's own classes. See docs/JOURNAL.md.
    "st_twowin": [MVP, FFI + "/twowin_probe.mst"],
    "st_mapped": [MVP, FFI + "/mapped_probe.mst"],
    # The Dolphin-owned view gates need the late compat layer, which reopens
    # translated classes and so must load after them.
    "st_dolphinview": [MVP, MVP_COMPAT],
    "st_dolphinshell": [MVP, MVP_COMPAT, FFI + "/dolphin_shell.mst"],
    "st_subclass": [MVP, MVP_COMPAT, FFI + "/control_subclass.mst"],
    "st_textedit": [MVP, MVP_COMPAT, FFI + "/dolphin_textedit.mst"],
    "st_menu": [MVP, MVP_COMPAT, FFI + "/dolphin_menu.mst"],
    "st_dolphinapp": [MVP, MVP_COMPAT, FFI + "/dolphin_app.mst"],
    "st_controls": [MVP, MVP_COMPAT, FFI + "/dolphin_controls.mst"],
    "st_browser": [MVP, MVP_COMPAT, FFI + "/dolphin_browser.mst"],
    # The REAL one: the whole live image (~700 classes), menu bar, collapsed
    # roots, lazy expand at scale, selection + keyboard driving the panes.
    "st_classbrowser": [MVP, MVP_COMPAT, FFI + "/dolphin_class_browser.mst"],
    # DD12's goal gate: owner disabled, showModal blocking, OK/Cancel over a
    # ValueBuffer, two stacked modals unwinding innermost-first.
    "st_modal": [MVP, MVP_COMPAT, FFI + "/dolphin_modal.mst"],
}

# Gates with no window and no message pump. They run under `dart.exe`, which
# exits when `main` returns; under the GUI host they would hang after printing
# every correct answer, which is the least informative way a gate can fail.
CONSOLE = {"st_structs", "st_marshal", "st_aliases"}

# Gates deliberately not in the sweep, with the reason. Recorded rather than
# omitted so "why is this not run" has an answer that is not archaeology.
EXCLUDED = {
    "st_one": "scratch gate — whatever is being bisected right now",
    "st_probe": "scratch gate",
    "st_world_probe": "scratch gate",
    "st_world_run": "scratch gate",
    "st_vs_dart": "benchmark, not a gate — no pass/fail",
    "st_cogbench": "benchmark, not a gate — no pass/fail",
}


def run_one(name, timeout):
    host = DARTC if name in CONSOLE else DARTUI
    argv = [host, "test/%s.dart" % name, BOOT] + GATES[name]
    try:
        p = subprocess.Popen(argv, cwd=REPO, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        out, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
        return "TIMEOUT", out.decode("utf-8", "replace")
    text = out.decode("utf-8", "replace")
    return ("PASS" if rc == 0 else "FAIL(%d)" % rc), text


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("which", nargs="*", help="gate name or prefix; all if omitted")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print each gate's full output, not just failures")
    args = ap.parse_args(argv)

    # Every run states its build. A gate result and a TIMING both mean
    # different things under Debug and Release, and the directory used to be
    # the same either way.
    print("build: %s  [%s]" % (BUILD, BUILD_KIND))
    if BUILD_KIND == "MISSING":
        print("  no dartui.exe found — build with:\n"
              "  powershell -File port-win/build.ps1 -Arch arm64 -Config Release"
              " -WorkRoot C:/projects/dolphindart-work"
              " -Tree C:/projects/dolphindart-work/tree")
        return 2

    if args.list:
        for g in sorted(GATES):
            print("  %-18s %s" % (g, " ".join(GATES[g]) or "(boot only)"))
        for g in sorted(EXCLUDED):
            print("  %-18s -- excluded: %s" % (g, EXCLUDED[g]))
        return 0

    names = sorted(GATES)
    if args.which:
        picked = []
        for w in args.which:
            w = w if w.startswith("st_") else "st_" + w
            hit = [g for g in names if g == w] or [g for g in names if g.startswith(w)]
            if not hit:
                print("gates: no gate matching %r" % w)
                return 2
            picked += hit
        names = sorted(set(picked))

    for exe in (DARTUI, DARTC):
        if not os.path.exists(exe):
            print("gates: no %s — build first" % exe)
            return 2

    bad = []
    for n in names:
        status, text = run_one(n, args.timeout)
        print("%-8s %s" % (status, n))
        if status != "PASS":
            bad.append(n)
        if args.verbose or status != "PASS":
            for line in text.splitlines():
                print("    | " + line)
    print("\n%d/%d gates pass" % (len(names) - len(bad), len(names)))
    if bad:
        print("failing: " + " ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
