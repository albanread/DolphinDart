@echo off
REM ============================================================================
REM  DolphinDart - the DD10 acceptance app, ON SCREEN.
REM
REM  Two UI.TextEdit fields over one UI.ValueHolder, arranged by Dolphin's own
REM  BorderLayout, under a UI.MenuBar whose commands route through Dolphin's
REM  command machinery. Every class in it is Dolphin's; the window class and
REM  message pump are ours.
REM
REM  Close the window to quit. Assertions live in test/st_dolphinapp.dart --
REM  this is the half a test cannot do, which is show you the thing.
REM ============================================================================
setlocal
set "ROOT=%~dp0"
set "EXE=C:\projects\dolphindart-work\build-arm64\dartui.exe"
set "LAYERS=st/world;st/dolphin_compat;st/prims/rt;st/prims/structs;st/prims;st/prims/aliases"

if not exist "%EXE%" (
  echo [dolphin-app] dartui.exe not found at %EXE%
  echo [dolphin-app] build first:
  echo     powershell -ExecutionPolicy Bypass -File port-win\build.ps1 -Arch arm64 -WorkRoot C:\projects\dolphindart-work -Tree C:\projects\dolphindart-work\tree
  exit /b 1
)

pushd "%ROOT%"
"%EXE%" demos\dolphin_app.dart "%LAYERS%" st/mvp st/mvp_compat st/test/ffi/dolphin_app.mst %*
popd
