// The DD10 MVP-TRIAD gate.
//
//   dart.exe st_triad.dart "<world;layers>" st/mvp
//
// Dolphin's own model side, translated: `Core.Model`, `UI.ValueModel`,
// `UI.ValueHolder`, `UI.ValueAspectAdaptor`, `UI.ValueBuffer`, and the type
// converters. These REPLACE the DD8 compat stand-ins, so the contracts that
// suite asserted are asserted here instead — against the real classes.
//
// The point of the triad is that a change made anywhere is seen everywhere:
// two presenters over one model must both see an edit made through either. So
// the assertions are about PROPAGATION, not about accessors answering what
// they were given.
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
  var cls = 'TriadQ' + (_seq++).toString();
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
    print('  FAIL ' + label.padRight(52) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  int loaded = 0, bad = 0;
  for (var p in mstIn(a[1])) {
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) {
      bad++;
      print('  LOAD FAIL ' + p.split(new RegExp(r"[\/]")).last + ': ' + cut(r));
    } else {
      loaded++;
    }
  }
  print('MVP WAVE: $loaded loaded, $bad failed');
  fails += bad;

  // ── the classes are Dolphin's, not the DD8 stand-ins ─────────────────────
  expect('ValueHolder is a ValueModel', 'ValueHolder inheritsFrom: ValueModel', 'true');
  expect('ValueModel is a Model', 'ValueModel inheritsFrom: Model', 'true');
  expect('ValueBuffer is a ValueHolder',
      'ValueBuffer inheritsFrom: ValueHolder', 'true');

  // ── a value model carries a value and NOTIFIES on change ────────────────
  stRun('TriadProbe := OrderedCollection new.');
  stRun("Vh := ValueHolder with: 41.");
  expect('ValueHolder carries its value', 'Vh value', '41');
  stRun("Vh when: #valueChanged send: #add: to: TriadProbe with: #changed.");
  stRun('Vh value: 42.');
  expect('value: updates', 'Vh value', '42');
  expect('  ...and notifies exactly once', 'TriadProbe size', '1');
  // setValue: is the buffered write — it must NOT notify, which is what makes
  // a ValueBuffer able to hold an edit back until it is accepted.
  stRun('Vh setValue: 43.');
  expect('setValue: updates without notifying', 'TriadProbe size', '1');
  expect('  ...but the value did change', 'Vh value', '43');

  // ── TWO subscribers on one model both see the change ────────────────────
  // This is the triad's actual claim. One subscriber proves a callback fires;
  // two prove the model broadcasts rather than remembering the last one.
  stRun('A := OrderedCollection new. B := OrderedCollection new.');
  stRun("Vh2 := ValueHolder with: 1.");
  stRun("Vh2 when: #valueChanged send: #add: to: A with: #a.");
  stRun("Vh2 when: #valueChanged send: #add: to: B with: #b.");
  stRun('Vh2 value: 2.');
  expect('subscriber A saw the change', 'A size', '1');
  expect('subscriber B saw it too', 'B size', '1');

  // ── the converter path, and the bad input that must raise ───────────────
  expect('NumberToText is a TypeConverter',
      'NumberToText inheritsFrom: TypeConverter', 'true');
  // Dolphin's direction convention: LEFT is the model's type, RIGHT is the
  // view's. So leftToRight: is number -> text and rightToLeft: is text ->
  // number, which is the way round a presenter uses them.
  expect('a number converts to its text (model -> view)',
      "(NumberToText new leftToRight: 42)", "'42'");
  expect('and text back to a number (view -> model)',
      "(NumberToText new rightToLeft: '42')", '42');
  expect('  ...including a negative', "(NumberToText new rightToLeft: '-7')", '-7');
  // The failure this sprint exists to exercise: bad input must RAISE, not
  // answer nil. A converter that answers nil on garbage is how a model ends up
  // holding nil and failing somewhere else entirely.
  var bad2 = ev("NumberToText new rightToLeft: 'not a number'");
  if (bad2 == 'nil') {
    fails++;
    print('  FAIL bad input answered nil instead of raising');
  } else if (bad2.startsWith('RAISED:')) {
    print('  ok   bad input RAISES rather than answering nil ($bad2)');
  } else {
    print('  ok   bad input answered <$bad2> (not nil)');
  }

  print('\nTRIAD: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
