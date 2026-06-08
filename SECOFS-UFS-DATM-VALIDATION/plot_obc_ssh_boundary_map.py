#!/usr/bin/env python3
"""
OBC elev2D (SSH) BOUNDARY MAP: operational vs UFS vs diff, at several time
snapshots (reference-plot style 04_ssh_boundary_map.png).

elev2D.th.nc has no coordinates, so the open-boundary node lon/lat are pulled
from the SECOFS hgrid.gr3 (open boundaries 1..NBND, which for SECOFS = the
1488 elevation-forced nodes). Coords are cached to a small .npz so the 321 MB
hgrid is parsed only once.

Usage:
  python3 plot_obc_ssh_boundary_map.py OPS_elev2D.th.nc UFS_elev2D.th.nc \
      --hgrid /path/to/hgrid.gr3 [--nbnd 3] [--out map.png] [--snaps 0,8,16]
"""
import argparse
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from netCDF4 import Dataset


def boundary_coords(hgrid, nbnd, cache):
    if cache and os.path.exists(cache):
        z = np.load(cache); return z["lon"], z["lat"]
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


def load_ssh(path):
    ds = Dataset(path)
    ts = np.array(ds.variables["time_series"][:, :, 0, 0], dtype="f8")
    ds.close(); return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--hgrid", required=True)
    ap.add_argument("--nbnd", type=int, default=3, help="num open boundaries = elev2D nodes")
    ap.add_argument("--cache", default="secofs_obc_bnd_coords.npz")
    ap.add_argument("--snaps", default=None, help="comma time-indices (default 3 evenly spaced)")
    ap.add_argument("--out", default="obc_ssh_boundary_map.png")
    ap.add_argument("--label", default="operational vs UFS")
    a = ap.parse_args()

    lon, lat = boundary_coords(a.hgrid, a.nbnd, a.cache)
    so, su = load_ssh(a.ops), load_ssh(a.ufs)
    nt = min(so.shape[0], su.shape[0]); nn = min(so.shape[1], su.shape[1], len(lon))
    so, su, lon, lat = so[:nt, :nn], su[:nt, :nn], lon[:nn], lat[:nn]
    print(f"nodes={nn}  steps={nt}  lon[{lon.min():.1f},{lon.max():.1f}] lat[{lat.min():.1f},{lat.max():.1f}]")

    snaps = ([int(x) for x in a.snaps.split(",")] if a.snaps
             else [0, nt // 2, nt - 1])
    vmax = max(np.nanmax(np.abs(so)), np.nanmax(np.abs(su)))
    dmax = max(np.nanmax(np.abs(su - so)), 1e-4)

    fig, ax = plt.subplots(len(snaps), 3, figsize=(15, 4.4 * len(snaps)), constrained_layout=True)
    if len(snaps) == 1:
        ax = ax[None, :]
    for r, ti in enumerate(snaps):
        for c, (dat, ttl, cmap, vlo, vhi) in enumerate([
                (so[ti], "operational", "RdBu_r", -vmax, vmax),
                (su[ti], "UFS", "RdBu_r", -vmax, vmax),
                (su[ti] - so[ti], "diff (UFS-ops)", "bwr", -dmax, dmax)]):
            sc = ax[r, c].scatter(lon, lat, c=dat, s=6, cmap=cmap, vmin=vlo, vmax=vhi)
            plt.colorbar(sc, ax=ax[r, c], fraction=0.046, pad=0.04,
                         label="SSH (m)" if c < 2 else "m")
            rm = np.sqrt(np.nanmean((su[ti] - so[ti]) ** 2)) * 1000
            ax[r, c].set_title(f"{ttl}" + (f"  step {ti}" if c == 0 else
                               (f"  RMSE={rm:.3f}mm" if c == 2 else "")), fontsize=10)
            ax[r, c].set_xlabel("lon"); ax[r, c].set_ylabel("lat")
            ax[r, c].set_aspect("auto")
    fig.suptitle(f"SSH at open-boundary nodes ({nn}): {a.label}", fontsize=14, fontweight="bold")
    fig.savefig(a.out, dpi=130, bbox_inches="tight")
    print("saved", a.out)


if __name__ == "__main__":
    main()
