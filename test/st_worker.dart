// The DD10 WORKER gate — the doctrine, proved.
//
//   dart.exe st_worker.dart "<world;layers>" st/mvp
//
// `docs/WORKERS.md` states it: work happens in an isolate, the UI is touched
// only on the UI thread, and only through the posted-action queue. Three
// things have to be true for that to be more than a slogan, and each gets its
// own assertion:
//
//   1. The submission RETURNS IMMEDIATELY — the UI thread never waits.
//   2. The pump stays LIVE while the isolate is busy. Measured by a real
//      WM_PAINT counter that has to keep advancing, not by asserting the call
//      was async.
//   3. The continuation runs on the UI THREAD via the posted-action queue,
//      NOT inline from the reply handler. Asserted by observing that the
//      continuation has not run at the moment the reply is known to have
//      arrived, and has run after the next pump.
//
// (3) is the one that carries the doctrine. Calling the continuation directly
// from the reply handler would satisfy (1) and (2) and still be wrong.
import 'dart:async';
import 'dart:io';
import 'dart:cocoa';
import 'worker_host.dart' as host;

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'WkQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', e messageText ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + cut(r);
  try {
    return stClassSend0(stClassNamed(cls), 'v').toString();
  } catch (e) {
    return 'THREW: ' + cut(e);
  }
}

int num(String expr) => int.parse(ev(expr), onError: (_) => -1);

void expect(String label, String expr, String want) {
  var got = ev(expr);
  if (got != want) {
    fails++;
    print('  FAIL ' + label.padRight(54) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

void must(bool ok, String label) {
  if (!ok) { fails++; print('  FAIL ' + label); } else { print('  ok   ' + label); }
}

main(List<String> a) async {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  for (var p in mstIn(a[1])) {
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('WAVE FAIL $p: ${cut(r)}'); exit(2); }
  }

  stRun('UiSession startUp. Worker reset.');
  // A visible window whose paint count is the liveness evidence.
  stRun('''
UiWindow subclass: WorkerProbe [
    | painted2 |
    initWindow [ super initWindow. painted2 := 0 ]
    painted2 [ ^painted2 ]
    onPaint: hdc [ painted2 := painted2 + 1. ^0 ]
]
''');
  stRun('WkWin := WorkerProbe open: 340 by: 200. WkWin show. UiSession pump.');
  stRun('WkModel := ValueHolder with: 0. WkRan := 0.');

  // ── (1) submission returns immediately ───────────────────────────────────
  var t0 = new DateTime.now();
  stRun("WkId := Worker do: #slowSum with: 30000000 "
        "then: [ :r | WkRan := WkRan + 1. WkModel value: r ].");
  var submitMs = new DateTime.now().difference(t0).inMilliseconds;
  must(submitMs < 100,
       'submitting returned immediately (${submitMs}ms — the UI thread never waited)');
  expect('the work is queued', 'Worker pendingCount', '1');
  expect('and its continuation is held in the image', 'Worker inFlight', '1');
  expect('nothing has run yet', 'WkRan', '0');

  // ── (2) the pump stays live while the isolate burns ──────────────────────
  // The paint counter is driven by real WM_PAINT messages: invalidate, pump,
  // and see the count move. If the UI thread were blocked on the worker this
  // would sit still.
  host.dispatchPending();
  expect('the host collected the submission', 'Worker pendingCount', '0');

  var paintsBefore = num('WkWin painted2');
  var loops = 0;
  while (host.outstanding > 0 && loops < 3000) {
    stRun('WkWin invalidate. UiSession pump.');
    await new Future.delayed(const Duration(milliseconds: 1));
    loops++;
  }
  var paintsDuring = num('WkWin painted2') - paintsBefore;
  must(host.outstanding == 0, 'the worker replied (after $loops pump slices)');
  must(paintsDuring > 5,
       'the pump stayed LIVE while the isolate worked '
       '($paintsDuring real WM_PAINTs during the run)');

  // ── (3) THE DOCTRINE: the continuation is POSTED, not called ─────────────
  // The reply has arrived — Worker's completed count says so — and the
  // continuation has NOT run. That gap is the whole point: it is waiting in
  // the posted-action queue for a pump.
  expect('the reply was received', 'Worker completed', '1');
  expect('the continuation is QUEUED, not run', 'WkRan', '0');
  must(num('UiSession pendingActions') == 1,
       'exactly one action is waiting in the queue');

  stRun('UiSession pump.');
  expect('the next pump ran it', 'WkRan', '1');
  expect('  ...on the UI thread, updating the model', 'WkModel value ~= 0', 'true');
  expect('the queue is empty again', 'UiSession pendingActions', '0');
  expect('and the image is no longer holding the block', 'Worker inFlight', '0');

  // ── a task that raises comes back as data, and still posts ───────────────
  stRun("WkErr := nil. Worker do: #boom with: 1 then: [ :e | WkErr := e ].");
  host.dispatchPending();
  loops = 0;
  while (host.outstanding > 0 && loops < 3000) {
    stRun('UiSession pump.');
    await new Future.delayed(const Duration(milliseconds: 1));
    loops++;
  }
  expect('the failure was recorded', 'Worker failed', '1');
  stRun('UiSession pump.');
  expect('and its continuation ran too', 'WkErr isNil', 'false');
  expect('  ...carrying the message as data', 'WkErr messageText isEmpty', 'false');

  stRun('WkWin close. UiSession pump. UiSession shutDown.');
  print('\nWORKER: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
