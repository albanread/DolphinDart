# Dolphin's artwork, and how this port retrieves it

Dolphin Smalltalk's own icons and bitmaps, and an ARM64 resource DLL built
from them so that Dolphin's *own retrieval mechanism* works unchanged on this
port.

| | |
|---|---|
| `icons/`, `bitmaps/` | 295 icons + 5 bitmaps, extracted verbatim |
| `MANIFEST.tsv` | resource NAME → file. Load-bearing, see below |
| `DolphinDR8.rc` | generated from the manifest |
| `DolphinDR8.dll` | **ARM64**, 300 resources, what the image loads |
| `LICENSE.dolphin`, `PROVENANCE.md` | MIT notice and origin — must ship |

```bash
python tools/extract_resources.py --write   # DLL -> files + MANIFEST.tsv
python tools/build_resources.py             # files -> .rc -> ARM64 .dll
```

## Why a DLL rather than a folder of icons

Because that is how Dolphin asks for artwork. Nothing in the corpus names a
path; everything names a *resource identifier*:

```smalltalk
Image class >> fromId: anId
    ^self fromId: anId in: SessionManager.Current defaultResourceLibrary

SessionManager >> defaultResLibPath    ^'DolphinDR8'
```

`External.ResourceLibrary open:` then looks for that library in the working
directory, next to the image, and finally in the install directory. Icon
references baked into Dolphin's view resources are strings like
`'ClassBrowserShell.ico'` resolved through exactly that path. Reproducing the
mechanism means those references work as written; a file-per-icon scheme would
mean rewriting every one of them and diverging from Dolphin where it is
cheapest not to.

## Why our own DLL, and why it keeps the name

Object Arts' `DolphinDR8.dll` is 32-bit x86. Interestingly it *does* still
serve resources to a 64-bit ARM64 process — `LoadLibraryEx` + `LoadImage`
against it return real `HICON`s, because resources are architecture-neutral
data. So shipping theirs would work today.

We build our own anyway, because relying on a foreign-architecture binary for
a core asset path is a dependency this port should not carry into an ARM64
future, and because building it is nine lines of tooling.

It **keeps the name `DolphinDR8.dll`** deliberately: `defaultResLibPath`
answers `'DolphinDR8'`, so an identically-named library is the difference
between zero code changes and an override to maintain forever. Ours lives
here and is never installed system-wide, so it cannot shadow an Object Arts
installation.

## The manifest is not a convenience

A resource name cannot be recovered from the filename it was written to:

```
ICON   !APPLICATION              icons/!APPLICATION.ico       <- name has NO extension
ICON   CLASSBROWSERSHELL.ICO     icons/CLASSBROWSERSHELL.ICO  <- name INCLUDES .ICO
```

Guessing by stripping the extension got the second kind wrong, and every
`FindResource` for it missed with `ERROR_RESOURCE_NAME_NOT_FOUND` — while the
resources were plainly present in the DLL, which is a memorable way to lose
an hour. Two further traps are recorded in the tools:

* **Resource names in a `.rc` are written BARE, never quoted.** `rc.exe` keeps
  the quotes as part of the name, so `"HEADERPIN.BMP"` compiles to a resource
  literally called `"HEADERPIN.BMP"`. Dolphin's own `devres.rc` settles the
  form — bare even for `!APPLICATION`.
* **`/NOENTRY`** — a resource-only DLL has no code and therefore no entry
  point.

Verified: all 300 resources extracted back out of our DLL are **byte-identical**
to the files they were built from.

## Licence

Dolphin Smalltalk is MIT, Copyright (c) 2015 Object Arts. `LICENSE.dolphin`
sits beside this file because the licence requires the copyright and
permission notice to accompany substantial portions of the work, and 300
pieces of artwork is a substantial portion. Do not remove it.
