// Evaluate a file of expressions and write `index<TAB>printString` per line.
//
//   dart.exe st_eval.dart <exprs> <results> "<world;layers>" st/mvp st/mvp_compat
//
// The mirror image of `tools/oracle.py`, which asks the same questions of real
// Dolphin 8. Together they make `tools/conform.py`, which diffs the two — so
// this file's output format is a CONTRACT with oracle.py and must stay
// identical: 1-based index, a tab, the printString on one line.
//
// Errors are reported in-band (`RAISED: <class>: <text>`) rather than thrown,
// for the same reason the oracle does it: one bad expression must not truncate
// the batch, and a short results file must mean the RUN died rather than that
// the expressions answered nothing.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

int _seq = 0;

// Compiled into a fresh class per expression, exactly as every gate's `ev`
// does — the front end has no standalone evaluator, so a throwaway class-side
// method IS the evaluator here.
String ev(String expr) {
  var cls = 'EvQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', (e messageText ifNil: [ '<none>' ]) ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE';
  try {
    return stClassSend0(stClassNamed(cls), 'v').toString();
  } catch (e) {
    return 'THREW: ' + e.toString().replaceAll('\n', ' | ');
  }
}

main(List<String> a) {
  var exprs = new File(a[0]).readAsStringSync().split('\n');
  // Layers from a[2] onward, so the two evaluators can be pointed at
  // different slices of the stack without editing this file.
  for (var g in a.sublist(2)) {
    for (var d in g.split(';')) {
      d = d.trim();
      if (d.isEmpty) continue;
      for (var p in (d.endsWith('.mst') ? [d] : mstIn(d))) {
        var r = stRun(new File(p).readAsStringSync());
        if (r.toString().startsWith('ERR')) {
          print('LOAD FAIL $p: ${r.toString()}');
          exit(2);
        }
      }
    }
  }
  // The view classes must be initialized or half the probes answer nil for a
  // reason that has nothing to do with the expression being asked.
  stRun('DolphinBoot initializeViewClasses.');

  var out = new StringBuffer();
  for (var i = 0; i < exprs.length; i++) {
    var e = exprs[i].trim();
    if (e.isEmpty) continue;
    out.write((i + 1).toString());
    out.write('\t');
    out.write(ev(e).replaceAll('\n', ' | '));
    out.write('\n');
  }
  new File(a[1]).writeAsStringSync(out.toString());
  exit(0);
}
