import 'dart:cocoa';
import 'dart:io';
List<String> mstIn(String d)=> new Directory(d).listSync().map((e)=>e.path).where((p)=>p.endsWith('.mst')).toList()..sort();
String cut(s){ s=s.toString().replaceAll("\n"," | "); return s.length>160? s.substring(0,160): s; }
main(List<String> a) {
  int bad=0;
  for (var d in a[0].split(';')) for (var p in mstIn(d)) {
    var r=stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('LOAD FAIL ${p.split(RegExp(r"[\/]")).last}: ${cut(r)}'); bad++; }
  }
  if (bad>0) { print('$bad load failures'); }
  for (var c in [
    // Dolphin's own selector + Dolphin's own struct name + typed accessors.
    "Transcript showCr: 'client rect = ', ([ | r | r := RECTL new. UserLibrary getClientRect: (UserLibrary getDesktopWindow) lpRect: r. r left printString, ' ', r top printString, ' ', r right printString, ' ', r bottom printString ] on: Error do: [:e | 'ERR ', e messageText ]).",
    // Round-trip a field through the setter.
    "Transcript showCr: 'setter = ', ([ | r | r := RECTL new. r right: 1234. r right printString ] on: Error do: [:e | 'ERR ', e messageText ]).",
    // Sizes come from metadata, not arithmetic here.
    "Transcript showCr: 'sizes = RECTL ', RECTL sizeInBytes printString, ' POINTL ', POINTL sizeInBytes printString, ' MSG ', MSG sizeInBytes printString.",
    // A nested struct is a VIEW: writing through it reaches the parent.
    "Transcript showCr: 'nested view = ', ([ | ps rc | ps := PAINTSTRUCT new. rc := ps rcPaint. rc right: 77. (ps rcPaint) right printString ] on: Error do: [:e | 'ERR ', e messageText ]).",
  ]) { var x=stRun(c); if (x.toString().startsWith('ERR')) print('  ERR ${cut(x)}'); }
}
