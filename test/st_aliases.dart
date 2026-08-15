// The DD9 library-alias gate.
//
//   dart.exe st_aliases.dart "st/world;st/dolphin_compat;st/prims/rt;st/prims/structs;st/prims;st/prims/aliases"
//
// Dolphin's MVP code writes `User32 beginPaint:` (434 sites corpus-wide), not
// `UserLibrary default beginPaint:` (10 in all of MVP). This proves the bare
// global reaches the generated library, that `default` bridges the other
// spelling, and that a struct out-param still round-trips through the alias.
//
// NOTE THE LAYER ORDER: the alias layer must load LAST. Placed in
// `st/prims/rt` it runs BEFORE the generated libraries and every global binds
// nil — measured, not hypothetical.
import 'dart:cocoa';
import 'dart:io';
List<String> mstIn(String d)=> new Directory(d).listSync().map((e)=>e.path).where((p)=>p.endsWith('.mst')).toList()..sort();
String cut(s){s=s.toString().replaceAll("\n"," | ");return s.length>130?s.substring(0,130):s;}
main(List<String> a) {
  for (var d in a[0].split(';')) for (var p in mstIn(d)) {
    var r=stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('LOAD FAIL ${p.split(RegExp(r"[\/]")).last}: ${cut(r)}'); exit(2); }
  }
  for (var c in [
    "Transcript showCr: 'User32 alias    = ', (User32 getSystemMetrics: 0) printString.",
    "Transcript showCr: 'Gdi32 alias     = ', (Gdi32 == GDILibrary) printString.",
    "Transcript showCr: 'default bridge  = ', (UserLibrary default getSystemMetrics: 1) printString.",
    "Transcript showCr: 'alias + default = ', (User32 default getSystemMetrics: 0) printString.",
    "| r | r := RECTL new. User32 getClientRect: (User32 getDesktopWindow) lpRect: r. Transcript showCr: 'via alias RECT  = ', r right printString, 'x', r bottom printString. r free.",
  ]) { var x=stRun(c); if (x.toString().startsWith('ERR')) print('  ERR ${cut(x)}'); }
}
