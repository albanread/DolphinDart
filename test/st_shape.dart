// Does a `self` send inside an INHERITED class-side method dispatch to the
// receiver, or bind to the defining class?
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

int _seq = 0;
String evb(String body) {
  var cls = 'PQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ ' + body + ' ] on: Error do: [ :e | ' +
      "'RAISED: ', e class name, ': ', (e messageText ifNil: [ '<none>' ]) ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE: ' + r.toString();
  try { return stClassSend0(stClassNamed(cls), 'v').toString(); }
  catch (e) { return 'THREW: ' + e.toString().replaceAll('\n', ' | '); }
}
void p(String l, String b) => print(('  ' + l).padRight(34) + '-> ' + evb(b));

main(List<String> a) {
  for (var g in a) { for (var d in g.split(';')) {
    d = d.trim(); if (d.isEmpty) continue;
    for (var f in (d.endsWith('.mst') ? [d] : mstIn(d))) {
      var r = stRun(new File(f).readAsStringSync());
      if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r.toString());
    } } }

  // The minimal shape of STxFiler/STLInFiler.
  var src = '''Object subclass: PBase [
    PBase class >> tag [ ^self subclassResponsibility ]
    PBase class >> useTag [ ^self tag ]
    PBase class >> useTagIndirect [ ^self useTag ]
]
PBase subclass: PDerived [
    PDerived class >> tag [ ^'DERIVED' ]
]''';
  print('load -> ' + (stRun(src).toString().startsWith('ERR') ? 'FAIL' : 'ok'));

  p('PDerived tag (own)', 'PDerived tag');
  p('PDerived useTag (inherited)', 'PDerived useTag');
  p('PDerived useTagIndirect', 'PDerived useTagIndirect');
  p('PBase useTag (should raise)', 'PBase useTag');

  // Instance side, for contrast — this is known to work.
  var isrc = '''Object subclass: IBase [
    tag [ ^self subclassResponsibility ]
    useTag [ ^self tag ]
]
IBase subclass: IDerived [
    tag [ ^'DERIVED' ]
]''';
  stRun(isrc);
  p('IDerived new useTag (inst)', 'IDerived new useTag');
  exit(0);
}
