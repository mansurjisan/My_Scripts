#!/usr/bin/env python3
"""
OBC 3D boundary forcing comparison (depth-aware): operational (secofs) vs UFS
(secofs_ufs), for the SCHISM *_3D.th.nc files:

  TEM_3D.th.nc  temperature (degC,  ncomp=1)
  SAL_3D.th.nc  salinity    (psu,   ncomp=1)
  uv3D.th.nc    velocity    (m/s,   ncomp=2 -> u, v; default metric = speed)

Layout (same as elev2D): variable `time_series` with dims
(time, nOpenBndNodes, nLevels, nComponents). Extract the file from obc.tar first:
  tar -xf <obc.tar> TEM_3D.th.nc

Auto-aligns the nowcast-window offset by cross-correlation (no base_date in file).

Panels: domain-mean(t), per-level RMSE, depth profile at a node, surface
time-series at a node.

Usage:
  python3 plot_obc_3d_compare.py OPS_TEM_3D.th.nc UFS_TEM_3D.th.nc \
      [--out tem.png] [--var auto|TEM|SAL|uv] [--component -1] \
      [--node 700] [--nodes 0,500,1000,1400] [--maxlag 400] [--label "..."]
"""
import argparse
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from netCDF4 import Dataset

UNITS = {"TEM": "degC", "SAL": "psu", "uv": "m/s"}


def detect_var(path, override):
    if override and override != "auto":
        return override
    b = os.path.basename(path).upper()
    if "TEM" in b:
        return "TEM"
    if "SAL" in b:
        return "SAL"
    if "UV" in b:
        return "uv"
    return "TEM"


def load(path):
    """Return (time[s], time_series(T, N, L, C))."""
    ds = Dataset(path)
    ts = np.array(ds.variables["time_series"][:], dtype="f8")
    while ts.ndim < 4:
        ts = ts[..., None]
    if "time" in ds.variables:
        t = np.array(ds.variables["time"][:], dtype="f8")
    elif "time_step" in ds.variables:
        dt = float(np.array(ds.variables["time_step"][:]).ravel()[0])
        t = np.arange(ts.shape[0]) * dt
    else:
        t = np.arange(ts.shape[0], dtype="f8")
    ds.close()
    return t, ts


def to_metric(ts, var, comp):
    """Collapse the component axis to a single scalar field (T, N, L)."""
    if ts.shape[-1] == 1:
        return ts[..., 0]
    if var == "uv" and comp is None:
        return np.hypot(ts[..., 0], ts[..., 1])      # speed
    return ts[..., comp]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--out", default="obc_3d_compare.png")
    ap.add_argument("--var", default="auto", help="auto|TEM|SAL|uv")
    ap.add_argument("--component", type=int, default=None,
                    help="uv: 0=u, 1=v; default None=speed")
    ap.add_argument("--node", type=int, default=None, help="node for depth profile")
    ap.add_argument("--nodes", default="0,500,1000,1400")
    ap.add_argument("--maxlag", type=int, default=400)
    ap.add_argument("--offset-hours", type=float, default=None,
                    help="force the ops->ufs window lag in hours and skip "
                         "auto-align. Use the value TEM_3D finds (the smooth "
                         "SAL field and the zero uv field do not cross-correlate "
                         "reliably; all OBC vars share the same tar time base).")
    ap.add_argument("--label", default="operational (secofs) vs UFS (secofs_ufs)")
    a = ap.parse_args()

    var = detect_var(a.ops, a.var)
    unit = UNITS.get(var, "")
    to, Oraw = load(a.ops); tu, Uraw = load(a.ufs)  # (T, N, L, C)
    nN = min(Oraw.shape[1], Uraw.shape[1]); nL = min(Oraw.shape[2], Uraw.shape[2])
    Oraw, Uraw = Oraw[:, :nN, :nL], Uraw[:, :nN, :nL]
    dt = (to[1] - to[0]) if len(to) > 1 else 120.0

    # AUTO-ALIGN in time (windows differ in nowcast lookback; no base_date in
    # file). Lock onto the SURFACE level of the FIRST component: it is
    # directional and aligns uniquely, whereas speed (sqrt(u^2+v^2)) halves the
    # tidal period and can alias to a wrong lag.
    surf = nL - 1
    if a.offset_hours is not None:
        lag = int(round(a.offset_hours * 3600.0 / dt))
    else:
        sub = slice(0, nN, max(1, nN // 40))
        os_, us_ = Oraw[:, sub, surf, 0], Uraw[:, sub, surf, 0]
        # Require at least half the shorter series to overlap. The 3D OBC files
        # are coarse (3-hourly, ~18 steps), so a fixed large floor would skip
        # every lag and leave the windows unaligned; elev2D-style 120s files
        # (~1600 steps) still get a meaningful floor.
        min_overlap = max(4, min(os_.shape[0], us_.shape[0]) // 2)
        best = (0, np.inf)
        for lag in range(-a.maxlag, a.maxlag + 1):
            if lag >= 0:
                A = os_[lag:]; B = us_[:A.shape[0]]
            else:
                A = os_[:us_.shape[0] + lag]; B = us_[-lag:]
            n = min(A.shape[0], B.shape[0])
            if n < min_overlap:
                continue
            rr = np.sqrt(np.nanmean((A[:n] - B[:n]) ** 2))
            if rr < best[1]:
                best = (lag, rr)
        lag = best[0]
    off_h = lag * dt / 3600.0
    if lag >= 0:
        Oraw, Uraw = Oraw[lag:], Uraw[:Oraw.shape[0] - lag]
    else:
        Oraw, Uraw = Oraw[:Uraw.shape[0] + lag], Uraw[-lag:]
    nt = min(Oraw.shape[0], Uraw.shape[0]); Oraw, Uraw = Oraw[:nt], Uraw[:nt]
    O = to_metric(Oraw, var, a.component); U = to_metric(Uraw, var, a.component)  # (T,N,L)
    hrs = np.arange(nt) * dt / 3600.0

    diff = U - O
    rmse = float(np.sqrt(np.nanmean(diff ** 2)))
    maxd = float(np.nanmax(np.abs(diff)))
    with np.errstate(invalid="ignore"):
        r = np.corrcoef(O.ravel(), U.ravel())[0, 1]
    near_zero = max(np.nanmax(np.abs(O)), np.nanmax(np.abs(U))) < 1e-9
    zero_note = "   [both fields ~0: no forcing, trivial parity]" if near_zero else ""

    node = a.node if a.node is not None else nN // 2
    nodes = [int(x) for x in a.nodes.split(",") if int(x) < nN]

    fig, ax = plt.subplots(2, 2, figsize=(16, 9), constrained_layout=True)

    # [0,0] domain-mean over time (mean over all nodes + levels)
    ax[0, 0].plot(hrs, O.mean((1, 2)), color="blue", lw=1.8, label="operational")
    ax[0, 0].plot(hrs, U.mean((1, 2)), color="red", lw=1.2, ls="--", label="UFS")
    ax[0, 0].set_title(f"Domain-mean {var} over time")
    ax[0, 0].set_xlabel("Time (hours)"); ax[0, 0].set_ylabel(f"{var} ({unit})")
    ax[0, 0].grid(True, alpha=0.25); ax[0, 0].legend()

    # [0,1] per-level RMSE (mean over nodes + time)
    lvl_rmse = np.sqrt(np.nanmean(diff ** 2, axis=(0, 1)))   # (L,)
    ax[0, 1].plot(lvl_rmse, np.arange(nL), color="purple", lw=1.6, marker="o", ms=3)
    ax[0, 1].set_title("Per-level RMSE (mean over nodes & time)")
    ax[0, 1].set_xlabel(f"RMSE ({unit})"); ax[0, 1].set_ylabel("level index (0=bottom)")
    ax[0, 1].grid(True, alpha=0.25)

    # [1,0] depth profile at `node` at mid-time
    mt = nt // 2
    ax[1, 0].plot(O[mt, node, :], np.arange(nL), color="blue", lw=1.8, marker="o",
                  ms=3, label="operational")
    ax[1, 0].plot(U[mt, node, :], np.arange(nL), color="red", lw=1.2, ls="--",
                  marker="s", ms=3, label="UFS")
    ax[1, 0].set_title(f"Depth profile @ node {node}, t={hrs[mt]:.0f}h")
    ax[1, 0].set_xlabel(f"{var} ({unit})"); ax[1, 0].set_ylabel("level index (0=bottom)")
    ax[1, 0].grid(True, alpha=0.25); ax[1, 0].legend()

    # [1,1] surface time-series at sample nodes
    for nd in nodes:
        ax[1, 1].plot(hrs, O[:, nd, surf], lw=1.5, label=f"ops n{nd}")
        ax[1, 1].plot(hrs, U[:, nd, surf], lw=1.0, ls="--", color="k", alpha=0.6)
    ax[1, 1].set_title(f"Surface-level {var} (ops solid, ufs black dashed)")
    ax[1, 1].set_xlabel("Time (hours)"); ax[1, 1].set_ylabel(f"{var} ({unit})")
    ax[1, 1].grid(True, alpha=0.25); ax[1, 1].legend(fontsize=8, ncol=2)

    metric = "speed" if (var == "uv" and a.component is None) else \
        (f"component {a.component}" if a.component is not None else var)
    fig.suptitle(f"OBC {var} ({metric}) boundary: {a.label}\n"
                 f"aligned {off_h:+.1f}h, {nt} steps x {nN} nodes x {nL} levels   "
                 f"RMSE={rmse:.4g} {unit}   max|diff|={maxd:.4g}   R={r:.6f}{zero_note}",
                 fontsize=13, fontweight="bold")
    fig.savefig(a.out, dpi=120, bbox_inches="tight")
    print(f"saved {a.out}  var={var} offset={off_h:+.1f}h RMSE={rmse:.4g} {unit} "
          f"max={maxd:.4g} R={r:.6f} shape=({nt},{nN},{nL})")


if __name__ == "__main__":
    main()
