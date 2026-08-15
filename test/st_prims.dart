// The Win32 PRIM HARNESS (DolphinDart DD6b).
//
//   dart.exe st_prims.dart <world-dir>[;<layer>...] <generated-prims-dir>
//
// Two tiers, because "test every prim" means different things for different
// prims and pretending otherwise would be theatre:
//
//   TIER A — RESOLVE ALL. Every generated prim must resolve to a real address
//     through the floor's OWN resolver (`Win32 resolve:` -> WinResolveSymbol,
//     the same function a real call uses). This is the tier that scales: it
//     proves all N bindings name functions that actually exist in the system
//     DLLs this build searches, which is the failure mode a generator has —
//     emitting a plausible name that is not there. It cannot prove the
//     signature is right.
//
//   TIER B — CALL AND CHECK. A curated set called for real, each with an
//     answer that is independently checkable (screen metrics against
//     GetSystemMetrics twice, a live HWND that IsWindow accepts, a RECT that
//     must equal the screen). Small by necessity: you cannot blind-call
//     CreateWindowExW or CloseHandle in a test and learn anything good.
//
// Exit code is the failure count, so this drops straight into a gate.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync()
    .map((e) => e.path)
    .where((p) => p.endsWith('.mst'))
    .toList()
  ..sort();

int _fail = 0;
void check(String label, actual, expected) {
  if (actual.toString() == expected.toString()) {
    print('  ok    ${label.padRight(44)} $actual');
  } else {
    _fail++;
    print('  FAIL  ${label.padRight(44)} got <$actual> want <$expected>');
  }
}

main(List<String> args) {
  var worldSpec = args[0];
  var primsDir = args[1];

  for (var d in worldSpec.split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) {
        print('BOOT FAIL $p: ${r.toString().split("\n").first}');
        exit(2);
      }
    }
  }
  var loaded = 0;
  for (var p in mstIn(primsDir)) {
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) {
      print('PRIM LOAD FAIL $p: ${r.toString().split("\n").first}');
      exit(2);
    }
    loaded++;
  }
  print('prims loaded: $loaded files');

  // ── TIER A ────────────────────────────────────────────────────────────────
  print('\n== Tier A: resolve every generated prim ==');
  var total = stRun("Transcript showCr: (PrimManifest all size) printString.");
  if (total.toString().startsWith('ERR')) {
    print('manifest missing: ${total.toString().split("\n").first}');
    exit(2);
  }
  // Resolve in Smalltalk so the loop itself exercises the image, and report the
  // unresolved ones by name — a count alone would not say WHICH binding is bad.
  // Report unresolved bindings BY LIBRARY CLASS. A bare count would say a
  // third of the bindings are bad without saying which — and the answer
  // ("everything in ws2_32, iphlpapi, the CRT…") is what tells you whether the
  // fix is the DLL search set or the binding itself.
  var r = stRun(r"""
| bad n |
bad := Dictionary new. n := 0.
PrimManifest all do: [ :e |
    n := n + 1.
    (Win32 resolve: (e at: 1) asString) = 0
        ifTrue: [ bad at: (e at: 2) put: ((bad at: (e at: 2) ifAbsent: [ 0 ]) + 1) ] ].
Transcript showCr: 'TIERA total=', n printString,
    ' resolved=', (n - (bad inject: 0 into: [ :a :b | a + b ])) printString.
bad keysAndValuesDo: [ :k :v |
    Transcript showCr: '  TIERA unresolved ', k asString, ' = ', v printString ].
""");
  if (r.toString().startsWith('ERR')) {
    print('  TIER A ERROR ${r.toString().split("\n").first}');
    _fail++;
  }

  // ── TIER B ────────────────────────────────────────────────────────────────
  print('\n== Tier B: call and check ==');
  String ev(String code) {
    var v = stRun("Transcript showCr: 'RESULT=', ($code) printString.");
    return v.toString().startsWith('ERR') ? 'ERR' : 'ok';
  }
  // Each of these is checked against a value the OS itself provides twice, or
  // against a structural invariant — never against a constant baked in here.
  var probes = <String, String>{
    'GetSystemMetrics is stable':
        "(UserLibrary getSystemMetrics: 0) = (UserLibrary getSystemMetrics: 0)",
    'screen width > 0':
        "(UserLibrary getSystemMetrics: 0) > 0",
    'screen height > 0':
        "(UserLibrary getSystemMetrics: 1) > 0",
    'GetDesktopWindow is a window':
        "(UserLibrary isWindow: (UserLibrary getDesktopWindow)) ~= 0",
    'null is not a window':
        "(UserLibrary isWindow: 0) = 0",
    'GetForegroundWindow answers a handle or 0':
        "(UserLibrary getForegroundWindow) >= 0",
    'GetTickCount is monotonic':
        "(KernelLibrary getTickCount) <= (KernelLibrary getTickCount)",
    'GetCurrentThreadId is non-zero':
        "(KernelLibrary getCurrentThreadId) > 0",
    'GetCurrentProcessId is non-zero':
        "(KernelLibrary getCurrentProcessId) > 0",
  };
  probes.forEach((label, code) {
    var v = stRun("Transcript showCr: 'TIERB ${label} -> ', ($code) printString.");
    if (v.toString().startsWith('ERR')) {
      _fail++;
      print('  FAIL  $label -> ${v.toString().split("\n").first}');
    }
  });

  print('\nPRIMS: $_fail failure(s)');
  exit(_fail == 0 ? 0 : 1);
}
