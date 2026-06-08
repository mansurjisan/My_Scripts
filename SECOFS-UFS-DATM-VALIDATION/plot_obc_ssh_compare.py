#!/usr/bin/env python3
"""
OBC elev2D (SSH) time-series comparison at a few boundary nodes:
operational (secofs) vs UFS (secofs_ufs), reference-plot style (2x2 nodes).

Inputs are the two elev2D.th.nc files (extract them from obc.tar first, e.g.
  tar -xf <obc.tar> elev2D.th.nc).

Usage:
  python3 plot_obc_ssh_compare.py OPS_elev2D.th.nc UFS_elev2D.th.nc \
      [--out ssh.png] [--nodes 0,500,1000,1400] [--label "..."]
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from netCDF4 import Dataset


def load(path):
    ds = Dataset(path)
    t = np.array(ds.variables["time"][:], dtype="f8")
    ts = np.array(ds.variables["time_series"][:, :, 0, 0], dtype="f8")  # (time, node)
    ds.close()
    return t, ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--out", default="obc_ssh_compare.png")
    ap.add_argument("--nodes", default="0,500,1000,1400")
    ap.add_argument("--maxlag", type=int, default=400, help="max alignment lag in steps")
    ap.add_argument("--label", default="operational (secofs) vs UFS (secofs_ufs)")
    a = ap.parse_args()

    to, so = load(a.ops); tu, su = load(a.ufs)
    nn = min(so.shape[1], su.shape[1])
    so, su = so[:, :nn], su[:, :nn]
    dt = (to[1] - to[0]) if len(to) > 1 else 120.0

    # The two OBC windows can differ in nowcast lookback and there is no
    # base_date in the file, so AUTO-ALIGN: find the integer step lag that
    # minimizes RMSE (search a subset of nodes for speed), then trim to overlap.
    sub = slice(0, nn, max(1, nn // 40))
    best = (0, np.inf)
    for lag in range(-a.maxlag, a.maxlag + 1):
        if lag >= 0:
            A = so[lag:, sub]; B = su[:A.shape[0], sub]
        else:
            A = so[:, sub]; B = su[-lag:, sub]; A = A[:B.shape[0]]
        n = min(A.shape[0], B.shape[0])
        if n < 300:
            continue
        rr = np.sqrt(np.nanmean((A[:n] - B[:n]) ** 2))
        if rr < best[1]:
            best = (lag, rr)
    lag = best[0]
    offset_h = lag * dt / 3600.0
    if lag >= 0:
        so, su = so[lag:], su[:so.shape[0] - lag]
    else:
        so, su = so[:su.shape[0] + lag], su[-lag:]
    nt = min(so.shape[0], su.shape[0])
    so, su = so[:nt], su[:nt]
    ho = hu = np.arange(nt) * dt / 3600.0   # hours into the aligned overlap
    nodes = [int(x) for x in a.nodes.split(",") if int(x) < nn]

    # overall stats over the common window
    diff = su - so
    rmse_mm = float(np.sqrt(np.nanmean(diff ** 2))) * 1000.0
    maxmm = float(np.nanmax(np.abs(diff))) * 1000.0
    r = np.corrcoef(so.ravel(), su.ravel())[0, 1]

    fig, axes = plt.subplots(2, 2, figsize=(16, 9), constrained_layout=True)
    for ax, nd in zip(axes.ravel(), nodes):
        ax.plot(ho, so[:, nd], color="blue", lw=1.6, label="operational (secofs)")
        ax.plot(hu, su[:, nd], color="red", lw=1.2, ls="--", label="UFS (secofs_ufs)")
        ax.set_title(f"Node {nd}")
        ax.set_xlabel("Time (hours)"); ax.set_ylabel("SSH (m)")
        ax.grid(True, alpha=0.25); ax.legend(fontsize=9)

    fig.suptitle(f"OBC elev2D (SSH): {a.label}\n"
                 f"aligned (ops leads ufs by {offset_h:+.1f}h), {nt} steps x {nn} nodes   "
                 f"RMSE={rmse_mm:.3f}mm  max|diff|={maxmm:.3f}mm  R={r:.6f}",
                 fontsize=14, fontweight="bold")
    fig.savefig(a.out, dpi=130, bbox_inches="tight")
    print(f"saved {a.out}  (RMSE={rmse_mm:.3f}mm, max={maxmm:.3f}mm, R={r:.6f})")


if __name__ == "__main__":
    main()
