// Scratch probe: the icon-title-font path, newly reachable now that
// LOGFONTW is its true 92 bytes and SystemParametersInfoForDpi succeeds.
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
void p(String l, String b) => print(('  ' + l).padRight(34) + '-> ' + evb(b));

main(List<String> a) {
  for (var g in a) { for (var d in g.split(';')) {
    d = d.trim(); if (d.isEmpty) continue;
    for (var f in (d.endsWith('.mst') ? [d] : mstIn(d))) {
      var r = stRun(new File(f).readAsStringSync());
      if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r.toString());
    } } }
  stRun('DolphinBoot initializeViewClasses.');
  stRun('UiSession startUp.');

  p('LOGFONTW sizeInBytes', 'LOGFONTW sizeInBytes printString');
  p('SystemMetrics current', 'SystemMetrics current class name');
  p('getSysParamForDpi 31', "| m | m := SystemMetrics current. "
      "(m getSysParamForDpi: 31 type: LOGFONTW ifError: [ 'ERR' ]) printString");
  p('  its class', "| m r | m := SystemMetrics current. "
      "r := m getSysParamForDpi: 31 type: LOGFONTW ifError: [ nil ]. r class name");
  p('  beImmutableObject', "| m r | m := SystemMetrics current. "
      "r := m getSysParamForDpi: 31 type: LOGFONTW ifError: [ nil ]. "
      "r beImmutableObject class name");
  p('Font fromLogFont:dpi:', "| m r | m := SystemMetrics current. "
      "r := m getSysParamForDpi: 31 type: LOGFONTW ifError: [ nil ]. "
      "(Font fromLogFont: r dpi: 96) class name");
  p('getIconTitleFont', 'SystemMetrics current getIconTitleFont class name');
  p('Font system', 'Font system class name');
  exit(0);
}
