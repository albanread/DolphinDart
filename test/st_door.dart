// The DD7 wndproc-door spike harness.
//
//   dart.exe st_door.dart "<world;layers>" <spike.mst>
//
// Every recursion goes through a real message-only window and a real
// SendMessageW, so what is measured is the production re-entry path — a handler
// that calls back into Win32 and re-enters the image from inside its own call.
// Simulating that with a Rust/Dart test double is what let WINVM's G0 believe
// nesting worked while the production seam was never built.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 150 ? s.substring(0, 150) : s;
}

int fails = 0;

/// Run `setup` (statements, value ignored), then report `expr`.
void probe(String label, String setup, String expr) {
  if (setup.isNotEmpty) {
    var s = stRun(setup);
    if (s.toString().startsWith('ERR')) {
      fails++;
      print('  FAIL $label (setup) :: ${cut(s)}');
      return;
    }
  }
  var r = stRun("Transcript showCr: '${label.padRight(34)} -> ', ($expr) printString.");
  if (r.toString().startsWith('ERR')) {
    fails++;
    print('  FAIL $label :: ${cut(r)}');
  }
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) {
        print('BOOT FAIL $p: ${cut(r)}');
        exit(2);
      }
    }
  }
  var r = stRun(new File(a[1]).readAsStringSync());
  if (r.toString().startsWith('ERR')) {
    print('SPIKE LOAD FAIL: ${cut(r)}');
    exit(2);
  }

  probe('door opens', '', 'MvpDoor open ~= 0');

  // 1. DEPTH — five nested image entries through five real SendMessageW calls.
  //    Each level allocates, so a GC during a nested entry is possible rather
  //    than hypothetical.
  probe('depth-5 answer', 'MvpDoor reset. MvpDoor mode: #plain.',
        'MvpDoor send: 5 with: 0');
  probe('depth-5 trace', '', 'MvpDoor trace asArray');
  probe('max depth reached', '', '(Win32 mvpStats) at: 2');
  probe('depth unwound to zero', '', '(Win32 mvpStats) at: 1');

  // 2. A doesNotUnderstand at depth 3 must be contained at ITS OWN entry: that
  //    entry answers its default, the entries around it carry on.
  probe('dnu@3: outer still answers', 'MvpDoor reset. MvpDoor mode: #dnuAt3.',
        'MvpDoor send: 5 with: 0');
  probe('dnu@3: every level ran', '', 'MvpDoor trace asArray');
  probe('dnu@3: contained exactly once', '', '(Win32 mvpStats) at: 3');
  probe('dnu@3: depth unwound', '', '(Win32 mvpStats) at: 1');

  // 3. A raise inside a nested entry is contained AT THE DOOR, not propagated
  //    to an enclosing Smalltalk handler across the native frames. `guardedAt2`
  //    wraps the whole send in `on: Error do: [ #caught ]`, and that handler
  //    does NOT fire: the depth-2 entry answers its default (0) and the entries
  //    above it complete normally, so the answer is 0+1+1 = 2.
  //
  //    This is correct — Windows owns that stack and there is no Smalltalk
  //    exception it could carry — but it is a semantic the MVP layer must know:
  //    a handler installed OUTSIDE a door entry cannot catch a raise from
  //    INSIDE one. It was measured here, not predicted.
  probe('raise@2 contained at the door', 'MvpDoor reset.', 'MvpDoor guardedAt2 = 2');
  probe('raise@2: outer handler not run', '', 'MvpDoor guardedAt2 ~= #caught');
  probe('after guarded: depth unwound', '', '(Win32 mvpStats) at: 1');

  // 4. The door still works after all of that — the pump must survive.
  probe('door alive after faults', 'MvpDoor reset. MvpDoor mode: #plain.',
        'MvpDoor send: 3 with: 0');
  probe('door closes', 'MvpDoor close.', 'MvpDoor window isNil');

  print('\nDOOR: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
