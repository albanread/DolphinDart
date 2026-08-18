#!/usr/bin/env bash
# Which winkb-derived struct size regresses a gate?
#
#   tools/bisect_sizes.sh st_textedit "A,B,C"   # candidates to test
#
# Applies the winkb size to MONITORINFOEXW plus the named candidates ONLY,
# holding every other struct at the old arithmetic size, then runs the gate.
# Exits 0 if the gate passes (candidates are innocent), 1 if it fails.
set -u
GATE="$1"
CANDIDATES="$2"
cd "$(dirname "$0")/.." || exit 2

ALL=$(for f in /tmp/nosize/*.mst; do basename "$f" .mst; done)
KEEP="MONITORINFOEXW,$CANDIDATES"
SKIP=$(for n in $ALL; do
    case ",$KEEP," in *",$n,"*) ;; *) echo "$n";; esac
done | paste -sd,)

GENSTRUCTS_SIZE_SKIP="$SKIP" python tools/dolphin2mst/genstructs.py \
    --out st/prims/structs --corpus /c/projects/dsfork \
    --winkb "C:\\projects\\windows_api\\windows_api.db" \
    --supplied CCITEM >/dev/null 2>&1

OUT=$(python tools/gates.py "$GATE" 2>&1 | tail -3)
if echo "$OUT" | grep -q "^1/1 gates pass"; then
    echo "PASS  with: $CANDIDATES"
    exit 0
else
    echo "FAIL  with: $CANDIDATES"
    exit 1
fi
