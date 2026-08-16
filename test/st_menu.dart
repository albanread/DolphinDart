// The DD10 DOLPHIN TEXTEDIT gate.
//
//   dartui.exe st_textedit.dart "<world;layers>" st/mvp st/mvp_compat \
//              st/test/ffi/dolphin_textedit.mst
//
// `st_subclass` proved the subclassing substrate with a hand-written probe
// standing in for a control view. This is the same thing with the stand-in
// removed: a real `UI.TextEdit` inside a real `UI.ShellView`, created by
// Dolphin's own `View>>create`, subclassed by Dolphin's own
// `ControlView>>subclassWindow`, and driven through Dolphin's own value
// protocol and `UI.TextPresenter`.
//
// This is what retires `WinTextEdit`/`TextField` — so the gate is written to
// prove the control is REAL rather than that our code ran: the window class
// is read back from Windows, and the text is read out of the control.
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
  var cls = 'MnQ' + (_seq++).toString();
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
  must(num('MenuShell routeDolphinMessages') > 0,
      'Dolphin message map installed as the routed set');

  stRun('MnShell := MenuShell new. MnShell create. MnShell show.');
  must(num('MnShell handle') > 0, 'the shell created its window');

  // ── Dolphin builds the menu ─────────────────────────────────────────────
  print('  .. buildMenu -> ' + ev('MnShell buildMenu printString'));
  expect('the shell has a MenuBar', '(MnShell bar isKindOf: MenuBar)', 'true');
  expect('  ...with two sub-menus', 'MnShell bar items size printString', "'2'");

  // WINDOWS' answer. A menu built but never attached passes everything else.
  var hmenu = num('MnShell windowMenuHandle');
  must(hmenu > 0, 'Windows says the window has a menu ($hmenu)');
  expect('and it is the MenuBar own handle',
      '(MnShell windowMenuHandle = MnShell bar handle)', 'true');

  // ── fire a command the way Windows does ─────────────────────────────────
  //
  // WM_COMMAND with lParam 0 is a MENU command — that null is what tells
  // Dolphin's handler to resolve the id through the CommandDescription
  // registry rather than treat it as a control notification.
  var openId = num("MnShell idFor: #fileOpen");
  must(openId > 0, 'the fileOpen item carries a command id ($openId)');

  stRun('Win32 mvpSendMsg: MnShell handle msg: 273 wparam: $openId lparam: 0.');
  stRun('UiSession pump.');
  expect('onCommand: fired once', 'MnShell receivedCount printString', "'1'");
  expect('  ...with a CommandDescription, not an id',
      '(MnShell received isKindOf: CommandDescription)', 'true');
  // `CommandDescription>>command` answers the SYMBOL, which is what an
  // application actually dispatches on — the numeric id is a Windows detail
  // that exists only to survive the trip through WM_COMMAND.
  expect('  ...and it is the command the ITEM carries',
      'MnShell received command printString', "'#fileOpen'");

  // A different item must resolve to a DIFFERENT command — otherwise the
  // assertion above would hold for a handler that ignored the id entirely.
  var pasteId = num("MnShell idFor: #editPaste");
  must(pasteId > 0 && pasteId != openId,
      'a second item has its own id ($pasteId)');
  stRun('Win32 mvpSendMsg: MnShell handle msg: 273 wparam: $pasteId lparam: 0.');
  stRun('UiSession pump.');
  expect('the second command arrived too', 'MnShell receivedCount printString', "'2'");
  expect('  ...and it is a DIFFERENT command',
      'MnShell received command printString', "'#editPaste'");

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  expect('destroy succeeded', 'MnShell destroy printString', "'true'");
  stRun('UiSession pump. UiSession shutDown.');

  print('');
  print('MENU: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
