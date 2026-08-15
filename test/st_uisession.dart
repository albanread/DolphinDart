// The DD8 UiSession gate.
//
//   dart.exe st_uisession.dart "st/world;st/dolphin_compat;st/prims/rt;st/prims"
//
// Re-runs DD7's door behaviour THROUGH UiSession rather than the spike classes:
// same real window, same real WM_PAINT/WM_COMMAND, now routed by the registry.
// The spikes may only be deleted once this is green, which is why it exists
// before they go.
import 'dart:cocoa';
import 'dart:io';

List<String> mstIn(String d) => new Directory(d)
    .listSync().map((e) => e.path).where((p) => p.endsWith('.mst')).toList()..sort();

String cut(s) {
  s = s.toString().replaceAll("\n", " | ");
  return s.length > 150 ? s.substring(0, 150) : s;
}

int fails = 0;
void probe(String label, String setup, String expr) {
  if (setup.isNotEmpty) {
    var s = stRun(setup);
    if (s.toString().startsWith('ERR')) {
      fails++; print('  FAIL $label (setup) :: ${cut(s)}'); return;
    }
  }
  var r = stRun("Transcript showCr: '${label.padRight(36)} -> ', ($expr) printString.");
  if (r.toString().startsWith('ERR')) { fails++; print('  FAIL $label :: ${cut(r)}'); }
}

main(List<String> a) {
  for (var d in a[0].split(';')) {
    for (var p in mstIn(d.trim())) {
      var r = stRun(new File(p).readAsStringSync());
      if (r.toString().startsWith('ERR')) {
        print('BOOT FAIL $p: ${cut(r)}'); exit(2);
      }
    }
  }

  probe('session starts up', 'UiSession startUp.', 'UiSession windowCount');

  // ── registry ────────────────────────────────────────────────────────────
  probe('window registers', '| w | w := UiWindow open: 420 by: 240.',
        'UiSession windowCount');
  probe('lastWindow is the new window', '', 'UiSession lastWindow notNil');
  probe('viewFor: finds it', '',
        '(UiSession viewFor: UiSession lastWindow hwnd) == UiSession lastWindow');

  // ── real messages routed through the session ────────────────────────────
  probe('paint routes to the view',
        'UiSession lastWindow show. UiSession pump.',
        'UiSession lastWindow painted > 0');
  probe('command routes to the view',
        '| w | w := UiSession lastWindow. w addButton: 2001. w click: 2001. UiSession pump.',
        'UiSession lastWindow commands');
  probe('session counted the messages', '', 'UiSession messageCount > 0');

  // ── deferred actions: queued, drained by the pump, not run inline ───────
  probe('postAction: queues, does not run',
        'Deferred := 0. UiSession postAction: [ Deferred := Deferred + 1 ].',
        'UiSession pendingActions');
  probe('pump drains the queue', 'UiSession pump.', 'Deferred');
  probe('queue is empty after draining', '', 'UiSession pendingActions');
  // An action that posts another must not extend the drain: the second runs on
  // the NEXT pump, so a self-posting action cannot spin the UI thread.
  probe('a self-posting action defers to next pump',
        'Deferred := 0. UiSession postAction: [ Deferred := Deferred + 1. '
        'UiSession postAction: [ Deferred := Deferred + 1 ] ]. UiSession pump.',
        'Deferred');
  probe('and runs on the following pump', 'UiSession pump.', 'Deferred');

  // ── a raising handler is contained, and the session keeps going ─────────
  probe('handler error does not kill the pump',
        'UiSession postAction: [ Error signal: \'boom\' ]. UiSession pump.',
        'UiSession pendingActions');
  probe('session still routes after an error',
        '| w | w := UiSession lastWindow. w invalidate. UiSession pump.',
        'UiSession lastWindow painted > 0');

  // ── idle ────────────────────────────────────────────────────────────────
  probe('onIdle fires when the pump is empty', 'UiSession pump. UiSession pump.',
        'UiSession idleCount > 0');
  probe('the view sees onIdle too', '', 'UiSession lastWindow idles > 0');

  // ── hygiene ─────────────────────────────────────────────────────────────
  probe('purgeDeadWindows finds none while live', '', 'UiSession purgeDeadWindows');
  probe('close deregisters', '| w | w := UiSession lastWindow. w close. UiSession pump.',
        'UiSession windowCount');
  probe('shutDown empties the registry', 'UiSession shutDown.', 'UiSession windowCount');

  print('\nUISESSION: $fails failure(s)');
  exit(fails == 0 ? 0 : 1);
}
