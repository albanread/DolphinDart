// st_backcolor — a view's `backcolor` reaches the SCREEN.
//
//   dartui.exe st_backcolor.dart "<world;layers>" st/mvp st/mvp_compat
//
// WHY THIS GATE EXISTS (DD16b/DD17). `View>>onEraseRequired:` fills the client
// rectangle with the view's background colour. Nothing had ever checked that it
// did, and it had not worked since DD10 — a compat override answered nil to
// decline every erase, put in while `Graphics.Canvas` was untranslated and
// carrying its own retirement note (*translate Canvas, then delete this*).
// Canvas landed in DD11; the override outlived it by five sprints because what
// it disables is PIXELS, and no assertion in this port looks at pixels.
//
// Three separate bugs had to be fixed before a colour reached the screen, and
// each was invisible behind the next:
//   * the routed set must be installed or the handler is never called at all;
//   * `LOGBRUSH class >> style:color:hatch:` did not exist, so the fill raised
//     inside a wndproc where errors are contained twice;
//   * the door marks a message handled ONLY for an Integer answer, and
//     Dolphin's handlers answer Booleans — so DefWindowProcW erased the class
//     brush over the top of Dolphin's fill.
//
// So this gate reads the PIXEL back. It is the only kind of assertion that
// could have caught any of the above: handles, class names, `backcolor`
// answering the colour, and the handler running all passed throughout.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

int fails = 0;
int _seq = 0;

String ev(String expr) {
  var cls = 'BcQ' + (_seq++).toString();
  var r = stRun('Object subclass: ' + cls + ' [ ' + cls + ' class >> v [ ' +
      '^[ (' + expr + ') printString ] on: Error do: [ :e | ' +
      "'RAISED: ', (e messageText ifNil: [ e class name ]) ] ] ]");
  if (r.toString().startsWith('ERR')) return 'NOCOMPILE';
  try { return stClassSend0(stClassNamed(cls), 'v').toString(); }
  catch (e) { return 'THREW'; }
}

/// The 24-bit BMP the door writes: bottom-up BGR rows, 4-byte aligned.
List<int> pixelAt(String path, int x, int y) {
  var d = new File(path).readAsBytesSync();
  int u32(int o) => d[o] | (d[o + 1] << 8) | (d[o + 2] << 16) | (d[o + 3] << 24);
  var off = u32(10), w = u32(18), h = u32(22);
  var row = ((w * 3) + 3) & ~3;
  var yy = h - 1 - y;                    // bottom-up
  var i = off + yy * row + x * 3;
  return [d[i + 2], d[i + 1], d[i]];     // r, g, b
}

void expectPixel(String what, List<int> got, List<int> want) {
  var ok = got[0] == want[0] && got[1] == want[1] && got[2] == want[2];
  if (!ok) fails++;
  print('  ' + (ok ? 'ok  ' : 'FAIL') + ' ' + what.padRight(38) +
        ' got ' + got.toString() + ' want ' + want.toString());
}

main(List<String> a) {
  for (var g in a) {
    for (var d in g.split(';')) {
      d = d.trim();
      if (d.isEmpty) continue;
      for (var f in (d.endsWith('.mst') ? [d] : mstIn(d))) {
        var r = stRun(new File(f).readAsStringSync());
        if (r.toString().startsWith('ERR')) print('LOAD FAIL ' + f + ': ' + r);
      }
    }
  }
  stRun('DolphinBoot initializeViewClasses.');
  stRun('UiSession startUp.');

  // The routed set is HALF the contract: a handler that is mapped but not
  // routed is never called, and looks exactly like a view that will not paint.
  var routed = ev('UiSession routeMessagesFrom: View');
  print('  routed messages: ' + routed);
  if (routed == '0' || routed.contains('RAISED')) {
    fails++;
    print('  FAIL no routed messages installed');
  }

  stRun('SV := ShellView new. SV create. SV extent: 300@220.');
  stRun('SV backcolor: (Color red).');
  stRun('CH := ContainerView new. CH parentView: SV. CH create.');
  stRun('CH rectangle: (20@20 corner: 140@120). CH backcolor: (Color blue). CH show.');
  stRun('SV show. SV invalidate. CH invalidate.');
  stRun('UiSession runFor: 700.');

  var dir = Directory.systemTemp.createTempSync('stbackcolor');
  var bmp = dir.path + Platform.pathSeparator + 'backcolor.bmp';
  var dims = ev("Win32 mvpCapture: SV handle path: '" +
      bmp.replaceAll(r'\', r'\\') + "' clientOnly: true");
  print('  capture: ' + dims);

  if (!new File(bmp).existsSync()) {
    fails++;
    print('  FAIL no capture written');
  } else {
    // Inside the child: blue. Outside it but inside the shell: red.
    expectPixel('child interior is its backcolor', pixelAt(bmp, 80, 70), [0, 0, 255]);
    expectPixel('shell interior is its backcolor', pixelAt(bmp, 220, 170), [255, 0, 0]);
  }
  try { dir.deleteSync(recursive: true); } catch (e) {}

  stRun('UiSession clearMessageMap. UiSession shutDown.');
  print('\nBACKCOLOR: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
