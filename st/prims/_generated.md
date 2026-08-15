# Generated Win32 prims

- external methods found in the corpus: **4511**
- **generated: 1126** across **37** library classes
- refused: **3385**
- winkb cross-check: **96** not found, **1** arity disagreements

## Refusals by reason

| Reason | Count |
|---|--:|
| `virtual` is a COM vtable call — a v1 non-goal | 3333 |
| `overlap` is an asynchronous call — v1 is synchronous | 35 |
| argument 'POINTL' is a struct passed BY VALUE — not representable as a word | 5 |
| return 'oop' is a Dolphin VM object reference — no translation | 2 |
| argument 'REFGUID' is a struct passed BY VALUE — not representable as a word | 1 |
| argument 'CURRENCY' is a struct passed BY VALUE — not representable as a word | 1 |
| argument 'double' is floating point — the floor takes word arguments only | 1 |
| ordinal export '12' — the floor resolves by name only | 1 |
| argument unknown type 'ntstatus' | 1 |
| argument unknown type 'char' | 1 |
| ordinal export '104' — the floor resolves by name only | 1 |
| ordinal export '132' — the floor resolves by name only | 1 |
| argument 'BLENDFUNCTION' is a struct passed BY VALUE — not representable as a word | 1 |
| return 'MemoryMappedFileView' is a struct passed BY VALUE — not representable as a word | 1 |

## winkb arity disagreements (pragma vs metadata)

- `URLOpenPullStreamW`: pragma 5, winkb 4 — `C:\projects\dsfork\Core\Object Arts\Dolphin\ActiveX\Structured Storage\OS.COM.URLMonLibrary.cls:134`

## Not in winkb (96)

- `CompareBrowserVersions` (`WebView2.WebView2Loader`)
- `CreateCoreWebView2Environment` (`WebView2.WebView2Loader`)
- `CreateCoreWebView2EnvironmentWithOptions` (`WebView2.WebView2Loader`)
- `GetAvailableCoreWebView2BrowserVersionString` (`WebView2.WebView2Loader`)
- `AtlAxWinInit` (`UI.AXHostLibrary`)
- `_snprintf_s` (`Kernel.VMLibrary`)
- `_snprintf_s` (`Kernel.VMLibrary`)
- `AnswerIntPtr` (`Kernel.VMLibrary`)
- `argc` (`Kernel.VMLibrary`)
- `argv` (`Kernel.VMLibrary`)
- `DebugDump` (`Kernel.VMLibrary`)
- `Dump` (`Kernel.VMLibrary`)
- `AnswerIntPtr` (`Kernel.VMLibrary`)
- `HashBytes` (`Kernel.VMLibrary`)
- `highBit` (`Kernel.VMLibrary`)
- `AnswerDWORD` (`Kernel.VMLibrary`)
- `IsUserBreakRequested` (`Kernel.VMLibrary`)
- `AnswerQWORD` (`Kernel.VMLibrary`)
- `AnswerQWORD` (`Kernel.VMLibrary`)
- `AnswerQWORD` (`Kernel.VMLibrary`)
- `AnswerQWORD` (`Kernel.VMLibrary`)
- `AnswerQWORD` (`Kernel.VMLibrary`)
- `AnswerQWORD` (`Kernel.VMLibrary`)
- `RegisterAsEventSource` (`Kernel.VMLibrary`)
- `StdErr` (`Kernel.VMLibrary`)
- `StdIn` (`Kernel.VMLibrary`)
- `StdOut` (`Kernel.VMLibrary`)
- `AnswerDWORD` (`Kernel.VMLibrary`)
- `AnswerIntPtr` (`Kernel.VMLibrary`)
- `_chsize_s` (`OS.CRTLibrary`)
- `_clearfp` (`OS.CRTLibrary`)
- `_close` (`OS.CRTLibrary`)
- `_control87` (`OS.CRTLibrary`)
- `_dup` (`OS.CRTLibrary`)
- `_dup2` (`OS.CRTLibrary`)
- `_errno` (`OS.CRTLibrary`)
- `_fdopen` (`OS.CRTLibrary`)
- `_filelengthi64` (`OS.CRTLibrary`)
- `_fileno` (`OS.CRTLibrary`)
- `_fseeki64` (`OS.CRTLibrary`)

## Per class

| Class | Methods |
|---|--:|
| `External.DynamicLinkLibrary` | 1 |
| `Kernel.VMLibrary` | 24 |
| `OLELibrary` | 1 |
| `OS.AdvApiLibrary` | 25 |
| `OS.BCryptLibrary` | 13 |
| `OS.COM.OLEAutLibrary` | 49 |
| `OS.COM.OLELibrary` | 52 |
| `OS.COM.URLMonLibrary` | 4 |
| `OS.CRTLibrary` | 49 |
| `OS.ComDlgLibrary` | 10 |
| `OS.CommCtrlLibrary` | 23 |
| `OS.Crypt32Library` | 4 |
| `OS.DwmApiLibrary` | 3 |
| `OS.GDILibrary` | 114 |
| `OS.HTMLHelpLibrary` | 1 |
| `OS.ICULibrary` | 21 |
| `OS.IPHlpApiLibrary` | 57 |
| `OS.KernelLibrary` | 162 |
| `OS.NTLibrary` | 3 |
| `OS.ODBCLibrary` | 42 |
| `OS.PathCchLibrary` | 18 |
| `OS.RPCLibrary` | 6 |
| `OS.SHCoreLibrary` | 2 |
| `OS.ShellLibrary` | 15 |
| `OS.ShlwapiLibrary` | 8 |
| `OS.ThemeLibrary` | 62 |
| `OS.UserLibrary` | 232 |
| `OS.VersionLibrary` | 3 |
| `OS.WS2_32Library` | 27 |
| `OS.WinInetLibrary` | 4 |
| `OS.WinMMLibrary` | 3 |
| `UI.AXHostLibrary` | 1 |
| `UI.Scintilla.LexillaLibrary` | 3 |
| `UI.Scintilla.ScintillaLibrary` | 5 |
| `WSockLibrary` | 41 |
| `WebView2.WebView2Loader` | 4 |
| `WinHttpServer.HttpApiLibrary` | 34 |
