// The DD10 TEXT-PRESENTER gate — the triad over real Win32 EDIT controls.
//
//   dart.exe st_text.dart "<world;layers>" st/mvp st/test/ffi/text_probe.mst
//
// Two fields over ONE model. Edit either and both it and the model move; the
// other field follows. Dolphin's ValueHolder, Dolphin's NumberToText,
// Dolphin's event system, Dolphin's InvalidFormat — the only thing that is
// ours is the EDIT control itself, created through the generated
// createWindowEx: prim.
//
// The text assertions read the WINDOW, via GetWindowTextW. A gate that asked
// the presenter what it thinks the text is would pass on a field that never
// updated.
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
  var cls = 'TextQ' + (_seq++).toString();
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
  stRun('TxWin := TextProbe open: 420 by: 200. TxWin show. UiSession pump.');
  expect('the shell opened', 'TxWin hwnd ~= 0', 'true');
  // Through `ev`, so a raise inside build is REPORTED rather than leaving
  // every later assertion to fail against a nil field.
  var built = ev('TxWin build class name');
  must(built == "'TextProbe'", 'the controls were built (' + built + ')');

  // ── real controls, not door conveniences ────────────────────────────────
  expect('the left field is a real window',
      'TxWin left edit isWindow', 'true');
  expect('the right field too', 'TxWin right edit isWindow', 'true');
  must(ev('TxWin left edit handle') != ev('TxWin right edit handle'),
       'they are distinct windows');
  expect('and they carry their control ids',
      'TxWin left edit controlId', '6001');

  // ── the model reaches both fields at construction ────────────────────────
  expect('the model holds its initial value', 'TxWin model value', '100');
  expect('the left field shows it', 'TxWin left text', "'100'");
  expect('the right field shows it too', 'TxWin right text', "'100'");

  // ── edit LEFT: the model moves, and RIGHT follows ────────────────────────
  // This is the triad's whole claim. Asserting the model alone would pass on a
  // model with one subscriber; asserting the other FIELD is what proves the
  // change propagated all the way back out to a second view.
  stRun("TxWin left type: '250'. TxWin left flush.");
  expect('editing left updates the model', 'TxWin model value', '250');
  expect('  ...and the RIGHT field followed', 'TxWin right text', "'250'");

  // ── and symmetrically ────────────────────────────────────────────────────
  stRun("TxWin right type: '7'. TxWin right flush.");
  expect('editing right updates the model', 'TxWin model value', '7');
  expect('  ...and the LEFT field followed', 'TxWin left text', "'7'");

  // ── a change made on the MODEL reaches both ──────────────────────────────
  // The path a worker continuation will use (docs/WORKERS.md): nothing touches
  // a view, the model is set, and the views follow.
  stRun('TxWin model value: 42.');
  expect('a model-side change reaches left', 'TxWin left text', "'42'");
  expect('  ...and right', 'TxWin right text', "'42'");

  // ── BEEP AND REVERT: the DD4 path, in anger ──────────────────────────────
  var beeps = int.parse(ev('TxWin left beeps'));
  stRun("TxWin left type: 'not a number'. TxWin left flush.");
  must(int.parse(ev('TxWin left beeps')) == beeps + 1,
       'bad input signalled InvalidFormat and was caught');
  expect('the model was NOT written', 'TxWin model value', '42');
  expect('the field reverted to the model value', 'TxWin left text', "'42'");
  expect('and the other field never moved', 'TxWin right text', "'42'");
  // The revert must survive a round trip — a field that reverts visually but
  // left a stale value behind would fail on the next flush.
  stRun('TxWin left flush.');
  expect('flushing the reverted field is a no-op', 'TxWin model value', '42');

  // ── teardown ─────────────────────────────────────────────────────────────
  stRun('TxWin close. UiSession pump. UiSession shutDown.');
  expect('the controls went with the window',
      'TxWin left edit isWindow', 'false');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('\nTEXT: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
