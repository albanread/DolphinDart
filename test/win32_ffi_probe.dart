import 'dart:cocoa';
import 'dart:io';
main(List<String> a) {
  for (var p in (new Directory(a[0]).listSync().map((e)=>e.path).where((p)=>p.endsWith('.mst')).toList()..sort())) { stRun(new File(p).readAsStringSync()); }
  var r = stRun(new File(a[1]).readAsStringSync());
  if (r.toString().startsWith('ERR')) { print('LOAD FAIL $r'); exit(1); }
  for (var c in [
    "Transcript showCr: 'SM_CXSCREEN     = ', (Win32Probe getSystemMetrics: 0) printString.",
    "Transcript showCr: 'SM_CYSCREEN     = ', (Win32Probe getSystemMetrics: 1) printString.",
    "Transcript showCr: 'GetCurrentThreadId= ', (Win32Probe getCurrentThreadId) printString.",
    "Transcript showCr: 'GetTickCount    = ', (Win32Probe getTickCount) printString.",
    "Transcript showCr: 'DesktopWindow   = ', (Win32Probe getDesktopWindow) printString.",
    "Transcript showCr: 'IsWindow(desktop)= ', (Win32Probe isWindow: Win32Probe getDesktopWindow) printString.",
    "Transcript showCr: 'IsWindow(0)     = ', (Win32Probe isWindow: 0) printString.",
    "Transcript showCr: 'MessageBeep(-1) = ', (Win32Probe messageBeep: 4294967295) printString.",
  ]) { var x=stRun(c); if (x.toString().startsWith('ERR')) print('  ERR $c -> ${x.toString().split("\n")[0]}'); }
  // last-error: force a failure, then read it
  var e = stRun("Win32Probe closeHandle: 1. Transcript showCr: 'lastError after bad CloseHandle = ', (Win32 lastError) printString.");
  if (e.toString().startsWith('ERR')) print('  ERR lasterror -> ${e.toString().split("\n")[0]}');
}
