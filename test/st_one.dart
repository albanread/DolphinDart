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
  for (var e in ['Array withAll: #(1 2)',
                 '(Array new: 3 withAll: 7) printString',
                 '(Array with: 1 with: 2) printString',
                 '(Array writeStream: 4) class name',
                 '(Array respondsTo: #new:withAll:) printString'])
    print('  ' + e.padRight(40) + ' -> ' + ev(e));
  exit(0);
}
