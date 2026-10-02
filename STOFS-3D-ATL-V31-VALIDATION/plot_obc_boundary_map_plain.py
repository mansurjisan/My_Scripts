#!/usr/bin/env python3
"""
Open-boundary map in the plain SECOFS-validation style: rows = snapshot times,
columns = operational | nos-workflow | difference, scatter on lon/lat axes with
a colorbar per panel and the RMSE in the difference title.

Works for elev2D (SSH) and the 3D files (TEM_3D / SAL_3D / uv3D at one level).

Usage:
  python3 plot_obc_boundary_map_plain.py --nodes-csv obc_nodes.csv \
      --ops OPS_elev2dth_non_adj.nc:2026092612 \
      --ours now/elev2D.th.nc:2026092612 fcst/elev2dth_non_adj.nc:2026092712 \
      [--var elev|TEM|SAL|uv] [--level -1] [--component 0|1] \
      [--snaps 2026092612,2026092618,2026092700] [--cycle 2026092712] [--out map.png]

Each file is PATH:YYYYMMDDHH, the absolute time of its time=0. Snapshots must be
record times present in both series (no interpolation).
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from obc_common import (EPOCH, common, cycle_label, load_nodes, load_series,
                        parse_dt, save, to_dt)

UNITS = {"elev": ("SSH", "m"), "TEM": ("temperature", "degC"),
         "SAL": ("salinity", "psu"), "uv": ("velocity", "m/s")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes-csv", required=True)
    ap.add_argument("--ops", required=True)
    ap.add_argument("--ours", nargs="+", required=True)
    ap.add_argument("--var", default="elev", choices=["elev", "TEM", "SAL", "uv"])
    ap.add_argument("--level", type=int, default=-1, help="3D level (-1 surface, 0 bottom)")
    ap.add_argument("--component", type=int, default=None, help="uv: 0=u, 1=v; default speed")
    ap.add_argument("--snaps", default=None, help="comma YYYYMMDDHH (default 3 spread over the common times)")
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--ours-label", default="nos-workflow (nos-utils)")
    ap.add_argument("--out", default="obc_boundary_map_plain.png")
    a = ap.parse_args()

    lon, lat, _, _ = load_nodes(a.nodes_csv)
    level = None if a.var == "elev" else a.level
    to, O = load_series(a.ops, a.var, a.component, level)
    tu, U = load_series(a.ours, a.var, a.component, level)
    io, iu = common(to, tu)
    to, O, U = to[io], O[io], U[iu]

    if a.snaps:
        want = [round((parse_dt(s) - EPOCH).total_seconds()) for s in a.snaps.split(",")]
        idx = [int(np.where(to == w)[0][0]) for w in want if w in to]
        if not idx:
            raise SystemExit("none of --snaps is a common record time")
    else:
        idx = sorted({0, len(to) // 2, len(to) - 1})

    name, unit = UNITS[a.var]
    if a.var == "uv":
        name = {0: "u velocity", 1: "v velocity"}.get(a.component, "speed")
    lvl = "" if a.var == "elev" else (" surface" if a.level == -1 else
                                      " bottom" if a.level == 0 else f" level {a.level + 1}")
    signed = a.var == "elev" or (a.var == "uv" and a.component is not None)
    both = np.concatenate([O[idx].ravel(), U[idx].ravel()])
    if signed:
        vmax = np.nanmax(np.abs(both)); vlo, vhi, cmap = -vmax, vmax, "RdBu_r"
    else:
        vlo, vhi, cmap = np.nanmin(both), np.nanmax(both), "viridis"
    D = U[idx] - O[idx]
    dmax = max(float(np.nanmax(np.abs(D))), 1e-12)
    in_mm = a.var == "elev"

    fig, ax = plt.subplots(len(idx), 3, figsize=(15, 4.4 * len(idx)), constrained_layout=True)
    ax = np.atleast_2d(ax)
    for r, k in enumerate(idx):
        when = to_dt(to[k]).strftime("%Y-%m-%d %HZ")
        d = U[k] - O[k]
        rmse = float(np.sqrt(np.nanmean(d * d)))
        rm_txt = f"RMSE={rmse * 1000:.3g}mm" if in_mm else f"RMSE={rmse:.3g} {unit}"
        panels = [(O[k], f"operational  {when}", cmap, vlo, vhi, f"{name} ({unit})"),
                  (U[k], a.ours_label, cmap, vlo, vhi, f"{name} ({unit})"),
                  (d, f"diff (nos-workflow - ops)  {rm_txt}", "bwr", -dmax, dmax, unit)]
        for c, (dat, ttl, cm, lo, hi, cbl) in enumerate(panels):
            sc = ax[r, c].scatter(lon, lat, c=dat, s=6, cmap=cm, vmin=lo, vmax=hi)
            plt.colorbar(sc, ax=ax[r, c], fraction=0.046, pad=0.04, label=cbl)
            ax[r, c].set_title(ttl, fontsize=10)
            ax[r, c].set_xlabel("lon"); ax[r, c].set_ylabel("lat")
            ax[r, c].set_aspect("auto")
    fig.suptitle(f"{name}{lvl} at open-boundary nodes ({len(lon)}): operational STOFS-3D-ATL vs "
                 f"{a.ours_label}  -  {cycle_label(parse_dt(a.cycle))}",
                 fontsize=14, fontweight="bold")
    save(fig, a.out)


if __name__ == "__main__":
    main()
