// DD12's GOAL GATE: a real modal dialog, on Dolphin's own DialogView.
//
//   dartui.exe st_modal.dart "<world;layers>" st/mvp st/mvp_compat \
//              st/test/ffi/dolphin_modal.mst
//
// A window with buttons on it is not a modal. The four things that make the
// difference are each asserted here, and three of the four are asked of
// WINDOWS rather than of the image:
//
//   1. THE OWNER IS DISABLED while the dialog is up -- sampled from inside
//      the nested loop via IsWindowEnabled, because after `showModal` returns
//      its ensure block has already re-enabled the owner and the answer would
//      be true no matter what happened.
//   2. `showModal` BLOCKS. Proved by ORDER, not by a flag: the dismissal is
//      posted as a deferred action BEFORE entering, and the only pump that
//      can drain it is the nested one inside the modal loop. If the trace
//      reads `entering dismissing returned`, the caller was blocked while the
//      dialog was dismissed. If `showModal` fell straight through, the same
//      action would drain later and the trace would read `entering returned
//      dismissing`.
//   3. OK APPLIES the buffered edit through to the subject; CANCEL leaves the
//      subject untouched. That is what a ValueBuffer is for, and the text
//      makes a genuine round trip through the Windows edit control -- `ok`
//      reads `edit text` back rather than trusting what it set.
//   4. TWO STACKED MODALS unwind innermost-first, the only order a
//      single-threaded nested pump can unwind in.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 200 ? s.substring(0, 200) : s;
}

int fails = 0;
int _seq = 0;

// NOTE the `ifNil:` on `messageText`. Without it this helper hides exactly
// the errors worth seeing: an Error signalled with no message text makes the
// handler's own `,` fail, and all the gate ever reports is
// `_OneByteString has no method ','` -- the harness's failure, not the
// image's. Two runs of this gate were spent on that.
String ev(String expr) {
  var cls = 'MdQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', (e messageText ifNil: [ '<none>' ]) ] ] ]");
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

  // `initializeViewClasses` is what resets DisplayMonitor's `Instances`.
  // Without it every window-positioning path -- including `showModal`'s
  // centring -- dies on `at:ifAbsentPut:` sent to nil, contained, and the
  // modal silently never opens.
  expect('every view class initialized',
      'DolphinBoot initializeViewClasses printString', "'()'");
  expect('DisplayMonitor has its instance cache',
      'DisplayMonitor classVarInstances isNil printString', "'false'");

  stRun('UiSession startUp.');
  must(num('ModalOwnerShell routeDolphinMessages') > 0,
      'Dolphin message map installed as the routed set');

  stRun('MO := ModalOwnerShell new.');
  stRun('MO create.');
  print('  .. build -> ' + ev('MO build printString'));
  stRun('MO show.');
  must(num('MO handle') > 0, 'the owner shell opened');
  expect('and starts enabled', 'MO ownerEnabled printString', "'true'");
  expect('with the subject at its original value',
      'MO subjectValue', "'original'");

  // ── 1 + 2 + 3: OK ────────────────────────────────────────────────────
  print('  .. modal OK -> ' + ev("(MO promptOk: 'typed') printString"));

  expect('showModal BLOCKED: dismissal happened before it returned',
      'MO traceString', "'entering dismissing returned'");
  expect('the owner was DISABLED while the dialog was up',
      'MO ownerEnabledWhileModal printString', "'false'");
  expect('and re-enabled after it closed',
      'MO ownerEnabled printString', "'true'");
  expect('showModal answered what was typed', 'MO lastAnswer', "'typed'");
  expect('OK APPLIED the buffer through to the subject',
      'MO subjectValue', "'typed'");
  expect('the dialog window is gone',
      '(User32 isWindow: MO inner handle asParameter) printString', "'false'");

  // ── 3: CANCEL ────────────────────────────────────────────────────────
  print('  .. modal Cancel -> ' + ev("(MO promptCancel: 'discarded') printString"));

  expect('Cancel also blocked in the nested loop',
      'MO traceString', "'entering dismissing returned'");
  expect('Cancel answered nil', 'MO lastAnswer printString', "'nil'");
  expect('and the subject was left UNTOUCHED',
      'MO subjectValue', "'typed'");

  // ── 4: two stacked modals ────────────────────────────────────────────
  print('  .. stacked -> ' + ev('MO promptStacked printString'));
  expect('two stacked modals unwind innermost-first',
      'MO traceString', "'enterA enterB closeB returnB closeA returnA'");
  // Both levels applied, in unwind order -- B first, then A over it. So the
  // subject holds the OUTER dialog's value, which is the same evidence for
  // the unwind order that the trace gives, read off the model instead.
  expect('each level applied its buffer in unwind order',
      'MO subjectValue', "'A'");

  expect('no handler error was contained',
      'UiSession handlerErrors printString', "'0'");

  expect('destroy succeeded', 'MO destroy printString', "'true'");
  stRun('UiSession pump. UiSession shutDown.');
  expect('the registry is empty', 'UiSession windowCount', '0');

  print('');
  print('MODAL: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
