// A DEMO, not a gate: a window that stays up, pumps real messages, and gets
// photographed along the way.
//
//   dartui.exe st_demo.dart "<world;layers>" st/mvp st/mvp_compat \
//              st/test/ffi/dolphin_browser.mst [seconds]
//
// WHY THIS IS SEPARATE FROM THE GATES. A gate creates, asserts and destroys in
// milliseconds; nothing pumps, so WM_PAINT never runs and the window on screen
// is an unpainted frame — chrome and a blank client area. That is what a human
// watching the suite actually sees, and it is why every GUI conclusion in this
// port so far has been an INFERENCE from handles and item counts rather than
// an observation.
//
// This runs the loop for a real interval and captures the client area to a BMP
// at intervals, which `tools/shot.py` turns into a PNG. An assertion cannot
// tell "drew correctly" from "never drew". A picture can.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 300 ? s.substring(0, 300) : s;
}

int _seq = 0;
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
  var seconds = a.length > 4 ? int.parse(a[4], onError: (_) => 60) : 60;
  var shotDir = a.length > 5 ? a[5] : '.';

  print('init      -> ' + ev('DolphinBoot initializeViewClasses'));
  stRun('UiSession startUp.');
  print('routed    -> ' + ev('BrowserShell routeDolphinMessages'));

  stRun('DShell := BrowserShell new.');
  stRun('DShell create.');
  print('build     -> ' + ev('DShell build printString'));
  stRun('DShell show.');
  print('populate  -> ' + ev('DShell populateTree printString'));
  print('showClass -> ' + ev('(DShell showClass: Integer) name'));

  // PUMP FIRST, then photograph. The capture reflects whatever the window has
  // actually painted, so a shot taken before the first WM_PAINT is a picture
  // of nothing — which would look exactly like a bug in the controls.
  print('pump      -> ' + ev('UiSession runFor: 500'));

  void shot(String tag) {
    var path = shotDir + Platform.pathSeparator + 'shot_' + tag + '.bmp';
    var dims = ev("Win32 mvpCapture: DShell handle path: '" +
        path.replaceAll('\\', '\\\\') + "' clientOnly: false");
    print('shot ' + tag.padRight(10) + ' -> ' + dims + '  ' + path);
  }

  shot('opened');
  stRun('DShell expandRoots.');
  stRun('DShell tree expand: Number.');
  print('expand    -> ' + ev('DShell treeItemCount'));
  print('pump      -> ' + ev('UiSession runFor: 500'));
  shot('expanded');

  // The long watch. Split into slices so the window keeps answering input
  // while a human looks at it, with a shot at the end for the record.
  print('watching for ' + seconds.toString() + 's ...');
  for (var i = 0; i < seconds; i++) {
    stRun('UiSession runFor: 1000.');
    if (i == seconds ~/ 2) shot('midway');
  }
  shot('final');

  print('notify counts -> ' + ev('NotifyTrace counts printString'));
  print('handlerErrors -> ' + ev('UiSession handlerErrors printString'));
  stRun('DShell destroy. UiSession pump. UiSession shutDown.');
  exit(0);
}
