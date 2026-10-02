#!/usr/bin/env python3
"""Compare nos-utils TEM_nu/SAL_nu phase files with the ops temnu/salnu at the same absolute times.

usage: compare_nudge.py OPS.nc:YYYYMMDDHH OURS.nc:YYYYMMDDHH [OURS2.nc:YYYYMMDDHH ...] [--step 216000]

YYYYMMDDHH is the absolute time of each file's time=0 (ops: the nowcast start, cycle - 24 h;
ours: the phase start, so the forecast file starts at the cycle).

The ops run reads its records by index with step_nu_tr = 216000 s although they are 6 h apart, so the
field SCHISM applies at model time tau (s since the ops nowcast start) is the linear blend of ops
records n and n+1 with n = floor(tau/step), f = tau/step - n. Each record of our files, taken at its
exact time, is compared with that ops-effective field (float64 blend, float32 result, no other
interpolation). Our files must carry the same field when run with step_nu_tr = 21600.

Records are streamed one at a time (the ops files are ~745 MB). Nodes are matched on
map_to_global_node. Statistics per file and per level third: max |diff|, RMS, equal count.
"""
import sys
from datetime import datetime

import numpy as np
from netCDF4 import Dataset

EPOCH = datetime(1970, 1, 1)
F32 = np.float32


def parse(arg):
    path, start = arg.rsplit(":", 1)
    return path, datetime.strptime(start, "%Y%m%d%H")


def time_seconds(ds):
    t = np.asarray(ds["time"][:], dtype=float)
    # ops writes days; older nos-utils files wrote seconds
    return t * 86400.0 if t.size and t.max() < 1000.0 else t


def record(ds, k, sel):
    return np.ma.filled(ds["tracer_concentration"][k, :, :, 0], np.nan).astype(F32)[sel]


class Acc:
    def __init__(self):
        self.n = self.eq = self.nonfinite = 0
        self.ss = 0.0
        self.mx = 0.0

    def add(self, d):
        ok = np.isfinite(d)
        self.nonfinite += int(d.size - ok.sum())
        d = d[ok].astype(np.float64)
        self.n += d.size
        self.eq += int((d == 0).sum())
        self.ss += float((d * d).sum())
        if d.size:
            self.mx = max(self.mx, float(np.abs(d).max()))

    def text(self):
        rms = (self.ss / self.n) ** 0.5 if self.n else float("nan")
        return (f"n={self.n} equal={self.eq} RMS {rms:.4g} max|d| {self.mx:.4g}"
                f" non-finite differences {self.nonfinite}")


def main(argv):
    step = 216000.0
    if "--step" in argv:
        i = argv.index("--step")
        step = float(argv[i + 1])
        del argv[i:i + 2]
    if len(argv) < 2:
        print(__doc__)
        return 2
    ops_path, ops_t0 = parse(argv[0])
    ops = Dataset(ops_path)
    ops_ids = np.asarray(ops["map_to_global_node"][:])
    n_ops = ops.dimensions["time"].size
    ops_dt = np.diff(time_seconds(ops)[:2])[0] if n_ops > 1 else float("nan")
    print(f"OPS {ops_path}: {n_ops} records x {len(ops_ids)} nodes, file spacing {ops_dt:.0f} s, "
          f"start {ops_t0:%Y-%m-%d %H}Z, effective step_nu_tr {step:.0f} s")
    cache = {}

    def ops_record(k, sel):
        if k not in cache:
            if len(cache) >= 2:
                cache.pop(next(iter(cache)))
            cache[k] = record(ops, k, sel)
        return cache[k]

    for arg in argv[1:]:
        path, t0 = parse(arg)
        with Dataset(path) as ds:
            ids = np.asarray(ds["map_to_global_node"][:])
            tt = time_seconds(ds)
            common, io, ioo = np.intersect1d(ids, ops_ids, return_indices=True)
            print(f"\nOURS {path}: {len(tt)} records x {len(ids)} nodes, dt "
                  f"{(tt[1] - tt[0]) if len(tt) > 1 else float('nan'):.0f} s, start {t0:%Y-%m-%d %H}Z; "
                  f"{len(common)} nodes in common ({len(ids) - len(common)} only ours, "
                  f"{len(ops_ids) - len(common)} only ops)")
            if not len(common):
                continue
            cache.clear()
            offset = (t0 - ops_t0).total_seconds()
            nlev = ds.dimensions["nLevels"].size
            thirds = np.array_split(np.arange(nlev), 3)
            total = Acc()
            by_third = [Acc() for _ in thirds]
            used = 0
            for j, s in enumerate(tt):
                tau = offset + float(s)
                n = int(np.floor(tau / step + 1e-9))
                f = (tau - n * step) / step
                if tau < 0 or n + (1 if f > 1e-9 else 0) >= n_ops:
                    print(f"  record {j} (tau {tau:.0f} s) outside the ops records; skipped")
                    continue
                if f <= 1e-9:
                    want = ops_record(n, ioo)
                else:
                    a, b = ops_record(n, ioo), ops_record(n + 1, ioo)
                    want = (a.astype(np.float64) * (1.0 - f) + b.astype(np.float64) * f).astype(F32)
                d = record(ds, j, io) - want
                total.add(d)
                for acc, idx in zip(by_third, thirds):
                    acc.add(d[:, idx])
                used += 1
            print(f"  {used} records compared at exact times")
            print(f"  all levels: {total.text()}")
            for name, acc, idx in zip(("bottom third", "middle third", "top third"), by_third, thirds):
                print(f"    levels {idx[0] + 1}-{idx[-1] + 1} ({name}): {acc.text()}")
    ops.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
