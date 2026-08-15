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
// WM_APP is the first message id safe for application use.
const UINT kMvpCall = WM_APP + 1;

Dart_PersistentHandle g_mvp_dispatch = nullptr;
bool g_class_registered = false;

// Live depth of image entries through the door. Reported to the image so a
// spike can assert the nesting really happened rather than inferring it.
int g_depth = 0;
int g_max_depth = 0;
// Set when an entry answers its default because the image raised. Counted, not
// swallowed silently.
int g_contained = 0;

LRESULT CALLBACK MvpWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
  if (msg != kMvpCall || g_mvp_dispatch == nullptr) {
    return DefWindowProcW(hwnd, msg, wp, lp);
  }
  g_depth++;
  if (g_depth > g_max_depth) g_max_depth = g_depth;

  int64_t result = 0;
  Dart_EnterScope();
  {
    Dart_Handle fn = Dart_HandleFromPersistent(g_mvp_dispatch);
    Dart_Handle a[2] = { Dart_NewInteger((int64_t)wp), Dart_NewInteger((int64_t)lp) };
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
  Dart_SetReturnValue(args, Dart_True());
}

}  // namespace bin
}  // namespace dart
