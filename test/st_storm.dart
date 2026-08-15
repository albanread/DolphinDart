// The DD9 STORM PROBE.
//
//   dart.exe st_storm.dart "st/world;st/dolphin_compat;st/prims/rt;st/prims/structs;st/prims;st/prims/aliases"
//
// Resize relayout is DD9's gate, and resize is where the high-rate messages
// live: a drag produces WM_MOUSEMOVE / WM_NCHITTEST / WM_SETCURSOR / WM_SIZE
// in bursts. The question this answers, before any View code depends on the
// answer, is what it costs to route one of those into the image.
//
// The prior art measured a door entry at ~154x DefWindowProcW on WINARM. That
// is a number worth re-measuring rather than inheriting: this door, this
// substrate, this arch. The comparison is made with ONE variable — the same
// window, the same message, the same process, routing on vs off.
//
// This probe REPORTS. It fails only on things that are unambiguously broken
// (a window that will not open, a census that does not count, a routed burst
// that the image never sees) — the timing is a measurement, and a measurement
// with a pass/fail line drawn through it invites tuning the line.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_MOUSEMOVE = 0x0200;
const int WM_NCHITTEST = 0x0084;
const int WM_SETCURSOR = 0x0020;
const int WM_SIZE = 0x0005;

const List<String> SLOTS = const [
  'WM_MOUSEMOVE', 'WM_NCHITTEST', 'WM_SETCURSOR',
  'WM_SIZE', 'WM_MOVING', 'WM_ERASEBKGND', '(other)'
];

int fails = 0;
void must(bool ok, String label) {
  if (!ok) { fails++; print('  FAIL $label'); } else { print('  ok   $label'); }
}

String per(int nanos, int n) {
  var ns = nanos / n;
  return ns.toStringAsFixed(1).padLeft(9) + ' ns/msg';
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p: $r'); exit(2); }
    }
  }

  // The routed path is the REAL one: the funnel hands a storm kind to
  // `UiSession wndProc:arg:`, which counts it and answers 0 — the least work
  // any real handler could do. So this times the DOOR, not a handler, while
  // still going through the dispatch every view will use. Its `messageCount`
  // is how we know the entries really happened.
  stRun("UiSession startUp.");

  var h = stMvpCreateTopWindow(360, 200);
  must(h != 0, 'a real top-level window opened');
  if (h == 0) { print('\nSTORM: cannot probe without a window'); exit(1); }
  stMvpShow(h);
  stMvpPump(40);

  // ── what the census sees ─────────────────────────────────────────────────
  //
  // A window sitting still receives almost nothing — the storms come from
  // interaction, which a headless gate cannot produce, so the census is
  // exercised with a synthetic burst of the same messages a drag generates.
  // What it proves is that the door SEES and CLASSIFIES them without routing
  // any into the image; the rates below are what a real drag would cost.
  stMvpResetStormCounts();
  stMvpSetStormRouting(false);
  stMvpStormBurst(h, WM_MOUSEMOVE, 300);
  stMvpStormBurst(h, WM_NCHITTEST, 200);
  stMvpStormBurst(h, WM_SIZE, 100);
  stMvpPump(40);
  var c = stMvpStormCounts();
  print('\nthe census, after a synthetic 600-message drag (routing OFF):');
  for (var i = 0; i < SLOTS.length; i++) {
    if (c[i] > 0) print('  ${SLOTS[i].padRight(14)} ${c[i]}');
  }
  print('  ${"TOTAL".padRight(14)} ${c[7]}');
  must(c[0] >= 300, 'WM_MOUSEMOVE counted in its own slot');
  must(c[1] >= 200, 'WM_NCHITTEST counted in its own slot');
  must(c[3] >= 100, 'WM_SIZE counted in its own slot');

  // ── the measurement: same message, routing off then on ───────────────────
  const int N = 20000;
  var report = <String, List<num>>{};
  for (var probe in [[WM_NCHITTEST, 'WM_NCHITTEST'],
                     [WM_MOUSEMOVE, 'WM_MOUSEMOVE'],
                     [WM_SETCURSOR, 'WM_SETCURSOR'],
                     [WM_SIZE, 'WM_SIZE']]) {
    var msg = probe[0], name = probe[1];
    stMvpSetStormRouting(false);
    stMvpStormBurst(h, msg, 2000);              // warm the path
    var off = stMvpStormBurst(h, msg, N);

    stMvpSetStormRouting(true);
    stMvpStormBurst(h, msg, 2000);
    var on = stMvpStormBurst(h, msg, N);
    stMvpSetStormRouting(false);
    report[name] = [off, on, off > 0 ? on / off : 0];
  }

  print('\ncost of a storm message, $N sends each:');
  print('  ${"message".padRight(14)} ${"DefWindowProc".padLeft(20)}'
        ' ${"routed to image".padLeft(20)}    ratio');
  for (var k in report.keys) {
    var r = report[k];
    print('  ${k.padRight(14)} ${per(r[0], N)} ${per(r[1], N)}'
          '   ${r[2].toStringAsFixed(1)}x');
  }

  // The routed burst must actually have entered the image — otherwise the
  // "routed" column is timing the same DefWindowProc path twice and the ratio
  // is meaningless. This is the assertion that keeps the measurement honest.
  var before = stClassSend0(stClassNamed('UiSession'), 'messageCount');
  stMvpSetStormRouting(true);
  stMvpStormBurst(h, WM_NCHITTEST, 500);
  stMvpSetStormRouting(false);
  var seen = stClassSend0(stClassNamed('UiSession'), 'messageCount') - before;
  print('\nimage entries from a routed 500-message burst: $seen');
  must(seen == 500, 'every routed message reached the image (otherwise the '
                    'ratio above compares DefWindowProc with itself)');

  // And with routing off nothing may reach it, or the baseline column is not
  // a baseline.
  before = stClassSend0(stClassNamed('UiSession'), 'messageCount');
  stMvpStormBurst(h, WM_NCHITTEST, 500);
  must(stClassSend0(stClassNamed('UiSession'), 'messageCount') == before,
       'with routing off, no storm message enters the image');

  stMvpDestroyWindow(h);
  stMvpPump(20);
  print('\nSTORM: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
