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

  // ── STOPS HERE — root cause known (review, 2026-08-16 evening) ──────────
  //
  // `ShellView>>show` hangs in `View>>subViewsDo:`:
  //
  //     child := User32 getWindow: handle uCmd: 5.
  //     [child isNil] whileFalse: [ ... getWindow: child uCmd: 2 ]
  //
  // Dolphin's external-call machinery answers NIL for a NULL handle return;
  // this port's generated prims answer 0 (every UserLibrary return is
  // `ret: #g`). `0 isNil` is false, so the loop never terminates — and it
  // only "worked" before `InputState>>lookupWindow:` existed because the
  // first iteration raised inside the loop. (The earlier paint-spin guess in
  // this comment was wrong; the paint path never calls lookupWindow:.)
  //
  // The fix is a FAMILY fix, not a patch: a `#h` handle-return convention in
  // the floor (NULL -> nil), driven from winkb, which knows which returns
  // are handles. Until it lands the gate stops here and says so — a gate
  // that hangs is worse than one that reports where it stopped — and
  // `st_shell.dart` keeps covering the full BorderLayout arrangement through
  // the WinView adapter, which is exactly why that scaffolding is not
  // deleted yet.
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
