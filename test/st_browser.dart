// The DD11 GOAL gate: a two-pane CLASS BROWSER over live reflection data.
//
//   dartui.exe st_browser.dart "<world;layers>" st/mvp st/mvp_compat //              st/test/ffi/dolphin_browser.mst
//
// st_controls proved the controls can be CREATED. This proves they can be
// USED: a tree holding a real slice of this image's class hierarchy, a list
// holding a class's real selectors, and the item counts read back from
// WINDOWS rather than from the models that were supposed to fill them.
//
// The data comes from ClassMirror, so a browser that renders a hard-coded
// array cannot pass — which matters, because reflection is half of what a
// class browser is.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 200 ? s.substring(0, 200) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'CtQ' + (_seq++).toString();
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
  must(num('BrowserShell routeDolphinMessages') > 0,
      'Dolphin message map installed as the routed set');

  // ── REFLECTION FIRST. If the data is wrong every later assertion is
  // measuring the wrong thing, and a tree with three items in it looks
  // identical whether the hierarchy is real or invented.
  expect('reflection knows the hierarchy',
      '(Integer superclass == Number and: [Number superclass == Magnitude])', 'true');
  must(num('(ClassMirror selectorsOf: Integer) size') > 0,
      'and a class has real selectors');

  stRun('BShell := BrowserShell new.');
  stRun('BShell create.');
  print('  .. build -> ' + ev('BShell build printString'));
  stRun('BShell show.');
  must(num('BShell handle') > 0, 'the shell opened');

  // ── THE TREE ────────────────────────────────────────────────────────────
  print('  .. populateTree -> ' + ev('BShell populateTree printString'));
  // The SHAPE, from the model: Magnitude is the only root and the other two
  // descend from it, so a flat tree fails here and nowhere else.
  expect('the tree has ONE root', 'BShell rootCount', '1');
  // The COUNT, from Windows. TVM_GETCOUNT — a model correctly filled and a
  // control that never received the items is the failure this asks about.
  must(num('BShell treeItemCount') == 3,
      'and WINDOWS holds all three tree items');

  // ── THE LIST ────────────────────────────────────────────────────────────
  print('  .. showClass -> ' + ev('(BShell showClass: Integer) name'));
  must(num('BShell listItemCount') > 0,
      'WINDOWS holds the selector rows');
  expect('and the count matches the reflection data',
      '(BShell listItemCount = (ClassMirror selectorsOf: Integer) size)', 'true');

  // ── THE THIRD PANE ──────────────────────────────────────────────────────
  // TextEdit reads its text back through WM_GETTEXT, so this is Windows'
  // answer too.
  must(ev('BShell text text').contains('Integer'),
      'the text pane names the selected class');

  // Switching class re-drives BOTH dependent panes — the thing that makes it
  // a browser rather than three controls in a window.
  stRun('BShell showClass: Magnitude.');
  expect('selecting another class re-fills the list',
      '(BShell listItemCount = (ClassMirror selectorsOf: Magnitude) size)', 'true');
  must(ev('BShell text text').contains('Magnitude'),
      'and re-fills the text pane');

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  expect('destroy succeeded', 'BShell destroy printString', "'true'");
  stRun('UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('');
  print('BROWSER: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
