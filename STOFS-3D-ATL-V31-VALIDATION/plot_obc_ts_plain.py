#!/usr/bin/env python3
"""
Open-boundary time series at four nodes in the plain SECOFS-validation style
(2x2 panels, operational solid blue vs nos-workflow dashed red), with the overall
RMSE, max |diff| and correlation over all boundary nodes in the title.

Works for elev2D (SSH) and the 3D files (TEM_3D / SAL_3D / uv3D at one level).

Usage:
  python3 plot_obc_ts_plain.py --ops OPS_elev2dth_non_adj.nc:2026092612 \
      --ours now/elev2D.th.nc:2026092612 fcst/elev2dth_non_adj.nc:2026092712 \
      [--var elev|TEM|SAL|uv] [--level -1] [--component 0|1] \
      [--nodes 8,200,500,766] [--cycle 2026092712] [--out ts.png]

Each file is PATH:YYYYMMDDHH, the absolute time of its time=0. Several --ours
files are merged into one series. Statistics use only record times present in
both series (no interpolation or alignment search).
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from obc_common import common, cycle_label, load_series, parse_dt, save, to_dt

UNITS = {"elev": ("SSH", "m"), "TEM": ("temperature", "degC"),
         "SAL": ("salinity", "psu"), "uv": ("velocity", "m/s")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ops", required=True)
    ap.add_argument("--ours", nargs="+", required=True)
    ap.add_argument("--var", default="elev", choices=["elev", "TEM", "SAL", "uv"])
    ap.add_argument("--level", type=int, default=-1, help="3D level (-1 surface, 0 bottom)")
    ap.add_argument("--component", type=int, default=None, help="uv: 0=u, 1=v; default speed")
    ap.add_argument("--nodes", default="8,200,500,766")
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--ours-label", default="nos-workflow (nos-utils)")
    ap.add_argument("--out", default="obc_ts_plain.png")
    a = ap.parse_args()

    level = None if a.var == "elev" else a.level
    to, O = load_series(a.ops, a.var, a.component, level)
    tu, U = load_series(a.ours, a.var, a.component, level)
    io, iu = common(to, tu)
    d = U[iu] - O[io]
    rmse = float(np.sqrt(np.nanmean(d * d)))
    dmax = float(np.nanmax(np.abs(d)))
    ok = np.isfinite(O[io]) & np.isfinite(U[iu])
    with np.errstate(invalid="ignore", divide="ignore"):
        r = float(np.corrcoef(O[io][ok], U[iu][ok])[0, 1])
    r_txt = f"R={r:.6f}" if np.isfinite(r) else "R=n/a (constant series)"

    name, unit = UNITS[a.var]
    if a.var == "uv":
        name = {0: "u velocity", 1: "v velocity"}.get(a.component, "speed")
    lvl = "" if a.var == "elev" else (" surface" if a.level == -1 else
                                      " bottom" if a.level == 0 else f" level {a.level + 1}")
    if a.var == "elev":
        st = f"RMSE={rmse * 1000:.3g}mm   max|diff|={dmax * 1000:.3g}mm"
    else:
        st = f"RMSE={rmse:.3g} {unit}   max|diff|={dmax:.3g} {unit}"

    t_ref = to[0]
    ho, hu = (to - t_ref) / 3600.0, (tu - t_ref) / 3600.0
    hc = (parse_dt(a.cycle).timestamp() - t_ref) / 3600.0
    start = to_dt(t_ref).strftime("%Y-%m-%d %HZ")
    nodes = [int(x) for x in a.nodes.split(",") if int(x) < O.shape[1]][:4]

    fig, axes = plt.subplots(2, 2, figsize=(15.5, 8.7), constrained_layout=True)
    for ax, nd in zip(axes.ravel(), nodes):
        ax.plot(ho, O[:, nd], color="blue", lw=1.6, label="operational STOFS-3D-ATL")
        ax.plot(hu, U[:, nd], color="red", lw=1.2, ls="--", label=a.ours_label)
        ax.axvline(hc, color="gray", lw=0.8, ls=":")
        ax.set_title(f"Node {nd}")
        ax.set_xlabel(f"Time (hours since {start}; dotted line = cycle)")
        ax.set_ylabel(f"{name} ({unit})")
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=9)
    fig.suptitle(f"OBC {name}{lvl}: operational STOFS-3D-ATL vs {a.ours_label}  -  "
                 f"{cycle_label(parse_dt(a.cycle))}\n{len(io)} common records x {O.shape[1]} nodes   "
                 f"{st}   {r_txt}", fontsize=13, fontweight="bold")
    save(fig, a.out)


if __name__ == "__main__":
    main()
