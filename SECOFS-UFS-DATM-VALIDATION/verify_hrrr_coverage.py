#!/usr/bin/env python3
"""
Verify HRRR forecast coverage in a prep input manifest.

After delaying the prep cron so HRRR's later forecast hours have posted,
run this on the new run's *.inputs.prep.json to confirm the fix:
  - prep ran later relative to cycle (offset should grow ~+1.65h -> ~+2.5h)
  - HRRR file count jumps (~34 -> ~54) and last forecast hour reaches f48

Usage:
  python3 verify_hrrr_coverage.py <prep_manifest.json> [more.json ...]
  python3 verify_hrrr_coverage.py            # defaults to V19 t00/06/12/18z
"""
import glob
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

FORECAST_HOURS = 48   # secofs_ufs.yaml
NOWCAST_HOURS = 6


def hrrr_fhr_cycle(path):
    m = re.search(r"hrrr\.(\d{8})/.*?hrrr\.t(\d{2})z\.wrfsfcf(\d{2,3})", path)
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def check(manifest_path):
    m = json.load(open(manifest_path))
    cyc = int(m["cyc"])
    cycdt = (datetime.strptime(m["pdy"], "%Y%m%d").replace(tzinfo=timezone.utc)
             + timedelta(hours=cyc))
    gen = datetime.fromisoformat(m["generated_at"])
    prep_off = (gen - cycdt).total_seconds() / 3600.0

    hrrr = [e for e in m["inputs"] if (e.get("source") or "").upper() == "HRRR"]
    files = hrrr[0]["files"] if hrrr else []
    bycyc = defaultdict(list)
    for f in files:
        r = hrrr_fhr_cycle(f)
        if r:
            bycyc[(r[0], r[1])].append(r[2])
    # main forecast cycle = the one contributing the most forecast hours
    last_fhr = 0
    fcst_cycle = "--"
    if bycyc:
        main = max(bycyc.items(), key=lambda kv: len(kv[1]))
        fcst_cycle, last_fhr = f"t{main[0][1]}z", max(main[1])

    expected = NOWCAST_HOURS + FORECAST_HOURS          # ~54
    gap = FORECAST_HOURS - last_fhr                     # forecast hours on GFS fallback
    status = "OK   " if last_fhr >= FORECAST_HOURS else "SHORT"
    print(f"{m['pdy']} t{cyc:02d}z | prep +{prep_off:4.2f}h | "
          f"HRRR files {len(files):2d}/{expected} | fcst {fcst_cycle} f01..{last_fhr:02d} | "
          f"last-{gap}h on GFS | {status}")
    return last_fhr >= FORECAST_HOURS


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = sorted(glob.glob(
            "/mnt/e/secofs_com_outs/PYTHON_V14/V19/"
            "secofs_ufs.t*z.20260604.inputs.prep.json"))
    print("cycle        | prep offset | HRRR coverage | forecast HRRR     | fallback | verdict")
    print("-" * 92)
    results = [check(a) for a in args]   # evaluate every cycle (no short-circuit)
    all_ok = all(results)
    print("-" * 92)
    print("ALL CYCLES REACH f48" if all_ok else
          "still SHORT -> prep is still running before HRRR f48 posts (delay cron further)")
