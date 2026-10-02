#!/usr/bin/env python3
"""Compare SCHISM staout_N station time series (text) at common absolute times.

usage: compare_staout.py REF_staout:YYYYMMDDHH TEST_staout:YYYYMMDDHH [--top 10]

YYYYMMDDHH is the start time of each run (column 0 is seconds since it). Rows are matched on
absolute time (no interpolation). Reports the overall and per-station max |diff| / RMS, and the
worst stations. Values <= -9000 are treated as missing.
"""
import sys
from datetime import datetime

import numpy as np


def load(arg):
    path, start = arg.rsplit(":", 1)
    d = np.loadtxt(path, dtype=np.float64)
    t0 = (datetime.strptime(start, "%Y%m%d%H") - datetime(1970, 1, 1)).total_seconds()
    v = d[:, 1:]
    v[v <= -9000] = np.nan
    return path, np.round(t0 + d[:, 0]).astype(np.int64), v


def main(argv):
    top = 10
    if "--top" in argv:
        i = argv.index("--top"); top = int(argv[i + 1]); del argv[i:i + 2]
    if len(argv) != 2:
        print(__doc__); return 2
    rp, rt, rv = load(argv[0])
    tp, tt, tv = load(argv[1])
    print(f"REF  {rp}: {len(rt)} rows x {rv.shape[1]} stations, dt {rt[1] - rt[0]} s")
    print(f"TEST {tp}: {len(tt)} rows x {tv.shape[1]} stations, dt {tt[1] - tt[0]} s")
    if rv.shape[1] != tv.shape[1]:
        print("station counts differ; comparing the first", min(rv.shape[1], tv.shape[1]))
    n = min(rv.shape[1], tv.shape[1])
    common, ir, it = np.intersect1d(rt, tt, return_indices=True)
    if not len(common):
        print("no common times"); return 1
    d = tv[it, :n] - rv[ir, :n]
    ok = np.isfinite(d)
    print(f"{len(common)} common rows, {(common[-1] - common[0]) / 3600:.1f} h; "
          f"values compared {int(ok.sum())}, equal {int((d[ok] == 0).sum())}, "
          f"max|d| {np.nanmax(np.abs(d)):.4g}, RMS {np.sqrt(np.nanmean(d * d)):.4g}, mean {np.nanmean(d):+.4g}")
    with np.errstate(invalid="ignore"):
        smax = np.nanmax(np.abs(d), axis=0)
        srms = np.sqrt(np.nanmean(d * d, axis=0))
    order = np.argsort(np.nan_to_num(smax, nan=-1))[::-1][:top]
    print(f"worst {top} stations (1-based column: max|d|, RMS):")
    for k in order:
        print(f"  {k + 1:4d}: {smax[k]:.4g}  {srms[k]:.4g}")
    for h in (6, 12, 24):
        sel = common <= common[0] + h * 3600
        dd = d[sel]
        print(f"  first {h:2d} h: max|d| {np.nanmax(np.abs(dd)):.4g}, RMS {np.sqrt(np.nanmean(dd * dd)):.4g}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
