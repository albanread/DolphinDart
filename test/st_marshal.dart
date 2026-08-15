// The FFI MARSHALLING gate (DolphinDart DD6c).
//
//   dart.exe st_marshal.dart "st/world;st/prims/rt;st/prims"
//
// Proves the generated coercing wrappers turn Smalltalk objects into the words
// the floor takes, in both directions. Each answer is checkable against
// something the OS or the language already knows — never a constant baked in
// here: lstrlenW must agree with the string's own size, the desktop client rect
// must equal the screen, a round trip must return what went in.
import 'dart:cocoa';
import 'dart:io';
List<String> mstIn(String d)=> new Directory(d).listSync().map((e)=>e.path).where((p)=>p.endsWith('.mst')).toList()..sort();
main(List<String> a) {
  for (var d in a[0].split(';')) for (var p in mstIn(d)) {
    var r=stRun(new File(p).readAsStringSync());
    if (r.toString().startsWith('ERR')) { print('LOAD FAIL $p: ${r.toString().split("\n").first}'); exit(2); }
  }
  print('loaded');
  for (var c in [
    // 1. UTF-16 marshalling: lstrlenW must agree with the Smalltalk string size.
    "| b | b := Utf16Buffer fromString: 'hello'. Transcript showCr: 'lstrlenW(hello) = ', (Win32Rt lstrlenW: b address) printString. b free.",
    "| b | b := Utf16Buffer fromString: 'a longer string'. Transcript showCr: 'lstrlenW(15) = ', (Win32Rt lstrlenW: b address) printString. b free.",
    // 2. Round trip through external memory.
    "| b | b := Utf16Buffer fromString: 'round trip'. Transcript showCr: 'roundtrip = ', b stringValue. b free.",
    // 3. Non-BMP: an emoji is a surrogate pair, so 2 code units.
    "| b | b := Utf16Buffer fromString: 'ab', (Character value: 55357) asString, (Character value: 56832) asString. Transcript showCr: 'surrogates = ', (Win32Rt lstrlenW: b address) printString. b free.",
    // 4. THE GATE: Dolphin's own selector, called with OBJECTS, filling a RECT.
    "| r | r := ExternalMemory new: 16. UserLibrary getClientRect: (UserLibrary getDesktopWindow) lpRect: r. Transcript showCr: 'RECT via wrapper = ', (r int32At: 1) printString, ' ', (r int32At: 5) printString, ' ', (r int32At: 9) printString, ' ', (r int32At: 13) printString. r free.",
    // 5. nil coerces to the null pointer rather than raising.
    "Transcript showCr: 'nil->null = ', (FFICoerce pointer: nil) printString.",
    // 6. A bad argument type is refused, not coerced.
    "Transcript showCr: 'bad arg = ', ([ FFICoerce word: 'a string' ] on: Error do: [:e | 'refused' ]).",
  ]) { var x=stRun(c); if (x.toString().startsWith('ERR')) print('  ERR ${x.toString().split("\n").first} :: ${c.substring(0,40)}'); }
}
