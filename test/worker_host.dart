// The Dart host for the worker doctrine (DolphinDart DD10).
//
// `docs/WORKERS.md` settles why; `st/dolphin_compat/11_worker.mst` is the
// image side. This is the transport, and it lives in ORDINARY Dart rather
// than in the bootstrap `dart:cocoa` library on purpose: isolates are the
// run loop's business, not the Smalltalk runtime's.
//
// THE RUN LOOP IS DART'S, and that is forced rather than chosen. `UiSession
// pump` drains Win32 messages through a native call and returns; it never runs
// Dart's event loop, so an isolate reply can only be delivered when control is
// back in Dart. The loop is therefore: pump a slice of Win32, yield to Dart,
// repeat. Both halves get their turn and neither blocks the other.
library worker_host;

import 'dart:async';
import 'dart:isolate';
import 'dart:cocoa';

/// A task an isolate can be spawned onto. Must be a TOP-LEVEL function —
/// `Isolate.spawn` cannot take a closure, which is the same restriction that
/// makes the arguments plain data.
typedef dynamic WorkerTask(dynamic arg);

/// The task table.
///
/// It is built by a TOP-LEVEL initializer, and that is a real constraint
/// rather than a style choice: a spawned isolate re-runs this library from
/// scratch with its own copy of every static, so anything registered by
/// calling a function from `main` is simply absent on the other side. Tasks
/// must therefore be visible at library-init time in BOTH isolates, which
/// means named top-level functions in a literal map.
///
/// (Letting an application add its own tasks means giving it a place in this
/// literal, or a generated one. Recorded as a limitation, not designed around
/// yet — the doctrine is what DD10 owes, and the transport is what proves it.)
final Map<String, WorkerTask> _tasks = <String, WorkerTask>{
  'slowSum': _slowSum,
  'boom': _boom,
};

/// Burn real CPU for a while and answer a checkable number. Deliberately not
/// a sleep: a sleeping isolate would prove the reply arrives, but not that the
/// UI thread kept running while another thread was actually busy.
dynamic _slowSum(dynamic arg) {
  var n = arg as int;
  var total = 0;
  for (var i = 1; i <= n; i++) {
    total += i % 7;
  }
  return total;
}

/// A task that raises, so the failure path has something to carry.
dynamic _boom(dynamic arg) {
  throw new StateError('worker task failed on purpose: $arg');
}

/// What actually runs in the spawned isolate: run the named task, send back
/// `[id, ok, valueOrMessage]`. The task name crosses as a STRING and is looked
/// up on the far side, because a function cannot be copied between isolates.
void _isolateEntry(List msg) {
  var reply = msg[0] as SendPort;
  var id = msg[1];
  var name = msg[2] as String;
  var arg = msg[3];
  try {
    var fn = _tasks[name];
    if (fn == null) {
      reply.send([id, false, 'no such worker task: $name']);
      return;
    }
    reply.send([id, true, fn(arg)]);
  } catch (e) {
    // An exception cannot cross an isolate boundary, so it becomes data here
    // and is rebuilt as an Error on the image side.
    reply.send([id, false, e.toString()]);
  }
}

int _outstanding = 0;

/// How many submissions are out with an isolate and not yet answered. The
/// pump loop uses this to know when it may stop.
int get outstanding => _outstanding;

/// Collect everything Smalltalk has queued and spawn an isolate for each.
/// Returns how many were dispatched.
int dispatchPending() {
  var pending = stClassSend0(stClassNamed('Worker'), 'takePending');
  if (pending == null) return 0;
  var n = 0;
  for (var item in pending) {
    var id = item[0], name = item[1].toString(), arg = item[2];
    _outstanding++;
    var port = new ReceivePort();
    port.listen((reply) {
      port.close();
      _outstanding--;
      var rid = reply[0], ok = reply[1], val = reply[2];
      // Back on the UI thread. This does NOT run the continuation — it hands
      // it to Smalltalk, which POSTS it. See WORKERS.md: calling it here would
      // work, look correct, and put a continuation inside a door entry.
      stClassSend2(stClassNamed('Worker'),
                   ok == true ? 'complete:with:' : 'fail:with:', rid, val);
    });
    Isolate.spawn(_isolateEntry, [port.sendPort, id, name, arg]);
    n++;
  }
  return n;
}

/// Pump Win32 and Dart alternately until `done()` answers true or the budget
/// of iterations runs out. Answers the number of iterations taken.
///
/// The `await` is the load-bearing line: without it the Dart event loop never
/// gets a turn and no isolate reply is ever delivered, however long the Win32
/// pump spins.
Future<int> runLoopUntil(bool done(), {int maxIterations: 2000,
                                       int pumpBudget: 32}) async {
  var i = 0;
  while (i < maxIterations && !done()) {
    dispatchPending();
    stRun('UiSession pump.');
    await new Future.delayed(const Duration(milliseconds: 1));
    i++;
  }
  return i;
}
