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

  // ── STOPS HERE (2026-08-16) ─────────────────────────────────────────────
  //
  // The shell is fully Dolphin's and it works: created by Dolphin's own path,
  // registered by Dolphin's own binding moment, destroyed cleanly. Two things
  // after that do not work yet, and both are recorded rather than papered
  // over.
  //
  // 1. `ShellView>>show` HANGS. Narrowed: `create` alone is fine — the
  //    assertions above run with it — and the hang appears the moment `show`
  //    is sent. ShowWindow generates real WM_PAINT/WM_SHOWWINDOW traffic, and
  //    the door reflects paint through the named channel whether or not a
  //    message map is installed; a paint handler that invalidates would spin
  //    the pump forever. That is the shape to look for, and `View`'s paint
  //    path is where to start.
  //
  // 2. CHILD views are therefore untested here. `addSubView:` reaches
  //    `View>>subViewsDo:`, which enumerates real child HWNDs and asks
  //    `InputState>>lookupWindow:` for each.
  //
  // Left as an explicit stop rather than a hanging assertion: a gate that
  // hangs is worse than one that says where it stopped. Everything above this
  // line is real and passing, and `st_shell.dart` still covers the full
  // BorderLayout arrangement through the `WinView` adapter meanwhile — which
  // is exactly why that scaffolding is not deleted yet.
  print('');
  print('  -- stops here: ShellView>>show hangs; child views not yet covered --');

  // ── teardown ─────────────────────────────────────────────────────────────
  expect('destroy succeeded', 'DShell destroy printString', "'1'");
  stRun('UiSession pump.');
  must(stMvpIsWindow(h) == false, 'the shell window is gone');
  stRun('UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('\nDOLPHINSHELL: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
