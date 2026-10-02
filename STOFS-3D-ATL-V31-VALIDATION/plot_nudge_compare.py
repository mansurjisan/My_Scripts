#!/usr/bin/env python3
"""
Nudging (TEM_nu / SAL_nu) comparison plots, operational STOFS-3D-ATL vs nos-workflow, in the plain
SECOFS-validation style. Inputs are the .npz subsets written by extract_nudge_subset.py.

usage: plot_nudge_compare.py --dir SUBSET_DIR --hgrid-ll HGRID.ll [--outdir DIR] [--cycle 2026092712]
           [--step 216000] [--nodes 2849801,2951437,3006799,3052121] [--snaps 2026092612,2026092712,2026093000]

SUBSET_DIR holds ops.npz, ours_now.npz, ours_fcst.npz and optionally before_now.npz /
before_fcst.npz. The ops run reads its 6-hourly records with step_nu_tr = 216000 s, so the field
SCHISM applies at time tau (s since the ops start) is the blend of records n and n+1 with
n = floor(tau/step), f = tau/step - n. That "ops-effective" field is what the port must and does
reproduce; the raw ops records are drawn too, to show the difference. The last record of each port
phase file is a buffer SCHISM never reads and is left out, as are old-file records past the phase end.

Writes: nudge_{tem,sal}_surface_ts.png, nudge_{tem,sal}_surface_map.png and, with the before files,
nudge_{tem,sal}_surface_map_before_fix.png.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from obc_common import EPOCH, cycle_label, parse_dt, save, to_dt

NAMES = {"tem": ("temperature", "degC"), "sal": ("salinity", "psu")}
PHASE_HOURS = {"now": 24, "fcst": 96}


def load(path):
    z = np.load(path)
    t0 = (parse_dt(str(z["start"])) - EPOCH).total_seconds()
    return {k: z[k] for k in z.files} | {"tabs": t0 + z["time"]}


def node_coords(ids, hgrid_ll, cache):
    if os.path.exists(cache):
        c = np.load(cache)
        if np.array_equal(c["ids"], ids):
            return c["lon"], c["lat"]
    want = {int(i): k for k, i in enumerate(ids)}
    lon = np.full(len(ids), np.nan); lat = np.full(len(ids), np.nan)
    with open(hgrid_ll) as f:
        f.readline()
        nn = int(f.readline().split()[1])
        for _ in range(nn):
            p = f.readline().split()
            k = want.get(int(p[0]))
            if k is not None:
                lon[k], lat[k] = float(p[1]), float(p[2])
    np.savez(cache, ids=ids, lon=lon, lat=lat)
    return lon, lat


def effective(ops, key, tabs, step):
    """Ops-effective field (all nodes) at absolute time tabs."""
    tau = tabs - ops["tabs"][0]
    n = int(np.floor(tau / step + 1e-9))
    f = (tau - n * step) / step
    R = ops[key]
    if f <= 1e-9:
        return R[n].astype(np.float32)
    return (R[n].astype(np.float64) * (1 - f) + R[n + 1].astype(np.float64) * f).astype(np.float32)


def merged(parts, key, ids_ref):
    """{abs_time: field on ids_ref (NaN where the node is absent)} for the records SCHISM reads."""
    out = {}
    for d, phase in parts:
        if d is None:
            continue
        pos = {int(i): k for k, i in enumerate(d["ids"])}
        idx = np.array([pos.get(int(i), -1) for i in ids_ref])
        t_end = d["tabs"][0] + PHASE_HOURS[phase] * 3600
        nrec = len(d["tabs"])
        for j, t in enumerate(d["tabs"]):
            if t > t_end + 1 or (j == nrec - 1 and d["tabs"][-1] > t_end):
                continue
            v = np.where(idx >= 0, d[key][j][np.clip(idx, 0, None)], np.nan).astype(np.float32)
            out[round(float(t))] = v
    return out


def ts_figure(ops, ours, before, var, nodes, lon, lat, cycle, step, outdir):
    name, unit = NAMES[var]
    key = f"{var}_surf"
    pos = {int(i): k for k, i in enumerate(ops["ids"])}
    t0 = ops["tabs"][0]
    hc = (parse_dt(cycle).timestamp() - t0) / 3600
    tt = sorted(ours)
    eff = {t: effective(ops, key, t, step) for t in tt}
    d_all = np.concatenate([ours[t] - eff[t] for t in tt])
    st = f"nos-workflow vs ops-effective: max|diff| {np.nanmax(np.abs(d_all)):.3g} {unit} over {len(tt)} records x {len(ops['ids'])} nodes"
    if before:
        tb = sorted(before)
        db = np.concatenate([before[t] - effective(ops, key, t, step) for t in tb])
        st += f"\nbefore fix vs ops-effective: RMS {np.sqrt(np.nanmean(db * db)):.3g}, max|diff| {np.nanmax(np.abs(db)):.3g} {unit}"
    fine = np.arange(0, (max(tt) - t0) + 1, 3600.0) + t0
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 9.2), constrained_layout=True)
    for ax, nid in zip(axes.ravel(), nodes):
        k = pos[nid]
        ax.plot((ops["tabs"] - t0) / 3600, ops[key][:, k], "o", color="gray", ms=3.5, alpha=0.7,
                label="ops temnu/salnu records at their real 6-hourly times")
        ax.plot((fine - t0) / 3600, [effective(ops, key, t, step)[k] for t in fine], color="blue", lw=1.6,
                label="operational: field SCHISM applies (step_nu_tr 216000)")
        ax.plot([(t - t0) / 3600 for t in tt], [ours[t][k] for t in tt], color="red", lw=1.2, ls="--",
                marker=".", label="nos-workflow (nos-utils)")
        if before:
            yb = [before[t][k] for t in sorted(before)]
            if np.isfinite(yb).any():
                ax.plot([(t - t0) / 3600 for t in sorted(before)], yb, color="green", lw=1.0, ls=":",
                        label="nos-workflow before fix")
            else:
                ax.text(0.02, 0.04, "node not in the old nudge set (one-element ring)", transform=ax.transAxes,
                        fontsize=8, color="green")
        ax.axvline(hc, color="gray", lw=0.8, ls=":")
        ax.set_xlim(0, (max(tt) - t0) / 3600 + 6)
        ax.set_title(f"Node {nid} ({lon[k]:.2f}, {lat[k]:.2f})")
        ax.set_xlabel(f"Time (hours since {to_dt(t0):%Y-%m-%d %HZ}; dotted line = cycle)")
        ax.set_ylabel(f"{name} ({unit})")
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=8)
    fig.suptitle(f"Nudging {name}, surface: operational STOFS-3D-ATL vs nos-workflow  -  "
                 f"{cycle_label(parse_dt(cycle))}\n{st}", fontsize=12, fontweight="bold")
    save(fig, os.path.join(outdir, f"nudge_{var}_surface_ts.png"))


def map_figure(ops, other, label, var, snaps, lon, lat, cycle, step, out):
    name, unit = NAMES[var]
    key = f"{var}_surf"
    rows = [s for s in snaps if s in other]
    if not rows:
        print("no snapshot times available for", out)
        return
    E = [effective(ops, key, s, step) for s in rows]
    O = [other[s] for s in rows]
    vals = np.concatenate(E + O)
    vlo, vhi = np.nanpercentile(vals, 1), np.nanpercentile(vals, 99)
    D = [o - e for o, e in zip(O, E)]
    dmax = max(float(np.nanmax(np.abs(np.concatenate(D)))), 1e-12)
    fig, ax = plt.subplots(len(rows), 3, figsize=(15, 4.4 * len(rows)), constrained_layout=True)
    ax = np.atleast_2d(ax)
    for r, s in enumerate(rows):
        when = to_dt(s).strftime("%Y-%m-%d %HZ")
        d = D[r]
        ok = np.isfinite(d)
        rmse = float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else float("nan")
        panels = [(E[r], f"operational (as applied)  {when}", "viridis", vlo, vhi, f"{name} ({unit})"),
                  (O[r], label, "viridis", vlo, vhi, f"{name} ({unit})"),
                  (d, f"diff (nos-workflow - ops)  RMSE={rmse:.3g} {unit}", "bwr", -dmax, dmax, unit)]
        for c, (dat, ttl, cm, lo, hi, cbl) in enumerate(panels):
            sc = ax[r, c].scatter(lon, lat, c=dat, s=0.6, cmap=cm, vmin=lo, vmax=hi, rasterized=True)
            plt.colorbar(sc, ax=ax[r, c], fraction=0.046, pad=0.04, label=cbl)
            ax[r, c].set_title(ttl, fontsize=10)
            ax[r, c].set_xlabel("lon"); ax[r, c].set_ylabel("lat")
            ax[r, c].set_aspect("auto")
    fig.suptitle(f"Nudging {name}, surface, nudge-zone nodes ({np.isfinite(lon).sum()}): operational STOFS-3D-ATL "
                 f"vs {label}  -  {cycle_label(parse_dt(cycle))}", fontsize=13, fontweight="bold")
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--hgrid-ll", required=True)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--step", type=float, default=216000.0)
    ap.add_argument("--nodes", default="2849801,2951437,3006799,3052121")
    ap.add_argument("--snaps", default="2026092612,2026092712,2026093000")
    a = ap.parse_args()

    j = lambda n: os.path.join(a.dir, n)
    ops = load(j("ops.npz"))
    now, fcst = load(j("ours_now.npz")), load(j("ours_fcst.npz"))
    bnow = load(j("before_now.npz")) if os.path.exists(j("before_now.npz")) else None
    bfcst = load(j("before_fcst.npz")) if os.path.exists(j("before_fcst.npz")) else None
    lon, lat = node_coords(ops["ids"], a.hgrid_ll, j("nudge_nodes_ll.npz"))
    nodes = [int(x) for x in a.nodes.split(",")]
    snaps = [round((parse_dt(s) - EPOCH).total_seconds()) for s in a.snaps.split(",")]
    os.makedirs(a.outdir, exist_ok=True)
    for var in ("tem", "sal"):
        key = f"{var}_surf"
        ours = merged([(now, "now"), (fcst, "fcst")], key, ops["ids"])
        before = merged([(bnow, "now"), (bfcst, "fcst")], key, ops["ids"]) if bnow is not None else {}
        ts_figure(ops, ours, before, var, nodes, lon, lat, a.cycle, a.step, a.outdir)
        map_figure(ops, ours, "nos-workflow (nos-utils)", var, snaps, lon, lat, a.cycle, a.step,
                   os.path.join(a.outdir, f"nudge_{var}_surface_map.png"))
        if before:
            map_figure(ops, before, "nos-workflow before fix", var, snaps, lon, lat, a.cycle, a.step,
                       os.path.join(a.outdir, f"nudge_{var}_surface_map_before_fix.png"))


if __name__ == "__main__":
    main()
