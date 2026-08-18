@ECHO OFF
REM Build Scintilla + Lexilla as ARM64 DLLs for this port.
REM
REM   port-win\build_scintilla.cmd [workdir]
REM
REM WHY WE BUILD THESE AT ALL. Dolphin ships Scintilla.dll and Lexilla.dll, and
REM `UI.Scintilla.ScintillaView` (438KB of Smalltalk) drives them. Unlike the
REM resource DLL, whose contents are architecture-neutral DATA that a 64-bit
REM process can read from a 32-bit module, these are CODE: Dolphin's are I386
REM and an ARM64 process cannot load them at all. So they are rebuilt rather
REM than copied.
REM
REM VERSIONS MATCH DOLPHIN'S, because the wrapper is generated against a
REM specific Scintilla interface:
REM   Scintilla 5.5.7  (scintilla.org - the GitHub mirror stops at 5.5.2)
REM   Lexilla   5.4.5  (github.com/ScintillaOrg/lexilla, rel-5-4-5)
REM
REM `scintilla.mak` detects ARM64 from the PLATFORM variable that vcvarsarm64
REM sets (`!IF "$(PLATFORM:64=)" == "arm"`), so no patching is needed - only
REM the right vcvars.

SETLOCAL
SET WORK=%~1
IF "%WORK%"=="" SET WORK=C:\projects\dolphindart-work\scintilla

SET VSROOT=C:\Program Files\Microsoft Visual Studio\18\Professional
SET VCVARS=%VSROOT%\VC\Auxiliary\Build\vcvarsarm64.bat
IF NOT EXIST "%VCVARS%" (
  ECHO build_scintilla: not found: %VCVARS%
  EXIT /B 2
)
CALL "%VCVARS%" >NUL
IF ERRORLEVEL 1 EXIT /B 1
ECHO build_scintilla: PLATFORM=%PLATFORM%

ECHO.
ECHO === Scintilla (ARM64) ===
PUSHD "%WORK%\scintilla\win32"
nmake -f scintilla.mak QUIET=1
IF ERRORLEVEL 1 (POPD & ECHO scintilla FAILED & EXIT /B 1)
POPD

ECHO.
ECHO === Lexilla (ARM64) ===
PUSHD "%WORK%\lexilla\src"
nmake -f lexilla.mak QUIET=1
IF ERRORLEVEL 1 (POPD & ECHO lexilla FAILED & EXIT /B 1)
POPD

ECHO.
ECHO === output ===
DIR /B "%WORK%\scintilla\bin\*.dll" 2>NUL
DIR /B "%WORK%\lexilla\bin\*.dll" 2>NUL
EXIT /B 0
