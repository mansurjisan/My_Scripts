#!/usr/bin/env python3
"""
OBC 3D boundary map (TEM, SAL or uv): operational vs nos-workflow vs difference
at one vertical level on the open-boundary nodes, at a few common times
(cartopy 10m coastline; main boundary plus a Belle Isle strait panel).
Node lon/lat come from the CSV written by extract_obc_nodes.py.

Files are PATH:YYYYMMDDHH (absolute UTC time of time=0); only exactly matching
record times are used. The diff colour scale is symmetric and auto-scaled.
uv defaults to speed; --component 0/1 gives u/v. Level index: 0 = bottom,
-1 = surface.

Usage:
  python3 plot_obc_3d_boundary_map.py --nodes-csv obc_nodes.csv \
      --ops OPS_tem3dth.nc:2026092612 \
      --ours NOW_TEM_3D.th.nc:2026092612 FCST_tem3dth.nc:2026092712 \
      [--level -1] [--var auto] [--component 0] \
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
    ap.add_argument("--var", default="auto")
    ap.add_argument("--component", type=int, default=None)
    ap.add_argument("--level", type=int, default=-1)
    ap.add_argument("--snaps", default=None, help="comma YYYYMMDDHH (default 3 evenly spaced)")
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--out", default="obc_3d_boundary_map.png")
    a = ap.parse_args()

    var = oc.detect_var(a.ops[0].rsplit(":", 1)[0], a.var); unit = oc.UNITS[var]
    cyc = oc.parse_dt(a.cycle)
    lon, lat, dep, seg = oc.load_nodes(a.nodes_csv)
    to, O = oc.load_series(a.ops, var, a.component, level=a.level)    # (T, N)
    tu, U = oc.load_series(a.ours, var, a.component, level=a.level)
    io, iu = oc.common(to, tu)
    t = to[io]; O, U = O[io], U[iu]
    if a.snaps:
        want = [round((oc.parse_dt(s) - oc.EPOCH).total_seconds()) for s in a.snaps.split(",")]
        sel = [int(np.where(t == w)[0][0]) for w in want if w in t]
    else:
        sel = sorted({0, len(t) // 2, len(t) - 1})
    times = [oc.to_dt(t[i]) for i in sel]
    lvname = "surface" if a.level == -1 else "bottom" if a.level == 0 else f"level {a.level}"
    what = "speed" if (var == "uv" and a.component is None) else (
        "u" if var == "uv" and a.component == 0 else "v" if var == "uv" else var)
    kw = dict(vmin=0.0) if what == "speed" else {}
    if kw:
        kw["vmax"] = max(float(np.nanmax(O[sel])), float(np.nanmax(U[sel])), 1e-6)
    mx, rms = oc.stats(U[sel] - O[sel])
    oc.boundary_map(a.out, lon, lat, seg, times, O[sel], U[sel], unit,
                    f"{var} {what}" if var == "uv" else var,
                    f"Open-boundary {var}{' ' + what if var == 'uv' else ''}, {lvname} level: "
                    f"{oc.NAMES['ops']} vs {oc.NAMES['ours']}, {oc.cycle_label(cyc)}",
                    cmap="viridis", cycle=cyc, **kw)
    print(f"shown snapshots: max|diff|={mx:.4g} {unit} RMS={rms:.4g}")


if __name__ == "__main__":
    main()
