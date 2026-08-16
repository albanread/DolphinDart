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
  var cls = 'TeQ' + (_seq++).toString();
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

  // Asserted, not just run. `initializeViewClasses` answers the classes that
  // FAILED, and swallowing that answer is how a class ends up half
  // initialized with a nil class variable that only bites much later.
  expect('every view class initialized',
      'DolphinBoot initializeViewClasses printString', "'()'");
  stRun('UiSession startUp.');

  // ── a shell that owns a text field ──────────────────────────────────────
  stRun('TeShell := TextEditShell new. TeShell create. TeShell show.');
  must(num('TeShell handle') > 0, 'the shell created its window');

  print('  .. buildEdit -> ' + ev('TeShell buildEdit printString'));
  var edit = num('TeShell editView handle');
  must(edit > 0, 'the TextEdit created its window ($edit)');
  expect('it is a UI.TextEdit', '(TeShell editView isKindOf: TextEdit)', 'true');
  expect('  ...which is a UI.ControlView',
      '(TeShell editView isKindOf: ControlView)', 'true');

  // WINDOWS' answer, not ours. A view that quietly fell back to the door's
  // own window class would satisfy every assertion above and fail this one.
  // Windows answers the class name with ITS capitalisation ('Edit'), not the
  // 'EDIT' the create call passed — window class names are case-insensitive.
  // Compared case-folded so the assertion is about the class, not the casing.
  expect('and Windows says the class is EDIT',
      'TeShell editClassName asUppercase', "'EDIT'");

  // ── it was subclassed, by Dolphin's own code ────────────────────────────
  expect('the control was subclassed',
      'TeShell editView oldWndProc notNil', 'true');
  var vmProc = num('VM getWndProc');
  must(num('TeShell editView oldWndProc') != vmProc,
      'and oldWndProc is comctl’s procedure, not ours');
  // `setWndProc:` branches on VMConstants.IsWin64. If that had stayed false
  // the 64-bit address would have been truncated by SetWindowLongW and the
  // window procedure now installed would be garbage — so read it back.
  expect('the installed procedure IS the trampoline',
      '((User32 getWindowLongPtr: TeShell editView handle nIndex: -4) = VM getWndProc)',
      'true');

  // ── Dolphin's own text protocol, through the control ────────────────────
  stRun("TeShell editView text: 'hello'.");
  expect('text: / text round-trips', 'TeShell editView text', "'hello'");
  expect('  ...and Windows holds it too',
      '(User32 getWindowText: TeShell editView handle)', "'hello'");

  // ── the value protocol, which is what a presenter drives ────────────────
  stRun("TeShell editView value: 'from the model'.");
  expect('value: reaches the control',
      '(User32 getWindowText: TeShell editView handle)', "'from the model'");
  expect('value reads back', 'TeShell editView value', "'from the model'");

  // ── UI.TextPresenter on top, over a ValueHolder ─────────────────────────
  //
  // The triad in anger on a REAL control: model -> presenter -> view. DD10's
  // `st_triad` proved the model side against no window at all; this is the
  // same classes with a Win32 EDIT at the end of the chain.
  stRun("TeModel := 'typed in' asValue.");
  stRun('TePres := TextPresenter new.');
  stRun('TePres model: TeModel; view: TeShell editView.');
  expect('the presenter took the model',
      '(TePres model == TeModel)', 'true');

  stRun("TeModel value: 'set through the model'.");
  expect('a model change reaches the CONTROL',
      '(User32 getWindowText: TeShell editView handle)', "'set through the model'");

  // The other direction: what the user would have typed. `setWindowText:`
  // stands in for the keystrokes — the control's own procedure stores it, and
  // the view must read that back rather than a cached copy.
  stRun("User32 setWindowText: TeShell editView handle lpString: 'as if typed'.");
  expect('and the view reads what the control holds',
      'TeShell editView text', "'as if typed'");

  // ── teardown ────────────────────────────────────────────────────────────
  expect('destroy succeeded', 'TeShell destroy printString', "'true'");
  stRun('UiSession pump.');
  must(stMvpIsWindow(edit) == false, 'the control window is gone');
  stRun('UiSession shutDown.');

  print('\nTEXTEDIT: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
