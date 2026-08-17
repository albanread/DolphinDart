// The REAL class browser gate: the WHOLE live image, ~700 classes.
//
//   dartui.exe st_browser.dart "<world;layers>" st/mvp st/mvp_compat //              st/test/ffi/dolphin_class_browser.mst
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
  must(num('ClassBrowserShell routeDolphinMessages') > 0,
      'Dolphin message map installed as the routed set');

  stRun('CB := ClassBrowserShell new.');
  stRun('CB create.');
  print('  .. build -> ' + ev('CB build printString'));
  stRun('CB show.');
  must(num('CB handle') > 0, 'the shell opened');
  // The MENU BAR is real: Windows says the window carries one.
  must(num('User32 getMenu: CB handle') > 0, 'and Windows says it has a menu bar');

  print('  .. populate -> ' + ev('CB populate printString'));
  // THE WHOLE IMAGE, not a hand-picked slice. The floor is deliberately far
  // below reality (~700) so adding or removing classes never fails this gate
  // for the wrong reason; a browser over a toy list cannot pass it.
  must(num('CB classCount') > 500, 'the model holds the live image (>500 classes)');

  // COLLAPSED ON OPEN, the classic look: lines-at-root suppresses Dolphin's
  // auto-expand, so Windows holds exactly the roots.
  expect('opens collapsed to its roots',
      '(CB treeItemCount = CB rootCount)', 'true');

  // EXPAND OBJECT: the lazy insert at real scale — its immediate subclasses
  // (~160) arrive in one TVN_ITEMEXPANDING round trip.
  stRun('CB expandClass: Object.');
  expect('expanding Object inserts exactly its children',
      '(CB treeItemCount - CB rootCount) = (CB treeModel childrenOf: Object) size',
      'true');

  // SELECTION drives the panes through the event chain.
  print('  .. select Magnitude -> ' + ev('(CB select: Magnitude) name'));
  expect('selecting fills the list with the selected class own selectors',
      '(CB listItemCount = (ClassMirror selectorsOf: Magnitude) size)', 'true');
  must(ev('CB shownClassName').contains('Magnitude'),
      'and the detail pane names it');

  // A REAL KEYSTROKE moves the selection; whatever WINDOWS now says is
  // selected, the list must match it — the assertion follows the control,
  // not a prediction of tree order.
  stRun('CB pressKey: 16r28.');
  must(!ev('CB shownClassName').contains('Magnitude < '),
      'VK_DOWN moved the selection off Magnitude');
  expect('and the list follows the keyboard selection',
      '(CB listItemCount = (ClassMirror selectorsOf: (CB tree selectionOrNil)) size)',
      'true');

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  expect('destroy succeeded', 'CB destroy printString', "'true'");
  stRun('UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('');
  print('CLASSBROWSER: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
