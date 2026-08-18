// SCRATCH GATE — currently bisecting: class-side `self` in an INHERITED
// class-side method binds to the DEFINING class, not the receiving one.
//
//   dart.exe test\st_one.dart "st/world;st/dolphin_compat"
//
// The blocker recorded at the end of the DD14 journal entry: the STB view
// filer stops because `STxFiler class >> classForVersion:` does
// `self versions lookup: ...` and, with receiver STLInFiler, still reaches
// STxFiler's own abstract `versions` instead of STLInFiler's override.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

int _seq = 0;
String ev(String expr) {
  var cls = 'QQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', (e messageText ifNil: [ '<none>' ]) ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + r.toString();
  try { return stClassSend0(stClassNamed(cls), 'v').toString(); }
  catch (e) { return 'THREW: ' + e.toString(); }
}

void def(String src) {
  var r = stRun(src);
  if (r.toString().startsWith('ERR')) print('DEF FAIL: ' + r.toString());
}

main(List<String> a) {
  for (var g in a) {
    for (var d in g.split(';')) {
      d = d.trim(); if (d.isEmpty) continue;
      var files = d.endsWith('.mst') ? [d] : mstIn(d);
      for (var f in files) {
        var r = stRun(new File(f).readAsStringSync());
        if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r.toString());
      }
    }
  }

  // --- the minimal case ---------------------------------------------------
  def('Object subclass: PBase [ '
      'PBase class >> tag [ ^self subclassResponsibility ] '
      'PBase class >> useTag [ ^self tag ] '
      'PBase class >> useTagIndirect [ ^self useTag ] '
      'tagI [ ^self class tag ] ]');
  def('PBase subclass: PDerived [ PDerived class >> tag [ ^#DERIVED ] ]');
  def('PDerived subclass: PDeeper [ ]');

  print('1 PDerived tag             -> ' + ev('PDerived tag'));           // DERIVED
  print('2 PDerived useTag          -> ' + ev('PDerived useTag'));        // want DERIVED
  print('3 PDerived useTagIndirect  -> ' + ev('PDerived useTagIndirect'));// want DERIVED
  print('4 PDeeper useTag           -> ' + ev('PDeeper useTag'));         // want DERIVED
  print('5 PBase useTag             -> ' + ev('PBase useTag'));           // want RAISED
  print('6 PDerived new tagI        -> ' + ev('PDerived new tagI'));      // DERIVED (works)

  // Does `self` itself carry the right class, or only the send resolve wrong?
  def('Object subclass: PWho [ PWho class >> who [ ^self name ] '
      'PWho class >> whoSelf [ ^self ] ]');
  def('PWho subclass: PWho2 [ ]');
  print('7 PWho2 who                -> ' + ev('PWho2 who'));             // want PWho2
  print('8 PWho2 whoSelf            -> ' + ev('PWho2 whoSelf name'));    // want PWho2

  // A non-abstract override, to separate "reaches super" from
  // "subclassResponsibility is special".
  def('Object subclass: QBase [ QBase class >> pick [ ^#BASE ] '
      'QBase class >> usePick [ ^self pick ] ]');
  def('QBase subclass: QDer [ QDer class >> pick [ ^#DER ] ]');
  print('9 QDer usePick             -> ' + ev('QDer usePick'));          // want DER

  // With an argument, and recursive (the perf path that must not regress).
  def('Object subclass: RBase [ RBase class >> scale: n [ ^n ] '
      'RBase class >> useScale: n [ ^self scale: n ] '
      'RBase class >> fib: n [ ^n < 2 ifTrue: [ n ] ifFalse: [ '
      '(self fib: n - 1) + (self fib: n - 2) ] ] ]');
  def('RBase subclass: RDer [ RDer class >> scale: n [ ^n * 10 ] ]');
  print('10 RDer useScale: 7        -> ' + ev('RDer useScale: 7'));      // want 70
  print('11 RBase fib: 20           -> ' + ev('RBase fib: 20'));         // 6765

  // --- the real case ------------------------------------------------------
  print('12 STLInFiler versions     -> ' + ev('STLInFiler versions printString'));
  print('13 STxFiler classForVersion-> '
      + ev('(STLInFiler classForVersion: 6) printString'));
  exit(0);
}
