// The DD10 PER-WINDOW ROUTING gate.
//
//   dart.exe st_twowin.dart "<world;layers>" st/mvp st/test/ffi/twowin_probe.mst
//
// Every other door gate in this tree opens ONE window, and every one of them
// passed while routing went to `LastWindow` — whichever view registered most
// recently. That is invisible with one window and wrong with two: a shell
// owning an EDIT control needs WM_COMMAND to reach the control's OWNER, and
// stacked modal dialogs (the DD12 goal gate) cannot work at all.
//
// So this gate opens two and insists each message lands on exactly one of
// them. The assertions are written as "A saw it AND B did not", because a
// broadcast to both would satisfy "A saw it" on its own.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_SIZE = 0x0005;

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'TwoWinQ' + (_seq++).toString();
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

int num(String expr) => int.parse(ev(expr), onError: (_) => -1);

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
  for (var p in mstIn(a[1])) {
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('WAVE FAIL $p: ${cut(r)}'); exit(2); }
  }
  var probe = stRun(new File(a[2]).readAsStringSync());
  if (probe.toString().startsWith('ERR')) {
    print('PROBE FAIL ${a[2]}: ${cut(probe)}'); exit(2);
  }

  stRun('UiSession startUp.');
  stRun('WinA := TwoWinProbe open: 300 by: 200. WinA tag: #a.');
  stRun('WinB := TwoWinProbe open: 320 by: 220. WinB tag: #b.');
  var ha = num('WinA hwnd'), hb = num('WinB hwnd');
  must(ha != 0 && hb != 0 && ha != hb,
       'two distinct windows opened ($ha, $hb)');
  must(num('UiSession windowCount') == 2, 'both are registered');

  // The registry resolves each handle to its own view. This is the lookup
  // dispatch now performs; asserting it separately means a routing failure
  // below is unambiguous — the registry is right, so the router is wrong.
  must(ev('(UiSession viewFor: WinA hwnd) tag') == '#a',
       'the registry maps A\'s handle to A');
  must(ev('(UiSession viewFor: WinB hwnd) tag') == '#b',
       'the registry maps B\'s handle to B');
  // B registered LAST, so under the old routing everything would land on B.
  must(ev('UiSession lastWindow tag') == '#b',
       'B is the most recently registered (the old router would pick it)');

  // ── a mapped message reaches only its own window ─────────────────────────
  stRun('UiSession routeMessagesFrom: View.');
  stMvpSendMsg(ha, WM_SIZE, 0, 0x00C80190);
  must(num('WinA sizes') == 1 && num('WinB sizes') == 0,
       'WM_SIZE to A reached A and NOT B '
       '(a=${num('WinA sizes')}, b=${num('WinB sizes')})');
  must(num('WinA lastL') == 13107600, '  ...carrying A\'s own lParam');

  stMvpSendMsg(hb, WM_SIZE, 0, 0x01100118);
  must(num('WinB sizes') == 1 && num('WinA sizes') == 1,
       'WM_SIZE to B reached B and left A\'s count alone '
       '(a=${num('WinA sizes')}, b=${num('WinB sizes')})');
  must(num('WinB lastL') == 17826072, '  ...carrying B\'s own lParam');

  // ── the named WM_COMMAND channel routes by owner too ─────────────────────
  // This is the one the view side needs: a control notifies its PARENT, and
  // the parent is the window the notification arrived at.
  stRun('UiSession clearMessageMap.');
  stRun('WinA addButton: 5001. UiSession pump.');
  stRun('WinB addButton: 5002. UiSession pump.');
  var ca = num('WinA commands'), cb = num('WinB commands');
  stRun('WinA click: 5001. UiSession pump.');
  must(num('WinA commands') == ca + 1 && num('WinB commands') == cb,
       'a command on A reached A only '
       '(a ${ca}->${num('WinA commands')}, b ${cb}->${num('WinB commands')})');
  stRun('WinB click: 5002. UiSession pump.');
  must(num('WinB commands') == cb + 1 && num('WinA commands') == ca + 1,
       'a command on B reached B only '
       '(a=${num('WinA commands')}, b=${num('WinB commands')})');

  // ── paint routes by owner ────────────────────────────────────────────────
  // Both must be VISIBLE first: invalidating a hidden window produces no
  // WM_PAINT at all, so the check would pass on two zeroes and prove nothing.
  stRun('WinA show. WinB show. UiSession pump.');
  var pa = num('WinA paints'), pb = num('WinB paints');
  stRun('WinA invalidate. UiSession pump.');
  must(num('WinA paints') > pa && num('WinB paints') == pb,
       'invalidating A painted A only '
       '(a ${pa}->${num('WinA paints')}, b ${pb}->${num('WinB paints')})');

  // ── closing one leaves the other routable ────────────────────────────────
  // Deregistration must not take the survivor's routing with it, which is
  // exactly what a LastWindow-shaped router does when the last window closes.
  stRun('WinA close. UiSession pump.');
  must(num('UiSession windowCount') == 1, 'closing A leaves one registered');
  stRun('UiSession routeMessagesFrom: View.');
  var bs = num('WinB sizes');
  stMvpSendMsg(hb, WM_SIZE, 0, 0x00640064);
  must(num('WinB sizes') == bs + 1,
       'B still routes after A closed (${bs}->${num('WinB sizes')})');

  stRun('UiSession clearMessageMap. WinB close. UiSession pump. UiSession shutDown.');
  must(num('UiSession windowCount') == 0, 'the registry empties');

  print('\nTWOWIN: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
