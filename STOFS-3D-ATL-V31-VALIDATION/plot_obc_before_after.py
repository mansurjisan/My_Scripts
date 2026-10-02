#!/usr/bin/env python3
"""
Before vs after summary: difference to the operational STOFS-3D-ATL boundary
files at one node, for elev2D, TEM and SAL (3D at one vertical level), for the
"before ops-parity fix" forecast files (left) and the current nos-workflow
files (right). Each panel has its own symmetric, auto-scaled y-axis (stated in
the panel); max |diff| and RMS over all boundary nodes are printed in the panel.

Files are PATH:YYYYMMDDHH; only exactly matching record times are compared.

Usage:
  python3 plot_obc_before_after.py --nodes-csv obc_nodes.csv \
      --ops-elev E:2026092612 --ours-elev A:2026092612 B:2026092712 --before-elev C:2026092712 \
      --ops-tem ... --ours-tem ... --before-tem ... --ops-sal ... --ours-sal ... --before-sal ... \
      [--node 200] [--level -1] [--cycle 2026092712] [--out before_after.png]
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import obc_common as oc


def main():
    ap = argparse.ArgumentParser()
    for v in ("elev", "tem", "sal"):
        for w in ("ops", "ours", "before"):
            ap.add_argument(f"--{w}-{v}", nargs="+", required=True)
    ap.add_argument("--nodes-csv", required=True)
    ap.add_argument("--node", type=int, default=200)
    ap.add_argument("--level", type=int, default=-1)
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--out", default="obc_before_after.png")
    a = ap.parse_args()

    cyc = oc.parse_dt(a.cycle)
    lon, lat, dep, seg = oc.load_nodes(a.nodes_csv)
    nd = a.node
    fig, ax = plt.subplots(3, 2, figsize=(16, 11), constrained_layout=True)
    for r, (v, var, unit, nm) in enumerate([("elev", "elev", "m", "SSH (elev2D)"),
                                           ("tem", "TEM", "degC", "temperature"),
                                           ("sal", "SAL", "psu", "salinity")]):
        kw = {} if var == "elev" else dict(level=a.level)
        to, O = oc.load_series(getattr(a, f"ops_{v}"), var, **kw)
        for c, (w, col, lab) in enumerate([("before", oc.COLORS["before"], "before ops-parity fix"),
                                           ("ours", oc.COLORS["ours"], "nos-workflow (nos-utils)")]):
            tx, X = oc.load_series(getattr(a, f"{w}_{v}"), var, **kw)
            io, ix = oc.common(to, tx)
            keep = to[io] >= round((cyc - oc.EPOCH).total_seconds())   # forecast period
            io, ix = io[keep], ix[keep]
            D = X[ix] - O[io]
            mx, rms = oc.stats(D)
            p = ax[r, c]
            td = [oc.to_dt(s) for s in to[io]]
            p.fill_between(td, np.nanmin(D, axis=1), np.nanmax(D, axis=1), color="0.88", label="range over all boundary nodes")
            p.plot(td, D[:, nd], color=col, lw=1.6, marker="o", ms=3, label=f"node {nd}")
            p.axhline(0, color="k", lw=0.5)
            lim = max(float(np.nanmax(np.abs(D))), 1e-12) * 1.15
            p.set_ylim(-lim, lim)
            p.set_xlim(td[0], td[-1])
            oc.fmt_time_axis(p)
            p.set_title(f"{nm}: {lab} minus operational", fontsize=10)
            p.set_ylabel(f"difference ({unit})")
            p.text(0.02, 0.04, f"all nodes{'' if var == 'elev' else ', level ' + str(a.level)}: "
                   f"max |diff| = {oc.fmt(mx)} {unit}, RMS = {oc.fmt(rms)} {unit}\n"
                   f"y-axis symmetric, auto-scaled to +/-{oc.fmt(lim)} {unit}",
                   transform=p.transAxes, fontsize=8, va="bottom", bbox=dict(fc="w", ec="0.6", alpha=0.9))
            p.grid(True, alpha=0.25)
            if r == 0 and c == 0:
                p.legend(fontsize=8, loc="upper right")
            print(f"{var} {w}: max={mx:.4g} rms={rms:.4g} {unit}")
    fig.suptitle(f"Difference to operational STOFS-3D-ATL at node {nd} ({abs(lon[nd]):.1f}W {lat[nd]:.1f}N, "
                 f"depth {dep[nd]:.0f} m): before vs after the ops-parity fix, {oc.cycle_label(cyc)}\n"
                 "forecast period, common record times only; note the different y-axis scale in each panel",
                 fontsize=13, fontweight="bold")
    oc.save(fig, a.out)


if __name__ == "__main__":
    main()
