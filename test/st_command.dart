// The DD10 COMMAND + MENU gate.
//
//   dart.exe st_command.dart "<world;layers>" st/mvp st/test/ffi/command_probe.mst
//
// A real Win32 menu bar — CreateMenu / InsertMenuItem / SetMenu — whose item
// enablement is decided by Dolphin's own `UI.CommandQuery` through the
// `queryCommand:` hook, and whose clicks arrive as genuine WM_COMMAND messages
// routed to the owning window.
//
// Enablement is read back FROM WINDOWS with GetMenuItemInfo. Asking the probe
// what it thinks it set would agree with itself whatever happened; asking
// Windows is the only way to know the state actually took.
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
  var cls = 'CmdQ' + (_seq++).toString();
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
  stRun('CmdWin := CommandProbe open: 420 by: 260. CmdWin show. UiSession pump.');
  expect('the shell opened', 'CmdWin hwnd ~= 0', 'true');
  var built = ev('CmdWin build class name');
  must(built == "'CommandProbe'", 'the menu was built (' + built + ')');
  expect('the menu bar is a real HMENU', 'CmdWin menu handle ~= 0', 'true');

  // ── queryCommand: decides, and WINDOWS agrees ────────────────────────────
  // The value starts at 5, so #reset is not meaningful and must be greyed.
  expect('the model starts at 5', 'CmdWin model value', '5');
  var doubleId = int.parse(ev('CommandProbe idDouble'));
  var resetId = int.parse(ev('CommandProbe idReset'));
  // Read the real state out of the real menu, via GetMenuItemInfo.
  expect('Reset is GREYED while the value is untouched',
      'CmdWin menuFileEnabled: ' + resetId.toString(), 'false');
  expect('Double is enabled',
      'CmdWin menuFileEnabled: ' + doubleId.toString(), 'true');

  // ── a real WM_COMMAND performs the command ───────────────────────────────
  stRun('CmdWin click: ' + doubleId.toString() + '. UiSession pump.');
  expect('clicking Double performed it', 'CmdWin lastCommand', '#double');
  expect('  ...and the model doubled', 'CmdWin model value', '10');

  // ── and enablement UPDATES observably ────────────────────────────────────
  // This is the assertion the gate exists for: the same item's state in the
  // real menu changed because queryCommand: answered differently.
  expect('Reset is now ENABLED (the value moved)',
      'CmdWin menuFileEnabled: ' + resetId.toString(), 'true');

  stRun('CmdWin click: ' + resetId.toString() + '. UiSession pump.');
  expect('clicking Reset performed it', 'CmdWin lastCommand', '#reset');
  expect('  ...and the model went back', 'CmdWin model value', '5');
  expect('Reset is GREYED again', 'CmdWin menuFileEnabled: ' + resetId.toString(),
      'false');

  // ── a DISABLED command refuses even when its id is delivered ─────────────
  // Windows greys the item so a user cannot click it, but an accelerator or a
  // posted message can still deliver the id. Dolphin checks; so does this.
  var before = int.parse(ev('CmdWin performed'));
  stRun('CmdWin click: ' + resetId.toString() + '. UiSession pump.');
  must(int.parse(ev('CmdWin performed')) == before,
       'a disabled command does not perform even when its id arrives '
       '(${before} -> ${ev('CmdWin performed')})');
  expect('and the model is untouched', 'CmdWin model value', '5');

  stRun('CmdWin close. UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('\nCOMMAND: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
