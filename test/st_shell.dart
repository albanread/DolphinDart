// The DD9 ACCEPTANCE SHELL gate.
//
//   dart.exe st_shell.dart "<world;layers>" st/mvp st/test/ffi/shell_probe.mst
//
// A code-built window with three real Win32 controls, arranged by DOLPHIN'S
// OWN BorderLayout running unmodified on this VM, relaid on every real WM_SIZE
// through Dolphin's own message map.
//
// The positions are asserted against what BorderLayout's north/center/south
// rules REQUIRE, computed here independently of the implementation — a gate
// that asked the layout what it did would pass whatever the layout did. The
// numbers come from GetWindowRect, so they are where Windows actually put the
// controls, not where the layout intended to.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'ShellQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e messageText ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + cut(r);
  try {
    return stClassSend0(stClassNamed(cls), 'v').toString();
  } catch (e) {
    return 'THREW: ' + cut(e);
  }
}

void expect(String label, String expr, String want) {
  var got = ev(expr);
  if (got != want) {
    fails++;
    print('  FAIL ' + label.padRight(50) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

void must(bool ok, String label) {
  if (!ok) { fails++; print('  FAIL ' + label); } else { print('  ok   ' + label); }
}

/// `(x y w h)` of a control, from GetWindowRect via the adapter.
List<int> rectOf(String recv) {
  // Four separate sends rather than one Array: a raise inside the expression
  // would otherwise be scanned for digits and silently become coordinates.
  var out = <int>[];
  for (var part in ['origin x', 'origin y', 'width', 'height']) {
    var v = ev('(ShellWin $recv getWindowRect) $part');
    var n = int.parse(v, onError: (_) => -999999);
    if (n == -999999) {
      fails++;
      print('  FAIL reading $recv $part -> ' + v);
      return [0, 0, 0, 0];
    }
    out.add(n);
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
  for (var p in mstIn(a[1])) {
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('WAVE FAIL $p: ${cut(r)}'); exit(2); }
  }
  var probe = stRun(new File(a[2]).readAsStringSync());
  if (probe.toString().startsWith('ERR')) {
    print('PROBE FAIL ${a[2]}: ${cut(probe)}'); exit(2);
  }

  stRun('UiSession startUp.');
  stRun('ShellWin := ShellProbe open: 400 by: 300.');
  expect('the shell window opened', 'ShellWin hwnd ~= 0', 'true');
  stRun('ShellWin show. UiSession pump.');
  expect('the controls were built', 'ShellWin buildControls > 0', 'true');
  expect('Dolphin BorderLayout is the layout manager',
      'ShellWin layout class name', "'BorderLayout'");

  // The container's client extent is what BorderLayout divides up.
  var cw = int.parse(ev('ShellWin container clientRectangle width'));
  var ch = int.parse(ev('ShellWin container clientRectangle height'));
  must(cw > 0 && ch > 0, 'the container has a real client area (${cw}x$ch)');

  // ── the north/center/south rules, computed independently ────────────────
  var edge = int.parse(ev('ShellProbe edgeHeight'));
  var gap = int.parse(ev('ShellWin layout verticalGap'));

  void checkLayout(String when, int cw, int ch) {
    var north = rectOf('label');
    var south = rectOf('okButton');
    var centre = rectOf('cancelButton');
    // north: full width, docked at the top.
    must(north[0] == 0 && north[1] == 0 && north[2] == cw,
         '$when north spans the top (got $north, width $cw)');
    // south: full width, docked at the bottom.
    must(south[0] == 0 && south[2] == cw && south[1] + south[3] == ch,
         '$when south is flush with the bottom (got $south, height $ch)');
    // centre: everything between them, minus the gaps.
    var top = north[1] + north[3] + gap;
    must(centre[0] == 0 && centre[1] == top && centre[2] == cw,
         '$when centre starts below north (got $centre, expected y $top)');
    must(centre[1] + centre[3] == south[1] - gap,
         '$when centre ends above south '
         '(got ${centre[1] + centre[3]}, expected ${south[1] - gap})');
    must(centre[3] > 0, '$when centre has positive height (${centre[3]})');
  }

  checkLayout('initial:', cw, ch);

  // ── LIVE RESIZE RELAYOUT ─────────────────────────────────────────────────
  // A real SetWindowPos generates a real WM_SIZE, which travels through the
  // door and Dolphin's message map to wmSize:wParam:lParam:.
  stRun('UiSession routeMessagesFrom: View.');
  var before = int.parse(ev('ShellWin relayouts'));
  stRun('ShellWin resizeTo: 640 by: 480. UiSession pump.');
  var after = int.parse(ev('ShellWin relayouts'));
  must(after > before,
       'a real WM_SIZE drove a relayout through Dolphin\'s message map '
       '($before -> $after)');

  var cw2 = int.parse(ev('ShellWin container clientRectangle width'));
  var ch2 = int.parse(ev('ShellWin container clientRectangle height'));
  must(cw2 != cw || ch2 != ch,
       'the client area actually changed (${cw}x$ch -> ${cw2}x$ch2)');
  checkLayout('after resize:', cw2, ch2);

  // ── focus / tab traversal ────────────────────────────────────────────────
  stRun('ShellWin focusOk.');
  expect('focus moves to the OK button', 'ShellWin okButton hasFocus', 'true');
  expect('  ...and off the other one', 'ShellWin cancelButton hasFocus', 'false');
  stRun('ShellWin focusCancel.');
  expect('focus moves to the Cancel button',
      'ShellWin cancelButton hasFocus', 'true');
  // A relayout must not steal it — SWP_NOACTIVATE is what guarantees that, and
  // without the assertion a regression there is invisible.
  stRun('ShellWin resizeTo: 500 by: 380. UiSession pump.');
  expect('a relayout does not steal focus',
      'ShellWin cancelButton hasFocus', 'true');

  // ── clean destroy with registry hygiene ──────────────────────────────────
  stRun('UiSession clearMessageMap.');
  stRun('ShellWin close. UiSession pump.');
  expect('the window is gone', 'ShellWin container isWindow', 'false');
  expect('and its controls with it', 'ShellWin okButton isWindow', 'false');
  stRun('UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  var faults = stMvpPaintFaults();
  must(faults == 0, 'no paint faults during the whole run ($faults)');

  print('\nSHELL: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
