// The MVP wndproc door (DolphinDart DD7).
//
// A real window class whose WndProc reflects messages into the image, and the
// natives to drive it. This is the seam Dolphin's MVP framework will sit on:
// Win32 sends are SYNCHRONOUS, so a handler that calls CreateWindowExW /
// SendMessageW / DestroyWindow re-enters the image from inside its own call, to
// arbitrary depth. The door must survive that; the spike measures whether it
// does before any GUI code leans on it.
//
// WHY THIS IS SEPARATE FROM THE VIEW-SERVER. win_view.h documents that the
// view-server's callback dispatcher SKIPS re-entrant dispatch, because
// "re-entering Dart (Dart_EnterScope) while Apply holds Dart handles corrupts
// the scope stack". That is a real constraint, and it is a constraint on
// HOLDING HANDLES ACROSS A RE-ENTRY — not on nesting as such. The door is
// entered from the OS message pump with no enclosing native frame of ours
// holding handles, so it can nest where Apply cannot. Keeping it in its own
// file keeps that distinction visible instead of encoding it as a flag.
//
// Discipline, in one line: enter a scope, invoke, exit the scope, and hold NO
// Dart handle across the invoke.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>

#include <cstdio>
#include <cstring>

#include "include/dart_api.h"

namespace dart {
namespace bin {

namespace {

const wchar_t* kMvpClass = L"DolphinDartMvpDoor";
const wchar_t* kMvpTopClass = L"DolphinDartMvpWindow";
// WM_APP is the first message id safe for application use.
const UINT kMvpCall = WM_APP + 1;
// Reflected message kinds, passed to the image as wParam of the funnel.
const int kKindMessage = 0;   // the spike's own recursion probe
const int kKindPaint   = 1;
const int kKindCommand = 2;
const int kKindDestroy = 3;

Dart_PersistentHandle g_mvp_dispatch = nullptr;
bool g_class_registered = false;

// Live depth of image entries through the door. Reported to the image so a
// spike can assert the nesting really happened rather than inferring it.
int g_depth = 0;
int g_max_depth = 0;
// Set when an entry answers its default because the image raised. Counted, not
// swallowed silently.
int g_contained = 0;

// GENERATION (prior-art G-i). A world reload leaves real HWNDs alive whose
// image-side owners are gone. Every window records the generation it was made
// in; a message to a stale window answers DefWindowProcW instead of reaching an
// image that no longer knows about it. Bumped by mvpBumpGeneration.
int g_generation = 1;
int g_paint_faults = 0;
bool g_top_registered = false;

// The accelerator table the pump consults, and the window it belongs to.
HACCEL g_accel = nullptr;
HWND g_accel_hwnd = nullptr;

// --- THE STORM CENSUS (DolphinDart DD9) -------------------------------------
//
// Resize relayout is this sprint's gate, and resize is exactly where the
// high-rate messages live. WM_MOUSEMOVE, WM_NCHITTEST, WM_SETCURSOR and
// WM_SIZE arrive in bursts during a drag; if each one costs an image entry,
// the drag stops being interactive. The prior art measured a door entry at
// ~154x DefWindowProcW on WINARM, which is the kind of number that decides an
// architecture — so measure it HERE, on this door, before any View code
// depends on the answer.
//
// Two instruments, both off the hot path when unused:
//   * a per-message CENSUS, so we know what actually arrives and how often;
//   * a routing SWITCH, so the same message can be timed both ways in one run.
// The switch is the honest way to do the comparison: same window, same
// messages, same process, one flag apart.
const int kKindStorm = 4;      // a storm message reflected, when routing is on
const int kKindWinMsg = 5;     // a reflected Windows message: (msg, wParam, lParam)
// WM_NCCREATE: a window has just come into existence. Dolphin binds its view
// to the HWND at exactly this moment, from the slot the creating process was
// holding it in.
const int kKindCreate = 6;

// Census slots. Indexed by kStormMsgs order; the last slot is everything else.
enum {
  kStormMouseMove = 0,
  kStormNcHitTest,
  kStormSetCursor,
  kStormSize,
  kStormMoving,
  kStormEraseBkgnd,
  kStormOther,
  kStormSlots
};
const UINT kStormMsgs[] = {
    WM_MOUSEMOVE, WM_NCHITTEST, WM_SETCURSOR,
    WM_SIZE,      WM_MOVING,    WM_ERASEBKGND,
};
int64_t g_storm_counts[kStormSlots] = {0};
int64_t g_storm_total = 0;
// When false (the default) a storm message never enters the image — it goes
// straight to DefWindowProcW, which is what the door has always done.
bool g_storm_route = false;

int StormSlot(UINT msg) {
  for (int i = 0; i < kStormOther; i++) {
    if (kStormMsgs[i] == msg) return i;
  }
  return kStormOther;
}

// --- the routed-message set (DD9) -------------------------------------------
//
// Which messages the image wants reflected. Supplied by the image (Dolphin's
// buildMessageMap is exactly this list) and empty by default, so a door with
// nobody listening behaves as it always has.
//
// A flat BITMAP over the low message ids rather than a set: the lookup is on
// EVERY message that reaches the default branch, so it must be a load and a
// mask, not a search. Windows' own messages all sit below WM_USER (0x400);
// anything above falls back to a small linear scan of the registered ids,
// which is where the handful of WM_APP/registered messages live.
const int kRoutedBitmapBits = 0x400;
uint32_t g_routed_bitmap[kRoutedBitmapBits / 32] = {0};
UINT g_routed_high[64] = {0};
int g_routed_high_count = 0;

inline bool IsRoutedMessage(UINT msg) {
  if (msg < kRoutedBitmapBits) {
    return (g_routed_bitmap[msg >> 5] & (1u << (msg & 31))) != 0;
  }
  for (int i = 0; i < g_routed_high_count; i++) {
    if (g_routed_high[i] == msg) return true;
  }
  return false;
}

LRESULT CALLBACK MvpWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
  if (msg != kMvpCall || g_mvp_dispatch == nullptr) {
    return DefWindowProcW(hwnd, msg, wp, lp);
  }
  g_depth++;
  if (g_depth > g_max_depth) g_max_depth = g_depth;

  int64_t result = 0;
  Dart_EnterScope();
  {
    // CHANNEL, then argument. The channel is a separate value from the payload
    // precisely so the two cannot collide: routing on the payload made a
    // depth-3 recursion probe look like a WM_DESTROY.
    Dart_Handle fn = Dart_HandleFromPersistent(g_mvp_dispatch);
    Dart_Handle a[5] = { Dart_NewInteger(kKindMessage),
                         Dart_NewInteger((int64_t)(intptr_t)hwnd),
                         Dart_NewInteger((int64_t)wp), Dart_NewInteger(0),
                         Dart_NewInteger(0) };
    Dart_Handle r = Dart_InvokeClosure(fn, 5, a);
    if (Dart_IsError(r)) {
      // CONTAINMENT. A raise inside the image must not escape into the OS: the
      // pump has to keep pumping, and Win32 has no notion of a Smalltalk
      // exception. The entry answers its default and the error is dropped HERE,
      // at the boundary that owns it — which is also why the count exists, so
      // "contained" can never be confused with "did not happen".
      //
      // Deliberately NOT Dart_PropagateError: that would unwind through the
      // WndProc's own C++ frame and out through Windows' dispatch, which owns
      // this stack.
      g_contained++;
      // AND SAY WHAT IT WAS. The count alone tells you something raised and
      // nothing about what — and an exception raised inside a WM_NOTIFY
      // handler is contained TWICE (the image's own `on: Error do:` and then
      // here), so removing the image-side guard to get a stack just moves the
      // silence. DD11 spent a sitting on `does not understand truncated` with
      // no receiver, no selector and no frame, because this line dropped it.
      //
      // Rate-limited: a notification storm would otherwise write thousands of
      // identical lines and bury the run.
      if (g_contained <= 8) {
        fprintf(stderr, "[door] contained: %s\n", Dart_GetError(r));
        fflush(stderr);
      }
      result = 0;
    } else if (Dart_IsInteger(r)) {
      Dart_IntegerToInt64(r, &result);
    }
  }
  Dart_ExitScope();
  g_depth--;
  return (LRESULT)result;
}

// Call the image funnel: (kind, hwnd, a, b, c).
//
// FIVE arguments. The middle three carry the payload — DD9 widened them from
// one to three so a reflected Windows message could pass (msg, wParam,
// lParam) to Dolphin's `buildMessageMap` dispatch.
//
// THE HWND IS THE DD10 ADDITION, and it is what makes more than one window
// possible. Without it the image can only ask "which message?", never "which
// WINDOW?", so `UiSession` had to route everything to whichever view was
// registered last. That is invisible while exactly one window exists and
// wrong the moment two do: a shell owning an EDIT control needs WM_COMMAND to
// reach the control's OWNER, and stacked modal dialogs (the DD12 goal gate)
// cannot work at all without it. The registry to route through — `viewFor:` —
// already existed and was already maintained; the HWND is the piece that was
// missing.
//
// Widening rather than packing keeps channel, window and payload separate,
// the same discipline that stopped a depth-3 recursion probe reading as a
// WM_DESTROY.
//
// Answers false when the image raised (contained here) — the caller then takes
// its default. `*handled` distinguishes "the image answered nothing" (Dart
// null, i.e. this message is not in its map) from "the image answered 0",
// which is a perfectly ordinary LRESULT.
bool CallImage(int64_t kind, HWND hwnd, int64_t a0, int64_t b0, int64_t c0,
               int64_t* out, bool* handled) {
  if (handled != nullptr) *handled = false;
  if (g_mvp_dispatch == nullptr) return false;
  bool ok = true;
  g_depth++;
  if (g_depth > g_max_depth) g_max_depth = g_depth;
  Dart_EnterScope();
  {
    Dart_Handle fn = Dart_HandleFromPersistent(g_mvp_dispatch);
    Dart_Handle a[5] = { Dart_NewInteger(kind),
                         Dart_NewInteger((int64_t)(intptr_t)hwnd),
                         Dart_NewInteger(a0), Dart_NewInteger(b0),
                         Dart_NewInteger(c0) };
    Dart_Handle r = Dart_InvokeClosure(fn, 5, a);
    if (Dart_IsError(r)) {
      g_contained++;
      // Same reason as the other containment site: the count says something
      // raised, the message says WHAT. This is the funnel every reflected
      // message goes through, WM_NOTIFY included.
      if (g_contained <= 8) {
        fprintf(stderr, "[door] contained: %s\n", Dart_GetError(r));
        fflush(stderr);
      }
      ok = false;
    } else if (Dart_IsInteger(r)) {
      if (handled != nullptr) *handled = true;
      if (out != nullptr) Dart_IntegerToInt64(r, out);
    }
  }
  Dart_ExitScope();
  g_depth--;
  return ok;
}

// The VISIBLE window's WndProc. Same door, real messages.
LRESULT CALLBACK MvpTopWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
  // GENERATION GUARD (prior-art G-i): a window outliving the image that made it
  // must not reach the image at all. The generation is stashed in the window's
  // own user data at creation, so this costs one load per message.
  const LONG_PTR gen = GetWindowLongPtrW(hwnd, GWLP_USERDATA);
  const bool live = (gen == (LONG_PTR)g_generation);

  switch (msg) {
    case WM_NCCREATE: {
      // STAMP AND BIND. Every window this WndProc serves gets the current
      // generation here, whoever created it — `mvpCreateTopWindow` stamps its
      // own, but a window created by Dolphin's `View>>create` through
      // CreateWindowExW has nobody else to do it, and an unstamped window
      // fails the generation guard on every later message.
      //
      // Then tell the image, because this is Dolphin's binding moment: it is
      // inside CreateWindowExW, so the view is still sitting in the slot the
      // creating code put it in and the HWND is not yet known to anyone else.
      SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)g_generation);
      CallImage(kKindCreate, hwnd, 0, 0, 0, nullptr, nullptr);
      return DefWindowProcW(hwnd, msg, wp, lp);
    }
    case WM_PAINT: {
      PAINTSTRUCT ps;
      HDC hdc = BeginPaint(hwnd, &ps);
      bool ok = false;
      if (live) {
        ok = CallImage(kKindPaint, hwnd, (int64_t)(intptr_t)hdc, 0, 0,
                       nullptr, nullptr);
      }
      if (!ok) {
        // THE BACKSTOP (prior-art G-b). If the image raised, the update region
        // is still invalid, so Windows re-posts WM_PAINT immediately and the
        // pump spins at 100% forever. EndPaint validates what BeginPaint
        // claimed, but only for the region it was given — validate the whole
        // window so a partially-painted failure cannot re-arm itself.
        g_paint_faults++;
        ValidateRect(hwnd, nullptr);
      }
      EndPaint(hwnd, &ps);
      return 0;
    }
    case WM_COMMAND: {
      if (!live) return DefWindowProcW(hwnd, msg, wp, lp);
      // TWO CONTRACTS SHARE THIS MESSAGE, and the routed one wins.
      //
      // Dolphin's `View class >> buildMessageMap` maps 273 to
      // `wmCommand:wParam:lParam:`, which needs the FULL wParam and lParam to
      // tell the three cases apart:
      //
      //     lParam null  -> a menu command; look up a CommandDescription by
      //                     its id and send `onCommand:` with THAT
      //     otherwise    -> a control notification; find the control by its
      //                     hwnd (lParam) and send `command:id:`
      //
      // The kKindCommand channel below carries only LOWORD(wParam) — the
      // control id — which is all the DD7 probes ever wanted, and is NOT
      // enough to make that distinction. Sending it to a translated view
      // reached Dolphin's `onCommand: aCommandDescription` with an INTEGER,
      // and every command died on `'int' has no instance method
      // queryCommand_` inside the contained handler-error path.
      //
      // So: offer the routed path first. A gate that installs Dolphin's
      // message map (`routeMessagesFrom: View`) gets Dolphin's own handler
      // with the real arguments; a spike window that routes nothing keeps the
      // narrow channel it was written against.
      if (IsRoutedMessage(msg)) {
        int64_t out = 0;
        bool handled = false;
        if (CallImage(kKindWinMsg, hwnd, (int64_t)msg, (int64_t)wp,
                      (int64_t)lp, &out, &handled) &&
            handled) {
          return (LRESULT)out;
        }
        return DefWindowProcW(hwnd, msg, wp, lp);
      }
      // A child control notifying its parent: the control id is LOWORD(wp).
      // The command's payload is the CONTROL id; the hwnd is the OWNER the
      // notification arrived at, which is the window that has to handle it.
      CallImage(kKindCommand, hwnd, (int64_t)LOWORD(wp), 0, 0, nullptr,
                nullptr);
      return 0;
    }
    case WM_DESTROY:
      if (live) CallImage(kKindDestroy, hwnd, 0, 0, 0, nullptr, nullptr);
      return 0;
    default: {
      // The storm census (DD9). Counting is two loads and a store — cheap
      // enough to leave on, and the point is to know the real message mix
      // rather than to reason about it. Routing stays OFF unless a probe
      // turns it on, so this branch is DefWindowProcW as before by default.
      const int slot = StormSlot(msg);
      g_storm_counts[slot]++;
      g_storm_total++;
      // THE ROUTED SET (DD9). Dolphin's `View class >> buildMessageMap` is an
      // explicit per-class list of the messages it wants; the image hands that
      // list here once and everything outside it goes straight to
      // DefWindowProcW. The storm measurement is what makes this the design
      // and not a preference: a routed message costs ~26 microseconds, so the
      // only lever is the message COUNT, and the corpus supplies the minimal
      // count for free.
      //
      // The image answering NOTHING (Dart null) means "not in my map after
      // all" and falls through to DefWindowProcW — distinct from answering 0,
      // which is an ordinary LRESULT that many messages return.
      if (live && IsRoutedMessage(msg)) {
        int64_t out = 0;
        bool handled = false;
        if (CallImage(kKindWinMsg, hwnd, (int64_t)msg, (int64_t)wp,
                      (int64_t)lp, &out, &handled) &&
            handled) {
          return (LRESULT)out;
        }
        return DefWindowProcW(hwnd, msg, wp, lp);
      }
      if (g_storm_route && live && slot != kStormOther) {
        CallImage(kKindStorm, hwnd, (int64_t)msg, (int64_t)wp, (int64_t)lp,
                  nullptr, nullptr);
      }
      return DefWindowProcW(hwnd, msg, wp, lp);
    }
  }
}

// ── CONTROL SUBCLASSING (DD10) ──────────────────────────────────────────────
//
// A Win32 control — EDIT, BUTTON, LISTBOX — belongs to a class comctl
// registered, whose WndProc is what MAKES it that control: the caret, the
// selection, the keyboard handling, all of it. Dolphin gets its own code into
// that stream the way every Windows program does, by SUBCLASSING: swap the
// window's WndProc for its own and keep the original to chain to.
//
// The mechanism here is Dolphin's, unchanged, from `UI.View`:
//
//     subclassWindow
//         | dolphinWndProc oldProc |
//         dolphinWndProc := VM getWndProc.
//         (oldProc := self setWndProc: dolphinWndProc) = dolphinWndProc
//             ifFalse: [self oldWndProc: oldProc]
//
// `VM getWndProc` answers the address below; `setWndProc:` is SetWindowLongPtr
// with GWLP_WNDPROC, already in the generated floor. `UI.ControlView` keeps
// the old procedure in an ivar and chains to it from
// `defaultWindowProcessing:wParam:lParam:` via CallWindowProcW — also already
// in the floor. So the image side needs no substrate invention at all.
//
// WHERE THIS DOOR DIFFERS FROM DOLPHIN'S VM, and why the extra binding call
// exists: Dolphin's VM reflects EVERY message into the image, so its WndProc
// never needs to know the original procedure — the image always decides, and
// chains when it declines. This door routes SELECTIVELY (DD9: a routed
// message costs ~26us, so the routed set is the whole performance design), and
// a message that is not routed must still reach the CONTROL's procedure or
// the control stops working — an EDIT that never sees WM_CHAR shows no typing.
// DefWindowProcW is not a substitute: it is precisely what the control's own
// procedure replaces.
//
// So the trampoline needs the original per window. It is kept in a window
// PROPERTY rather than a C++ side table: a property dies with the window,
// which a map keyed by HWND does not — and Windows recycles handle values,
// so a stale entry would eventually answer for a different window.
static const wchar_t* kOldProcProp = L"DolphinDartOldWndProc";

LRESULT CALLBACK MvpControlWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
  WNDPROC old = (WNDPROC)GetPropW(hwnd, kOldProcProp);

  // Chain to the control's own procedure, or to DefWindowProcW only if we have
  // nothing better. The latter is the "not bound yet" case, not a design
  // choice: between SetWindowLongPtr and the image binding the old procedure
  // there is a window of a few instructions, and a message can arrive in it.
  auto chain = [&]() -> LRESULT {
    if (old != nullptr) return CallWindowProcW(old, hwnd, msg, wp, lp);
    return DefWindowProcW(hwnd, msg, wp, lp);
  };

  const LONG_PTR gen = GetWindowLongPtrW(hwnd, GWLP_USERDATA);
  const bool live = (gen == (LONG_PTR)g_generation);

  // WM_NCDESTROY is the last message any window receives, so it is the only
  // safe place to drop the property. Leaving it set would leak an atom per
  // control for the life of the process.
  if (msg == WM_NCDESTROY) {
    LRESULT r = chain();
    RemovePropW(hwnd, kOldProcProp);
    return r;
  }

  if (live && IsRoutedMessage(msg)) {
    int64_t out = 0;
    bool handled = false;
    if (CallImage(kKindWinMsg, hwnd, (int64_t)msg, (int64_t)wp, (int64_t)lp,
                  &out, &handled) &&
        handled) {
      return (LRESULT)out;
    }
    // The image answering nothing means "not in my map after all" — the same
    // contract as the top-level door, and it chains rather than swallowing.
  }
  return chain();
}

}  // namespace

// Answer the address of the trampoline, for `VM getWndProc`.
void ST_mvpControlWndProc(Dart_NativeArguments args) {
  Dart_SetReturnValue(
      args, Dart_NewInteger((int64_t)(intptr_t)&MvpControlWndProc));
}

// Record the procedure the trampoline must chain to for this window.
//
// Called from the image with the value Dolphin's own `subclassWindow` already
// captured, so nothing is discovered twice and the image stays the authority
// on what it subclassed. Answers true when the window accepted the property.
void ST_mvpBindOldProc(Dart_NativeArguments args) {
  int64_t h = 0, proc = 0;
  Dart_GetNativeIntegerArgument(args, 0, &h);
  Dart_GetNativeIntegerArgument(args, 1, &proc);
  HWND hwnd = (HWND)(intptr_t)h;
  bool ok = false;
  if (hwnd != nullptr && IsWindow(hwnd)) {
    // Stamp the generation too. A control created through Dolphin's
    // `View>>create` goes to comctl's WndProc, not ours, so it never saw our
    // WM_NCCREATE and carries no generation — and an unstamped window fails
    // the guard on every message, which would route nothing at all.
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)g_generation);
    ok = SetPropW(hwnd, kOldProcProp, (HANDLE)(intptr_t)proc) != 0;
  }
  Dart_SetReturnValue(args, Dart_NewBoolean(ok));
}

// COMMON CONTROLS must be initialized before the first one is CREATED, on the
// UI thread. `InitCommonControlsEx` is what registers the comctl32 window
// classes — SysListView32, SysTreeView32, SysTabControl32 and the rest — and
// without it `CreateWindowExW` for any of them fails with ERROR_CANNOT_FIND_WND_CLASS.
//
// PUT HERE rather than in a lazily-hit native, which is the DD11 brief's own
// trap: the first control created decides whether the whole comctl32 wave
// works, and a lazy call can end up on the wrong thread or after the fact.
// This runs on the same path that registers the door's own window class, so
// it cannot be skipped by any route that makes a window.
//
// ICC_WIN95_CLASSES covers list/tree/tab/status/toolbar/progress/trackbar —
// everything DD11 needs. Asking for classes that are already registered is
// harmless and idempotent.
bool g_comctl_ready = false;

bool EnsureCommonControls() {
  if (g_comctl_ready) return true;
  INITCOMMONCONTROLSEX icc;
  ZeroMemory(&icc, sizeof(icc));
  icc.dwSize = sizeof(icc);
  icc.dwICC = ICC_WIN95_CLASSES | ICC_DATE_CLASSES | ICC_USEREX_CLASSES |
              ICC_COOL_CLASSES | ICC_INTERNET_CLASSES | ICC_STANDARD_CLASSES |
              ICC_LINK_CLASS;
  g_comctl_ready = (InitCommonControlsEx(&icc) != FALSE);
  return g_comctl_ready;
}

bool EnsureTopClass() {
  EnsureCommonControls();
  if (g_top_registered) return true;
  WNDCLASSEXW wc;
  ZeroMemory(&wc, sizeof(wc));
  wc.cbSize = sizeof(wc);
  wc.lpfnWndProc = MvpTopWndProc;
  wc.hInstance = GetModuleHandleW(nullptr);
  wc.lpszClassName = kMvpTopClass;
  wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
  g_top_registered = (RegisterClassExW(&wc) != 0);
  return g_top_registered;
}

bool EnsureClass() {
  if (g_class_registered) return true;
  WNDCLASSEXW wc;
  ZeroMemory(&wc, sizeof(wc));
  wc.cbSize = sizeof(wc);
  wc.lpfnWndProc = MvpWndProc;
  wc.hInstance = GetModuleHandleW(nullptr);
  wc.lpszClassName = kMvpClass;
  g_class_registered = (RegisterClassExW(&wc) != 0);
  return g_class_registered;
}

int64_t ArgInt(Dart_NativeArguments args, int i) {
  int64_t v = 0;
  Dart_IntegerToInt64(Dart_GetNativeArgument(args, i), &v);
  return v;
}

// A UTF-8 string argument. The pointer is owned by the Dart API and stays
// valid for the duration of the native call, which is all `ST_mvpCapture`
// needs it for (it opens the file and is done).
const char* ArgStr(Dart_NativeArguments args, int i) {
  const char* p = nullptr;
  Dart_Handle h = Dart_GetNativeArgument(args, i);
  if (Dart_IsError(Dart_StringToCString(h, &p))) return nullptr;
  return p;
}

// _mvpRegisterDispatch(Function f) — the single funnel, as the view-server does.
void ST_mvpRegisterDispatch(Dart_NativeArguments args) {
  Dart_Handle f = Dart_GetNativeArgument(args, 0);
  if (g_mvp_dispatch != nullptr) Dart_DeletePersistentHandle(g_mvp_dispatch);
  g_mvp_dispatch = Dart_NewPersistentHandle(f);
  Dart_SetReturnValue(args, Dart_True());
}

// A MESSAGE-ONLY window (HWND_MESSAGE): no pixels, no pump of its own, but
// SendMessageW to it is genuinely synchronous and re-entrant — the exact shape
// a real MVP handler creates when it calls CreateWindowExW mid-handler. The
// spike therefore measures the production path, not a simulation of it.
void ST_mvpCreateWindow(Dart_NativeArguments args) {
  if (!EnsureClass()) {
    Dart_SetReturnValue(args, Dart_NewInteger(0));
    return;
  }
  HWND h = CreateWindowExW(0, kMvpClass, L"", 0, 0, 0, 0, 0,
                           HWND_MESSAGE, nullptr, GetModuleHandleW(nullptr),
                           nullptr);
  Dart_SetReturnValue(args, Dart_NewInteger((int64_t)(intptr_t)h));
}

void ST_mvpDestroyWindow(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  Dart_SetReturnValue(args, Dart_NewBoolean(h != nullptr && DestroyWindow(h)));
}

// The synchronous send. Returns whatever the image answered.
void ST_mvpSend(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  WPARAM wp = (WPARAM)ArgInt(args, 1);
  LPARAM lp = (LPARAM)ArgInt(args, 2);
  LRESULT r = SendMessageW(h, kMvpCall, wp, lp);
  Dart_SetReturnValue(args, Dart_NewInteger((int64_t)r));
}

// (currentDepth, maxDepthSeen, containedCount) — the spike's instrument.
void ST_mvpStats(Dart_NativeArguments args) {
  Dart_Handle list = Dart_NewList(3);
  Dart_ListSetAt(list, 0, Dart_NewInteger(g_depth));
  Dart_ListSetAt(list, 1, Dart_NewInteger(g_max_depth));
  Dart_ListSetAt(list, 2, Dart_NewInteger(g_contained));
  Dart_SetReturnValue(args, list);
}

void ST_mvpResetStats(Dart_NativeArguments args) {
  g_max_depth = 0;
  g_contained = 0;
  g_paint_faults = 0;
  Dart_SetReturnValue(args, Dart_True());
}

// A VISIBLE top-level window, stamped with the current generation.
void ST_mvpCreateTopWindow(Dart_NativeArguments args) {
  if (!EnsureTopClass()) {
    Dart_SetReturnValue(args, Dart_NewInteger(0));
    return;
  }
  int64_t w = ArgInt(args, 0), h = ArgInt(args, 1);
  HWND hwnd = CreateWindowExW(0, kMvpTopClass, L"DolphinDart",
                              WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT,
                              (int)w, (int)h, nullptr, nullptr,
                              GetModuleHandleW(nullptr), nullptr);
  if (hwnd != nullptr) SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)g_generation);
  Dart_SetReturnValue(args, Dart_NewInteger((int64_t)(intptr_t)hwnd));
}

// A child BUTTON whose control id is the ticket the image will see in WM_COMMAND.
void ST_mvpCreateButton(Dart_NativeArguments args) {
  HWND parent = (HWND)(intptr_t)ArgInt(args, 0);
  int64_t id = ArgInt(args, 1);
  HWND b = CreateWindowExW(0, L"BUTTON", L"Press",
                           WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                           10, 10, 120, 30, parent, (HMENU)(intptr_t)id,
                           GetModuleHandleW(nullptr), nullptr);
  Dart_SetReturnValue(args, Dart_NewInteger((int64_t)(intptr_t)b));
}

void ST_mvpShow(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  ShowWindow(h, SW_SHOW);
  UpdateWindow(h);   // synchronous WM_PAINT, so a paint fault surfaces NOW
  Dart_SetReturnValue(args, Dart_True());
}

// CAPTURE a window to a 24-bit BMP file, and answer the pixel dimensions.
//
// WHY THIS EXISTS. Every GUI conclusion in this port so far has been an
// INFERENCE: a handle is non-zero, a control answers its class name, an item
// count comes back from TVM_GETCOUNT. All true, and all of it was true while
// the window on screen was an unpainted frame — because the gates pump once,
// at the end, so WM_PAINT never ran. An assertion cannot tell the difference
// between "drew correctly" and "never drew". A picture can.
//
// PrintWindow FIRST, BitBlt as the fallback. PrintWindow asks the window to
// render itself into the DC, which works for a window that is occluded or has
// never been shown; BitBlt copies whatever is actually on the screen DC, which
// is what a human would see. Trying PrintWindow first and falling back means
// an occluded window still yields a picture rather than a black rectangle.
//
// BMP because it needs no encoder: a 14-byte file header, a 40-byte info
// header, and bottom-up BGR rows padded to 4 bytes. tools/shot.py converts it
// to PNG so it can be looked at.
void ST_mvpCapture(Dart_NativeArguments args) {
  HWND h = reinterpret_cast<HWND>(static_cast<intptr_t>(ArgInt(args, 0)));
  const char* path = ArgStr(args, 1);
  int64_t client_only = ArgInt(args, 2);
  if (h == nullptr || !IsWindow(h) || path == nullptr) {
    Dart_SetReturnValue(args, Dart_NewInteger(0));
    return;
  }
  RECT r;
  if (client_only != 0 ? !GetClientRect(h, &r) : !GetWindowRect(h, &r)) {
    Dart_SetReturnValue(args, Dart_NewInteger(0));
    return;
  }
  const int w = r.right - r.left;
  const int ht = r.bottom - r.top;
  if (w <= 0 || ht <= 0) {
    Dart_SetReturnValue(args, Dart_NewInteger(0));
    return;
  }
  HDC src = client_only != 0 ? GetDC(h) : GetWindowDC(h);
  HDC mem = CreateCompatibleDC(src);
  HBITMAP bmp = CreateCompatibleBitmap(src, w, ht);
  HGDIOBJ old = SelectObject(mem, bmp);
  // PW_RENDERFULLCONTENT = 2 — needed for a window that is partly occluded.
  if (!PrintWindow(h, mem, client_only != 0 ? 1 : 0)) {
    BitBlt(mem, 0, 0, w, ht, src, 0, 0, SRCCOPY);
  }

  BITMAPINFOHEADER bi;
  ZeroMemory(&bi, sizeof(bi));
  bi.biSize = sizeof(bi);
  bi.biWidth = w;
  bi.biHeight = ht;          // positive = bottom-up, which BMP wants
  bi.biPlanes = 1;
  bi.biBitCount = 24;
  bi.biCompression = BI_RGB;
  const int stride = ((w * 3) + 3) & ~3;
  const size_t bytes = static_cast<size_t>(stride) * ht;
  unsigned char* pixels = new unsigned char[bytes];
  const int got = GetDIBits(mem, bmp, 0, ht, pixels,
                            reinterpret_cast<BITMAPINFO*>(&bi), DIB_RGB_COLORS);

  int64_t answer = 0;
  if (got != 0) {
    FILE* f = nullptr;
    fopen_s(&f, path, "wb");
    if (f != nullptr) {
      const uint32_t offbits = 14 + 40;
      const uint32_t total = offbits + static_cast<uint32_t>(bytes);
      unsigned char fh[14] = {0};
      fh[0] = 'B'; fh[1] = 'M';
      memcpy(fh + 2, &total, 4);
      memcpy(fh + 10, &offbits, 4);
      fwrite(fh, 1, 14, f);
      fwrite(&bi, 1, 40, f);
      fwrite(pixels, 1, bytes, f);
      fclose(f);
      // width and height packed into one integer, so one call answers both.
      answer = (static_cast<int64_t>(w) << 20) | static_cast<int64_t>(ht);
    }
  }
  delete[] pixels;
  SelectObject(mem, old);
  DeleteObject(bmp);
  DeleteDC(mem);
  ReleaseDC(h, src);
  Dart_SetReturnValue(args, Dart_NewInteger(answer));
}

// Pump every pending message and answer how many were dispatched. The image
// drives the pump so a test can bound it; a real app loop is DD9's problem.
void ST_mvpPump(Dart_NativeArguments args) {
  int64_t budget = ArgInt(args, 0);
  int64_t n = 0;
  MSG m;
  while (n < budget && PeekMessageW(&m, nullptr, 0, 0, PM_REMOVE)) {
    // ACCELERATORS ARE A PUMP CONCERN (DD10). TranslateAcceleratorW turns a
    // key chord into the WM_COMMAND its table names and dispatches it itself,
    // so it must run BEFORE TranslateMessage/DispatchMessageW and the message
    // must then be dropped — passing it on as well would deliver both the
    // command and the raw keystroke. There is nowhere else this can live: the
    // pump is native, so an image-side accelerator table would never see the
    // MSG.
    if (g_accel != nullptr && g_accel_hwnd != nullptr &&
        TranslateAcceleratorW(g_accel_hwnd, g_accel, &m)) {
      n++;
      continue;
    }
    TranslateMessage(&m);
    DispatchMessageW(&m);
    n++;
  }
  Dart_SetReturnValue(args, Dart_NewInteger(n));
}

// Install the accelerator table the pump consults, for one window. Passing 0
// for either clears it — a torn-down window must not leave its accelerators
// live, since TranslateAcceleratorW on a dead HWND is undefined.
void ST_mvpSetAccelerators(Dart_NativeArguments args) {
  g_accel_hwnd = (HWND)(intptr_t)ArgInt(args, 0);
  g_accel = (HACCEL)(intptr_t)ArgInt(args, 1);
  if (g_accel_hwnd == nullptr || g_accel == nullptr) {
    g_accel_hwnd = nullptr;
    g_accel = nullptr;
  }
  Dart_SetReturnValue(args, Dart_NewBoolean(g_accel != nullptr));
}

// Send a real WM_COMMAND, as a button click does.
void ST_mvpClick(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  int64_t id = ArgInt(args, 1);
  SendMessageW(h, WM_COMMAND, MAKEWPARAM((WORD)id, BN_CLICKED), 0);
  Dart_SetReturnValue(args, Dart_True());
}

void ST_mvpInvalidate(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  InvalidateRect(h, nullptr, TRUE);
  Dart_SetReturnValue(args, Dart_True());
}

// Bump the generation: every existing window becomes stale and stops reaching
// the image, which is what a world reload needs.
void ST_mvpBumpGeneration(Dart_NativeArguments args) {
  g_generation++;
  Dart_SetReturnValue(args, Dart_NewInteger(g_generation));
}

// Registry hygiene (UiSession purgeDeadWindows): is this handle still a window?
void ST_mvpIsWindow(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  Dart_SetReturnValue(args, Dart_NewBoolean(h != nullptr && IsWindow(h)));
}

// The door's top-level window class name. `View class >> winClassName`
// answers this, so Dolphin's own creation path builds windows whose WndProc
// is ours.
void ST_mvpTopClassName(Dart_NativeArguments args) {
  // REGISTER IT BEFORE ANSWERING. The door registers its window class lazily,
  // and until DD10 the only path in was `mvpCreateTopWindow`, which does it
  // itself. Dolphin's own `View>>create` asks for the NAME and then calls
  // CreateWindowExW directly — so an unregistered class answered 0 with
  // GetLastError 0, the least informative failure Win32 offers. A name for a
  // class that does not exist is not a useful answer.
  EnsureTopClass();
  Dart_SetReturnValue(args, Dart_NewStringFromUTF8(
      reinterpret_cast<const uint8_t*>("DolphinDartMvpWindow"),
      strlen("DolphinDartMvpWindow")));
}

void ST_mvpPaintFaults(Dart_NativeArguments args) {
  Dart_SetReturnValue(args, Dart_NewInteger(g_paint_faults));
}

// --- the storm probe's instruments (DD9) ------------------------------------

// (mouseMove, ncHitTest, setCursor, size, moving, eraseBkgnd, other, total)
void ST_mvpStormCounts(Dart_NativeArguments args) {
  Dart_Handle list = Dart_NewList(kStormSlots + 1);
  for (int i = 0; i < kStormSlots; i++) {
    Dart_ListSetAt(list, i, Dart_NewInteger(g_storm_counts[i]));
  }
  Dart_ListSetAt(list, kStormSlots, Dart_NewInteger(g_storm_total));
  Dart_SetReturnValue(args, list);
}

// Replace the routed-message set with the given list of message ids. Answers
// how many were accepted — the caller can compare against what it sent, since
// silently dropping half a message map would look exactly like a view whose
// handlers never fire.
void ST_mvpSetRoutedMessages(Dart_NativeArguments args) {
  for (size_t i = 0; i < sizeof(g_routed_bitmap) / sizeof(g_routed_bitmap[0]);
       i++) {
    g_routed_bitmap[i] = 0;
  }
  g_routed_high_count = 0;
  Dart_Handle list = Dart_GetNativeArgument(args, 0);
  intptr_t n = 0;
  int64_t accepted = 0;
  if (!Dart_IsError(Dart_ListLength(list, &n))) {
    for (intptr_t i = 0; i < n; i++) {
      Dart_Handle e = Dart_ListGetAt(list, i);
      int64_t v = 0;
      if (Dart_IsError(e) || !Dart_IsInteger(e)) continue;
      if (Dart_IsError(Dart_IntegerToInt64(e, &v))) continue;
      if (v < 0) continue;
      const UINT msg = (UINT)v;
      if (msg < kRoutedBitmapBits) {
        g_routed_bitmap[msg >> 5] |= (1u << (msg & 31));
        accepted++;
      } else if (g_routed_high_count <
                 (int)(sizeof(g_routed_high) / sizeof(g_routed_high[0]))) {
        g_routed_high[g_routed_high_count++] = msg;
        accepted++;
      }
    }
  }
  Dart_SetReturnValue(args, Dart_NewInteger(accepted));
}

// Send an ARBITRARY message and answer its LRESULT. `ST_mvpSend` is hardwired
// to the door's private kMvpCall; this is how a probe can check that a routed
// message's return value really comes back out through the WndProc — which is
// the difference between "the handler ran" and "the handler's answer is what
// Windows saw".
void ST_mvpSendMsg(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  UINT msg = (UINT)ArgInt(args, 1);
  WPARAM wp = (WPARAM)ArgInt(args, 2);
  LPARAM lp = (LPARAM)ArgInt(args, 3);
  Dart_SetReturnValue(
      args, Dart_NewInteger((int64_t)SendMessageW(h, msg, wp, lp)));
}

void ST_mvpRoutedMessageCount(Dart_NativeArguments args) {
  int64_t n = g_routed_high_count;
  for (size_t i = 0; i < sizeof(g_routed_bitmap) / sizeof(g_routed_bitmap[0]);
       i++) {
    uint32_t w = g_routed_bitmap[i];
    while (w) { n += (w & 1); w >>= 1; }
  }
  Dart_SetReturnValue(args, Dart_NewInteger(n));
}

void ST_mvpResetStormCounts(Dart_NativeArguments args) {
  for (int i = 0; i < kStormSlots; i++) g_storm_counts[i] = 0;
  g_storm_total = 0;
  Dart_SetReturnValue(args, Dart_True());
}

// Route storm messages into the image, or not. The probe times the SAME
// message both ways so the comparison has one variable.
void ST_mvpSetStormRouting(Dart_NativeArguments args) {
  bool on = false;
  Dart_BooleanValue(Dart_GetNativeArgument(args, 0), &on);
  g_storm_route = on;
  Dart_SetReturnValue(args, Dart_NewBoolean(on));
}

// Send `msg` to `hwnd` `n` times and answer the elapsed NANOSECONDS. Timed in
// native code deliberately: a Dart-side loop would time the FFI call overhead
// as well as the wndproc, and the whole question is what the wndproc costs.
void ST_mvpStormBurst(Dart_NativeArguments args) {
  HWND h = (HWND)(intptr_t)ArgInt(args, 0);
  UINT msg = (UINT)ArgInt(args, 1);
  int64_t n = ArgInt(args, 2);
  LARGE_INTEGER freq, t0, t1;
  QueryPerformanceFrequency(&freq);
  QueryPerformanceCounter(&t0);
  for (int64_t i = 0; i < n; i++) {
    SendMessageW(h, msg, 0, 0);
  }
  QueryPerformanceCounter(&t1);
  const int64_t ticks = t1.QuadPart - t0.QuadPart;
  Dart_SetReturnValue(
      args, Dart_NewInteger(freq.QuadPart > 0
                                ? (ticks * 1000000000LL) / freq.QuadPart
                                : 0));
}

}  // namespace bin
}  // namespace dart
