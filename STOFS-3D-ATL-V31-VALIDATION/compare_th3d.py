#!/usr/bin/env python3
"""Compare SCHISM *.th.nc boundary files (TEM_3D, SAL_3D, uv3D, elev2D) at common times.

usage: compare_th3d.py REF.nc:YYYYMMDDHH TEST.nc:YYYYMMDDHH [TEST2.nc:YYYYMMDDHH ...]

YYYYMMDDHH is the absolute time of the file's time=0. Only records whose
absolute times match exactly in both files are compared (no interpolation),
so a bit-for-bit match shows up as max |diff| = 0.
"""
import sys
from datetime import datetime, timedelta

import numpy as np
from netCDF4 import Dataset


def load(arg):
    path, start = arg.rsplit(":", 1)
    with Dataset(path) as ds:
        t = np.asarray(ds["time"][:], dtype=float)
        v = np.ma.filled(ds["time_series"][:], np.nan)
    return path, datetime.strptime(start, "%Y%m%d%H"), t, v


def stats(d):
    a = np.abs(d)
    return (f"n={np.isfinite(d).sum()} equal={int((d == 0).sum())} "
            f"mean {np.nanmean(d):+.4g} RMS {np.sqrt(np.nanmean(d * d)):.4g} max|d| {np.nanmax(a):.4g}")


ref_path, ref_t0, ref_t, ref_v = load(sys.argv[1])
print(f"REF {ref_path}: shape {ref_v.shape}, dt={ref_t[1] - ref_t[0]:.0f}s, start {ref_t0:%Y-%m-%d %H}Z")
ref_abs = {round((ref_t0 - datetime(1970, 1, 1)).total_seconds() + s): i for i, s in enumerate(ref_t)}

for arg in sys.argv[2:]:
    path, t0, t, v = load(arg)
    print(f"\nTEST {path}: shape {v.shape}, dt={t[1] - t[0]:.0f}s, start {t0:%Y-%m-%d %H}Z")
    if v.shape[1:] != ref_v.shape[1:]:
        print(f"  shape differs from REF {ref_v.shape[1:]}; skipped")
        continue
    pairs = []
    for j, s in enumerate(t):
        key = round((t0 - datetime(1970, 1, 1)).total_seconds() + s)
        if key in ref_abs:
            pairs.append((ref_abs[key], j))
    if not pairs:
        print("  no common record times; skipped")
        continue
    ri, tj = zip(*pairs)
    first = t0 + timedelta(seconds=float(t[tj[0]]))
    last = t0 + timedelta(seconds=float(t[tj[-1]]))
    print(f"  {len(pairs)} common records, {first:%m-%d %H}Z to {last:%m-%d %H}Z")
    d = v[list(tj)] - ref_v[list(ri)]
    ncomp = d.shape[-1]
    nlev = d.shape[2]
    for c in range(ncomp):
        dc = d[..., c]
        print(f"  component {c}: {stats(dc)}")
        if nlev > 1:
            thirds = np.array_split(np.arange(nlev), 3)
            for name, idx in zip(("bottom third", "middle third", "top third"), thirds):
                print(f"    levels {idx[0] + 1}-{idx[-1] + 1} ({name}): {stats(dc[:, :, idx])}")
        node_max = np.nanmax(np.abs(dc), axis=(0, 2))
        worst = np.argsort(np.nan_to_num(node_max))[-5:][::-1]
        print("    worst nodes (index: max|d|): " + ", ".join(f"{k}: {node_max[k]:.4g}" for k in worst))
