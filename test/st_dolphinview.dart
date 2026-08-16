// The DD10 DOLPHIN-VIEW gate — UI.View owns a real window.
//
//   dart.exe st_dolphinview.dart "<layers>" st/mvp st/mvp_compat
//
// Everything under test here is Dolphin's own code. `View>>create` ->
// `createWindow:` -> `basicCreateWindow:` -> `CreateWindow>>create:` ->
// `User32 createWindowEx:` runs unmodified; the substrate supplies only the
// window CLASS (its WndProc has to be the door's), the module handle, the
// green-process slot Dolphin uses to hold the view during CreateWindowExW,
// and a desktop object to be the creation parent.
//
// This is what retires the `WinView` scaffolding: a Dolphin View that owns
// its own HWND does not need an adapter to stand in for one.
import 'dart:io';
import 'dart:cocoa';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_SIZE = 0x0005;

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'DvQ' + (_seq++).toString();
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

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  // The wave, then the LATE layer — in that order, because the late layer
  // overrides methods the wave defines.
  for (var dir in [a[1], a[2]]) {
    for (var p in mstIn(dir)) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('LOAD FAIL $p: ${cut(r)}'); exit(2); }
    }
  }

  // Dolphin's package loader sends class-side initialize; the layer loader has
  // no package concept, so this is the explicit equivalent.
  // Reported, not assumed: a boot line that aborts half way leaves whatever
  // followed it silently un-run, which is exactly how this gate first read a
  // registry of 0 windows.
  expect('every view class initialized',
      'DolphinBoot initializeViewClasses printString', "'()'");
  stRun('UiSession startUp.');
  expect('View class variables initialized (NextId is live)',
      'View new defaultId > 0', 'true');

  // ── Dolphin's own create makes a real window ─────────────────────────────
  stRun('DV := View new. DV create.');
  var h = num('DV handle');
  must(h != 0, 'View>>create produced a handle ($h)');
  // `stMvpIsWindow` answers a BOOLEAN. Comparing it to 0 is not a comparison
  // — `true != 0` is true and `false == 0` is false, so an `!= 0` test passes
  // whatever the answer and an `== 0` test never passes. Both were written
  // that way here and both were meaningless.
  must(stMvpIsWindow(h) == true, '  ...and Windows agrees it is a window');

  // ── it registered ITSELF, through Dolphin's own binding moment ───────────
  // `basicCreateWindow:` parks the view in the green-process slot, the door
  // reports WM_NCCREATE from inside CreateWindowExW, and UiSession binds the
  // pair. Nothing in the gate registered anything.
  expect('the view registered itself', 'UiSession windowCount', '1');
  must(ev('(UiSession viewFor: DV handle) == DV') == 'true',
       '  ...and the registry maps its handle back to IT');

  // ── messages reach Dolphin's own handlers ────────────────────────────────
  // Routed by the map Dolphin's own buildMessageMap supplies, dispatched to
  // the wmXxx:wParam:lParam: selectors it names.
  var accepted = num('UiSession routeMessagesFrom: View');
  must(accepted > 50, 'the routed set came from buildMessageMap ($accepted)');
  expect('WM_SIZE names Dolphin\'s own selector',
      '(UiSession selectorForMessage: 5) printString',
      "'#wmSize:wParam:lParam:'");
  // A real WM_SIZE into a real Dolphin View. It must not raise — the door
  // counts a contained raise, so a handler that blew up would be invisible
  // without this.
  var before = stMvpStats()[2];
  stMvpSendMsg(h, WM_SIZE, 0, 0x00C80190);
  must(stMvpStats()[2] == before,
       'a real WM_SIZE reached the view without the door containing a raise');

  // ── ShellView too: two levels of Dolphin inheritance ─────────────────────
  stRun('SV := ShellView new. SV create.');
  var sh = num('SV handle');
  must(sh != 0 && sh != h, 'ShellView>>create produced its own window ($sh)');
  expect('  ...and it registered too', 'UiSession windowCount', '2');
  expect('  ...as a ShellView', '(UiSession viewFor: SV handle) class name',
      "'ShellView'");

  // ── destroy ──────────────────────────────────────────────────────────────
  // `View>>destroy` answers `basicDestroy`, which answers DestroyWindow's
  // BOOL — so 1 IS the success report, not a Smalltalk receiver. Asserted
  // rather than ignored: a raise inside destroy would otherwise look exactly
  // like a window that refused to close.
  expect('View>>destroy succeeded', 'DV destroy printString', "'1'");
  expect('ShellView>>destroy succeeded', 'SV destroy printString', "'1'");
  stRun('UiSession pump.');
  must(stMvpIsWindow(h) == false, 'destroy took the View\'s window with it');
  must(stMvpIsWindow(sh) == false, '  ...and the ShellView\'s');

  stRun('UiSession clearMessageMap. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('\nDOLPHINVIEW: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
