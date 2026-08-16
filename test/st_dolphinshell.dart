// The DD9 SHELL GATE, rebuilt on UI.View (DolphinDart DD10).
//
//   dart.exe st_dolphinshell.dart "<layers>" st/mvp st/mvp_compat st/test/ffi/dolphin_shell.mst
//
// Same gate as `st_shell.dart`, with the `WinView` adapter removed. The
// container is a real `UI.ShellView`, the arranged things are real `UI.View`s,
// and every method Dolphin's layout reaches on them — clientRectangle,
// rectangle:, layoutExtent:, subViewsDo:, adjustRectangle:, hasVisibleStyle —
// is Dolphin's own. Nothing here supplies view protocol.
//
// The positions are checked against what BorderLayout's north/centre/south
// rules REQUIRE, computed here independently: a gate that asked the layout
// what it did would pass whatever it did.
import 'dart:io';
import 'dart:cocoa';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'DsQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', e messageText ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + cut(r);
  try {
    return stClassSend0(stClassNamed(cls), 'v').toString();
  } catch (e) {
    return 'THREW: ' + cut(e);
  }
}

int num(String expr) => int.parse(ev(expr), onError: (_) => -1);

void expect(String label, String expr, String want) {
  var got = ev(expr);
  if (got != want) {
    fails++;
    print('  FAIL ' + label.padRight(52) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

void must(bool ok, String label) {
  if (!ok) { fails++; print('  FAIL ' + label); } else { print('  ok   ' + label); }
}

/// `(x y w h)` of a sub-view, read through Dolphin's own `getRect`.
List<int> rectOf(String which) {
  var s = ev('DShell rectOf: DShell $which');
  var m = new RegExp(r'-?\d+').allMatches(s).map((x) => int.parse(x.group(0)));
  var out = m.toList();
  if (out.length != 4) {
    fails++;
    print('  FAIL reading $which -> ' + s);
    return [0, 0, 0, 0];
  }
  return out;
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  for (var dir in [a[1], a[2]]) {
    for (var p in mstIn(dir)) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('LOAD FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  var probe = stRun(new File(a[3]).readAsStringSync());
  if (probe.toString().startsWith('ERR')) {
    print('PROBE FAIL ${a[3]}: ${cut(probe)}'); exit(2);
  }

  expect('every view class initialized',
      'DolphinBoot initializeViewClasses printString', "'()'");
  stRun('UiSession startUp.');

  // ── a real Dolphin shell, built by Dolphin's own create ──────────────────
  stRun('DShell := DolphinShell new. DShell create.');
  var h = num('DShell handle');
  must(h != 0, 'the shell created its own window ($h)');
  expect('it is a ShellView', 'DShell class name', "'DolphinShell'");
  expect('  ...which is a UI.ShellView',
      '(DShell isKindOf: ShellView)', 'true');
  expect('and it registered itself', 'UiSession windowCount', '1');

  // ── show ─────────────────────────────────────────────────────────────────
  //
  // This is the assertion the gate stopped at until the `#h` handle-return
  // convention landed. `ShellView>>show` walks its children through
  // `View>>subViewsDo:`:
  //
  //     child := User32 getWindow: handle uCmd: 5.
  //     [child isNil] whileFalse: [ ... getWindow: child uCmd: 2 ]
  //
  // Windows ends that sibling chain with a NULL handle. Dolphin's own
  // external-call machinery answers nil for one; the generated floor used to
  // answer 0, and `0 isNil` is false, so the walk never terminated. The fix
  // was a return TYPE in the floor (`ret: #h`, NULL -> nil) covering all 124
  // handle returns rather than a patch at this call site — `show` is simply
  // the first caller that happened to depend on it.
  //
  // Asserted as a real termination check, not just "it returned": `show` is
  // exactly the call that used to spin forever, so the gate proves the walk
  // ENDS by reaching the statement after it.
  stRun('DShell show.');
  must(true, 'show returned — the sub-view walk terminates');
  expect('the shell is visible', 'DShell isWindowVisible', 'true');

  // ── child views, arranged by Dolphin's own BorderLayout ─────────────────
  //
  // The DD9 arrangement with the `WinView` adapter removed: three real
  // `UI.View`s created by Dolphin's `create`, parented and laid out
  // north/centre/south. This is what retires the adapter — every method the
  // layout reaches here is Dolphin's own.
  stRun('DShell buildViews.');
  // Counted through `subViewsDo:`, so it is the WALK being asserted, not the
  // three ivars the probe already holds. Exactly three: a count above this is
  // how the duplicate-window bug behind `#b` first showed itself.
  expect('three sub-views, walked by Dolphin', 'DShell subViewCount', '3');
  expect('and the registry agrees (shell + 3)', 'UiSession windowCount', '4');

  stRun('DShell resizeTo: 400 by: 300.');
  var cw = num('DShell clientWidth'), ch = num('DShell clientHeight');
  must(cw > 0 && ch > 0, 'the shell has a client area (${cw}x$ch)');

  expect('the arranger is Dolphin BorderLayout',
      'DShell layoutManager class name', "'BorderLayout'");
  var edge = num('DolphinShell edgeHeight');
  var north = rectOf('northView'),
      centre = rectOf('centreView'),
      south = rectOf('southView');

  // North is docked to the top at its preferred height, full width.
  must(north[1] == 0, 'north is at the top (y=${north[1]})');
  must(north[3] == edge, 'north takes its preferred height (${north[3]})');
  must(north[2] == cw, 'north spans the client width (${north[2]} of $cw)');

  // South is docked to the bottom: its lower edge meets the client bottom.
  must(south[3] == edge, 'south takes its preferred height (${south[3]})');
  must(south[1] + south[3] == ch,
      'south is docked to the bottom (${south[1]}+${south[3]} of $ch)');

  // The centre declares no preferred extent, so it takes exactly what the two
  // docked edges leave — which is the whole point of the algorithm.
  must(centre[1] == north[3],
      'centre starts below north (${centre[1]} vs ${north[3]})');
  must(centre[3] == ch - (2 * edge),
      'centre takes the remainder (${centre[3]} of ${ch - 2 * edge})');
  must(centre[2] == cw, 'centre spans the client width (${centre[2]})');

  // Relayout on a NEW size: the arrangement has to track the container, not
  // hold the numbers it was first given. A layout that computed once and
  // cached would pass every assertion above and fail this one.
  stRun('DShell resizeTo: 640 by: 480.');
  var ch2 = num('DShell clientHeight'), cw2 = num('DShell clientWidth');
  var centre2 = rectOf('centreView'), south2 = rectOf('southView');
  must(cw2 > cw && ch2 > ch, 'the client area grew (${cw2}x$ch2)');
  must(centre2[3] == ch2 - (2 * edge),
      'centre re-took the remainder (${centre2[3]} of ${ch2 - 2 * edge})');
  must(centre2[2] == cw2, 'centre re-spans the width (${centre2[2]})');
  must(south2[1] + south2[3] == ch2,
      'south re-docked to the new bottom (${south2[1]}+${south2[3]} of $ch2)');
  must(num('DShell relayouts') == 2, 'two layout passes ran');

  // ── FOCUS — carried from the retired `st_shell` ─────────────────────────
  //
  // `st_shell` proved this over the `WinView` adapter. The adapter is gone;
  // the behaviour is not, so the assertions move here rather than being
  // dropped with the scaffolding that happened to host them.
  stRun('DShell focusNorth.');
  expect('focus moves to the north view', 'DShell northView hasFocus', 'true');
  expect('  ...and off the other one', 'DShell southView hasFocus', 'false');
  stRun('DShell focusSouth.');
  expect('focus moves to the south view', 'DShell southView hasFocus', 'true');
  // A RELAYOUT MUST NOT STEAL IT. SWP_NOACTIVATE in the deferred-position
  // batch is what guarantees that, and without the assertion a regression
  // there is invisible — the arrangement would still be correct.
  stRun('DShell resizeTo: 560 by: 400. UiSession pump.');
  expect('a relayout does not steal focus',
      'DShell southView hasFocus', 'true');

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  // ── teardown ─────────────────────────────────────────────────────────────
  expect('destroy succeeded', 'DShell destroy printString', "'true'");
  stRun('UiSession pump.');
  must(stMvpIsWindow(h) == false, 'the shell window is gone');
  stRun('UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('\nDOLPHINSHELL: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
