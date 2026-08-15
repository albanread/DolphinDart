# `st/test` — the ST feature battery (vendored, DD0)

## Where it came from

| | |
|---|---|
| Repo | `https://github.com/albanread/MACDARTV1.git` |
| Branch | **`dartui-workspace`** |
| Commit | `68b168961f4413ea228278ee000c8ed8ec306820` (2026-08-05) |
| Path | `macdart/st/test` |
| Vendored | 2026-08-15 (DolphinDart DD0) — 13 `features/*.mst` + 3 loose `.mst` |

Same author, same project family — a copy of our own code, like `st/world`.

## Why it is vendored now

`st/world/PROVENANCE.md` recorded these as *"Still in MACDARTV1 only, and not
required to run the world."* True, and it cost this port its regression net:
without them the only headless coverage was `st_world_run.dart`'s nine smoke
checks. DolphinDart is about to change the ST front-end (DD4 exceptions), add
primitives (DD5) and grow a Windows FFI floor (DD6) — every one of which needs
a battery underneath it. So the suites come in **before** the first sprint that
mutates the substrate, not after.

Run it:

```bash
C:\projects\dolphindart-work\build-arm64\dart.exe test\st_battery.dart st\world st\test\features
```

## What vendoring them immediately found

The battery had **never been run against this port**. On first run: one suite
crashed the VM outright and two more failed. All four defects were inherited
from the Windows port's seed (each reproduced against the sibling WINDARTTALK
build), not introduced by DolphinDart, and all four are now fixed — see
`docs/sprints/dd00_NOTES.md` for the full diagnosis. Baseline at the end of DD0:

**12 suites, 566 assertions, 0 failures**, on arm64 and x64.

The suites are worth reading before touching dispatch: `test_class_side.mst`
in particular carries a written history of the class-side-dNU corruption that
cost the MACDART lineage two debugging rounds, and three of DD0's four fixes
were rediscoveries of exactly what that history describes.
