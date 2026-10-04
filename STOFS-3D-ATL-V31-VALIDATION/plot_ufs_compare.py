#!/usr/bin/env python3
"""
Three-way station comparison for the STOFS-3D-ATL PDY 2026-10-01 12z nowcast (24 h from 2026-09-30 12:00 UTC):
operational STOFS-3D-ATL v3.1, nos-workflow standalone (ops SCHISM 5.14) and nos-workflow UFS coupled (DATM+SCHISM).

usage: plot_ufs_compare.py --ops-dir DIR --standalone-dir DIR --coupled-dir DIR --station-in FILE
           --names-csv FILE --msl-nco FILE --obs-dir DIR --outdir DIR

*-dir      directories holding SCHISM station text output staout_1..8 (column 0 = seconds since 2026-09-30 12:00,
           then 166 station columns in station.in order). Variables: 1 elevation, 2 air pressure (Pa), 3/4 wind x/y,
           5 temperature, 6 salinity, 7/8 u/v. Values <= -9000 are missing. First 288 rows (5 min) used.
--station-in  stofs_3d_atl_station.in ("i lon lat z !ID");  --names-csv  stofs_3d_atl_staout_nc.csv
--msl-nco  stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco (WL(MSL) = elevation - offset_k, k = station.in row, 1-based)
--obs-dir  cached CO-OPS water_level JSON (datum MSL) named wl_msl_<ID>.json; missing files are skipped

Writes ufs_wl_ts.png, ufs_wl_maxdiff_map.png, ufs_wl_stats.png, ufs_atmos_at_stations.png, ufs_ts_temp_salt.png,
ufs_wl_obs.png (if obs cached) and ufs_summary.txt into --outdir.
"""
import argparse
import warnings
import json
import os
import re
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from PIL import Image

warnings.filterwarnings("ignore", category=RuntimeWarning)
NR = 288
START = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
TITLE = "PDY 2026-10-01 12z"
LAB = {"ops": "operational STOFS-3D-ATL", "sa": "nos-workflow standalone (ops SCHISM 5.14)",
       "ufs": "nos-workflow UFS coupled (DATM+SCHISM)"}
COL = {"ops": "#0072B2", "sa": "#D55E00", "ufs": "#009E73", "obs": "k"}
STY = {"ops": dict(lw=2.8, alpha=0.6), "sa": dict(lw=1.2, ls="--"), "ufs": dict(lw=0.9)}
DLAB = {"sa": "standalone − operational", "ufs": "UFS − operational"}
FLOOR = 1e-6
VARS = {"elev": 1, "pres": 2, "wx": 3, "wy": 4, "temp": 5, "salt": 6, "u": 7, "v": 8}
DEFAULT_WL = ["8518750", "8651370", "8761724", "8773037", "8454000", "8631044", "8419317", "8423898", "8443970"]


def save_png(fig, out):
    fig.savefig(out, dpi=100, metadata={"Software": None})
    plt.close(fig)
    w, h = Image.open(out).size
    assert max(w, h) <= 1500, f"{out}: {w}x{h}"
    print(f"saved {out} {w}x{h}")
    return w, h


def load_var(d, k):
    a = np.loadtxt(os.path.join(d, f"staout_{k}"), max_rows=NR)
    assert a.shape[0] == NR
    t, x = a[:, 0], a[:, 1:].copy()
    x[x <= -9000] = np.nan
    return t, x


def load_stations(path, names_csv):
    ids, lon, lat = [], [], []
    with open(path) as f:
        f.readline()
        n = int(f.readline().split()[0])
        for _ in range(n):
            s, _, c = f.readline().partition("!")
            p = s.split()
            lon.append(float(p[1])); lat.append(float(p[2])); ids.append(c.strip())
    names = {}
    with open(names_csv) as f:
        next(f)
        for line in f:
            t = line.rstrip("\n").split(";")[1].split()
            if len(t) >= 5:
                names[t[2]] = f"{' '.join(t[4:])}, {t[3]}"
    return ids, np.array(lon), np.array(lat), names


def load_offsets(path):
    return {int(m.group(1)): float(m.group(2)) for m in
            re.finditer(r"zeta\(:,(\d+)\)\s*=\s*zeta\(:,\d+\)\s*-\s*float\(([-+0-9.eE]+)\)", open(path).read())}


def tnum(t):
    return mdates.date2num([START + timedelta(seconds=float(s)) for s in t])


def fmt_time(ax):
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %Hz"))
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3)


def handles(diff=False):
    if diff:
        return [Line2D([], [], color=COL[k], lw=2 if k == "sa" else 1.2, ls="--" if k == "sa" else "-",
                       label=DLAB[k]) for k in ("sa", "ufs")]
    return [Line2D([], [], color=COL["ops"], lw=3, alpha=0.6, label=LAB["ops"]),
            Line2D([], [], color=COL["sa"], lw=1.4, ls="--", label=LAB["sa"]),
            Line2D([], [], color=COL["ufs"], lw=1.0, label=LAB["ufs"])]


def overlay(ax):
    import cartopy.feature as cf
    ax.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#e6f0f7", zorder=0)
    ax.add_feature(cf.LAND.with_scale("50m"), facecolor="0.85", zorder=1)
    ax.add_feature(cf.COASTLINE.with_scale("50m"), edgecolor="0.3", lw=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.5)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}


def sname(names, sid):
    return names.get(sid, sid).split(",")[0].title() if sid in names else sid


def fig_wl_ts(T, E, sids, names, ids, out):
    n = len(ids)
    nc = 3
    nr = int(np.ceil(n / nc))
    fig = plt.figure(figsize=(15, 3.4 * nr + 1.0))
    gs = fig.add_gridspec(nr * 2, nc, height_ratios=[3, 1.4] * nr, left=0.06, right=0.985, top=0.87,
                          bottom=0.05, hspace=0.75, wspace=0.18)
    x = tnum(T)
    for i, sid in enumerate(ids):
        r, c = divmod(i, nc)
        k = sids.index(sid)
        a = fig.add_subplot(gs[2 * r, c])
        b = fig.add_subplot(gs[2 * r + 1, c], sharex=a)
        for key in ("ops", "sa", "ufs"):
            a.plot(x, E[key][:, k], color=COL[key], **STY[key])
        ds, du = E["sa"][:, k] - E["ops"][:, k], E["ufs"][:, k] - E["ops"][:, k]
        b.plot(x, ds, color=COL["sa"], lw=1.4, ls="--")
        b.plot(x, du, color=COL["ufs"], lw=1.0)
        b.axhline(0, color="0.5", lw=0.5)
        a.set_title(f"{names.get(sid, sid)} ({sid})\nmax|diff|: standalone {np.nanmax(abs(ds)):.1e} m, "
                    f"UFS {np.nanmax(abs(du)):.1e} m", fontsize=8.5)
        a.set_ylabel("elevation (m)", fontsize=8)
        b.set_ylabel("diff (m)", fontsize=8)
        a.tick_params(labelbottom=False, labelsize=7)
        a.grid(alpha=0.3)
        fmt_time(b)
    fig.legend(handles=handles(), loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.965), fontsize=9.5, frameon=False)
    fig.text(0.5, 0.925, "lower panels: standalone − operational (dashed), UFS − operational (solid)",
             ha="center", fontsize=8.5, color="0.3")
    fig.suptitle(f"Station water level, 24 h nowcast, {TITLE}", fontsize=13, y=0.985)
    return save_png(fig, out)


def fig_map(lon, lat, mx, mxs, out):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    fig = plt.figure(figsize=(15, 9.4))
    norm = LogNorm(vmin=FLOOR, vmax=1.0)
    exts = [([-98, -52, 7, 52], 30), ([-76.5, -65.5, 38.5, 45.5], 60)]
    sc = None
    for j, key in enumerate(("sa", "ufs")):
        for i, (ext, s) in enumerate(exts):
            w = [0.07, 0.0][0] if False else None
            left = 0.04 + j * 0.46
            if i == 0:
                ax = fig.add_axes([left, 0.40, 0.44, 0.50], projection=pc)
            else:
                ax = fig.add_axes([left, 0.04, 0.44, 0.31], projection=pc)
            ax.set_extent(ext, crs=pc)
            overlay(ax)
            m = mx[key]
            z = m == 0
            ax.scatter(lon[z], lat[z], s=s, marker="s", facecolor="white", edgecolor="k", lw=0.9, zorder=5, transform=pc)
            o = np.argsort(m); o = o[m[o] > 0]
            sc = ax.scatter(lon[o], lat[o], c=np.clip(m[o], FLOOR, None), s=s, cmap="viridis_r", norm=norm,
                            edgecolor="0.2", lw=0.3, zorder=6, transform=pc)
            if i == 0:
                ax.set_title(f"{DLAB[key]}  ({int(z.sum())} bit-identical)", fontsize=11)
                ax.plot([-76.5, -65.5, -65.5, -76.5, -76.5], [38.5, 38.5, 45.5, 45.5, 38.5], color="crimson",
                        lw=1.1, transform=pc, zorder=7)
            else:
                ax.set_title("Northeast US zoom", fontsize=9, pad=14)
    cax = fig.add_axes([0.94, 0.15, 0.012, 0.70])
    cb = fig.colorbar(sc, cax=cax, extend="min")
    cb.set_label("max |difference| over 24 h (m)", fontsize=10)
    fig.legend(handles=[Line2D([], [], marker="s", ls="", mfc="white", mec="k", ms=7, label="bit-identical (max diff = 0)")],
               loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=1, fontsize=8.5)
    fig.suptitle(f"Station water level: largest difference from operational STOFS-3D-ATL, {TITLE}", fontsize=12.5, y=0.97)
    return save_png(fig, out)


BINS = [("< 1 mm", 0, 1e-3), ("1 mm - 1 cm", 1e-3, 1e-2), ("1 - 5 cm", 1e-2, 5e-2), ("> 5 cm", 5e-2, np.inf)]


def bin_counts(mx):
    return [int(((mx >= lo) & (mx < hi)).sum()) for _, lo, hi in BINS]


def fig_stats(T, D, mx, out):
    fig = plt.figure(figsize=(15, 8.5))
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.985, top=0.88, bottom=0.08, hspace=0.32, wspace=0.18)
    a = fig.add_subplot(gs[0, 0]); c = fig.add_subplot(gs[1, 0]); b = fig.add_subplot(gs[0, 1])
    d = fig.add_subplot(gs[1, 1])
    hrs = np.arange(24)
    for key in ("sa", "ufs"):
        A = np.abs(D[key]).reshape(24, 12, -1)
        med = np.array([np.nanmedian(A[h]) for h in hrs]); p90 = np.array([np.nanpercentile(A[h], 90) for h in hrs])
        a.plot(hrs + 0.5, np.clip(med, FLOOR / 10, None), color=COL[key], lw=2, ls="--" if key == "sa" else "-",
               label=f"{DLAB[key]}, median")
        a.plot(hrs + 0.5, np.clip(p90, FLOOR / 10, None), color=COL[key], lw=1.2, ls=":", marker="o", ms=3,
               label=f"{DLAB[key]}, 90th percentile")
    a.set_yscale("log"); a.set_xlabel("hours since 2026-09-30 12:00 UTC"); a.set_ylabel("|difference| over stations (m)")
    a.set_title("(a) hourly median and 90th percentile of |difference|", fontsize=10)
    a.legend(fontsize=7.5, ncol=1); a.grid(alpha=0.3, which="both")
    for key in ("sa", "ufs"):
        s = np.sort(np.clip(mx[key], FLOOR / 10, None))[::-1]
        b.plot(np.arange(1, len(s) + 1), s, color=COL[key], lw=2, ls="--" if key == "sa" else "-", label=DLAB[key])
    for v, l in ((1e-3, "1 mm"), (1e-2, "1 cm"), (5e-2, "5 cm")):
        b.axhline(v, color="0.6", lw=0.7); b.text(166, v * 1.1, l, ha="right", fontsize=7, color="0.4")
    b.set_yscale("log"); b.set_xlabel("stations, ranked by max |difference|"); b.set_ylabel("max |difference| over 24 h (m)")
    b.set_title("(b) per-station maximum difference, ranked", fontsize=10); b.legend(fontsize=8); b.grid(alpha=0.3, which="both")
    w = 0.38; xi = np.arange(4)
    for j, key in enumerate(("sa", "ufs")):
        cn = bin_counts(mx[key])
        bars = c.bar(xi + (j - 0.5) * w, cn, w, color=COL[key], label=DLAB[key])
        for r, v in zip(bars, cn):
            c.text(r.get_x() + w / 2, v + 1, str(v), ha="center", fontsize=8)
    c.set_xticks(xi); c.set_xticklabels([b_[0] for b_ in BINS]); c.set_ylabel("number of stations (of 166)")
    c.set_title("(c) stations by max |difference| class", fontsize=10); c.legend(fontsize=8); c.grid(axis="y", alpha=0.3)
    d.axis("off")
    rows = [["", "standalone", "UFS"]]
    for lab, f in (("median station max (mm)", lambda m: np.nanmedian(m) * 1e3), ("90th pct station max (mm)", lambda m: np.nanpercentile(m, 90) * 1e3),
                   ("worst station (cm)", lambda m: np.nanmax(m) * 1e2), ("bit-identical stations", lambda m: (m == 0).sum())):
        rows.append([lab] + [f"{f(mx[k]):.3g}" for k in ("sa", "ufs")])
    tb = d.table(cellText=rows[1:], colLabels=rows[0], loc="center", cellLoc="center")
    tb.auto_set_font_size(False); tb.set_fontsize(10); tb.scale(1, 1.8)
    d.set_title("(d) summary", fontsize=10)
    fig.suptitle(f"Station water level: standalone and UFS differences from operational STOFS-3D-ATL, {TITLE}", fontsize=13, y=0.96)
    return save_png(fig, out)


def wspd_dir(wx, wy):
    return np.hypot(wx, wy), (np.degrees(np.arctan2(-wx, -wy)) + 360) % 360


def rms(x):
    return np.sqrt(np.nanmean(x ** 2, axis=0))


def rank_plot(ax, ru, rs, un, floor=1e-9):
    ok = np.isfinite(ru) & np.isfinite(rs)
    ru, rs = ru[ok], rs[ok]
    o = np.argsort(ru)[::-1]
    xs = np.arange(1, len(o) + 1)
    ax.plot(xs, np.clip(ru[o], floor, None), color=COL["ufs"], lw=1.6, label=DLAB["ufs"])
    ax.plot(xs, np.clip(rs[o], floor, None), color=COL["sa"], lw=0, marker="o", ms=2.5, label=DLAB["sa"] +
            f" (zero drawn at {floor:g})")
    ax.set_yscale("log")
    ax.set_xlabel(f"stations with data (n={len(o)}), ranked by UFS RMS difference")
    ax.set_ylabel(f"RMS difference ({un})")
    ax.legend(fontsize=7.5)
    ax.grid(alpha=0.3, which="both")


def fig_atmos(T, P, WX, WY, sids, names, ids, out):
    x = tnum(T)
    n = len(ids)
    fig = plt.figure(figsize=(15, 12))
    gs = fig.add_gridspec(4, n, left=0.06, right=0.985, top=0.9, bottom=0.07, hspace=0.42, wspace=0.28,
                          height_ratios=[1, 1, 1, 1.15])
    spd = {k: wspd_dir(WX[k], WY[k])[0] for k in P}
    for j, sid in enumerate(ids):
        k = sids.index(sid)
        for r, (lab, arr) in enumerate((("pressure (hPa)", {q: P[q] / 100 for q in P}), ("wind speed (m/s)", spd),
                                         ("wind from-direction (deg)", {q: wspd_dir(WX[q], WY[q])[1] for q in P}))):
            ax = fig.add_subplot(gs[r, j])
            for key in ("ops", "sa", "ufs"):
                ax.plot(x, arr[key][:, k], color=COL[key], **STY[key])
            if r == 0:
                ax.set_title(names.get(sid, sid) + f" ({sid})", fontsize=9)
            if j == 0:
                ax.set_ylabel(lab, fontsize=8)
            fmt_time(ax)
    ax1 = fig.add_subplot(gs[3, : n // 2]); ax2 = fig.add_subplot(gs[3, n // 2:])
    for ax, f, ttl, un in ((ax1, lambda q: P[q] - P["ops"], "air pressure", "Pa"),
                           (ax2, lambda q: spd[q] - spd["ops"], "wind speed", "m/s")):
        rank_plot(ax, rms(f("ufs")), rms(f("sa")), un)
        ax.set_title(f"per-station RMS of {ttl} difference from operational (24 h)", fontsize=9)
    fig.legend(handles=handles(), loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.945), fontsize=9.5, frameon=False)
    fig.suptitle(f"Atmospheric forcing as seen by SCHISM at stations, {TITLE}", fontsize=13, y=0.985)
    return save_png(fig, out)


def fig_ts(T, V, sids, names, ids, out):
    x = tnum(T)
    n = len(ids)
    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(3, n, left=0.06, right=0.985, top=0.9, bottom=0.07, hspace=0.42, wspace=0.28,
                          height_ratios=[1, 1, 1.1])
    for j, sid in enumerate(ids):
        k = sids.index(sid)
        for r, (v, lab) in enumerate((("temp", "temperature (°C)"), ("salt", "salinity (psu)"))):
            ax = fig.add_subplot(gs[r, j])
            for key in ("ops", "sa", "ufs"):
                ax.plot(x, V[v][key][:, k], color=COL[key], **STY[key])
            if r == 0:
                ax.set_title(names.get(sid, sid) + f" ({sid})", fontsize=9)
            if j == 0:
                ax.set_ylabel(lab, fontsize=8)
            fmt_time(ax)
    for j, (v, lab, un) in enumerate((("temp", "temperature", "°C"), ("salt", "salinity", "psu"))):
        ax = fig.add_subplot(gs[2, j * (n // 2): (j + 1) * (n // 2)])
        rank_plot(ax, rms(V[v]["ufs"] - V[v]["ops"]), rms(V[v]["sa"] - V[v]["ops"]), un)
        ax.set_title(f"per-station RMS of {lab} difference from operational (24 h)", fontsize=9)
    fig.legend(handles=handles(), loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.945), fontsize=9.5, frameon=False)
    fig.suptitle(f"Station temperature and salinity (model station level), {TITLE}", fontsize=13, y=0.985)
    return save_png(fig, out)


def load_obs(obs_dir, sid):
    fn = os.path.join(obs_dir, f"wl_msl_{sid}.json")
    if not os.path.exists(fn):
        return None, None
    js = json.load(open(fn))
    if "data" not in js:
        return None, None
    t, v = [], []
    for d in js["data"]:
        if d["v"].strip():
            t.append(datetime.strptime(d["t"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())
            v.append(float(d["v"]))
    return (np.array(t), np.array(v)) if len(t) > 10 else (None, None)


def fig_obs(T, E, sids, names, off, obs_dir, out, summ):
    ts = START.timestamp() + T
    cand = []
    for sid in sids:
        ot, ov = load_obs(obs_dir, sid)
        k = sids.index(sid) + 1
        if ot is None or k not in off:
            continue
        ok = (ot >= ts[0]) & (ot <= ts[-1]) & np.isfinite(ov)
        if ok.sum() < 200:
            continue
        r = {"sid": sid, "ot": ot[ok], "ov": ov[ok]}
        for key in ("ops", "sa", "ufs"):
            m = E[key][:, k - 1] - off[k]
            r[key] = m
            mi = np.interp(r["ot"], ts, m)
            good = np.isfinite(mi)
            r["rmse_" + key] = float(np.sqrt(np.mean((mi[good] - r["ov"][good]) ** 2))) if good.sum() > 100 else np.nan
        r["dsa"] = float(np.nanmax(abs(E["sa"][:, k - 1] - E["ops"][:, k - 1])))
        r["dufs"] = float(np.nanmax(abs(E["ufs"][:, k - 1] - E["ops"][:, k - 1])))
        cand.append(r)
    if not cand:
        print("no observations; skipping ufs_wl_obs.png")
        return None
    pick = [c for c in cand if c["sid"] in DEFAULT_WL]
    pick += [c for c in cand if c not in pick]
    pick = pick[:8]
    summ.append("\nWater level vs CO-OPS (MSL), RMSE in m, all stations with cached obs (n=%d)" % len(cand))
    summ.append(f"{'ID':8s} {'ops':>7s} {'standalone':>10s} {'UFS':>7s} {'max|sa-ops|':>12s} {'max|UFS-ops|':>12s}")
    for c in cand:
        summ.append(f"{c['sid']:8s} {c['rmse_ops']:7.3f} {c['rmse_sa']:10.3f} {c['rmse_ufs']:7.3f} {c['dsa']:12.2e} {c['dufs']:12.2e}")
    summ.append("mean RMSE: ops %.4f, standalone %.4f, UFS %.4f" % tuple(
        np.nanmean([c["rmse_" + k] for c in cand]) for k in ("ops", "sa", "ufs")))
    fig = plt.figure(figsize=(15, 11.5))
    gs = fig.add_gridspec(3, 4, left=0.06, right=0.985, top=0.87, bottom=0.08, hspace=0.45, wspace=0.25,
                          height_ratios=[1, 1, 1.05])
    x = tnum(T)
    for i, c in enumerate(pick):
        ax = fig.add_subplot(gs[i // 4, i % 4])
        ax.plot(mdates.date2num([datetime.fromtimestamp(v, timezone.utc) for v in c["ot"]]), c["ov"], color="k", lw=0.9)
        for key in ("ops", "sa", "ufs"):
            ax.plot(x, c[key], color=COL[key], **STY[key])
        ax.set_title(f"{names.get(c['sid'], c['sid'])} ({c['sid']})\nRMSE: op {c['rmse_ops']:.3f}, sa {c['rmse_sa']:.3f}, "
                     f"UFS {c['rmse_ufs']:.3f} m", fontsize=8)
        if i % 4 == 0:
            ax.set_ylabel("water level, MSL (m)", fontsize=8)
        fmt_time(ax)
    ax1 = fig.add_subplot(gs[2, :2]); ax2 = fig.add_subplot(gs[2, 2:])
    xi = np.arange(len(pick)); w = 0.27
    for j, key in enumerate(("ops", "sa", "ufs")):
        ax1.bar(xi + (j - 1) * w, [c["rmse_" + key] for c in pick], w, color=COL[key], label=LAB[key])
    lbl = [f"{names.get(c['sid'], c['sid']).split(',')[0].title()}\n{c['sid']}" for c in pick]
    for ax in (ax1, ax2):
        ax.set_xticks(xi); ax.set_xticklabels(lbl, fontsize=6.5, rotation=35, ha="right"); ax.grid(axis="y", alpha=0.3, which="both")
    ax1.set_ylabel("RMSE vs observed (m)"); ax1.set_title("RMSE against observations", fontsize=9.5); ax1.legend(fontsize=7)
    ax2.bar(xi - 0.2, [max(c["dsa"], FLOOR) for c in pick], 0.4, color=COL["sa"], label=DLAB["sa"])
    ax2.bar(xi + 0.2, [max(c["dufs"], FLOOR) for c in pick], 0.4, color=COL["ufs"], label=DLAB["ufs"])
    ax2.set_yscale("log"); ax2.set_ylabel("max |difference| (m)"); ax2.set_title("run-to-run difference over 24 h", fontsize=9.5)
    ax2.legend(fontsize=7)
    fig.legend(handles=[Line2D([], [], color="k", lw=1, label="observed (NOAA CO-OPS)")] + handles(), loc="upper center",
               ncol=4, bbox_to_anchor=(0.5, 0.96), fontsize=9, frameon=False)
    fig.suptitle(f"Water level vs NOAA CO-OPS observations (MSL), {TITLE}", fontsize=13, y=0.985)
    return save_png(fig, out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for o in ("ops-dir", "standalone-dir", "coupled-dir", "station-in", "names-csv", "msl-nco", "obs-dir", "outdir"):
        ap.add_argument("--" + o, required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    dirs = {"ops": a.ops_dir, "sa": a.standalone_dir, "ufs": a.coupled_dir}
    sids, lon, lat, names = load_stations(a.station_in, a.names_csv)
    off = load_offsets(a.msl_nco)
    V, T = {}, None
    for v, k in VARS.items():
        V[v] = {}
        for key, d in dirs.items():
            t, V[v][key] = load_var(d, k)
            T = t if T is None else T
            assert np.allclose(t, T)
    ns = len(sids)
    assert V["elev"]["ops"].shape[1] == ns
    D = {k: V["elev"][k] - V["elev"]["ops"] for k in ("sa", "ufs")}
    mx = {k: np.nanmax(np.abs(D[k]), axis=0) for k in D}
    O = lambda p: os.path.join(a.outdir, p)
    sizes = {}
    wl_ids = [s for s in DEFAULT_WL if s in sids]
    sizes["ufs_wl_ts.png"] = fig_wl_ts(T, V["elev"], sids, names, wl_ids, O("ufs_wl_ts.png"))
    try:
        sizes["ufs_wl_maxdiff_map.png"] = fig_map(lon, lat, mx, None, O("ufs_wl_maxdiff_map.png"))
    except Exception as ex:
        print("map failed:", ex)
    sizes["ufs_wl_stats.png"] = fig_stats(T, D, mx, O("ufs_wl_stats.png"))
    at_ids = [s for s in ("8518750", "8651370", "8443970", "8773037") if s in sids]
    sizes["ufs_atmos_at_stations.png"] = fig_atmos(T, V["pres"], V["wx"], V["wy"], sids, names, at_ids, O("ufs_atmos_at_stations.png"))
    ts_ids = [s for s in ("8518750", "8651370", "8443970", "8773037") if s in sids]
    sizes["ufs_ts_temp_salt.png"] = fig_ts(T, V, sids, names, ts_ids, O("ufs_ts_temp_salt.png"))

    S = [f"STOFS-3D-ATL {TITLE} 24 h nowcast: station comparison (166 stations, 288 x 5 min)",
         "Differences are standalone − operational and UFS − operational.", ""]
    S.append("Water level (elevation, m)")
    for k in ("sa", "ufs"):
        m = mx[k]
        S.append(f"  {DLAB[k]}: median station max {np.nanmedian(m):.2e}, 90th pct {np.nanpercentile(m, 90):.2e}, worst {np.nanmax(m):.2e}; "
                 f"bit-identical {int((m == 0).sum())}; classes " +
                 ", ".join(f"{b[0]}: {c}" for b, c in zip(BINS, bin_counts(m))) +
                 f"; mean RMS over all stations/times {np.sqrt(np.nanmean(D[k] ** 2)):.2e}")
        w = np.argsort(m)[::-1][:8]
        S.append("    largest: " + "; ".join(f"{names.get(sids[i], sids[i])} {sids[i]} {m[i]:.3f} m" for i in w))
    S.append("")
    spd = {k: wspd_dir(V["wx"][k], V["wy"][k])[0] for k in dirs}
    for lab, un, arrs in (("Air pressure", "Pa", V["pres"]), ("Wind speed", "m/s", spd), ("Wind x", "m/s", V["wx"]),
                          ("Wind y", "m/s", V["wy"]), ("Temperature", "C", V["temp"]), ("Salinity", "psu", V["salt"]),
                          ("u velocity", "m/s", V["u"]), ("v velocity", "m/s", V["v"])):
        S.append(f"{lab} ({un})")
        for k in ("sa", "ufs"):
            d = arrs[k] - arrs["ops"]
            pr = rms(d)
            S.append(f"  {DLAB[k]}: RMS all {np.sqrt(np.nanmean(d ** 2)):.3e}, max|diff| {np.nanmax(abs(d)):.3e}, "
                     f"median station RMS {np.nanmedian(pr):.3e}, worst station RMS {np.nanmax(pr):.3e} "
                     f"({sids[int(np.nanargmax(pr))]}); NaN samples {int(np.isnan(d).sum())}")
    S.append("")
    S.append("Station class: open-coast quiet (Battery 8518750, Duck 8651370, Gulf 8761724), flagged (Seadrift 8773037, Providence 8454000, "
             "Wachapreague 8631044), Gulf of Maine wet/dry (Wells 8419317, Fort Point 8423898, Boston 8443970): max|WL diff| m")
    for cls, ids in (("quiet", ["8518750", "8651370", "8761724"]), ("flagged", ["8773037", "8454000", "8631044"]),
                     ("GoM wet/dry", ["8419317", "8423898", "8443970"])):
        for k in ("sa", "ufs"):
            S.append(f"  {cls:12s} {DLAB[k]:26s} " + ", ".join(f"{s}:{mx[k][sids.index(s)]:.2e}" for s in ids if s in sids))
    E = V["elev"]
    ofig = fig_obs(T, E, sids, names, off, a.obs_dir, O("ufs_wl_obs.png"), S)
    if ofig:
        sizes["ufs_wl_obs.png"] = ofig
    open(O("ufs_summary.txt"), "w").write("\n".join(S) + "\n")
    print("\n".join(S))


if __name__ == "__main__":
    main()
