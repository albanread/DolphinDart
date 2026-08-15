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

#include <cstdio>

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
    Dart_Handle a[2] = { Dart_NewInteger(kKindMessage), Dart_NewInteger((int64_t)wp) };
    Dart_Handle r = Dart_InvokeClosure(fn, 2, a);
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
      result = 0;
    } else if (Dart_IsInteger(r)) {
      Dart_IntegerToInt64(r, &result);
    }
  }
  Dart_ExitScope();
  g_depth--;
  return (LRESULT)result;
}

// Call the image funnel. Returns false when the image raised (contained here).
bool CallImage(int64_t wp, int64_t lp, int64_t* out) {
  if (g_mvp_dispatch == nullptr) return false;
  bool ok = true;
  g_depth++;
  if (g_depth > g_max_depth) g_max_depth = g_depth;
  Dart_EnterScope();
  {
    Dart_Handle fn = Dart_HandleFromPersistent(g_mvp_dispatch);
    Dart_Handle a[2] = { Dart_NewInteger(wp), Dart_NewInteger(lp) };
    Dart_Handle r = Dart_InvokeClosure(fn, 2, a);
    if (Dart_IsError(r)) {
      g_contained++;
      ok = false;
    } else if (out != nullptr && Dart_IsInteger(r)) {
      Dart_IntegerToInt64(r, out);
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
    case WM_PAINT: {
      PAINTSTRUCT ps;
      HDC hdc = BeginPaint(hwnd, &ps);
      bool ok = false;
      if (live) ok = CallImage(kKindPaint, (int64_t)(intptr_t)hdc, nullptr);
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
    case WM_COMMAND:
      // A child control notifying its parent: the control id is LOWORD(wp).
      if (live) CallImage(kKindCommand, (int64_t)LOWORD(wp), nullptr);
      return 0;
    case WM_DESTROY:
      if (live) CallImage(kKindDestroy, 0, nullptr);
      return 0;
    default:
      return DefWindowProcW(hwnd, msg, wp, lp);
  }
}

bool EnsureTopClass() {
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

}  // namespace

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

// Pump every pending message and answer how many were dispatched. The image
// drives the pump so a test can bound it; a real app loop is DD9's problem.
void ST_mvpPump(Dart_NativeArguments args) {
  int64_t budget = ArgInt(args, 0);
  int64_t n = 0;
  MSG m;
  while (n < budget && PeekMessageW(&m, nullptr, 0, 0, PM_REMOVE)) {
    TranslateMessage(&m);
    DispatchMessageW(&m);
    n++;
  }
  Dart_SetReturnValue(args, Dart_NewInteger(n));
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

void ST_mvpPaintFaults(Dart_NativeArguments args) {
  Dart_SetReturnValue(args, Dart_NewInteger(g_paint_faults));
}

}  // namespace bin
}  // namespace dart
