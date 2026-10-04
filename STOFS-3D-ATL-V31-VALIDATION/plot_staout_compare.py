#!/usr/bin/env python3
"""
Station water-level (staout_1) validation figures: nos-workflow STOFS-3D-ATL standalone nowcast
(ops SCHISM 5.14 executable) vs the operational STOFS-3D-ATL v3.1, PDY 2026-10-01 12z.

usage: plot_staout_compare.py --ops OPS_STAOUT_1 --nos-workflow NOS_STAOUT_1 --station-in STATION_IN
           --outdir DIR [--names-csv STAOUT_NC_CSV] [--start 2026093012] [--cycle 2026100112]
           [--ts-ids 8725520,...]

OPS_STAOUT_1   operational continuous run started at --start (column 0 = seconds, 1 row per output)
NOS_STAOUT_1   the nos-workflow 24 h nowcast started at the same time (column k = station k of STATION_IN)
STATION_IN     stofs_3d_atl_station.in ("i lon lat z !ID", 166 rows after the flag line + count)
STAOUT_NC_CSV  stofs_3d_atl_staout_nc.csv (";"-separated, "idx;NWSID SOUS.. ID ST Name;lat;lon"), optional
Rows are matched on the seconds column (the rows both files have, 288 x 300 s = 24 h); the output
interval is 300 s. nos-workflow - operational is always shown.

Figures (PNG, dpi 100, <= 1500 px):
  1 staout_wl_ts.png          6 stations (3 quiet + Wells, Fort Point, Boston): operational vs nos-workflow + difference
  2 staout_maxdiff_map.png    max |nos-workflow - operational| per station (log colour), full domain + Northeast zoom
  3 staout_divergence.png     stations above 1 mm / 1 cm vs time, RMS vs time, per-station max |diff|
  4 staout_wells_lowtide.png  Wells and Fort Point at 5 min resolution around the largest difference
plus staout_summary.txt (per-station max / RMS / equal fraction, sorted, and the counts).
"""
import argparse
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

LAB = {"ops": "operational STOFS-3D-ATL", "ours": "nos-workflow (standalone, ops SCHISM 5.14)"}
COL = {"ops": "#0072B2", "ours": "#D55E00"}          # Okabe-Ito, colour-blind safe
WELLS, FORT_POINT, BOSTON = "8419317", "8423898", "8443970"
FLOOR = 1e-6


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


def load_stations(path, names_csv):
    ids, lon, lat = [], [], []
    with open(path) as f:
        f.readline()
        n = int(f.readline().split()[0])
        for _ in range(n):
            line = f.readline()
            data, _, sid = line.partition("!")
            p = data.split()
            lon.append(float(p[1]))
            lat.append(float(p[2]))
            ids.append(sid.strip())
    names = {}
    if names_csv:
        with open(names_csv) as f:
            next(f)
            for line in f:
                p = line.rstrip("\n").split(";")
                t = p[1].split()
                if len(t) >= 5:
                    names[t[2]] = f"{' '.join(t[4:])}, {t[3]}"
    lab = [f"{names.get(i, i)} ({i})" for i in ids]
    short = [names.get(i, i).split(",")[0] + f" {i}" for i in ids]
    return ids, np.array(lon), np.array(lat), lab, short


def load_common(ops_p, nos_p):
    o, u = np.loadtxt(ops_p), np.loadtxt(nos_p)
    n = min(len(o), len(u))
    assert np.allclose(o[:n, 0], u[:n, 0]), "time columns differ"
    return o[:n, 0], o[:n, 1:], u[:n, 1:]


def fmt_m(x):
    return f"{x:.2e}" if 0 < x < 1e-3 else f"{x:.3f}"


def pick_quiet(ids, lon, lat, mx):
    """Quiet (max|diff| < 1 mm) stations nearest to a Gulf/Florida, mid-Atlantic and Northeast point."""
    out = []
    for tlon, tlat in ((-84.0, 28.0), (-76.0, 36.5), (-70.5, 42.5)):
        d = np.hypot(lon - tlon, lat - tlat)
        d[mx >= 1e-3] = 1e9
        for i in out:
            d[i] = 1e9
        out.append(int(np.argmin(d)))
    return out


def tfmt(ax, start):
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %Hz\n%b"))
    ax.tick_params(labelsize=8)


# ------------------------------------------------------------------ figures
def fig1(sel, T, O, U, lab, mx, out, cycle_title):
    T = np.array(T)
    fig = plt.figure(figsize=(15, 9.6))
    gs = fig.add_gridspec(4, 3, height_ratios=[3, 1.2, 3, 1.2], hspace=0.55, wspace=0.22,
                          left=0.06, right=0.985, top=0.86, bottom=0.07)
    for k, i in enumerate(sel):
        r, c = divmod(k, 3)
        a1 = fig.add_subplot(gs[2 * r, c])
        a2 = fig.add_subplot(gs[2 * r + 1, c], sharex=a1)
        a1.plot(T, O[:, i], color=COL["ops"], lw=2.6, alpha=0.55)
        a1.plot(T, U[:, i], color=COL["ours"], lw=1.1)
        a2.plot(T, U[:, i] - O[:, i], color="0.15", lw=0.9)
        a2.axhline(0, color="0.6", lw=0.6)
        tag = "quiet: " if k < 3 else ""
        a1.set_title(f"{tag}{lab[i]}\nmax |diff| = {fmt_m(mx[i])} m", fontsize=9.5)
        a1.set_ylabel("water level (m, msl)", fontsize=8)
        a2.set_ylabel("nos-workflow - operational (m)", fontsize=8)
        a1.grid(alpha=0.3)
        a2.grid(alpha=0.3)
        a1.tick_params(labelbottom=False, labelsize=8)
        a2.tick_params(labelsize=8)
        tfmt(a2, None)
        if mx[i] < 1e-3:
            a2.ticklabel_format(axis="y", style="sci", scilimits=(-3, -3))
    h = [Line2D([], [], color=COL["ops"], lw=2.6, alpha=0.55, label=LAB["ops"]),
         Line2D([], [], color=COL["ours"], lw=1.1, label=LAB["ours"])]
    fig.legend(handles=h, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.925), fontsize=10, frameon=False)
    fig.suptitle(f"Station water level, 24 h nowcast, {cycle_title}", fontsize=13, y=0.975)
    save_png(fig, out)


def overlay(ax):
    import cartopy.feature as cf
    ax.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#e6f0f7", zorder=0)
    ax.add_feature(cf.LAND.with_scale("50m"), facecolor="0.85", zorder=1)
    ax.add_feature(cf.COASTLINE.with_scale("50m"), edgecolor="0.3", lw=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.5)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}


def fig2(ids, lon, lat, mx, short, out, cycle_title):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    fig = plt.figure(figsize=(15, 8))
    a1 = fig.add_axes([0.03, 0.08, 0.50, 0.80], projection=pc)
    a2 = fig.add_axes([0.54, 0.08, 0.37, 0.80], projection=pc)
    norm = LogNorm(vmin=FLOOR, vmax=1.0)
    sc = None
    for ax, ext, s in ((a1, [-98, -52, 7, 52], 34), (a2, [-76.5, -65.5, 38.5, 45.5], 70)):
        ax.set_extent(ext, crs=pc)
        overlay(ax)
        z = mx == 0
        ax.scatter(lon[z], lat[z], s=s, marker="s", facecolor="white", edgecolor="k", lw=1.0, zorder=5, transform=pc)
        o = np.argsort(mx)
        o = o[mx[o] > 0]
        sc = ax.scatter(lon[o], lat[o], c=np.clip(mx[o], FLOOR, None), s=s, cmap="viridis_r", norm=norm,
                        edgecolor="0.2", lw=0.3, zorder=6, transform=pc)
    a1.plot([-76.5, -65.5, -65.5, -76.5, -76.5], [38.5, 38.5, 45.5, 45.5, 38.5], color="crimson", lw=1.2,
            transform=pc, zorder=7)
    a1.set_title("All 166 stations", fontsize=11)
    a2.set_title("Northeast US (Delaware River to Gulf of Maine)", fontsize=11)
    for i in np.where(mx > 1e-2)[0]:
        if -76.5 < lon[i] < -65.5 and 38.5 < lat[i] < 45.5:
            a2.text(lon[i] + 0.12, lat[i] + 0.08, short[i].rsplit(" ", 1)[0], fontsize=7, zorder=8,
                    transform=pc, bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.8))
    cax = fig.add_axes([0.925, 0.12, 0.012, 0.72])
    cb = fig.colorbar(sc, cax=cax, extend="min")
    cb.set_label("max |nos-workflow - operational| over 24 h (m)", fontsize=10)
    h = [Line2D([], [], marker="s", ls="", mfc="white", mec="k", mew=1.0, ms=7,
                label=f"bit-identical for all 24 h ({int((mx == 0).sum())} stations)")]
    a1.legend(handles=h, loc="lower left", fontsize=8.5, framealpha=0.9)
    fig.suptitle(f"Station water level: largest difference between nos-workflow standalone and operational "
                 f"STOFS-3D-ATL, {cycle_title}", fontsize=12.5, y=0.96)
    save_png(fig, out)


def fig3(T, D, mx, dt0, out, cycle_title):
    A = np.abs(D)
    th = [dt0 + timedelta(seconds=float(t)) for t in T]
    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.985, top=0.88, bottom=0.08, hspace=0.32, wspace=0.18)
    a = fig.add_subplot(gs[0, 0])
    b = fig.add_subplot(gs[1, 0], sharex=a)
    c = fig.add_subplot(gs[:, 1])
    a.step(th, (A > 1e-3).sum(1), where="post", color="#E69F00", lw=1.5, label="> 1 mm")
    a.step(th, (A > 1e-2).sum(1), where="post", color="#CC3311", lw=1.5, label="> 1 cm")
    a.set_ylabel("stations with |nos-workflow - operational| above threshold\n(of 166)", fontsize=9)
    a.set_title("(a) Stations above 1 mm / 1 cm", fontsize=10.5, loc="left")
    a.legend(fontsize=9, loc="upper left")
    rms = np.sqrt((D ** 2).mean(1))
    b.semilogy(th[1:], np.maximum(rms[1:], 1e-9), color="0.15", lw=1.3)
    b.scatter([th[0]], [1e-9], marker="v", color="crimson", zorder=5, clip_on=False)
    b.annotate("first output (300 s):\nbit-identical at all 166\nstations (diff = 0)", (th[0], 1e-9), xytext=(8, 14),
               textcoords="offset points", fontsize=8.5, color="crimson")
    b.set_ylim(1e-9, 1)
    b.set_ylabel("RMS over 166 stations (m)", fontsize=9)
    b.set_title("(b) RMS difference over stations", fontsize=10.5, loc="left")
    for ax in (a, b):
        ax.grid(alpha=0.3, which="both")
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 3)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %Hz"))
        ax.tick_params(labelsize=8)
    a.tick_params(labelbottom=False)
    b.set_xlabel("time (UTC, 2026-09-30 / 10-01)", fontsize=9)
    o = np.sort(np.maximum(mx, FLOOR))[::-1]
    col = np.where(o > 1e-2, "#CC3311", np.where(o > 1e-3, "#E69F00", "#0072B2"))
    c.bar(np.arange(len(o)), o, width=1.0, color=col)
    c.set_yscale("log")
    c.set_ylim(FLOOR, 2)
    c.axhline(1e-3, color="0.4", ls="--", lw=0.8)
    c.axhline(1e-2, color="0.4", ls="--", lw=0.8)
    c.text(len(o) - 1, 1.15e-3, "1 mm", ha="right", fontsize=8)
    c.text(len(o) - 1, 1.15e-2, "1 cm", ha="right", fontsize=8)
    nz = int((mx == 0).sum())
    c.set_xlim(-1, len(o))
    c.set_xlabel("stations, sorted by max |diff|", fontsize=9)
    c.set_ylabel(f"max |nos-workflow - operational| over 24 h (m); exact zero ({nz} stations) drawn at {FLOOR:g}", fontsize=9)
    c.set_title(f"(c) Per-station maximum: {int((mx > 1e-2).sum())} above 1 cm, "
                f"{int((mx < 1e-3).sum())} below 1 mm", fontsize=10.5, loc="left")
    c.grid(alpha=0.3, which="both", axis="y")
    c.legend(handles=[Line2D([], [], color=x, lw=6, label=l) for x, l in
                      (("#CC3311", "> 1 cm"), ("#E69F00", "1 mm - 1 cm"), ("#0072B2", "< 1 mm"))],
             fontsize=9, loc="upper right", bbox_to_anchor=(1, 0.93))
    fig.suptitle(f"Divergence of the standalone nowcast from operational STOFS-3D-ATL, {cycle_title}",
                 fontsize=13, y=0.96)
    save_png(fig, out)


def fig4(ids, T, O, U, lab, dt0, out, cycle_title):
    ia, ib = ids.index(WELLS), ids.index(FORT_POINT)
    D = U - O
    ipk = int(np.argmax(np.abs(np.diff(O[:, ia])))) + 1          # largest output-to-output jump of ops itself
    lo, hi = max(ipk - 30, 0), min(ipk + 30, len(T))          # +-2.5 h
    th = np.array([dt0 + timedelta(seconds=float(t)) for t in T])
    fig, ax = plt.subplots(2, 2, figsize=(14, 7), sharex=True,
                           gridspec_kw=dict(height_ratios=[3, 1.3], hspace=0.12, wspace=0.18,
                                            left=0.07, right=0.985, top=0.76, bottom=0.09))
    for c, i in enumerate((ia, ib)):
        a, b = ax[0, c], ax[1, c]
        a.plot(th[lo:hi], O[lo:hi, i], "-o", color=COL["ops"], lw=2.2, ms=4, alpha=0.6)
        a.plot(th[lo:hi], U[lo:hi, i], "-o", color=COL["ours"], lw=1.0, ms=2.5)
        b.plot(th[lo:hi], D[lo:hi, i], "-o", color="0.15", lw=0.9, ms=2.5)
        b.axhline(0, color="0.6", lw=0.6)
        st = np.abs(np.diff(O[lo:hi, i])).max()
        a.set_title(f"{lab[i]}\nmax |diff| in window = {np.abs(D[lo:hi, i]).max():.2f} m; "
                    f"largest ops step between outputs = {st:.2f} m", fontsize=9.5)
        a.set_ylabel("water level (m, msl)", fontsize=9)
        b.set_ylabel("nos-workflow - operational (m)", fontsize=9)
        b.xaxis.set_major_formatter(mdates.DateFormatter("%d %H:%M"))
        b.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 20)))
        b.tick_params(labelsize=8, axis="x", rotation=30)
        a.grid(alpha=0.3)
        b.grid(alpha=0.3)
    h = [Line2D([], [], color=COL["ops"], lw=2.2, alpha=0.6, marker="o", label=LAB["ops"]),
         Line2D([], [], color=COL["ours"], lw=1.0, marker="o", ms=3, label=LAB["ours"])]
    fig.legend(handles=h, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.86), fontsize=10, frameon=False)
    fig.suptitle(f"Shallow wet/dry gauges near low tide, 5-min output, {cycle_title}\n"
                 "both runs jump by tens of cm between consecutive outputs when the gauge is nearly dry; "
                 "the differences between the runs appear in this regime", fontsize=11.5, y=0.985)
    save_png(fig, out)


def summary(path, ids, lab, lon, lat, T, D, mx):
    rms = np.sqrt((D ** 2).mean(0))
    eq = (D == 0).mean(0)
    A = np.abs(D)
    L = ["Station water level (staout_1): nos-workflow standalone nowcast minus operational STOFS-3D-ATL",
         "PDY 2026-10-01 12z, %d outputs (%.0f s each, %.1f h), %d stations; difference = nos-workflow - operational (m)"
         % (len(T), T[1] - T[0], len(T) * (T[1] - T[0]) / 3600, len(ids)), "",
         f"first output (t = {T[0]:.0f} s) bit-identical at all stations: {bool((D[0] == 0).all())}",
         f"stations with max|diff| == 0 over the window: {(mx == 0).sum()}",
         f"stations with max|diff| < 1e-6 m: {(mx < 1e-6).sum()}",
         f"stations with max|diff| < 1 mm: {(mx < 1e-3).sum()}",
         f"stations with max|diff| > 1 mm: {(mx > 1e-3).sum()}",
         f"stations with max|diff| > 1 cm: {(mx > 1e-2).sum()}",
         f"stations with max|diff| > 10 cm: {(mx > 1e-1).sum()}",
         f"global max |diff| = {mx.max():.4f} m at {lab[int(np.argmax(mx))]}",
         "first output time with any |diff| > 0: %s s" % (T[np.argmax((A > 0).any(1))] if (A > 0).any() else "none"),
         "", "%-4s %-9s %-42s %8s %8s %12s %12s %9s" % ("col", "ID", "name", "lon", "lat", "max|diff|", "RMS", "equal_frac"),
         ]
    for i in np.argsort(-mx):
        nm = re.sub(r"\s*\(\d+\)$", "", lab[i])
        L.append("%-4d %-9s %-42s %8.3f %8.3f %12.3e %12.3e %9.3f" % (i + 1, ids[i], nm[:42], lon[i], lat[i], mx[i],
                                                                     rms[i], eq[i]))
    open(path, "w").write("\n".join(L) + "\n")
    print("saved", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ops", required=True, help="operational staout_1")
    ap.add_argument("--nos-workflow", required=True, help="nos-workflow nowcast staout_1")
    ap.add_argument("--station-in", required=True, help="stofs_3d_atl_station.in")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--names-csv", default=None, help="stofs_3d_atl_staout_nc.csv (station names)")
    ap.add_argument("--start", default="2026093012", help="time of t = 0 of both runs, YYYYMMDDHH")
    ap.add_argument("--cycle", default="2026100112", help="cycle time YYYYMMDDHH (title only)")
    ap.add_argument("--ts-ids", default=None, help="comma list of 3 quiet station IDs for figure 1 (default: auto)")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    o = lambda n: os.path.join(args.outdir, n)
    ids, lon, lat, lab, short = load_stations(args.station_in, args.names_csv)
    T, O, U = load_common(args.ops, args.nos_workflow)
    assert O.shape[1] == len(ids)
    D = U - O
    mx = np.abs(D).max(0)
    dt0 = parse_dt(args.start)
    ct = parse_dt(args.cycle).strftime("PDY %Y-%m-%d %Hz")
    quiet = [ids.index(s) for s in args.ts_ids.split(",")] if args.ts_ids else pick_quiet(ids, lon, lat, mx)
    sel = quiet + [ids.index(s) for s in (WELLS, FORT_POINT, BOSTON)]
    TH = np.array([dt0 + timedelta(seconds=float(t)) for t in T])
    fig1(sel, TH, O, U, lab, mx, o("staout_wl_ts.png"), ct)
    fig2(ids, lon, lat, mx, short, o("staout_maxdiff_map.png"), ct)
    fig3(T, D, mx, dt0, o("staout_divergence.png"), ct)
    fig4(ids, T, O, U, lab, dt0, o("staout_wells_lowtide.png"), ct)
    summary(o("staout_summary.txt"), ids, lab, lon, lat, T, D, mx)


if __name__ == "__main__":
    main()
