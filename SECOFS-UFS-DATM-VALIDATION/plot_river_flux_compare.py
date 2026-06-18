#!/usr/bin/env python3
"""
River flow-boundary forcing comparison: operational vs UFS, from schism_flux.th
(SCHISM flow-boundary discharge; col0=time(s), cols1..N = per-river flux m3/s,
negative = inflow). This is the COMF river.ctl open-boundary USGS river family,
SEPARATE from the NWM vsource source/sink family (see plot_nwm_vsource_compare.py).
Auto-aligns the nowcast-window offset (same structural shift as OBC).

Usage:
  python3 plot_river_flux_compare.py OPS_schism_flux.th UFS_schism_flux.th \
      [--out river.png] [--label "..."] [--maxlag 300] [--unit "m3/s"]
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--out", default="river_flux_compare.png")
    ap.add_argument("--label", default="operational vs UFS")
    ap.add_argument("--maxlag", type=int, default=300)
    ap.add_argument("--unit", default="m3/s")
    a = ap.parse_args()

    O = np.loadtxt(a.ops); U = np.loadtxt(a.ufs)
    to, fo = O[:, 0], O[:, 1:]
    tu, fu = U[:, 0], U[:, 1:]
    nr = min(fo.shape[1], fu.shape[1]); fo, fu = fo[:, :nr], fu[:, :nr]
    dt = (to[1] - to[0]) if len(to) > 1 else 3600.0

    # River flux is typically ~constant (climatological flow boundary), so
    # cross-correlation is unreliable. The windows differ only in leading
    # lookback (same structural offset as OBC), so END-align: keep the last nt
    # steps of each (both end at cycle+forecast).
    nt = min(fo.shape[0], fu.shape[0])
    off_h = (max(fo.shape[0], fu.shape[0]) - nt) * dt / 3600.0
    fo, fu = fo[-nt:], fu[-nt:]
    hrs = np.arange(nt) * dt / 3600.0

    rmse = float(np.sqrt(np.nanmean((fu - fo) ** 2)))
    mx = float(np.nanmax(np.abs(fu - fo)))

    ncol = min(3, nr); nrow = int(np.ceil(nr / ncol))
    fig, ax = plt.subplots(nrow, ncol, figsize=(6 * ncol, 3.4 * nrow),
                           constrained_layout=True, squeeze=False)
    for k in range(nrow * ncol):
        r, c = divmod(k, ncol); axk = ax[r][c]
        if k >= nr:
            axk.axis("off"); continue
        axk.plot(hrs, fo[:, k], color="blue", lw=1.6, label="operational")
        axk.plot(hrs, fu[:, k], color="red", lw=1.1, ls="--", label="UFS")
        rk = np.sqrt(np.nanmean((fu[:, k] - fo[:, k]) ** 2))
        axk.set_title(f"river {k + 1}   RMSE={rk:.3g} {a.unit}", fontsize=10)
        axk.set_xlabel("Time (hours)"); axk.set_ylabel(a.unit)
        axk.grid(True, alpha=0.25); axk.legend(fontsize=8)
    fig.suptitle(f"River flow-boundary flux: {a.label}\n"
                 f"end-aligned (window diff {off_h:.1f}h), {nt} steps x {nr} cols   "
                 f"RMSE={rmse:.4g}  max|diff|={mx:.4g} {a.unit}",
                 fontsize=14, fontweight="bold")
    fig.savefig(a.out, dpi=130, bbox_inches="tight")
    print(f"saved {a.out}  (offset {off_h:+.1f}h, RMSE={rmse:.4g}, max={mx:.4g})")


if __name__ == "__main__":
    main()
