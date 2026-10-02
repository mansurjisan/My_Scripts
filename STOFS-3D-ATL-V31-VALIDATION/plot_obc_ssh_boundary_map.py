#!/usr/bin/env python3
"""
OBC elev2D (SSH) boundary map: operational vs nos-workflow vs difference on the
open-boundary nodes at a few common times (cartopy 10m coastline; main boundary
plus a Belle Isle strait panel). Node lon/lat come from the CSV written by
extract_obc_nodes.py (first 778 nodes of open boundaries 1-2).

Files are PATH:YYYYMMDDHH (absolute UTC time of time=0); only exactly matching
record times are used. The diff colour scale is symmetric and auto-scaled.

Usage:
  python3 plot_obc_ssh_boundary_map.py --nodes-csv obc_nodes.csv \
      --ops OPS.nc:2026092612 --ours NOW.nc:2026092612 FCST.nc:2026092712 \
      [--snaps 2026092612,2026092712,2026093012] [--cycle 2026092712] [--out map.png]
"""
import argparse

import numpy as np

import obc_common as oc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ops", nargs="+", required=True)
    ap.add_argument("--ours", nargs="+", required=True)
    ap.add_argument("--nodes-csv", required=True)
    ap.add_argument("--snaps", default=None, help="comma YYYYMMDDHH (default 3 evenly spaced)")
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--out", default="obc_ssh_boundary_map.png")
    a = ap.parse_args()

    lon, lat, dep, seg = oc.load_nodes(a.nodes_csv)
    to, O = oc.load_series(a.ops, "elev")
    tu, U = oc.load_series(a.ours, "elev")
    io, iu = oc.common(to, tu)
    t = to[io]; O, U = O[io], U[iu]
    if a.snaps:
        want = [round((oc.parse_dt(s) - oc.EPOCH).total_seconds()) for s in a.snaps.split(",")]
        sel = [int(np.where(t == w)[0][0]) for w in want if w in t]
    else:
        sel = sorted({0, len(t) // 2, len(t) - 1})
    times = [oc.to_dt(t[i]) for i in sel]
    mx, rms = oc.stats(U[sel] - O[sel])
    oc.boundary_map(a.out, lon, lat, seg, times, O[sel], U[sel], "m", "SSH", 
                    f"Open-boundary SSH (elev2D): {oc.NAMES['ops']} vs {oc.NAMES['ours']}, "
                    f"{oc.cycle_label(oc.parse_dt(a.cycle))}",
                    cmap="RdBu_r", symmetric=True, cycle=oc.parse_dt(a.cycle))
    print(f"shown snapshots: max|diff|={mx:.4g} m RMS={rms:.4g} m")


if __name__ == "__main__":
    main()
