// The DD10 CONTROL-SUBCLASSING gate.
//
//   dartui.exe st_subclass.dart "<world;layers>" st/mvp st/mvp_compat \
//              st/test/ffi/control_subclass.mst
//
// A real Win32 EDIT control, subclassed by Dolphin's own `subclassWindow`
// shape, with the door's trampoline in the WndProc slot and comctl's original
// procedure chained behind it.
//
// THE TWO HALVES ARE ASSERTED ON THE SAME MESSAGE, deliberately. Each half
// fails invisibly on its own:
//
//   * a trampoline that routes NOTHING looks exactly like a working control
//     — the EDIT keeps editing, because its own procedure is still there;
//   * a trampoline that SWALLOWS instead of chaining looks exactly like a
//     working image — the handler runs, and only the control is broken.
//
// So WM_SETTEXT is routed, the image counts it, and the text is then read
// back out of the control. Both must hold: the count proves the door reached
// the image, and the text proves the door chained to the procedure that
// actually stores it.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

const int WM_SETTEXT = 0x000C;

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'SubQ' + (_seq++).toString();
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
  for (var dir in [a[1], a[2]]) {
    for (var p in mstIn(dir)) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) { print('LOAD FAIL $p: ${cut(r)}'); exit(2); }
    }
  }
  var probe = stRun(new File(a[3]).readAsStringSync());
  if (probe.toString().startsWith('ERR')) {
    print('PROBE FAIL ${a[3]}: ${cut(probe)}'); exit(2);
  }

  stRun('UiSession startUp.');

  // A host window to parent the control to. Any WS_CHILD needs a real parent
  // (DD9: a WS_CHILD with hWndParent 0 fails outright).
  stRun('SubHost := UiWindow open: 320 by: 200.');
  var host = num('SubHost hwnd');
  // `> 0`, not `!= 0`: `num` answers -1 when the expression RAISED, and -1
  // satisfies `!= 0` — so the weaker test reports a healthy host window for a
  // send that did not work at all. (It did exactly that on the first run.)
  must(host > 0, 'host window ($host)');

  // ── the control ─────────────────────────────────────────────────────────
  stRun('SubEd := SubclassProbe on: SubHost hwnd.');
  var edit = num('SubEd handle');
  must(edit > 0 && edit != host, 'a real EDIT control ($edit)');

  // Before subclassing: the control works, and nothing routes to us.
  stRun("SubEd text: 'before'.");
  expect('the control edits before subclassing', 'SubEd text', "'before'");
  expect('and nothing has routed yet', 'SubEd seen', '0');

  // ── subclass it, Dolphin's way ──────────────────────────────────────────
  var old = num('SubEd subclassWindow');
  must(old > 0, 'subclassWindow answered the comctl procedure ($old)');
  expect('which was saved as oldWndProc', 'SubEd oldWndProc notNil', 'true');

  var vmProc = num('VM getWndProc');
  must(vmProc > 0, 'VM getWndProc is a real address ($vmProc)');
  must(old != vmProc, 'and it is NOT our own trampoline');
  // Stability matters: `subclassWindow`'s equality test uses it to detect an
  // already-subclassed window, and an address that varied per call would make
  // that test answer false and chain the trampoline to itself.
  must(num('VM getWndProc') == vmProc, 'VM getWndProc is stable across calls');

  // Route WM_SETTEXT and register the control so the door can find its view.
  stRun('UiSession routeMessages: (Array with: ${WM_SETTEXT}).');
  stRun('UiSession register: SubEd for: SubEd handle.');

  // ── the two halves, on one message ──────────────────────────────────────
  stRun("SubEd text: 'after'.");
  var seen = num('SubEd seen');
  must(seen > 0, 'the image saw the routed message (seen=$seen)');
  expect('  ...and it was WM_SETTEXT', 'SubEd lastMsg', '$WM_SETTEXT');
  // The half that a routing-only test would miss: comctl's procedure is what
  // stores the text, so this passing proves the trampoline CHAINED.
  expect('the control still stores its text', 'SubEd text', "'after'");

  // UNROUTED messages must reach the control without entering the image at
  // all — that is the default path, and the one that carries typing.
  //
  // `text` reads through WM_GETTEXTLENGTH and WM_GETTEXT, neither of which is
  // in the routed set, so the counter must not move while the answer stays
  // correct. Asserted as EQUALITY on the counter: an earlier version of this
  // check said `seen >= before`, which a counter that never decreases
  // satisfies unconditionally — it measured nothing at all.
  var before = num('SubEd seen');
  expect('an unrouted read still works', 'SubEd text', "'after'");
  must(num('SubEd seen') == before,
      'and it did NOT enter the image (seen stayed $before)');

  // `defaultWindowProcessing:` is the path `UI.ControlView` will use to chain
  // from Smalltalk rather than from C++. Proven callable here so the class
  // wave does not discover it later.
  // Compared against the control's OWN text length rather than a literal, so
  // the assertion stays true if the text above ever changes — a magic number
  // here just re-asserts what the test author believed at the time.
  expect('the image can chain through oldWndProc',
      "((SubEd defaultWindowProcessing: 16rE wParam: 0 lParam: 0) "
      "= SubEd text size)", 'true');

  // ── unsubclass, and the control is comctl's again ───────────────────────
  var restored = num('SubEd unsubclassWindow');
  must(restored == vmProc, 'unsubclassWindow removed our trampoline');
  var seenAfter = num('SubEd seen');
  stRun("SubEd text: 'restored'.");
  expect('the control still works unsubclassed', 'SubEd text', "'restored'");
  must(num('SubEd seen') == seenAfter,
      'and nothing routes to the image any more');

  stRun('SubEd destroy. SubHost close. UiSession pump. UiSession shutDown.');

  print('\nSUBCLASS: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
