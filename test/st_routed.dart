// The DD9 ROUTED-MESSAGE gate.
//
//   dart.exe st_routed.dart "<world;layers>" st/test/ffi/routed_probe.mst
//
// The door reflects only the messages the image asks for. That set is what
// makes Dolphin's dispatch affordable: the storm probe measured a routed
// message at ~26 microseconds, so the only lever is the message COUNT, and
// `View class >> buildMessageMap` hands us the minimal count for free.
//
// Three things here that a paint-style count cannot tell apart: that the
// widened funnel carries (msg, wParam, lParam); that a handler's answer comes
// back out as the LRESULT; and that answering NIL declines the message,
// falling through to DefWindowProcW, which is not the same as answering 0.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_NCHITTEST = 0x0084;
const int WM_MOUSEMOVE = 0x0200;
const int WM_SETCURSOR = 0x0020;
const int WM_APP_ISH = 0x8123;     // above the bitmap: exercises the high list

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 150 ? s.substring(0, 150) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'RoutedQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e messageText ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + cut(r);
  try {
    return stClassSend0(stClassNamed(cls), 'v').toString();
  } catch (e) {
    return 'THREW: ' + cut(e);
  }
}

void expect(String label, String expr, String want) {
  var got = ev(expr);
  if (got != want) {
    fails++;
    print('  FAIL ' + label.padRight(52) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

void must(bool ok, String label) {
  if (!ok) { fails++; print('  FAIL ' + label); } else { print('  ok   ' + label); }
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('BOOT FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  var probe = stRun(new File(a[1]).readAsStringSync());
  if (probe.toString().startsWith('ERR')) {
    print('PROBE FAIL ${a[1]}: ${cut(probe)}'); exit(2);
  }

  stRun('UiSession startUp.');
  stRun('RoutedWin := RoutedProbe open: 300 by: 180.');
  expect('the probe window opened', 'RoutedWin hwnd ~= 0', 'true');
  var h = int.parse(ev('RoutedWin hwnd'));

  // ── nothing is routed until the image asks ───────────────────────────────
  stMvpSetRoutedMessages([]);
  must(stMvpRoutedMessageCount() == 0, 'the routed set starts empty');
  stMvpSendMsg(h, WM_NCHITTEST, 0, 0);
  expect('an unrouted message never reaches the image', 'RoutedWin seen', '0');

  // ── installing the set ───────────────────────────────────────────────────
  // The high id exercises the linear tail past the bitmap; a set that quietly
  // dropped it would look exactly like a handler that never fires.
  var wanted = [WM_NCHITTEST, WM_MOUSEMOVE, WM_SETCURSOR, WM_APP_ISH];
  var accepted = stMvpSetRoutedMessages(wanted);
  must(accepted == wanted.length,
       'the door accepted every id it was given ($accepted of ${wanted.length})');
  must(stMvpRoutedMessageCount() == wanted.length,
       'and reports the same set back');

  // ── the widened funnel carries all three values ──────────────────────────
  stMvpSendMsg(h, WM_MOUSEMOVE, 0x1111, 0x22223333);
  expect('a routed message reaches the handler', 'RoutedWin seen', '1');
  expect('  ...with the message id', 'RoutedWin lastMsg', WM_MOUSEMOVE.toString());
  expect('  ...with wParam (new in the 4-arg funnel)',
      'RoutedWin lastW', '4369');
  expect('  ...with lParam (new in the 4-arg funnel)',
      'RoutedWin lastL', '572666675');

  // ── the answer comes back out as the LRESULT ─────────────────────────────
  var claim = int.parse(ev('RoutedProbe claimValue'));
  var got = stMvpSendMsg(h, WM_NCHITTEST, 0, 0);
  must(got == claim,
       "the handler's answer is the LRESULT Windows saw (got $got, want $claim)");

  // ── nil declines: the result must be DefWindowProcW's, whatever it is ────
  //
  // Compared against an UNROUTED send of the same message rather than against
  // a hardcoded constant. DefWindowProcW's answer depends on the arguments —
  // WM_NCHITTEST at screen point (0,0) is outside the window and correctly
  // answers HTNOWHERE, which is 0 — so an assertion like "not 0" tests the
  // probe's coordinates, not the door. This tests the door: declining must
  // produce exactly what never routing produces.
  stMvpSetRoutedMessages([]);
  var defResult = stMvpSendMsg(h, WM_NCHITTEST, 0, 0);
  stMvpSetRoutedMessages(wanted);
  stRun('RoutedWin claim: false.');
  var seenBefore = ev('RoutedWin seen');
  var declined = stMvpSendMsg(h, WM_NCHITTEST, 0, 0);
  must(declined != claim,
       'answering nil does NOT return the claim value (got $declined)');
  must(declined == defResult,
       'answering nil falls through to DefWindowProcW — same LRESULT as an '
       'unrouted send (got $declined, unrouted $defResult)');
  expect('and the declining handler DID run (so this was a decline, not a '
      'missed route)', 'RoutedWin seen > ' + seenBefore, 'true');

  // ── a high-id message routes through the tail list ───────────────────────
  stRun('RoutedWin claim: true.');
  var high = stMvpSendMsg(h, WM_APP_ISH, 7, 8);
  must(high == claim, 'a message above the bitmap routes too (got $high)');
  expect('  ...and arrives with its own id', 'RoutedWin lastMsg',
      WM_APP_ISH.toString());

  // ── clearing the set stops it again ──────────────────────────────────────
  stMvpSetRoutedMessages([]);
  var before = ev('RoutedWin seen');
  stMvpSendMsg(h, WM_NCHITTEST, 0, 0);
  expect('clearing the set stops routing', 'RoutedWin seen', before);

  stRun('RoutedWin close. UiSession pump. UiSession shutDown.');
  print('\nROUTED: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
