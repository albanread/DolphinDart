import 'dart:cocoa';
import 'dart:io';
main(List<String> a) {
  for (var p in (new Directory(a[0]).listSync().map((e)=>e.path).where((p)=>p.endsWith('.mst')).toList()..sort())) { stRun(new File(p).readAsStringSync()); }
  var r = stRun(new File(a[1]).readAsStringSync());
  if (r.toString().startsWith('ERR')) { print('LOAD FAIL ${r.toString().split("\n")[0]}'); exit(1); }
  var x = stRun(
    "| p hwnd ok fields | "
    "p := W32 localAlloc: 64 size: 16. "
    "Transcript showCr: 'RECT buffer = ', (p ~= 0) printString. "
    "hwnd := W32 getDesktopWindow. "
    "ok := W32 getClientRect: hwnd into: p. "
    "Transcript showCr: 'GetClientRect ok = ', ok printString. "
    "fields := W32 rectFieldsAt: p. "
    "Transcript showCr: 'RECT l,t,r,b = ', fields printString. "
    "W32 localFree: p.");
  if (x.toString().startsWith('ERR')) print('ERR ${x.toString().split("\n")[0]}');
}
