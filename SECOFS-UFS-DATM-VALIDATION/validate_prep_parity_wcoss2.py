#!/usr/bin/env python3
"""
Validate prep PARITY between two COMOUTs (operational/standalone vs UFS
secofs_ufs) for the non-atmospheric products: OBC, River, Tides.

Most of these SHOULD be identical between the two paths (same RTOFS/NWM/tidal
inputs regardless of nws=2 vs nws=4). Known intentional differences: the UFS
OBC node subset (e.g. 781 -> 778) and elev2D model_dt. This tool reports
MATCH / DIFF per product, with where, so unexpected drift is caught and the
expected diffs are visible (it still compares values at the common nodes).

Library-graceful for WCOSS2:
  - River, Tides : Python standard library only.
  - OBC (.th.nc) : numpy + netCDF4 (present in the prep env).

Files are matched by SUFFIX inside each dir, so you just pass the two COMOUTs:
  module load python/3.8.6
  python3 validate_prep_parity_wcoss2.py \
      --ops-dir /path/to/standalone/COMOUT \
      --ufs-dir /path/to/secofs_ufs/COMOUT \
      --phase nowcast --products obc,river,tides
"""
import argparse
import glob
import os
import shutil
import sys
import tarfile
import tempfile

TOL = 1e-4   # max abs difference treated as "MATCH"
OBC_TIME_SAMPLES = 50   # evenly-spaced timesteps sampled per .th.nc (memory-safe)


def find_suffix(d, suffix):
    hits = sorted(glob.glob(os.path.join(d, "*" + suffix)))
    return hits[0] if hits else None


# ----------------------------- River (.th ASCII) ---------------------------
def _read_th(path):
    rows = []
    with open(path) as f:
        for ln in f:
            p = ln.split()
            if p:
                rows.append([float(x) for x in p])
    return rows


def compare_river(ops, ufs):
    print("=" * 70); print("RIVER (NWM)"); print("=" * 70)
    ok = True
    seen = False
    for kind in ("vsource", "vsink", "msource"):
        a = find_suffix(ops, f".river.{kind}.th")
        b = find_suffix(ufs, f".river.{kind}.th")
        if not a or not b:
            if a or b:
                print(f"  {kind:8s}: SKIP  (ops={'y' if a else 'n'} ufs={'y' if b else 'n'})")
            continue
        seen = True
        ra, rb = _read_th(a), _read_th(b)
        na, nca = len(ra), (len(ra[0]) if ra else 0)
        nb, ncb = len(rb), (len(rb[0]) if rb else 0)
        if (na, nca) != (nb, ncb):
            print(f"  {kind:8s}: DIFF shape  ops={na}x{nca}  ufs={nb}x{ncb}"); ok = False; continue
        md = 0.0
        for r1, r2 in zip(ra, rb):
            for x, y in zip(r1, r2):
                d = abs(x - y)
                if d > md:
                    md = d
        v = "MATCH" if md <= TOL else "DIFF"
        ok = ok and md <= TOL
        print(f"  {kind:8s}: {v}  ({na} rows x {nca} cols, max|diff|={md:.3e})")
    return ok if seen else None


# ----------------------------- Tides (bctides.in) --------------------------
def _norm(path):
    return [ln.rstrip() for ln in open(path).read().splitlines()]


def compare_tides(ops, ufs, phase):
    print("=" * 70); print("TIDES (bctides.in)"); print("=" * 70)
    a = find_suffix(ops, f".bctides.in.{phase}") or find_suffix(ops, ".bctides.in")
    b = find_suffix(ufs, f".bctides.in.{phase}") or find_suffix(ufs, ".bctides.in")
    if not a or not b:
        print(f"  SKIP  (ops={'y' if a else 'n'} ufs={'y' if b else 'n'})"); return None
    la, lb = _norm(a), _norm(b)
    if la == lb:
        print(f"  bctides.in: MATCH  ({len(la)} lines identical)"); return True
    ndiff = sum(1 for x, y in zip(la, lb) if x != y) + abs(len(la) - len(lb))
    print(f"  bctides.in: DIFF  ({ndiff} differing lines; {len(la)} vs {len(lb)} lines)")
    shown = 0
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y and shown < 6:
            print(f"    L{i+1:4d} ops: {x[:60]}")
            print(f"         ufs: {y[:60]}")
            shown += 1
    return False


# ----------------------------- OBC (.th.nc) --------------------------------
def compare_obc(ops, ufs, phase):
    print("=" * 70); print("OBC (RTOFS)"); print("=" * 70)
    try:
        import numpy as np
        from netCDF4 import Dataset
    except ImportError as e:
        print(f"  SKIP: numpy/netCDF4 not importable ({e})")
        print("    -> module load python/3.8.6 ; export PYTHONPATH=$HOMEnos/ush/python:$PYTHONPATH")
        return None
    a = find_suffix(ops, f".obc.{phase}.tar") or find_suffix(ops, ".obc.tar")
    b = find_suffix(ufs, f".obc.{phase}.tar") or find_suffix(ufs, ".obc.tar")
    if not a or not b:
        print(f"  SKIP  (ops={'y' if a else 'n'} ufs={'y' if b else 'n'})"); return None
    da, db = tempfile.mkdtemp(prefix="obc_a_"), tempfile.mkdtemp(prefix="obc_b_")
    ok = True
    try:
        with tarfile.open(a) as t:
            t.extractall(da, filter="data")
        with tarfile.open(b) as t:
            t.extractall(db, filter="data")
        for fn in ("elev2D.th.nc", "TEM_3D.th.nc", "SAL_3D.th.nc", "uv3D.th.nc"):
            fa = find_suffix(da, fn) or (glob.glob(os.path.join(da, "**", fn), recursive=True) or [None])[0]
            fb = find_suffix(db, fn) or (glob.glob(os.path.join(db, "**", fn), recursive=True) or [None])[0]
            if not fa or not fb:
                continue
            dsa, dsb = Dataset(fa), Dataset(fb)
            va, vb = dsa.variables["time_series"], dsb.variables["time_series"]
            sa, sb = tuple(va.shape), tuple(vb.shape)
            nt = min(sa[0], sb[0]); nn = min(sa[1], sb[1])
            idx = range(0, nt, max(1, nt // OBC_TIME_SAMPLES))
            md = 0.0; sse = 0.0; cnt = 0
            for i in idx:
                xa = np.asarray(va[i, :nn], dtype="f8")
                xb = np.asarray(vb[i, :nn], dtype="f8")
                d = np.abs(xa - xb)
                md = max(md, float(np.nanmax(d)))
                sse += float(np.nansum(d ** 2)); cnt += d.size
            rmse = (sse / cnt) ** 0.5 if cnt else float("nan")
            shape_note = "" if sa == sb else f"  SHAPE ops={sa} ufs={sb} (node/level diff)"
            val = "MATCH" if md <= TOL else "DIFF"
            ok = ok and (md <= TOL) and (sa == sb)
            print(f"  {fn:13s}: {val}{shape_note}")
            print(f"               common[{nt}x{nn}] sampled {len(list(idx))} steps: "
                  f"max|diff|={md:.3e} rmse={rmse:.3e}")
            dsa.close(); dsb.close()
    finally:
        shutil.rmtree(da, ignore_errors=True)
        shutil.rmtree(db, ignore_errors=True)
    return ok


def main():
    global TOL
    ap = argparse.ArgumentParser(description="Validate OBC/River/Tides parity between two COMOUTs.")
    ap.add_argument("--ops-dir", required=True, help="operational/standalone COMOUT")
    ap.add_argument("--ufs-dir", required=True, help="secofs_ufs COMOUT")
    ap.add_argument("--phase", default="nowcast", choices=("nowcast", "forecast"))
    ap.add_argument("--products", default="obc,river,tides",
                    help="comma list of obc,river,tides (default all)")
    ap.add_argument("--tol", type=float, default=TOL)
    a = ap.parse_args()
    TOL = a.tol
    want = {p.strip() for p in a.products.split(",")}

    print(f"ops : {a.ops_dir}")
    print(f"ufs : {a.ufs_dir}")
    print(f"phase={a.phase}  products={sorted(want)}  tol={TOL:g}\n")

    results = {}
    if "obc" in want:
        results["OBC"] = compare_obc(a.ops_dir, a.ufs_dir, a.phase)
    if "river" in want:
        results["RIVER"] = compare_river(a.ops_dir, a.ufs_dir)
    if "tides" in want:
        results["TIDES"] = compare_tides(a.ops_dir, a.ufs_dir, a.phase)

    print("=" * 70)
    for k, v in results.items():
        print(f"  {k:6s}: {'MATCH' if v else ('SKIP' if v is None else 'DIFF')}")
    hard = [v for v in results.values() if v is not None]
    print("OVERALL:", "MATCH" if hard and all(hard) else ("SKIP" if not hard else "DIFF"))
    sys.exit(0 if (hard and all(hard)) else 1)


if __name__ == "__main__":
    main()
