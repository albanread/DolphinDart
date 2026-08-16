import 'dart:cocoa';
import 'dart:io';
List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();
int _seq = 0;
String ev(String expr) {
  var cls = 'QQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', e messageText ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + r.toString();
  try { return stClassSend0(stClassNamed(cls), 'v').toString(); }
  catch (e) { return 'THREW: ' + e.toString(); }
}
main(List<String> a) {
  for (var g in a) { for (var d in g.split(';')) {
    d = d.trim(); if (d.isEmpty) continue;
    var files = d.endsWith('.mst') ? [d] : mstIn(d);
    for (var f in files) {
      var r = stRun(new File(f).readAsStringSync());
      if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r.toString());
    } } }
  stRun(new File('st/test/ffi/dolphin_controls.mst').readAsStringSync());
  print('  initViewClasses -> ' + ev('DolphinBoot initializeViewClasses'));
  print('  NextId after init  -> ' + ev('View classVarNextId'));
  stRun('UiSession startUp.');
  stRun('CShell := ControlsShell new.'); stRun('CShell create.');
  stRun('Object subclass: Raw [ Raw class >> go [ ^CShell build ] ]');
  try { stClassSend0(stClassNamed('Raw'), 'go'); print('BUILD OK'); }
  catch (e, st) { print('RAW THREW: ' + e.toString()); print(st.toString()); }
  exit(0);
}
