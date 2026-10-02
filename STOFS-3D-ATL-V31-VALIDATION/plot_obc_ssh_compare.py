#!/usr/bin/env python3
"""
OBC elev2D (SSH) time series at a few open-boundary nodes: operational
STOFS-3D-ATL vs nos-workflow (nowcast + forecast as one series), optional
"before the ops-parity fix" series, plus a difference panel.

Files are PATH:YYYYMMDDHH (absolute UTC time of time=0). Differences use only
records whose absolute times match exactly (no interpolation).

Usage:
  python3 plot_obc_ssh_compare.py --nodes-csv obc_nodes.csv \
      --ops ops/stofs_3d_atl.t12z.elev2dth_non_adj.nc:2026092612 \
      --ours now/elev2D.th.nc:2026092612 fcst/..elev2dth_non_adj.nc:2026092712 \
      [--before port/..elev2dth_non_adj.nc:2026092712] \
      [--nodes 8,200,500,728,766] [--cycle 2026092712] [--out ssh.png]
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import obc_common as oc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ops", nargs="+", required=True)
    ap.add_argument("--ours", nargs="+", required=True)
    ap.add_argument("--before", nargs="+", default=None)
    ap.add_argument("--nodes-csv", required=True)
    ap.add_argument("--nodes", default=oc.DEFAULT_NODES, help="0-based node indices")
    ap.add_argument("--cycle", default="2026092712", help="cycle time YYYYMMDDHH")
    ap.add_argument("--out", default="obc_ssh_compare.png")
    a = ap.parse_args()

    cyc = oc.parse_dt(a.cycle)
    lon, lat, dep, seg = oc.load_nodes(a.nodes_csv)
    nodes = [int(x) for x in a.nodes.split(",")]
    to, Oall = oc.load_series(a.ops, "elev")
    tu, Uall = oc.load_series(a.ours, "elev")
    io, iu = oc.common(to, tu)
    Dall = Uall[iu] - Oall[io]
    mx, rms = oc.stats(Dall)                       # all boundary nodes
    O, U = Oall[:, nodes], Uall[:, nodes]
    D = U[iu] - O[io]
    td = [oc.to_dt(s) for s in to[io]]
    B = None
    if a.before:
        tb, Ball = oc.load_series(a.before, "elev")
        jo, jb = oc.common(to, tb)
        bmx, brms = oc.stats(Ball[jb] - Oall[jo])
        B = Ball[:, nodes]

    fig, axes = plt.subplots(3, 2, figsize=(16, 11), constrained_layout=True)
    ax = axes.ravel()
    xlo, xhi = oc.to_dt(min(to[0], tu[0])), oc.to_dt(max(to[-1], tu[-1]))
    for k, nd in enumerate(nodes):
        p = ax[k]
        p.plot([oc.to_dt(s) for s in to], O[:, k], color=oc.COLORS["ops"], lw=1.8, label=oc.NAMES["ops"])
        p.plot([oc.to_dt(s) for s in tu], U[:, k], color=oc.COLORS["ours"], lw=1.2, ls="--", label=oc.NAMES["ours"])
        if B is not None:
            p.plot([oc.to_dt(s) for s in tb], B[:, k], color=oc.COLORS["before"], lw=1.2, ls=":", label=oc.NAMES["before"])
        p.set_title(oc.node_label(nd, lon[nd], lat[nd], dep[nd], seg[nd]), fontsize=10)
        p.set_ylabel("SSH (m)"); p.grid(True, alpha=0.25)
        p.set_xlim(xlo, xhi)
        oc.shade_phases(p, cyc, (xlo, xhi), label=(k == 0))
        oc.fmt_time_axis(p)
        if k == 0:
            p.legend(fontsize=8, loc="lower left")

    p = ax[5]
    p.fill_between(td, np.nanmin(Dall, axis=1), np.nanmax(Dall, axis=1), color="0.8",
                   label=f"range over all {Oall.shape[1]} nodes")
    for k, nd in enumerate(nodes):
        p.plot(td, D[:, k], color=oc.NODE_COLORS[k % 5], lw=1.2, marker="o", ms=3, label=f"node {nd}")
    p.axhline(0, color="k", lw=0.5)
    lim = max(mx, 1e-12) * 1.15
    p.set_ylim(-lim, lim)
    p.set_xlim(xlo, xhi)
    oc.shade_phases(p, cyc, (xlo, xhi), label=False)
    oc.fmt_time_axis(p)
    p.set_ylabel("nos-workflow - operational (m)")
    p.set_title("Difference at common record times (y-axis symmetric, auto-scaled to max |diff|)", fontsize=10)
    txt = f"all {Oall.shape[1]} nodes: max |diff| = {oc.fmt(mx)} m, RMS = {oc.fmt(rms)} m"
    if B is not None:
        txt += f"\nbefore fix vs operational: max |diff| = {oc.fmt(bmx)} m, RMS = {oc.fmt(brms)} m"
    p.text(0.02, 0.05, txt, transform=p.transAxes, fontsize=9, va="bottom",
           bbox=dict(fc="w", ec="0.6", alpha=0.9))
    p.grid(True, alpha=0.25); p.legend(fontsize=8, ncol=3, loc="upper right")

    fig.suptitle(f"Open-boundary elev2D (SSH): {oc.NAMES['ops']} vs {oc.NAMES['ours']}, "
                 f"{oc.cycle_label(cyc)}", fontsize=14, fontweight="bold")
    oc.save(fig, a.out)
    print(f"ours-ops: max|diff|={mx:.4g} m RMS={rms:.4g} m over {len(io)} common records"
          + (f"; before-ops: max={bmx:.4g} RMS={brms:.4g}" if B is not None else ""))


if __name__ == "__main__":
    main()
