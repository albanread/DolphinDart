import 'dart:cocoa';
import 'dart:io';
List<String> mstIn(String d)=> new Directory(d).listSync().map((e)=>e.path).where((p)=>p.endsWith('.mst')).toList()..sort();
String cut(s){s=s.toString().replaceAll("\n"," | ");return s.length>160?s.substring(0,160):s;}
main(List<String> a) {
  for (var d in a[0].split(';')) for (var p in mstIn(d)) {
    var r=stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('BASE FAIL ${p.split(new RegExp(r"[\/]")).last}: ${cut(r)}'); exit(2); }
  }
  int ok=0, bad=0;
  for (var p in mstIn(a[1])) {
    var r=stRun(new File(p).readAsStringSync());
    var n=p.split(new RegExp(r"[\/]")).last;
    if (r.toString().startsWith('ERR')) { bad++; print('  LOAD FAIL ${n.padRight(20)} ${cut(r)}'); }
    else { ok++; print('  loaded ${n}'); }
  }
  print('\nVIEW WAVE: $ok loaded, $bad failed');
}
