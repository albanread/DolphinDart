// Scratch probe: the resource/icon chain, end to end.
//   Icon fromId: 'ShellView.ico'  ->  defaultResourceLibrary  ->  LoadImage
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

int _seq = 0;
String evb(String body) {
  var cls = 'SQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ ' + body + ' ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', (e messageText ifNil: [ '<none>' ]) ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + r.toString();
  try { return stClassSend0(stClassNamed(cls), 'v').toString(); }
  catch (e) { return 'THREW: ' + e.toString().replaceAll('\n', ' | '); }
}
void p(String l, String b) => print(('  ' + l).padRight(36) + '-> ' + evb(b));

main(List<String> a) {
  for (var g in a) { for (var d in g.split(';')) {
    d = d.trim(); if (d.isEmpty) continue;
    for (var f in (d.endsWith('.mst') ? [d] : mstIn(d))) {
      var r = stRun(new File(f).readAsStringSync());
      if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r.toString());
    } } }
  stRun('DolphinBoot initializeViewClasses.');
  stRun('UiSession startUp.');

  // The classes themselves.
  p('ResourceLibrary', 'ResourceLibrary name');
  p('ImageFromResourceInitializer', 'ImageFromResourceInitializer name');
  p('Icon', 'Icon name');

  // The raw Win32 path first: if THIS fails the DLL or prims are wrong,
  // not the image-side plumbing.
  p('loadLibraryEx our DLL',
    "(Kernel32 loadLibraryEx: (Utf16Buffer fromString: "
    "'C:\\projects\\DolphinDart\\resources\\DolphinDR8.dll') "
    "hFile: 0 dwFlags: 0) printString");
  p('loadImage from it',
    "| h n | h := Kernel32 loadLibraryEx: (Utf16Buffer fromString: "
    "'C:\\projects\\DolphinDart\\resources\\DolphinDR8.dll') hFile: 0 dwFlags: 0. "
    "n := Utf16Buffer fromString: 'ShellView.ico'. "
    "(User32 loadImage: h lpszName: n uType: 1 cxDesired: 0 cyDesired: 0 "
    "fuLoad: 16r8040) printString");

  // Then Dolphin's own plumbing.
  p('SessionManager current', 'SessionManager classVarCurrent class name');
  p('defaultResLibPath', 'SessionManager classVarCurrent defaultResLibPath');
  p('defaultResourceLibrary', 'SessionManager classVarCurrent defaultResourceLibrary printString');
  p('ResourceLibrary open:', "(ResourceLibrary open: 'DolphinDR8') printString");
  p('Icon fromId:', "(Icon fromId: 'ShellView.ico') printString");
  p('  its handle', "(Icon fromId: 'ShellView.ico') handle printString");
  p('ShellView defaultIcon', 'ShellView defaultIcon printString');
  p('ShellView icon', 'ShellView icon printString');
  exit(0);
}
