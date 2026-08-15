// The DD9 MESSAGE-MAP gate — Dolphin's own dispatch, end to end.
//
//   dart.exe st_mapped.dart "<world;layers>" st/mvp st/test/ffi/mapped_probe.mst
//
// `UI.View class >> buildMessageMap` is Dolphin's own method, translated
// unmodified: a 1024-slot Array from message number + 1 to a handler selector.
// This drives the whole chain from it — the door's routed set is derived from
// the map, a real message arrives, the map picks the selector, the view's
// answer becomes the LRESULT — which is the dispatch every translated view
// will use.
//
// The two things worth being careful about, both asserted below: the routed
// set and the map must AGREE (a map entry whose message is not routed never
// arrives, and that is the silent half of the pair); and a view with a map
// entry but no method must decline rather than raise, because Dolphin's own
// views are exactly like that — the map is built once on View and each
// subclass handles its own subset.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_SIZE = 0x0005;
const int WM_SETCURSOR = 0x0020;
const int WM_MOUSEMOVE = 0x0200;   // in the map, NOT implemented by the probe
const int WM_USER_ISH = 0x0401;    // not in the map at all

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 150 ? s.substring(0, 150) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'MappedQ' + (_seq++).toString();
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
    print('  FAIL ' + label.padRight(54) + ' got <' + got + '> want <' + want + '>');
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
  for (var p in mstIn(a[1])) {           // the View wave, for buildMessageMap
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('WAVE FAIL $p: ${cut(r)}'); exit(2); }
  }
  var probe = stRun(new File(a[2]).readAsStringSync());
  if (probe.toString().startsWith('ERR')) {
    print('PROBE FAIL ${a[2]}: ${cut(probe)}'); exit(2);
  }

  stRun('UiSession startUp.');

  // ── the map is Dolphin's, and it runs ────────────────────────────────────
  expect("Dolphin's buildMessageMap runs", 'View buildMessageMap size', '1024');
  expect('  ...and WM_PAINT maps to Dolphin\'s own selector',
      '(View buildMessageMap at: 16) printString', "'#wmPaint:wParam:lParam:'");

  // ── installing it derives the routed set ─────────────────────────────────
  stRun('MappedWin := MappedProbe open: 300 by: 180.');
  expect('the probe window opened', 'MappedWin hwnd ~= 0', 'true');
  var h = int.parse(ev('MappedWin hwnd'));

  var accepted = int.parse(ev('UiSession routeMessagesFrom: View'));
  must(accepted > 50,
       'the map yielded a substantial routed set ($accepted messages)');
  must(stMvpRoutedMessageCount() == accepted,
       'and the door holds exactly that many');
  expect('the session kept the map', 'UiSession messageMap size', '1024');

  // The pair must agree: every non-nil map entry must be a routed message.
  // This is the assertion that catches the silent half — a map entry whose
  // message never arrives looks identical to a handler that is never called.
  expect('every map entry is routed',
      '(((1 to: UiSession messageMap size) select: [ :i | '
      '(UiSession messageMap at: i) notNil ]) '
      'detect: [ :i | (UiSession selectorForMessage: i - 1) isNil ] '
      'ifNone: [ #allRouted ])', '#allRouted');

  // ── dispatch picks the selector from the map ─────────────────────────────
  var claim = int.parse(ev('MappedProbe claimValue'));
  var got = stMvpSendMsg(h, WM_SIZE, 0, 0x00C80190);
  must(got == claim, 'WM_SIZE reached wmSize:wParam:lParam: (got $got)');
  expect('  ...exactly once', 'MappedWin sizes', '1');
  expect('  ...carrying lParam (the new client size)',
      'MappedWin lastL', '13107600');

  got = stMvpSendMsg(h, WM_SETCURSOR, 0, 0);
  must(got == claim, 'WM_SETCURSOR reached a DIFFERENT selector (got $got)');
  expect('  ...so the map is choosing, not funnelling', 'MappedWin sizes', '1');
  expect('  ...and both handlers ran', 'MappedWin hits', '2');

  // ── a mapped message the view does not implement DECLINES ────────────────
  // Dolphin's views are all like this: the map is built once on View, and each
  // subclass implements its own subset.
  stMvpSetRoutedMessages([]);
  var unrouted = stMvpSendMsg(h, WM_MOUSEMOVE, 0, 0);
  stRun('UiSession routeMessagesFrom: View.');
  var declined = stMvpSendMsg(h, WM_MOUSEMOVE, 0, 0);
  must(declined == unrouted,
       'a mapped message with no method falls through to DefWindowProcW '
       '(got $declined, unrouted $unrouted)');
  expect('  ...and did not run a handler', 'MappedWin hits', '2');

  // ── a message outside the map never routes ───────────────────────────────
  expect('a message outside the map has no selector',
      'UiSession selectorForMessage: ' + WM_USER_ISH.toString(), 'nil');
  stMvpSendMsg(h, WM_USER_ISH, 0, 0);
  expect('  ...and reaches no handler', 'MappedWin hits', '2');

  // ── clearing puts the door back to silent ────────────────────────────────
  stRun('UiSession clearMessageMap.');
  must(stMvpRoutedMessageCount() == 0, 'clearMessageMap empties the routed set');
  stMvpSendMsg(h, WM_SIZE, 0, 0);
  expect('and nothing routes after it', 'MappedWin sizes', '1');

  stRun('MappedWin close. UiSession pump. UiSession shutDown.');
  print('\nMAPPED: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
