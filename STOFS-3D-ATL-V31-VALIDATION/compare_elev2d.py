#!/usr/bin/env python3
"""Compare SCHISM elev2D.th.nc files on a common hourly axis.

usage: compare_elev2d.py REF.nc:YYYYMMDDHH TEST.nc:YYYYMMDDHH [TEST2.nc:YYYYMMDDHH ...]

YYYYMMDDHH is the absolute time of the file's time=0 (the run start).
For each TEST, prints the difference TEST - REF over the overlapping hours.
"""
import sys
from datetime import datetime

import numpy as np
from netCDF4 import Dataset


def load(arg):
    path, start = arg.rsplit(":", 1)
    with Dataset(path) as ds:
        t = np.asarray(ds["time"][:], dtype=float)
        z = np.ma.filled(ds["time_series"][:], np.nan).astype(float)[:, :, 0, 0]
    z[np.abs(z) > 100] = np.nan
    return path, datetime.strptime(start, "%Y%m%d%H"), t, z


def hourly(t, z, hours):
    return np.stack([np.interp(hours, t, z[:, i]) for i in range(z.shape[1])], axis=1)


ref_path, ref_t0, ref_t, ref_z = load(sys.argv[1])
print(f"REF {ref_path}: {ref_z.shape[0]} steps x {ref_z.shape[1]} nodes, "
      f"dt={ref_t[1] - ref_t[0]:.0f}s, start {ref_t0:%Y-%m-%d %H}Z")

for arg in sys.argv[2:]:
    path, t0, t, z = load(arg)
    print(f"\nTEST {path}: {z.shape[0]} steps x {z.shape[1]} nodes, "
          f"dt={t[1] - t[0]:.0f}s, start {t0:%Y-%m-%d %H}Z")
    if z.shape[1] != ref_z.shape[1]:
        print("  node count differs from REF; skipped")
        continue
    r0 = z[0] - ref_z[0]
    print(f"  record 0 vs REF record 0: mean {np.nanmean(r0):+.3f} m; RMS {np.sqrt(np.nanmean(r0**2)):.3f} m; "
          f"RMS after removing mean {np.nanstd(r0):.3f} m; max |diff| {np.nanmax(np.abs(r0)):.3f} m")
    print(f"  REF constant in time: {bool(np.allclose(ref_z, ref_z[0], equal_nan=True))}; "
          f"TEST constant in time: {bool(np.allclose(z, z[0], equal_nan=True))}")
    tt = t + (t0 - ref_t0).total_seconds()
    lo, hi = max(ref_t[0], tt[0]), min(ref_t[-1], tt[-1])
    hours = np.arange(np.ceil(lo / 3600), np.floor(hi / 3600) + 1) * 3600
    if hours.size == 0:
        print("  no overlapping time; skipped")
        continue
    d = hourly(tt, z, hours) - hourly(ref_t, ref_z, hours)
    m = np.nanmean(d)
    print(f"  overlap {hours.size} h; mean diff {m:+.3f} m; RMS {np.sqrt(np.nanmean(d**2)):.3f} m; "
          f"RMS after removing mean {np.sqrt(np.nanmean((d - m)**2)):.3f} m")
    node_mean = np.nanmean(d, axis=0)
    print(f"  per-node mean diff: min {np.nanmin(node_mean):+.3f}  max {np.nanmax(node_mean):+.3f} m")
    for k in range(0, hours.size, 24):
        seg = d[k:k + 24]
        h0 = int((hours[k]) / 3600)
        print(f"    hours {h0:4d}-{h0 + seg.shape[0] - 1:4d} from REF start: mean {np.nanmean(seg):+.3f} m")
