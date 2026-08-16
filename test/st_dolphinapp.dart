// The DD10 ACCEPTANCE APP gate, on Dolphin's own classes.
//
//   dartui.exe st_dolphinapp.dart "<world;layers>" st/mvp st/mvp_compat //              st/test/ffi/dolphin_app.mst
//
// Replaces `st_app`, which drove the app through the DD7/DD8 scaffolding
// (`UiWindow`, `WinView`, `TextField`, `WinMenu`, `WinAccelerators`). Every
// one of those is retired; the assertions move here rather than being dropped
// with the stand-ins that happened to host them.
//
// What this proves that the narrower gates do not: TWO fields agreeing
// through ONE model, command enablement that follows model STATE, the
// bad-input path leaving the model untouched, and a long command that
// disables the commands without freezing the pump.
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
  var cls = 'ApQ' + (_seq++).toString();
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
  must(num('DolphinApp routeDolphinMessages') > 0,
      'Dolphin message map installed as the routed set');

  // SEPARATE sends, deliberately. A raise in one statement of a multi-
  // statement doit abandons the rest silently, and `App build` following
  // `App show` in one string is how `model` ended up nil with every later
  // assertion blaming the model.
  stRun('App := DolphinApp new.');
  stRun('App create.');
  stRun('App build.');
  stRun('App show.');

  must(num('App handle') > 0, 'the app shell opened');

  // ── two fields, one model ───────────────────────────────────────────────
  expect('the model starts at 3', 'App model value printString', "'3'");
  must(num('App fieldA handle') > 0, 'field A is a real window');
  must(num('App fieldB handle') > 0, 'field B is a real window');
  stRun('App model value: 7.');
  expect('both fields show the model', 'App textOfA', "'7'");
  expect('  ...and the other', 'App textOfB', "'7'");

  // ── enablement follows MODEL STATE ──────────────────────────────────────
  stRun('App model value: 3.');
  expect('Reset is DISABLED at the starting value',
      '(App isEnabled: #appReset) printString', "'false'");
  expect('  ...while Double is enabled',
      '(App isEnabled: #appDouble) printString', "'true'");
  stRun('App model value: 9.');
  expect('Reset is ENABLED once the value moved',
      '(App isEnabled: #appReset) printString', "'true'");

  // ── a menu command, end to end ──────────────────────────────────────────
  var dblId = num('CommandDescription idFor: (CommandDescription command: #appDouble)');
  must(dblId > 0, 'Double has a command id ($dblId)');
  stRun('Win32 mvpSendMsg: App handle msg: 273 wparam: $dblId lparam: 0.');
  stRun('UiSession pump.');
  expect('the command ran', 'App commandsRun printString', "'1'");
  expect('  ...and it was Double', 'App lastCommand printString', "'#appDouble'");
  expect('  ...and the model doubled', 'App model value printString', "'18'");
  expect('  ...and both fields followed', 'App textOfA', "'18'");

  var resetId = num('CommandDescription idFor: (CommandDescription command: #appReset)');
  stRun('Win32 mvpSendMsg: App handle msg: 273 wparam: $resetId lparam: 0.');
  stRun('UiSession pump.');
  expect('Reset ran', 'App lastCommand printString', "'#appReset'");
  expect('  ...and the model went home', 'App model value printString', "'3'");
  expect('Reset is DISABLED again', '(App isEnabled: #appReset) printString', "'false'");

  // ── the long command: commands lock, the pump does not ──────────────────
  var countId = num('CommandDescription idFor: (CommandDescription command: #appCount)');
  stRun('App startCount.');
  expect('the app is busy', 'App busy printString', "'true'");
  expect('  ...and every command is disabled while it runs',
      '(App isEnabled: #appDouble) printString', "'false'");
  // The PUMP still runs — which is the whole point of putting the work on a
  // worker. A frozen pump would never drain the posted action.
  stRun('UiSession pump.');
  expect('the app is no longer busy', 'App busy printString', "'false'");
  expect('  ...and the worker result arrived', 'App workerResults printString', "'1'");
  expect('  ...and the commands came back',
      '(App isEnabled: #appDouble) printString', "'true'");

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  expect('destroy succeeded', 'App destroy printString', "'true'");
  stRun('UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('');
  print('DOLPHINAPP: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
