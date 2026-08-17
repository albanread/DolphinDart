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
  for (var g in a) {
    for (var d in g.split(';')) {
      d = d.trim(); if (d.isEmpty) continue;
      var files = d.endsWith('.mst') ? [d] : mstIn(d);
      for (var f in files) {
        var r = stRun(new File(f).readAsStringSync());
        if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r.toString());
      }
    }
  }
  stRun(new File('st/test/ffi/dolphin_modal.mst').readAsStringSync());
  print('init   -> ' + ev('DolphinBoot initializeViewClasses'));
  stRun('UiSession startUp.');
  print('routed -> ' + ev('ModalOwnerShell routeDolphinMessages'));
  stRun('MO := ModalOwnerShell new.'); stRun('MO create.'); stRun('MO build.');
  stRun('MO show.');
  print('newPrompt -> ' + ev('MO newPrompt printString'));
  // Isolate each step of what showModal does, in order.
  for (var e in ['(DisplayMonitor respondsTo: #reset) printString',
                 'DisplayMonitor isNil printString',
                 '(DisplayMonitor respondsTo: #fromHandle:) printString',
                 'DisplayMonitor new class name',
                 '(DisplayMonitor new handle: 65537; yourself) class name',
                 'DisplayMonitor classVarInstances printString',
                 '(DisplayMonitor fromHandle: 65537) printString',
                 '(DisplayMonitor nearestPoint: 100@100) printString',
                 'MO inner isModal printString',
                 'MO inner owner class name',
                 '(MO inner owner isEnabled) printString'])
    print('  ' + e.padRight(46) + ' -> ' + ev(e));
  exit(0);
}
