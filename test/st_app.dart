// A SUBSTRATE DEMONSTRATION gate (demoted 2026-08-16) — NOT the DD10
// acceptance gate. The app it drives has a hand-written presenter/view layer
// (scaffolding; see docs/sprints/dd10_NOTES.md, course correction). It stays
// because it proves the substrate carries a whole application end to end;
// DD10's acceptance app must be built from Dolphin's own classes.
//
//   dart.exe st_app.dart "<world;layers>" st/mvp st/test/ffi/counter_app.mst
//
// Everything DD10 built, in one application, driven end to end:
//
//   * edits round-trip model <-> both presenters, over real EDIT controls;
//   * bad input beeps and reverts through InvalidFormat;
//   * queryCommand: enables and disables observably, read back from Windows;
//   * a Ctrl+D ACCELERATOR fires the same command a menu click does;
//   * a long command runs in an isolate with the pump provably live, and its
//     continuation updates the model on the UI thread.
//
// The app's parts are Dolphin's — ValueHolder, NumberToText, CommandQuery,
// the event system, InvalidFormat. What is ours is the substrate under them.
import 'dart:async';
import 'dart:io';
import 'dart:cocoa';
import 'worker_host.dart' as host;

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_KEYDOWN = 0x0100;
const int VK_CONTROL = 0x11;
const int VK_D = 0x44;

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'AppQ' + (_seq++).toString();
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
    print('  FAIL ' + label.padRight(54) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

void must(bool ok, String label) {
  if (!ok) { fails++; print('  FAIL ' + label); } else { print('  ok   ' + label); }
}

main(List<String> a) async {
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
  // The app leans on the DD10 text-field presenter, which lives with the
  // text probe.
  for (var f in ['st/test/ffi/text_probe.mst', a[2]]) {
    var r = stRun(new File(f).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('APP FAIL $f: ${cut(r)}'); exit(2); }
  }

  stRun('UiSession startUp. Worker reset.');
  stRun('App := CounterApp open: 460 by: 280. App show. UiSession pump.');
  var built = ev('App build class name');
  must(built == "'CounterApp'", 'the app built ($built)');

  var dbl = num('CounterApp cmdDouble');
  var rst = num('CounterApp cmdReset');
  var cnt = num('CounterApp cmdCount');

  // ── the triad ────────────────────────────────────────────────────────────
  print('\n-- the triad --');
  expect('the model starts at 3', 'App model value', '3');
  expect('both fields show it', 'App fieldA text', "'3'");
  expect('  ...and the other', 'App fieldB text', "'3'");
  stRun("App fieldA type: '11'. App fieldA flush.");
  expect('editing A moves the model', 'App model value', '11');
  expect('  ...and B follows', 'App fieldB text', "'11'");

  // ── bad input ────────────────────────────────────────────────────────────
  print('\n-- bad input --');
  var beeps = num('App fieldB beeps');
  stRun("App fieldB type: 'zzz'. App fieldB flush.");
  must(num('App fieldB beeps') == beeps + 1, 'bad input beeped (InvalidFormat)');
  expect('the model was not written', 'App model value', '11');
  expect('the field reverted', 'App fieldB text', "'11'");

  // ── commands, read back from Windows ─────────────────────────────────────
  print('\n-- commands --');
  expect('Reset is enabled (the value moved off 3)',
      'App isEnabled: ' + rst.toString(), 'true');
  stRun('App click: ' + rst.toString() + '. UiSession pump.');
  expect('Reset ran', 'App lastCommand', '#doReset');
  expect('  ...and the model went home', 'App model value', '3');
  expect('  ...and the fields followed', 'App fieldA text', "'3'");
  expect('Reset is greyed again', 'App isEnabled: ' + rst.toString(), 'false');

  // ── THE ACCELERATOR ──────────────────────────────────────────────────────
  // Ctrl+D. The key event goes into the queue as a real WM_KEYDOWN with the
  // Ctrl key held; TranslateAcceleratorW in the pump turns it into the same
  // WM_COMMAND a menu click sends. Nothing here posts a WM_COMMAND directly —
  // that would test the command path, which the menu already covers.
  print('\n-- the accelerator --');
  var runsBefore = num('App commandsRun');
  var valBefore = num('App model value');
  stRun('App focusSelf. App pressCtrlD. UiSession pump.');
  must(num('App commandsRun') > runsBefore,
       'Ctrl+D fired a command through TranslateAcceleratorW '
       '(${runsBefore} -> ${num('App commandsRun')})');
  expect('  ...and it was Double', 'App lastCommand', '#doDouble');
  must(num('App model value') == valBefore * 2,
       '  ...which doubled the model ($valBefore -> ${num('App model value')})');

  // ── the long command ─────────────────────────────────────────────────────
  print('\n-- the long command --');
  var results = num('App workerResults');
  stRun('App click: ' + cnt.toString() + '. UiSession pump.');
  expect('the app is busy', 'App busy', 'true');
  expect('  ...and every command is disabled while it runs',
      'App isEnabled: ' + dbl.toString(), 'false');

  host.dispatchPending();
  var paints = num('App painted');
  var loops = 0;
  while (host.outstanding > 0 && loops < 3000) {
    stRun('App invalidate. UiSession pump.');
    await new Future.delayed(const Duration(milliseconds: 1));
    loops++;
  }
  must(host.outstanding == 0, 'the worker finished (after $loops slices)');
  // Windows coalesces WM_PAINT, so the exact count is timing-dependent —
  // three real paints already prove the pump ran while the isolate burned.
  must(num('App painted') - paints >= 3,
       'the UI kept painting throughout '
       '(${num('App painted') - paints} real WM_PAINTs)');

  stRun('UiSession pump.');
  must(num('App workerResults') == results + 1,
       'the continuation ran on the UI thread');
  expect('the app is no longer busy', 'App busy', 'false');
  expect('  ...and the commands came back',
      'App isEnabled: ' + dbl.toString(), 'true');
  expect('the fields show the worker\'s result',
      'App fieldA text = App fieldB text', 'true');

  // ── teardown ─────────────────────────────────────────────────────────────
  print('');
  stRun('WinAccelerators uninstall. App close. UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');
  must(stMvpPaintFaults() == 0,
       'no paint faults across the whole run (${stMvpPaintFaults()})');

  print('\nAPP: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
