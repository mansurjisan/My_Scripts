#!/usr/bin/env python3
"""
OBC 3D BOUNDARY MAP: operational vs UFS vs diff, depth-resolved, for the SCHISM
*_3D.th.nc files (TEM_3D / SAL_3D / uv3D). Plots a chosen vertical level on the
open-boundary nodes (lon/lat from hgrid.gr3) at several time snapshots - the
depth analog of plot_obc_ssh_boundary_map.py.

The *_3D.th.nc files carry no coordinates, so open-boundary node lon/lat are
pulled from the SECOFS hgrid.gr3 (open boundaries 1..nbnd) and cached to a small
.npz (the 321 MB hgrid is parsed only once). The 3D node set is the same 1488
elevation-forced boundary nodes as elev2D, so the cache is shared.

The 3D files are coarse (3-hourly) and offset from ufs by the nowcast lookback;
TEM aligns cleanly, but pass --offset-hours (the value TEM finds, e.g. 6) for the
smooth SAL field and the zero uv field, which do not cross-correlate reliably.

Usage:
  python3 plot_obc_3d_boundary_map.py OPS_TEM_3D.th.nc UFS_TEM_3D.th.nc \
      --hgrid /path/to/hgrid.gr3 [--level -1] [--var auto] [--nbnd 3] \
      [--offset-hours 6] [--snaps 0,8,16] [--out map.png]
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
    return ("TEM" if "TEM" in b else "SAL" if "SAL" in b
            else "uv" if "UV" in b else "TEM")


def boundary_coords(hgrid, nbnd, cache):
    """Open-boundary node lon/lat from hgrid.gr3 (boundaries 1..nbnd), cached."""
    if cache and os.path.exists(cache):
        z = np.load(cache); return z["lon"], z["lat"]
    if not hgrid:
        raise SystemExit("need --hgrid (or an existing --cache .npz)")
    with open(hgrid) as f:
        f.readline()
        ne, nn = (int(x) for x in f.readline().split()[:2])
        lon = np.empty(nn); lat = np.empty(nn)
        for i in range(nn):
            p = f.readline().split(); lon[i] = float(p[1]); lat[i] = float(p[2])
        for _ in range(ne):
            f.readline()
        n_open = int(f.readline().split()[0]); f.readline()  # n_open ; total
        ids = []
        for b in range(n_open):
            cnt = int(f.readline().split()[0])
            bids = [int(f.readline().split()[0]) for _ in range(cnt)]
            if b < nbnd:
                ids.extend(bids)
    idx = np.array(ids) - 1
    blon, blat = lon[idx], lat[idx]
    if cache:
        np.savez(cache, lon=blon, lat=blat)
    return blon, blat


def to_metric(ts, var, comp):
    if ts.shape[-1] == 1:
        return ts[..., 0]
    if var == "uv" and comp is None:
        return np.hypot(ts[..., 0], ts[..., 1])
    return ts[..., comp]


def load_level(path, level, var, comp):
    ds = Dataset(path)
    ts = np.array(ds.variables["time_series"][:], dtype="f8")
    dt = (float(np.diff(ds.variables["time"][:2])[0])
          if "time" in ds.variables and len(ds.variables["time"]) > 1 else 10800.0)
    ds.close()
    while ts.ndim < 4:
        ts = ts[..., None]
    return to_metric(ts, var, comp)[:, :, level], dt   # (T, N), dt


def align_lag(o, u, dt, offset_hours, maxlag):
    if offset_hours is not None:
        return int(round(offset_hours * 3600.0 / dt))
    sub = slice(0, o.shape[1], max(1, o.shape[1] // 40))
    os_, us_ = o[:, sub], u[:, sub]
    mo = max(4, min(os_.shape[0], us_.shape[0]) // 2); best = (0, np.inf)
    for lag in range(-maxlag, maxlag + 1):
        if lag >= 0:
            A = os_[lag:]; B = us_[:A.shape[0]]
        else:
            A = os_[:us_.shape[0] + lag]; B = us_[-lag:]
        n = min(A.shape[0], B.shape[0])
        if n < mo:
            continue
        rr = np.sqrt(np.nanmean((A[:n] - B[:n]) ** 2))
        if rr < best[1]:
            best = (lag, rr)
    return best[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--hgrid", default=None)
    ap.add_argument("--nbnd", type=int, default=3, help="num elevation-forced open boundaries")
    ap.add_argument("--cache", default="secofs_obc_bnd_coords.npz")
    ap.add_argument("--level", type=int, default=-1, help="vertical level (-1=surface, 0=bottom)")
    ap.add_argument("--var", default="auto")
    ap.add_argument("--component", type=int, default=None, help="uv: 0=u, 1=v; default speed")
    ap.add_argument("--offset-hours", type=float, default=None,
                    help="force ops->ufs lag in hours (use for SAL/uv)")
    ap.add_argument("--maxlag", type=int, default=400)
    ap.add_argument("--snaps", default=None, help="comma time-indices (default 3 evenly spaced)")
    ap.add_argument("--out", default="obc_3d_boundary_map.png")
    ap.add_argument("--label", default="operational vs UFS")
    a = ap.parse_args()

    var = detect_var(a.ops, a.var); unit = UNITS.get(var, "")
    lon, lat = boundary_coords(a.hgrid, a.nbnd, a.cache)
    O, dt = load_level(a.ops, a.level, var, a.component)
    U, _ = load_level(a.ufs, a.level, var, a.component)
    lag = align_lag(O, U, dt, a.offset_hours, a.maxlag); off_h = lag * dt / 3600.0
    if lag >= 0:
        O, U = O[lag:], U[:O.shape[0] - lag]
    else:
        O, U = O[:U.shape[0] + lag], U[-lag:]
    nt = min(O.shape[0], U.shape[0]); O, U = O[:nt], U[:nt]
    nn = min(O.shape[1], U.shape[1], len(lon))
    O, U, lon, lat = O[:, :nn], U[:, :nn], lon[:nn], lat[:nn]
    print(f"var={var} level={a.level} nodes={nn} steps={nt} offset={off_h:+.1f}h "
          f"lon[{lon.min():.1f},{lon.max():.1f}] lat[{lat.min():.1f},{lat.max():.1f}]")

    snaps = ([int(x) for x in a.snaps.split(",")] if a.snaps
             else [0, nt // 2, nt - 1])
    snaps = [s for s in snaps if s < nt]
    vmin = min(np.nanmin(O), np.nanmin(U)); vmax = max(np.nanmax(O), np.nanmax(U))
    dmax = max(np.nanmax(np.abs(U - O)), 1e-6)

    fig, ax = plt.subplots(len(snaps), 3, figsize=(15, 4.4 * len(snaps)),
                           constrained_layout=True)
    if len(snaps) == 1:
        ax = ax[None, :]
    for r, ti in enumerate(snaps):
        rm = np.sqrt(np.nanmean((U[ti] - O[ti]) ** 2))
        for c, (dat, ttl, cmap, vlo, vhi, cl) in enumerate([
                (O[ti], "operational", "viridis", vmin, vmax, f"{var} ({unit})"),
                (U[ti], "UFS", "viridis", vmin, vmax, f"{var} ({unit})"),
                (U[ti] - O[ti], "diff (UFS-ops)", "bwr", -dmax, dmax, unit)]):
            sc = ax[r, c].scatter(lon, lat, c=dat, s=6, cmap=cmap, vmin=vlo, vmax=vhi)
            plt.colorbar(sc, ax=ax[r, c], fraction=0.046, pad=0.04, label=cl)
            ttl2 = ttl + (f"  step {ti}" if c == 0 else
                          (f"  RMSE={rm:.3g} {unit}" if c == 2 else ""))
            ax[r, c].set_title(ttl2, fontsize=10)
            ax[r, c].set_xlabel("lon"); ax[r, c].set_ylabel("lat")
    lvlname = ("surface" if a.level == -1 else
               "bottom" if a.level == 0 else f"level {a.level}")
    fig.suptitle(f"OBC {var} @ {lvlname} on open-boundary nodes ({nn}): {a.label}\n"
                 f"aligned {off_h:+.1f}h, {nt} steps",
                 fontsize=14, fontweight="bold")
    fig.savefig(a.out, dpi=130, bbox_inches="tight")
    print("saved", a.out)


if __name__ == "__main__":
    main()
