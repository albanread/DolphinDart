// The DD11 COMMON CONTROLS gate.
//
//   dartui.exe st_controls.dart "<world;layers>" st/mvp st/mvp_compat //              st/test/ffi/dolphin_controls.mst
//
// A real SysTreeView32 and a real SysListView32, created by Dolphin's own
// View>>create and subclassed by its own ControlView>>subclassWindow. The
// same substrate UI.TextEdit uses — which is the claim under test: an EDIT
// and a ListView differ only in which class comctl registered.
//
// Windows is asked for each control's class name. A control that quietly
// fell back to the door's own window class would satisfy everything else.
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
  must(num('ControlsShell routeDolphinMessages') > 0,
      'Dolphin message map installed as the routed set');

  stRun('CShell := ControlsShell new.');
  stRun('CShell create.');
  print('  .. build -> ' + ev('CShell build printString'));
  stRun('CShell show.');
  must(num('CShell handle') > 0, 'the shell opened');

  // ── the TREE ─────────────────────────────────────────────────────────────
  must(num('CShell tree handle') > 0, 'the TreeView has a real window');
  expect('it is a UI.TreeView', '(CShell tree isKindOf: TreeView)', 'true');
  // WINDOWS' answer. This is the assertion InitCommonControlsEx exists for:
  // without it CreateWindowExW cannot find the class at all.
  expect('and Windows says SysTreeView32',
      '(CShell classNameOf: CShell tree)', "'SysTreeView32'");
  expect('Dolphin subclassed it', '(CShell isSubclassed: CShell tree)', 'true');

  // ── the LIST ─────────────────────────────────────────────────────────────
  must(num('CShell list handle') > 0, 'the ListView has a real window');
  expect('it is a UI.ListView', '(CShell list isKindOf: ListView)', 'true');
  expect('and Windows says SysListView32',
      '(CShell classNameOf: CShell list)', "'SysListView32'");
  expect('Dolphin subclassed it', '(CShell isSubclassed: CShell list)', 'true');

  // Both are ControlViews, which is the whole point: the subclassing
  // substrate is indifferent to WHICH comctl class it is.
  expect('both are UI.ControlViews',
      '((CShell tree isKindOf: ControlView) and: [CShell list isKindOf: ControlView])',
      'true');

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  expect('destroy succeeded', 'CShell destroy printString', "'true'");
  stRun('UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('');
  print('CONTROLS: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
