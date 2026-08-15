// The DD9 View-wave gate.
//
//   dart.exe st_viewwave.dart "st/world;st/dolphin_compat;st/prims/rt;st/prims/structs;st/prims;st/prims/aliases" st/mvp
//
// Two stages, and the second is the one that matters. Stage 1 LOADS the
// translated Dolphin view classes; stage 2 INSTANTIATES them. Loading was green
// for a whole sprint while `View new` still answered null, because the
// constructor idiom every one of these classes uses —
//
//     View class >> new [ ^super new initialize ]
//
// — had no front-end path and compiled to a null. A load-only gate cannot see
// that, so it is not a gate. This one sends `new`.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync()
    .map((e) => e.path)
    .where((p) => p.endsWith('.mst'))
    .toList()..sort();

String base(String p) => p.split(new RegExp(r"[\/]")).last;

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 160 ? s.substring(0, 160) : s;
}

int fails = 0;
int _probeSeq = 0;

/// Evaluate [expr] and compare its printString against [want].
///
/// The expression is compiled as a class-side method and SENT, because a
/// `stRun` do-it answers a loader message rather than the expression's value —
/// the trap that let three DD7 assertions pass while proving nothing. A raise
/// is caught in Smalltalk and reported as its message, so a missing method
/// cannot read as a pass either.
void expect(String label, String expr, String want) {
  var cls = 'WaveProbe' + (_probeSeq++).toString();
  var src = 'Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e messageText ] ] ]";
  var load = stRun(src);
  if (load.toString().startsWith('ERR')) {
    fails++;
    print('  FAIL ' + label.padRight(46) + ' probe would not compile: ' + cut(load));
    return;
  }
  var g;
  try {
    g = stClassSend0(stClassNamed(cls), 'v').toString();
  } catch (e) {
    g = 'THREW: ' + cut(e);
  }
  if (g != want) {
    fails++;
    print('  FAIL ' + label.padRight(46) + ' got <' + g + '> want <' + want + '>');
  } else {
    print('  ok   ' + label);
  }
}

main(List<String> a) {
  if (a.length < 2) {
    print('usage: st_viewwave.dart "<layer;layer;...>" <mvp-dir>');
    exit(2);
  }
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) {
        print('BASE FAIL ' + base(p) + ': ' + cut(r));
        exit(2);
      }
    }
  }

  // ── stage 1: the wave loads ───────────────────────────────────────────────
  int ok = 0, bad = 0;
  for (var p in mstIn(a[1])) {
    var r = stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) {
      bad++;
      print('  LOAD FAIL ' + base(p).padRight(20) + ' ' + cut(r));
    } else {
      ok++;
      print('  loaded ' + base(p));
    }
  }
  print('\nVIEW WAVE: ' + ok.toString() + ' loaded, ' + bad.toString() + ' failed');
  fails += bad;

  // ── stage 2: the hierarchy linked ─────────────────────────────────────────
  print('\nhierarchy:');
  expect('ShellView inheritsFrom: View', 'ShellView inheritsFrom: View', 'true');
  expect('ContainerView inheritsFrom: View', 'ContainerView inheritsFrom: View', 'true');
  expect('BorderLayout inheritsFrom: LayoutManager',
      'BorderLayout inheritsFrom: LayoutManager', 'true');

  // ── stage 3: they INSTANTIATE (the DD9 class-side-super gate) ─────────────
  //
  // `LayoutManager class >> new` and `View class >> new` are both
  // `^super new initialize`, with no ancestor defining a class-side `new` —
  // the fallback that raw-allocates the RECEIVING class.
  print('\ninstantiation (class-side super):');
  expect('LayoutManager new is a LayoutManager',
      'LayoutManager new class name', "'LayoutManager'");
  expect('BorderLayout new is a BorderLayout (inherited ctor)',
      'BorderLayout new class name', "'BorderLayout'");
  expect('BorderLayout new is still a LayoutManager',
      '(BorderLayout new isKindOf: LayoutManager)', 'true');
  // BorderLayout writes its own `initialize` calling `super initialize`, so
  // this also proves the INSTANCE-side super still runs from a class built
  // through the class-side one.
  expect('BorderLayout new ran its own initialize',
      'BorderLayout new verticalGap notNil', 'true');

  // The views themselves. `View class >> new` is the same idiom, but its
  // `initialize` reaches much further: defaultStyle, Color default,
  // isManaged:, initializeModel -> setModel: self class defaultModel ->
  // connectModel. This is where the corpus stops being a hierarchy and starts
  // being a program.
  print('\ninstantiation (the views):');
  expect('View new is a View', 'View new class name', "'View'");
  expect('View new ran initialize (presenter wired to self)',
      'View new presenter notNil', 'true');
  expect('ContainerView new is a ContainerView (inherited ctor)',
      'ContainerView new class name', "'ContainerView'");
  expect('ShellView new is a ShellView (two levels inherited)',
      'ShellView new class name', "'ShellView'");
  expect('ShellView new is still a View', '(ShellView new isKindOf: View)', 'true');

  print('\nVIEWWAVE: ' + fails.toString() + ' failure(s)');
  exit(fails == 0 ? 0 : 1);
}
