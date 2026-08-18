# Where these came from

Dolphin Smalltalk 8's own UI artwork, extracted verbatim from its
resource DLL by `tools/extract_resources.py`. Nothing here was
redrawn, resized or recoloured.

| | |
|---|---|
| source | `C:\projects\dolphin8\DolphinDR8.dll` |
| size | 15845376 bytes |
| dated | 2025-07-20 |
| icons | 295 |
| cursors | 0 |
| bitmaps | 5 |

**Why extracted rather than copied from source.** They are not in
the Dolphin source repository: `git ls-files Core/DolphinVM/Res`
answers four files, none of them images, while `devres.rc`
references dozens of `Res\\*.ico`. The compiled DLL is the only
place they exist, and it is committed upstream.

**Licence.** Dolphin Smalltalk is MIT, Copyright (c) 2015 Object
Arts — see `LICENSE.dolphin` beside this file, which is kept here
because the licence requires the notice to accompany substantial
portions of the work.

Regenerate with:

    python tools/extract_resources.py --write
