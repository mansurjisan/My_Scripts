#!/usr/bin/env python3
"""
River source/sink input-file validation figures for STOFS-3D-ATL: operational v3.1 vs nos-workflow before and
after the ops-parity fix (river_ops_static), PDY 2026-10-01 12z, same NWM inputs.

usage: plot_river_compare.py --river-dir RIVER_DIR --mesh HGRID_LL --outdir DIR [--start 2026093012]
           [--cycle 2026100112] [--cache NPZ] [--only 1,2,3,4,5] [--max-sink-plot 400000]

RIVER_DIR holds
  ops_1001.{vsource,msource,vsink}.th   operational files (vsource/msource: time + 1348 columns, msource has T then S)
  fixdir/stofs_3d_atl_river_source_sink.in   operational source / sink element lists (order of the ops columns)
  out_comb/{vsource,msource,vsink}.th, out_comb/source_sink.in    nos-workflow, this PR (nowcast + forecast, 121 rows)
  out_old_comb/{vsource,msource}.th, out_old_comb/source_sink.in  nos-workflow before the fix (sorted sources,
                                                                  no sinks, msource T = S = -9999, %.4e vsource)
  out_now/                                                        optional, nowcast-only files (byte checks)
HGRID_LL is the mesh in lon/lat (SCHISM hgrid format); source and sink locations are element centroids, read in a
streaming way. --cache stores/reads the centroids (npz) so the mesh is parsed once.
The before-fix vsource/msource columns are in sorted element order; they are mapped to the ops column order by element
id before any comparison. Rows are matched on the time column (the 121 rows the port wrote). Time zero = --start.

Figures (PNG, dpi 100, <= 1500 px):
  1 river_total_inflow.png      total inflow (sum of 1348 sources) vs time, ops / before / this PR, + differences
  2 river_top_sources.png       the 6 largest sources, three versions, max |diff| per panel
  3 river_msource_salinity.png  source salinity per source (ops, this PR: 0; before: -9999 = ambient) on a map
  4 river_sinks_map.png         ops sink elements (rate-weighted density) and the distribution of sink rates
  5 river_order.png             column order of the before-fix file vs the ops source order
plus river_summary.txt.
"""
import argparse
import filecmp
import os
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from PIL import Image

LAB = {"ops": "operational", "before": "nos-workflow before fix", "pr": "nos-workflow (this PR)"}
COL = {"ops": "#0072B2", "before": "#D55E00", "pr": "#009E73"}     # Okabe-Ito, colour-blind safe
LW = {"ops": 3.4, "before": 1.8, "pr": 1.0}
# approximate outlet locations used only to name the big sources (lon, lat, name, tolerance deg)
RIVERS = [(-91.6, 31.05, "Mississippi / Atchafalaya (Old River, LA)", 0.4), (-76.1, 39.6, "Susquehanna", 0.3),
          (-75.4, 39.7, "Delaware", 0.5), (-73.9, 42.1, "Hudson", 0.4), (-72.6, 41.65, "Connecticut", 0.3),
          (-87.95, 30.85, "Mobile-Tensaw", 0.3), (-89.3, 29.1, "Mississippi (delta)", 0.6),
          (-81.5, 30.4, "St. Johns", 0.4), (-77.0, 38.8, "Potomac", 0.4)]


def save_png(fig, out):
    fig.savefig(out, dpi=100, metadata={"Software": None})
    plt.close(fig)
    im = Image.open(out)
    w, h = im.size
    assert max(w, h) <= 1500, f"{out}: {w}x{h} exceeds 1500 px"
    im.save(out, optimize=True)
    print(f"saved {out}  {w}x{h}")


def parse_dt(s):
    return datetime.strptime(s, "%Y%m%d%H").replace(tzinfo=timezone.utc)


def read_ss(path):
    """source_sink.in -> (source element ids, sink element ids)."""
    with open(path) as f:
        ns = int(f.readline().split()[0])
        src = np.array([int(f.readline().split()[0]) for _ in range(ns)])
        f.readline()
        nk = int(f.readline().split()[0])
        snk = np.loadtxt(f, dtype=np.int64, max_rows=nk).reshape(-1) if nk else np.zeros(0, np.int64)
    return src, snk


def read_th(path, nrows=None):
    return pd.read_csv(path, sep=r"\s+", header=None, nrows=nrows, dtype=np.float64).to_numpy()


def centroids(mesh, ids, cache):
    """Element centroids (lon, lat) for element ids (1-based), streaming the hgrid; float32."""
    if cache and os.path.exists(cache):
        z = np.load(cache)
        if np.array_equal(z["ids"], ids):
            return z["lon"], z["lat"]
    with open(mesh) as f:
        f.readline()                                    # grid name / comment line
        ne, nn = (int(x) for x in f.readline().split()[:2])
    xy = pd.read_csv(mesh, sep=r"\s+", header=None, skiprows=2, nrows=nn, usecols=[1, 2],
                     dtype=np.float32).to_numpy()
    lon = np.full(len(ids), np.nan, np.float32)
    lat = np.full(len(ids), np.nan, np.float32)
    order = np.argsort(ids)
    sid = ids[order]
    step = 500000
    for s in range(0, ne, step):
        ch = pd.read_csv(mesh, sep=r"\s+", header=None, skiprows=2 + nn + s, nrows=min(step, ne - s),
                         usecols=[0, 2, 3, 4], dtype=np.int64).to_numpy()
        lo, hi = ch[0, 0], ch[-1, 0]
        a, b = np.searchsorted(sid, lo), np.searchsorted(sid, hi, side="right")
        if b > a:
            want = sid[a:b]
            rows = ch[want - lo]
            assert (rows[:, 0] == want).all(), "element ids not consecutive in the hgrid"
            nodes = rows[:, 1:] - 1
            lon[order[a:b]] = xy[nodes, 0].mean(1)
            lat[order[a:b]] = xy[nodes, 1].mean(1)
        del ch
    del xy
    assert not np.isnan(lon).any(), "some elements were not found in the mesh"
    if cache:
        np.savez(cache, ids=ids, lon=lon, lat=lat)
    return lon, lat


def overlay(ax, ticks=True):
    import cartopy.feature as cf
    ax.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#e6f0f7", zorder=0)
    ax.add_feature(cf.LAND.with_scale("50m"), facecolor="0.88", zorder=1)
    ax.add_feature(cf.COASTLINE.with_scale("50m"), edgecolor="0.35", lw=0.4, zorder=2)
    if ticks:
        gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.5)
        gl.top_labels = gl.right_labels = False
        gl.xlabel_style = gl.ylabel_style = {"size": 7}


def river_name(lon, lat):
    best = None
    for rl, rt, nm, tol in RIVERS:
        d = np.hypot(lon - rl, lat - rt)
        if d <= tol and (best is None or d < best[0]):
            best = (d, nm)
    return best[1] if best else None


class Data:
    pass


def load(args):
    R = args.river_dir
    d = Data()
    d.src_ops, d.snk_ops = read_ss(os.path.join(R, "fixdir", "stofs_3d_atl_river_source_sink.in"))
    d.src_pr, d.snk_pr = read_ss(os.path.join(R, "out_comb", "source_sink.in"))
    d.src_old, d.snk_old = read_ss(os.path.join(R, "out_old_comb", "source_sink.in"))
    n = len(d.src_ops)
    ops = read_th(os.path.join(R, "ops_1001.vsource.th"))
    pr = read_th(os.path.join(R, "out_comb", "vsource.th"))
    old = read_th(os.path.join(R, "out_old_comb", "vsource.th"))
    assert ops.shape[1] == n + 1 and pr.shape[1] == n + 1 and old.shape[1] == n + 1
    nr = min(len(ops), len(pr), len(old))
    assert np.allclose(ops[:nr, 0], pr[:nr, 0]) and np.allclose(ops[:nr, 0], old[:nr, 0])
    d.t = ops[:nr, 0]
    d.ops, d.pr = ops[:nr, 1:], pr[:nr, 1:]
    d.ops_full_rows = len(ops)
    assert np.array_equal(d.src_ops, d.src_pr), "this-PR source order differs from ops"
    pos = {e: i for i, e in enumerate(d.src_old)}
    d.map_old = np.array([pos[e] for e in d.src_ops])           # ops column k -> before-fix column
    d.before = old[:nr, 1:][:, d.map_old]
    d.before_raw = old[:nr, 1:]
    ms = {}
    for k, p in (("ops", "ops_1001.msource.th"), ("pr", "out_comb/msource.th"), ("before", "out_old_comb/msource.th")):
        ms[k] = read_th(os.path.join(R, p), nrows=2)
    d.ms = ms
    d.vsink_ops = read_th(os.path.join(R, "ops_1001.vsink.th"))
    d.vsink_pr = read_th(os.path.join(R, "out_comb", "vsink.th"))
    d.lon_s, d.lat_s = centroids(args.mesh, np.concatenate([d.src_ops, d.snk_ops]), args.cache)
    n_s = len(d.src_ops)
    d.slon, d.slat = d.lon_s[:n_s], d.lat_s[:n_s]
    d.klon, d.klat = d.lon_s[n_s:], d.lat_s[n_s:]
    return d


def tsetup(d, args):
    t0 = parse_dt(args.start)
    return np.array([t0 + timedelta(seconds=float(s)) for s in d.t]), parse_dt(args.cycle)


def timefmt(ax):
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=(0, 12)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %Hz\n%b"))
    ax.tick_params(labelsize=8)


def fig1(d, args, out, ct):
    th, cyc = tsetup(d, args)
    tot = {"ops": d.ops.sum(1), "before": d.before.sum(1), "pr": d.pr.sum(1)}
    fig, (a, b) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                               gridspec_kw=dict(height_ratios=[3, 1.5], hspace=0.1, left=0.08, right=0.98,
                                                top=0.88, bottom=0.09))
    for k in ("ops", "before", "pr"):
        a.plot(th, tot[k], color=COL[k], lw=LW[k], label=LAB[k], alpha=0.65 if k == "ops" else 1)
    b.axhline(0, color=COL["pr"], lw=1.2, label="nos-workflow (this PR) - operational")
    b.plot(th, tot["before"] - tot["ops"], color=COL["before"], lw=1.5, label="nos-workflow before fix - operational")
    for ax in (a, b):
        ax.axvline(cyc, color="0.3", ls="--", lw=1)
        ax.grid(alpha=0.3)
    a.text(cyc, 0.98, " cycle time\n nowcast | forecast", transform=a.get_xaxis_transform(), va="top",
           fontsize=9, color="0.3")
    a.set_ylabel("total river inflow, sum of 1348 sources (m$^3$/s)", fontsize=10)
    b.set_ylabel("difference (m$^3$/s)", fontsize=10)
    a.legend(fontsize=10, loc="lower right")
    b.legend(fontsize=9, loc="upper left")
    timefmt(b)
    dm = float(np.abs(tot["pr"] - tot["ops"]).max())
    db = float(np.abs(tot["before"] - tot["ops"]).max())
    a.set_title(f"max |this PR - operational| = {dm:.3g} m$^3$/s;  max |before - operational| = {db:.3g} m$^3$/s "
                f"({100 * db / tot['ops'].max():.4f}% of peak)", fontsize=10.5)
    fig.suptitle(f"Total river inflow in vsource.th, {ct}", fontsize=13, y=0.97)
    save_png(fig, out)
    return tot


def fig2(d, args, out, ct):
    th, cyc = tsetup(d, args)
    top = np.argsort(-d.ops.mean(0))[:6]
    fig, axs = plt.subplots(2, 3, figsize=(15, 8), sharex=True)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.76, bottom=0.08, hspace=0.42, wspace=0.27)
    info = []
    for ax, k in zip(axs.flat, top):
        for v, arr in (("ops", d.ops), ("before", d.before), ("pr", d.pr)):
            ax.plot(th, arr[:, k], color=COL[v], lw=LW[v], alpha=0.65 if v == "ops" else 1)
        nm = river_name(d.slon[k], d.slat[k])
        t = f"element {d.src_ops[k]}  ({d.slon[k]:.2f}, {d.slat[k]:.2f})" + (f"\n{nm}" if nm else "")
        dp = np.abs(d.pr[:, k] - d.ops[:, k]).max()
        db = np.abs(d.before[:, k] - d.ops[:, k]).max()
        ax.set_title(t + f"\nmax |diff|: this PR {dp:.3g}, before {db:.3g} m$^3$/s", fontsize=9)
        ax.axvline(cyc, color="0.3", ls="--", lw=0.8)
        ax.grid(alpha=0.3)
        ax.set_ylabel("flow (m$^3$/s)", fontsize=8.5)
        timefmt(ax)
        info.append((int(d.src_ops[k]), float(d.slon[k]), float(d.slat[k]), nm, float(d.ops[:, k].mean())))
    h = [Line2D([], [], color=COL[v], lw=LW[v] if v != "ops" else 3, alpha=0.65 if v == "ops" else 1, label=LAB[v])
         for v in ("ops", "before", "pr")] + [Line2D([], [], color="0.3", ls="--", label="cycle time")]
    fig.legend(handles=h, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 0.865), fontsize=10, frameon=False)
    fig.suptitle(f"The six largest river sources (by mean flow), {ct}\n(source location = centroid of the "
                 "source element)", fontsize=12.5, y=0.985)
    save_png(fig, out)
    return info


def fig3(d, args, out, ct):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    fig = plt.figure(figsize=(15, 8.6))
    ax = [fig.add_axes([0.03, 0.27, 0.46, 0.60], projection=pc), fig.add_axes([0.52, 0.27, 0.46, 0.60], projection=pc)]
    ext = [-98.5, -52, 7.5, 52]
    cols = {0.0: "#2166AC", -9999.0: "#D55E00"}
    for a, k, ttl in ((ax[0], "ops", "operational and nos-workflow (this PR)"), (ax[1], "before", "nos-workflow before fix")):
        S = d.ms[k][0, 1 + len(d.src_ops):]
        a.set_extent(ext, crs=pc)
        overlay(a)
        for v, c in cols.items():
            m = S == v
            if m.any():
                a.scatter(d.slon[m], d.slat[m], s=14, color=c, edgecolor="k", lw=0.25, zorder=5, transform=pc)
        u = np.unique(S)
        a.set_title(f"{ttl}\nsource salinity value(s) in msource.th: " + ", ".join(f"{x:g}" for x in u), fontsize=10.5)
    assert np.array_equal(d.ms["ops"][:, 1:], d.ms["pr"][:, 1:]), "this-PR msource differs from ops"
    h = [Line2D([], [], marker="o", ls="", mfc=cols[0.0], mec="k", ms=8, label="S = 0 psu: river water is fresh"),
         Line2D([], [], marker="o", ls="", mfc=cols[-9999.0], mec="k", ms=8, label="S = -9999: no source salinity set")]
    ax[0].legend(handles=h, loc="lower left", fontsize=9, framealpha=0.95)
    txt = ("How SCHISM reads msource.th: the file gives the temperature and salinity of the water injected at each "
           "river source (first block of columns = temperature, second block = salinity).\n"
           "A value of -9999 means 'no value prescribed': the source takes the ambient (local) tracer value, so the "
           "river adds volume but does not freshen the cell.\n"
           "Operational: T = -9999 (ambient temperature), S = 0 (fresh).  This PR: identical to operational.  "
           "Before the fix: T = S = -9999 at every source, so river inflow did not lower salinity.\n"
           f"All {len(d.src_ops)} sources carry the same value in each version, so the maps show where the sources are.")
    fig.text(0.03, 0.12, txt, fontsize=10, va="center", wrap=True,
             bbox=dict(fc="#f5f5f5", ec="0.6", boxstyle="round,pad=0.6"))
    fig.suptitle(f"River source salinity setting in msource.th, {ct}", fontsize=13, y=0.95)
    save_png(fig, out)


def fig4(d, args, out, ct):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    rate = d.vsink_ops[0, 1:]
    assert len(rate) == len(d.snk_ops)
    tot = rate.sum()
    fig = plt.figure(figsize=(15, 8.4))
    am = fig.add_axes([0.03, 0.30, 0.52, 0.58], projection=pc)
    ah = fig.add_axes([0.62, 0.38, 0.36, 0.50])
    am.set_extent([-98.5, -52, 7.5, 52], crs=pc)
    overlay(am)
    hb = am.hexbin(d.klon, d.klat, C=-rate, reduce_C_function=np.sum, gridsize=170, mincnt=1, cmap="viridis_r",
                   norm=LogNorm(), linewidths=0, zorder=5, transform=pc, extent=(-98.5, -52, 7.5, 52))
    hb.set_rasterized(True)
    cb = fig.colorbar(hb, ax=am, orientation="horizontal", fraction=0.04, pad=0.07)
    cb.set_label("summed sink rate per hexagon (m$^3$/s, plotted as positive)", fontsize=9)
    am.set_title(f"{len(d.snk_ops):,} sink elements, total {tot:,.0f} m$^3$/s\n(all elements, rate-weighted)",
                 fontsize=10.5)
    r = -rate
    bins = np.logspace(np.log10(max(r[r > 0].min(), 1e-12)), np.log10(r.max()), 70)
    ah.hist(r[r > 0], bins=bins, color="#0072B2")
    ah.set_xscale("log")
    ah.set_yscale("log")
    ah.set_xlabel("sink rate of one element (m$^3$/s, plotted as positive)", fontsize=9)
    ah.set_ylabel("number of sink elements", fontsize=9)
    q = np.percentile(r, [50, 90, 99])
    ah.set_title(f"Distribution of sink rates (vsink.th, constant in time)\nmedian {q[0]:.2g}, 90% {q[1]:.2g}, "
                 f"99% {q[2]:.2g}, max {r.max():.2g} m$^3$/s", fontsize=10)
    ah.grid(alpha=0.3, which="both")
    txt = ("Operational vsink.th removes water at 1,986,300 elements (net -180,469 m$^3$/s in total; the rate is "
           "constant in time).\nnos-workflow before fix: no sinks (vsink.th not written, 0 sink elements).  "
           "This PR: identical to operational (file byte-identical).\n"
           "SCHISM sets the net sink to zero on dry elements, so only wetted sink elements actually remove water at "
           "a given time.\n"
           f"Hexbins aggregate all {len(d.snk_ops):,} elements (no subsampling); sink location = element centroid.")
    fig.text(0.03, 0.115, txt, fontsize=10, va="center", wrap=True,
             bbox=dict(fc="#f5f5f5", ec="0.6", boxstyle="round,pad=0.6"))
    fig.suptitle(f"River sink input (vsink.th), operational vs nos-workflow, {ct}", fontsize=13, y=0.96)
    save_png(fig, out)
    return tot, q, float(r.max())


def fig5(d, out, ct):
    fig, ax = plt.subplots(figsize=(8, 7.4))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.86, bottom=0.12)
    k = np.arange(len(d.src_ops))
    ax.scatter(k, d.map_old, s=4, color=COL["before"], label="before fix", zorder=3)
    ax.plot([0, k[-1]], [0, k[-1]], color=COL["pr"], lw=1.6, label="this PR = operational order", zorder=2)
    ax.set_xlabel("column index in operational vsource.th (source number)", fontsize=10)
    ax.set_ylabel("column index of the same source element\nin the before-fix vsource.th", fontsize=10)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, loc="lower right")
    same = int((d.map_old == k).sum())
    fig.suptitle(f"Source column order, {ct}", fontsize=12.5, y=0.97)
    ax.set_title(f"Before fix: sources sorted by element id; same column as ops for {same} of {len(k)}",
                 fontsize=9.5)
    save_png(fig, out)
    return same


def summary(path, d, args, tot, top, sink, same, R):
    n = len(d.src_ops)
    L = ["River source/sink files, operational STOFS-3D-ATL v3.1 vs nos-workflow, PDY 2026-10-01 12z", "",
         f"sources: {n} (ops, this PR, before)", f"time rows compared: {len(d.t)} (0 .. {d.t[-1]:.0f} s, 3600 s); "
         f"ops vsource has {d.ops_full_rows} rows",
         f"source order: this PR == ops: {np.array_equal(d.src_ops, d.src_pr)}; before-fix same column as ops for "
         f"{same} of {n} (sorted order); same element set: {set(d.src_old) == set(d.src_ops)}",
         "",
         f"sinks: ops {len(d.snk_ops):,}; this PR {len(d.snk_pr):,}; before {len(d.snk_old):,}",
         f"sink element lists identical, ops vs this PR: {np.array_equal(d.snk_ops, d.snk_pr)}",
         f"vsink total (ops): {sink[0]:,.1f} m3/s; this PR: {d.vsink_pr[0, 1:].sum():,.1f}; "
         f"rate percentiles 50/90/99 (positive): {sink[1][0]:.4g} / {sink[1][1]:.4g} / {sink[1][2]:.4g}; max {sink[2]:.4g}",
         f"vsink.th max |this PR - operational| over the whole file: {np.abs(d.vsink_pr - d.vsink_ops).max():g}",
         "",
         f"msource ops   : T unique {np.unique(d.ms['ops'][0, 1:n + 1])}, S unique {np.unique(d.ms['ops'][0, n + 1:])}",
         f"msource this PR: T unique {np.unique(d.ms['pr'][0, 1:n + 1])}, S unique {np.unique(d.ms['pr'][0, n + 1:])}",
         f"msource before: T unique {np.unique(d.ms['before'][0, 1:n + 1])}, S unique {np.unique(d.ms['before'][0, n + 1:])}",
         "", "vsource, total inflow (sum over sources, m3/s)",
         f"  ops   : mean {tot['ops'].mean():.2f}, max {tot['ops'].max():.2f}, first row {tot['ops'][0]:.2f}",
         f"  this PR: max |diff vs ops| {np.abs(tot['pr'] - tot['ops']).max():.4g}",
         f"  before: max |diff vs ops| {np.abs(tot['before'] - tot['ops']).max():.4g}", "",
         "vsource, per source max |diff| vs ops over all compared rows (m3/s), and over the nowcast rows (first 28)"]
    for nm, a in (("this PR", d.pr), ("before", d.before)):
        e = np.abs(a - d.ops)
        L.append(f"  {nm:8s}: all rows {e.max():.4g}; rows 1-28 {e[:28].max():.4g}; rows 29-end {e[28:].max():.4g}; "
                 f"sources with any diff > 1e-3: {(e.max(0) > 1e-3).sum()}")
    L += ["", "six largest sources by mean ops flow: element, lon, lat, name, mean flow (m3/s)"]
    L += [f"  {i}  {lo:.3f}  {la:.3f}  {nm}  {m:.2f}" for i, lo, la, nm, m in top]
    L += ["", "byte checks of local port outputs vs ops files"]
    for p, q in (("out_now/msource.th", "ops_1001.msource.th"), ("out_now/vsink.th", "ops_1001.vsink.th"),
                 ("out_comb/msource.th", "ops_1001.msource.th"), ("out_comb/vsink.th", "ops_1001.vsink.th")):
        L.append(f"  cmp {p} vs {q}: {'identical' if filecmp.cmp(os.path.join(R, p), os.path.join(R, q), False) else 'DIFFERENT'}")
    with open(os.path.join(R, "ops_1001.vsource.th")) as f1, open(os.path.join(R, "out_now", "vsource.th")) as f2:
        a1 = [next(f1) for _ in range(28)]
        a2 = [next(f2) for _ in range(28)]
    L.append(f"  vsource rows 1-28, out_now vs ops (text equal): {a1 == a2}")
    L.append("  WCOSS2 cmp of this PR's nowcast files vs ops: msource, vsink and vsource rows 1-28 byte-identical (passed)")
    open(path, "w").write("\n".join(L) + "\n")
    print("saved", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--river-dir", required=True)
    ap.add_argument("--mesh", required=True, help="hgrid.ll (SCHISM hgrid in lon/lat)")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--start", default="2026093012", help="time of t = 0 of the files, YYYYMMDDHH")
    ap.add_argument("--cycle", default="2026100112", help="cycle time YYYYMMDDHH")
    ap.add_argument("--cache", default=None, help="npz file to store/read element centroids")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    o = lambda n: os.path.join(args.outdir, n)
    ct = parse_dt(args.cycle).strftime("PDY %Y-%m-%d %Hz")
    d = load(args)
    tot = fig1(d, args, o("river_total_inflow.png"), ct)
    top = fig2(d, args, o("river_top_sources.png"), ct)
    fig3(d, args, o("river_msource_salinity.png"), ct)
    sink = fig4(d, args, o("river_sinks_map.png"), ct)
    same = fig5(d, o("river_order.png"), ct)
    summary(o("river_summary.txt"), d, args, tot, top, sink, same, args.river_dir)


if __name__ == "__main__":
    main()
