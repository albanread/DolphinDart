// Photograph the modal WHILE IT IS UP.
//
//   dartui.exe st_modalshot.dart "<world;layers>" st/mvp st/mvp_compat \
//              st/test/ffi/dolphin_modal.mst <shotdir>
//
// `showModal` blocks, so the capture cannot be taken after it — by then the
// dialog is destroyed and the owner re-enabled. It is taken from INSIDE the
// nested modal loop, by the same mechanism the gate uses to dismiss the
// dialog: an action posted BEFORE entering, which only the nested pump can
// drain. The shot therefore proves the same thing the gate asserts, in
// pixels: the caller is blocked, the dialog is real, and the owner is behind
// it disabled.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

int _seq = 0;
String ev(String expr) {
  var cls = 'MsQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', (e messageText ifNil: [ '<none>' ]) ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + r.toString();
  try { return stClassSend0(stClassNamed(cls), 'v').toString(); }
  catch (e) { return 'THREW: ' + e.toString().replaceAll('\n', ' | '); }
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p'); exit(2); }
    }
  }
  for (var dir in [a[1], a[2]]) {
    for (var p in mstIn(dir)) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('LOAD FAIL $p: $r'); exit(2); }
    }
  }
  stRun(new File(a[3]).readAsStringSync());
  var shotDir = a.length > 4 ? a[4] : '.';
  String esc(String p) => p.replaceAll('\\', '\\\\');

  print('init   -> ' + ev('DolphinBoot initializeViewClasses printString'));
  stRun('UiSession startUp.');
  stRun('MO := ModalOwnerShell new. MO create. MO build. MO show.');
  print('owner  -> ' + ev('MO handle printString'));

  // Give the owner an icon too, so the shot shows the resource path working
  // on the same window that owns the dialog.
  print('icon   -> ' + ev(
      "MO largeIcon: (Icon fromId: 'DialogView.ico'); "
      "smallIcon: (Icon fromId: 'DialogView.ico'); updateIcons; yourself"));
  stRun('UiSession runFor: 400.');

  // CONTROL SHOT, from the MAIN loop, before any modal exists. If this one
  // paints and the in-modal shots are black, the difference is the capture
  // being taken during a NESTED pump — not the windows failing to paint.
  var ctrl = shotDir + Platform.pathSeparator + 'modal_control.bmp';
  print('control-> ' + ev("Win32 mvpCapture: MO handle path: '" + esc(ctrl) +
      "' clientOnly: false"));

  // Build the dialog, then post: paint, photograph, THEN dismiss. All three
  // run inside the nested loop while `promptModally` is still blocked.
  stRun('DLG := MO newPrompt.');
  var owner = shotDir + Platform.pathSeparator + 'modal_owner.bmp';
  var dlgShot = shotDir + Platform.pathSeparator + 'modal_dialog.bmp';
  stRun("UiSession postAction: [ "
      "UiSession runFor: 600. "
      "Win32 mvpCapture: MO handle path: '" + esc(owner) + "' clientOnly: false. "
      "Win32 mvpCapture: DLG handle path: '" + esc(dlgShot) + "' clientOnly: false. "
      "DLG edit text: 'photographed from inside the modal loop'. "
      "UiSession runFor: 400. "
      "Win32 mvpCapture: DLG handle path: '" + esc(dlgShot) + "' clientOnly: false. "
      "DLG ok ].");
  print('modal  -> ' + ev('MO promptModally printString'));
  print('trace  -> ' + ev('MO traceString'));
  print('subject-> ' + ev('MO subjectValue'));
  print('shots  -> ' + owner + ' , ' + dlgShot);
  stRun('MO destroy. UiSession pump. UiSession shutDown.');
  exit(0);
}
