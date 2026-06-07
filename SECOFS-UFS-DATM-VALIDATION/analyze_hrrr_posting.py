#!/usr/bin/env python3
"""
Turn HRRR file posting times into a prep-cron recommendation.

Input CSV (capture on WCOSS2): columns  pdy,cyc,fhr,mtime_epoch
  for f in .../hrrr.tCYz.wrfsfcf*.grib2: echo "$PDY,$CYC,$fhr,$(stat -c %Y "$f")"

For each cycle it prints when key forecast hours posted (lag from cycle time),
the f48 lag, and a recommended prep-cron offset = f48_lag + BUFFER.

Usage:  python3 analyze_hrrr_posting.py hrrr_posting_20260605.csv [more.csv ...]
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone

NEED_FHR = 48        # last forecast hour SECOFS needs (forecast_hours)
BUFFER_MIN = 15      # safety margin added on top of the f48 posting lag
MILESTONES = [18, 28, 36, 48]


def cyc_epoch(pdy, cyc):
    return datetime.strptime(f"{pdy}{int(cyc):02d}", "%Y%m%d%H").replace(
        tzinfo=timezone.utc).timestamp()


def load(paths):
    rows = defaultdict(dict)   # (pdy,cyc) -> {fhr: mtime_epoch}
    for p in paths:
        with open(p) as fh:
            for r in csv.DictReader(fh):
                rows[(r["pdy"], r["cyc"])][int(r["fhr"])] = float(r["mtime_epoch"])
    return rows


def fmt_lag(sec):
    sec = int(sec)
    return f"+{sec//3600}h{(sec%3600)//60:02d}m"


def main(paths):
    rows = load(paths)
    worst_f48 = 0.0
    print(f"{'cycle':14} | " + " | ".join(f"f{n:02d}" for n in MILESTONES)
          + " | f48 lag | rec. cron offset")
    print("-" * 86)
    for (pdy, cyc), fhrs in sorted(rows.items()):
        c0 = cyc_epoch(pdy, cyc)
        cells = []
        for n in MILESTONES:
            cells.append(fmt_lag(fhrs[n] - c0) if n in fhrs else "  --  ")
        if NEED_FHR in fhrs:
            lag = fhrs[NEED_FHR] - c0
            worst_f48 = max(worst_f48, lag)
            rec = fmt_lag(lag + BUFFER_MIN * 60)
            f48 = fmt_lag(lag)
        else:
            f48, rec = "MISSING", "n/a (f48 not posted)"
        print(f"{pdy} t{int(cyc):02d}z | " + " | ".join(f"{c:>6}" for c in cells)
              + f" | {f48:>7} | {rec}")
    print("-" * 86)
    if worst_f48:
        rec_min = int(worst_f48 / 60) + BUFFER_MIN
        print(f"Worst-case f48 across the sampled cycles: {fmt_lag(worst_f48)}")
        print(f"=> set prep cron to fire >= +{rec_min} min after cycle "
              f"(f48 lag + {BUFFER_MIN}min buffer).")
        print("   Capture a few more days to size the buffer against slow HRRR runs.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: analyze_hrrr_posting.py <hrrr_posting_*.csv> ...")
    main(sys.argv[1:])
