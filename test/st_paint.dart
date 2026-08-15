// The DD9 PAINT GATE — drawing through the WM_PAINT HDC.
//
//   dart.exe st_paint.dart "<world;layers>" st/test/ffi/paint_probe.mst
//
// The door has handed the image a real HDC since DD7 and nothing had drawn
// with it. This closes that: a real WM_PAINT reaches a Smalltalk handler, the
// handler calls GDI through the generated prims, and the result is READ BACK
// from the same device context.
//
// The readback is the whole point. Counting paints proves a handler ran; it
// says nothing about whether the HDC was valid, whether the arguments reached
// GDI in the right order, or whether the pixel landed where we asked. GetPixel
// answering exactly the COLORREF we wrote cannot happen by accident — a broken
// link answers CLR_INVALID (0xFFFFFFFF) or the background colour.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 150 ? s.substring(0, 150) : s;
}

int fails = 0;
int _seq = 0;

/// Evaluate an expression in the image and answer its printString. Compiled as
/// a class-side method and SENT — `stRun` of a do-it answers a loader message,
/// not the expression's value.
String ev(String expr) {
  var cls = 'PaintProbeQ' + (_seq++).toString();
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
    print('  FAIL ' + label.padRight(48) + ' got <' + got + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
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
    print('PROBE FAIL ${a[1]}: ${cut(probe)}');
    exit(2);
  }

  stRun('UiSession startUp.');
  stRun('PaintWin := PaintProbe open: 320 by: 200.');
  expect('the probe window opened', 'PaintWin hwnd ~= 0', 'true');
  expect('and it is registered with the session', 'UiSession windowCount', '1');

  // A visible window generates a real WM_PAINT; the pump delivers it.
  stRun('PaintWin show. UiSession pump.');
  expect('a real WM_PAINT reached the handler', 'PaintWin probed > 0', 'true');

  // THE ASSERTION. GetPixel answers the COLORREF at that coordinate — the same
  // value SetPixelV was given, or the drawing never happened.
  expect('GetPixel answers exactly the COLORREF we wrote',
      'PaintWin readback', ev('PaintProbe inkColor'));
  expect('and it is not CLR_INVALID (which is what a bad HDC answers)',
      'PaintWin readback ~= 16rFFFFFFFF', 'true');
  expect('TextOutW reported success', 'PaintWin textOk', 'true');

  // Invalidate and pump again: the second paint must draw too, so this is not
  // a one-shot that happened to work while the window was being created.
  var first = ev('PaintWin probed');
  stRun('PaintWin invalidate. UiSession pump.');
  expect('a second WM_PAINT arrives after invalidate',
      'PaintWin probed > ' + first, 'true');
  expect('and the second paint drew as well',
      'PaintWin readback', ev('PaintProbe inkColor'));

  // The paint path must not be silently failing and being backstopped: the
  // door counts a paint fault whenever a handler raises and it has to
  // ValidateRect to stop the pump spinning.
  var faults = stMvpPaintFaults();
  if (faults != 0) {
    fails++;
    print('  FAIL the door recorded $faults paint fault(s) — a handler raised');
  } else {
    print('  ok   no paint faults: no handler raised inside the door');
  }

  stRun('PaintWin close. UiSession pump. UiSession shutDown.');
  expect('the registry is empty again', 'UiSession windowCount', '0');

  print('\nPAINT: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
