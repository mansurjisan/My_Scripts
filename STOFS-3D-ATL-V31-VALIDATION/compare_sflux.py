#!/usr/bin/env python3
"""Compare SCHISM sflux files (air / prc / rad) at common absolute times.

usage: compare_sflux.py REF.nc TEST.nc [TEST2.nc ...]

Times come from each file's time variable: days relative to the `base_date` attribute
([yyyy, mm, dd, hh]) or, failing that, the `units` string ("days since ..."). Records are matched
on absolute time to the second (no interpolation). Grids must have the same shape; the lon/lat
arrays are compared first. For every data variable in both files: values compared, equal count,
max |diff|, RMS and mean.
"""
import re
import sys
from datetime import datetime, timedelta

import numpy as np
from netCDF4 import Dataset

SKIP = {"time", "lon", "lat"}


def abs_times(ds):
    tv = ds["time"]
    t = np.asarray(tv[:], dtype=np.float64)
    if "base_date" in tv.ncattrs():
        b = [int(x) for x in np.atleast_1d(tv.getncattr("base_date"))[:4]]
        base = datetime(b[0], b[1], b[2], b[3] if len(b) > 3 else 0)
        scale = 86400.0
    else:
        u = tv.getncattr("units")
        m = re.match(r"(\w+) since (\d{4})-(\d{1,2})-(\d{1,2})[ T]?(\d{1,2})?", u)
        base = datetime(int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5) or 0))
        scale = {"days": 86400.0, "hours": 3600.0, "seconds": 1.0}[m.group(1)]
    epoch = (base - datetime(1970, 1, 1)).total_seconds()
    return np.round(epoch + t * scale).astype(np.int64)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    with Dataset(argv[0]) as R:
        rt = abs_times(R)
        print(f"REF {argv[0]}: {len(rt)} records, {datetime(1970,1,1)+timedelta(seconds=int(rt[0])):%Y-%m-%d %H:%M}Z"
              f" .. {datetime(1970,1,1)+timedelta(seconds=int(rt[-1])):%Y-%m-%d %H:%M}Z, grid {R['lon'].shape}")
        for path in argv[1:]:
            with Dataset(path) as T:
                tt = abs_times(T)
                print(f"\nTEST {path}: {len(tt)} records, "
                      f"{datetime(1970,1,1)+timedelta(seconds=int(tt[0])):%Y-%m-%d %H:%M}Z .. "
                      f"{datetime(1970,1,1)+timedelta(seconds=int(tt[-1])):%Y-%m-%d %H:%M}Z, grid {T['lon'].shape}")
                if T["lon"].shape != R["lon"].shape:
                    print("  grid shape differs; skipped"); continue
                for c in ("lon", "lat"):
                    dd = np.abs(np.asarray(T[c][:], np.float64) - np.asarray(R[c][:], np.float64))
                    print(f"  {c}: max|d| {dd.max():.3g}")
                common, ir, it = np.intersect1d(rt, tt, return_indices=True)
                print(f"  {len(common)} common records")
                if not len(common):
                    continue
                for v in sorted((set(T.variables) & set(R.variables)) - SKIP):
                    n = eq = 0; ss = 0.0; mx = 0.0; sm = 0.0
                    for a, b in zip(ir, it):
                        x = np.ma.filled(R[v][a], np.nan).astype(np.float64)
                        y = np.ma.filled(T[v][b], np.nan).astype(np.float64)
                        d = (y - x)[np.isfinite(y - x)]
                        n += d.size; eq += int((d == 0).sum()); ss += float((d * d).sum()); sm += float(d.sum())
                        if d.size:
                            mx = max(mx, float(np.abs(d).max()))
                    print(f"  {v:8s} n={n} equal={eq} max|d| {mx:.4g} RMS {(ss / n) ** 0.5 if n else float('nan'):.4g}"
                          f" mean {sm / n if n else float('nan'):+.4g}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
