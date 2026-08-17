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
  stRun(new File('st/test/ffi/dolphin_class_browser.mst').readAsStringSync());
  stRun('DolphinBoot initializeViewClasses.'); stRun('UiSession startUp.');
  print('  routed -> ' + ev('ClassBrowserShell routeDolphinMessages'));
  stRun('CB := ClassBrowserShell new.'); stRun('CB create.');
  print('  build      -> ' + ev('CB build printString'));
  stRun('CB show.');
  print('  populate   -> ' + ev('CB populate printString'));
  for (var e in ['CB classCount', 'CB rootCount', 'CB treeItemCount',
                 'CB expandClass: Object', 'CB treeItemCount',
                 '(CB treeModel childrenOf: Object) size',
                 '(CB select: Magnitude) name', 'CB listItemCount',
                 'CB shownClassName'])
    print('  ' + e.padRight(40) + ' -> ' + ev(e));
  exit(0);
}
