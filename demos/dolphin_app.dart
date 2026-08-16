// THE VISIBLE SHELL — DD10's acceptance app, on screen, driven by hand.
//
//   run-dolphin-app.cmd            (or)
//   dartui.exe demos/dolphin_app.dart "<layers>" st/mvp st/mvp_compat \
//              st/test/ffi/dolphin_app.mst
//
// Every DD10 gate so far is HEADLESS: it creates a window, asserts against it
// and destroys it inside one run, and nothing is ever left on screen. That is
// the right shape for a test and it is not proof that a person can use the
// thing. This is the other half — the same `DolphinApp`, the same Dolphin
// classes, shown and then pumped until the user closes it.
//
// It is NOT a gate. It has no assertions and never exits non-zero; its whole
// job is to put a real window in front of a real person. `st_dolphinapp` is
// where the behaviour is asserted.
//
// WHAT YOU SHOULD SEE: a window with two edit fields stacked north/south
// (Dolphin's BorderLayout), an "Edit" menu carrying Double, Reset, a
// separator and "Count (slow)". Typing a number in the top field and moving
// focus updates the model, and the bottom field follows. Typing something
// that is not a number beeps and clears the field — Dolphin's own
// beep-and-revert. Reset is greyed until the value moves off 3.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 200 ? s.substring(0, 200) : s;
}

int _seq = 0;

/// Evaluate a Smalltalk EXPRESSION and answer its printString.
///
/// `stRun` answers the LOADER's report — "loaded st:mst/336 (1 classes)" —
/// not the value of anything, so it cannot be used to ask a question. The
/// first version of this demo tested `App isOpen` with `stRun` and got that
/// report back, which is not 'true', so the pump loop exited immediately and
/// the window vanished the instant it appeared.
String ev(String expr) {
  var cls = 'DemoQ' + (_seq++).toString();
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

/// Load a layer, and STOP on the first error with the file named. A demo that
/// half-loads and then shows an empty window is worse than one that refuses.
void load(String path) {
  var r = stRun(new File(path).readAsStringSync());
  if (r.toString().startsWith('ERR')) {
    print('LOAD FAIL $path: ${cut(r)}');
    exit(2);
  }
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) load(p);
  }
  for (var dir in [a[1], a[2]]) {
    for (var p in mstIn(dir)) load(p);
  }
  load(a[3]);

  print('[dolphin-app] view classes that failed to initialize: '
      + ev('DolphinBoot initializeViewClasses printString'));

  stRun('UiSession startUp.');
  stRun('DolphinApp routeDolphinMessages.');

  // Separate sends: a raise inside a multi-statement doit abandons the rest
  // of the string silently.
  stRun('App := DolphinApp new.');
  stRun('App create.');
  stRun('App build.');
  stRun('App show.');

  // A SIZE the user can actually use. The gates resize to prove the layout
  // tracks the container; here it is simply set once to something reasonable.
  stRun('App resizeTo: 420 by: 200.');

  print('[dolphin-app] window ' + ev('App handle printString') + ' is up.');
  print('[dolphin-app] Edit menu: Double, Reset, Count (slow).');
  print('[dolphin-app] Close the window to quit.');

  // THE PUMP. `UiSession pump` drains a slice of the Windows queue and runs
  // any posted actions; looping it is what makes the window live rather than
  // appear-and-freeze. It ends when the window is gone — the user closed it.
  var idle = 0;
  while (true) {
    stRun('UiSession pump.');
    if (ev('App isOpen') != 'true') break;
    // Yield to the OS when there is nothing to do, so an idle window does not
    // spin a core. 5ms is below the threshold where typing feels laggy.
    idle = (idle + 1) % 1000;
    sleep(const Duration(milliseconds: 5));
  }

  print('[dolphin-app] window closed; shutting down.');
  stRun('UiSession shutDown.');
  exit(0);
}
