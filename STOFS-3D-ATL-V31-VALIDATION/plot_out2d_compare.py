#!/usr/bin/env python3
"""
Full-domain SCHISM 2-D output (out2d) validation: nos-workflow STOFS-3D-ATL standalone nowcast (ops SCHISM
5.14 executable) vs the operational STOFS-3D-ATL v3.1, PDY 2026-10-01 12z.

usage: plot_out2d_compare.py --ops-files OPS_1.nc OPS_2.nc --nos-files NOS_1.nc NOS_2.nc --station-in STATION_IN
           --outdir DIR [--cache NPZ] [--cycle-title "PDY 2026-10-01 12z"]

OPS_*.nc       operational fields.out2d_n001_012.nc / fields.out2d_n013_024.nc (12 hourly records each)
NOS_*.nc       nos-workflow out2d_1.nc / out2d_2.nc (same layout); records are matched on absolute time
STATION_IN     stofs_3d_atl_station.in ("i lon lat z !ID"), used only to place the Wells / Fort Point time series
Memory: one variable / one record at a time (float32, running statistics); the per-node statistics are cached
in --cache (default OUTDIR/out2d_stats_cache.npz) so figures can be re-made without re-reading the 6.5 GB.

Comparison masks: the operational S3 files store -99999 in elevation at dry nodes while the nos-workflow files
store the SCHISM value, and the operational files also publish -99999 at every node with idmask == 1 (a fixed
set, dryFlag 0 or 1). Elevation is therefore compared only at nodes that have idmask == 0 and are wet
(dryFlagNode == 0) in BOTH runs at that record. "intermittently wet" = dryFlagNode changes during the 24 h in either run.

Figures (PNG, dpi 100, <= 1500 px):
  out2d_wl_maxdiff_map.png    per-node max |elevation diff| over 24 h (log colour): full domain + Northeast + Gulf
  out2d_wl_diff_stats.png     (a) CDF/histogram, (b) max|diff| vs depth, (c) nodes above thresholds per hour,
                              (d) attribution of nodes above 1 cm
  out2d_wl_ts.png             hourly elevation at 8 nodes, operational vs nos-workflow + difference
  out2d_dryflag_diff_map.png  records with different dryFlagNode, Northeast zoom, with the > 1 cm nodes
  out2d_wl_ts_<region>[_N].png  hourly elevation at the nearest wet node (depth > 1 m, idmask 0) to every station of
                              STATION_IN, grouped by region, <= 20 panels per figure (operational thick, nos-workflow thin)
  out2d_wl_ts_offshore.png    12 deep-ocean / shelf nodes
plus out2d_summary.txt. Station names come from --names-csv (stofs_3d_atl_staout_nc.csv) when given.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from PIL import Image

LAB = {"ops": "operational STOFS-3D-ATL", "ours": "nos-workflow (standalone, ops SCHISM 5.14)"}
COL = {"ops": "#0072B2", "ours": "#D55E00"}
FORCING = ["airPressure", "windSpeedX", "windSpeedY", "windStressX", "windStressY", "precipitationRate",
           "evaporationRate"]
TH = [1e-3, 1e-2, 1e-1]
FLOOR = 1e-6
NE = [-76.5, -65.5, 38.5, 45.5]
GULF = [-95.5, -87.0, 28.0, 31.0]


def save_png(fig, out):
    fig.savefig(out, dpi=100, metadata={"Software": None})
    plt.close(fig)
    im = Image.open(out)
    w, h = im.size
    assert max(w, h) <= 1500, f"{out}: {w}x{h} exceeds 1500 px"
    im.save(out, optimize=True)
    print(f"saved {out}  {w}x{h}")


def open_set(paths):
    """-> list of (Dataset, record index, absolute time seconds)"""
    recs = []
    for p in paths:
        d = nc.Dataset(p)
        d.set_auto_mask(False)
        for i, t in enumerate(d["time"][:]):
            recs.append((d, i, float(t)))
    return recs


def load_stations(path):
    ids, lon, lat = [], [], []
    with open(path) as f:
        f.readline()
        n = int(f.readline().split()[0])
        for _ in range(n):
            data, _, sid = f.readline().partition("!")
            p = data.split()
            lon.append(float(p[1]))
            lat.append(float(p[2]))
            ids.append(sid.strip())
    return ids, np.array(lon), np.array(lat)


def load_names(path, ids):
    names = {}
    if path:
        with open(path) as f:
            next(f)
            for line in f:
                t = line.rstrip("\n").split(";")[1].split()
                if len(t) >= 5:
                    names[t[2]] = f"{' '.join(t[4:])}, {t[3]}"
    return [names.get(i, i) for i in ids]


def region_of(lon, lat):
    if lon < -82.2 and lat > 24.0 and lat < 31.5:
        return "gulf"
    if lat < 22.5 or lon > -75.0 and lat < 22.5:
        return "caribbean"
    if lat < 22.5:
        return "caribbean"
    if lat < 31.0:
        return "florida"
    if lat < 36.0:
        return "southeast"
    if lat < 40.9 and lon > -76.2 or lat < 39.8:
        return "midatlantic"
    if lat < 40.9 or lon < -76.2:
        return "midatlantic"
    return "northeast"


OFFSHORE = [(-60.0, 30.0, 4000, 1e9), (-72.0, 26.0, 4000, 1e9), (-85.0, 25.0, 3000, 1e9), (-66.0, 17.0, 3500, 1e9),
            (-55.0, 42.0, 3000, 1e9), (-68.0, 38.0, 3000, 1e9), (-73.0, 39.0, 40, 80), (-86.5, 29.0, 40, 80),
            (-79.0, 31.5, 40, 80), (-69.0, 42.5, 100, 250), (-92.0, 28.0, 60, 120), (-65.5, 41.0, 100, 200)]


def compute_stations(ops_files, nos_files, station_in, names_csv, cache):
    O, U = open_set(ops_files), open_set(nos_files)
    io = {r[2]: r for r in O}
    iu = {r[2]: r for r in U}
    common = sorted(set(io) & set(iu))
    d0 = O[0][0]
    x, y = d0["SCHISM_hgrid_node_x"][:], d0["SCHISM_hgrid_node_y"][:]
    depth = d0["depth"][:]
    masked = d0["idmask"][:] != 0
    ids, slon, slat = load_stations(station_in)
    names = load_names(names_csv, ids)

    def near(lon, lat, lo, hi):
        d = np.hypot((x - lon) * np.cos(np.radians(lat)), y - lat)
        d[(depth < lo) | (depth > hi) | masked] = 1e9
        k = int(np.argmin(d))
        return k, float(d[k] * 111.0)
    nodes = [near(a, b, 1.0, 1e9) for a, b in zip(slon, slat)]
    off = [near(a, b, lo, hi) for a, b, lo, hi in OFFSHORE]
    idx = np.array([k for k, _ in nodes] + [k for k, _ in off])
    nt = len(common)
    eo = np.zeros((nt, len(idx)))
    eu = np.zeros((nt, len(idx)))
    do = np.zeros((nt, len(idx)))
    du = np.zeros((nt, len(idx)))
    for k, t in enumerate(common):
        a, i = io[t][0], io[t][1]
        b, j = iu[t][0], iu[t][1]
        eo[k] = a["elevation"][i][idx]
        eu[k] = b["elevation"][j][idx]
        do[k] = a["dryFlagNode"][i][idx]
        du[k] = b["dryFlagNode"][j][idx]
        print(f"  station pass record {k + 1}/{nt}", flush=True)
    np.savez_compressed(cache, idx=idx, nsta=len(ids), ids=np.array(ids), names=np.array(names), slon=slon, slat=slat,
                        dist_km=np.array([d for _, d in nodes] + [d for _, d in off]), ndepth=depth[idx],
                        nlon=x[idx], nlat=y[idx], common=np.array(common), eo=eo, eu=eu, do=do, du=du)


def ts_panels(T, idx_list, Q, titles, out, suptitle, ncol=5):
    n = len(idx_list)
    nrow = (n + ncol - 1) // ncol
    fig, axs = plt.subplots(nrow, ncol, figsize=(15, 3.0 * nrow + 1.0), squeeze=False)
    fig.subplots_adjust(left=0.05, right=0.99, top=1 - 1.0 / (3.0 * nrow + 1.0) * 1.0, bottom=0.05, hspace=0.62,
                        wspace=0.28)
    for ax in axs.ravel():
        ax.axis("off")
    for ax, k, ttl in zip(axs.ravel(), idx_list, titles):
        ax.axis("on")
        o = np.where(Q["do"][:, k] > 0.5, np.nan, Q["eo"][:, k])
        u = np.where(Q["du"][:, k] > 0.5, np.nan, Q["eu"][:, k])
        ax.plot(T, o, color=COL["ops"], lw=3.0, alpha=0.55)
        ax.plot(T, u, color=COL["ours"], lw=1.0)
        ax.set_title(ttl, fontsize=7.5)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=7)
        ax.set_xticks([0, 6, 12, 18, 24])
    for ax in axs[:, 0]:
        ax.set_ylabel("elevation (m)", fontsize=8)
    for ax in axs[-1]:
        ax.set_xlabel("nowcast hour", fontsize=8)
    h = [Line2D([], [], color=COL["ops"], lw=3.0, alpha=0.55, label=LAB["ops"]),
         Line2D([], [], color=COL["ours"], lw=1.0, label=LAB["ours"])]
    fig.legend(handles=h, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.985), fontsize=9.5, frameon=False)
    fig.suptitle(suptitle, fontsize=11.5, y=1.0, va="bottom")
    save_png(fig, out)


def fig_station_ts(Q, outdir, title):
    T = (Q["common"] - Q["common"][0]) / 3600.0 + 1
    n = int(Q["nsta"])
    d = Q["eu"] - Q["eo"]
    d[(Q["do"] > 0.5) | (Q["du"] > 0.5)] = np.nan
    mxs = np.nanmax(np.abs(d), axis=0)
    reg = [region_of(a, b) for a, b in zip(Q["slon"], Q["slat"])]
    RN = {"gulf": "Gulf of Mexico", "florida": "Florida", "southeast": "Southeast US", "midatlantic": "Mid-Atlantic",
          "northeast": "Northeast US / Gulf of Maine", "caribbean": "Puerto Rico / Caribbean"}
    lines = []
    for r in ("gulf", "florida", "southeast", "midatlantic", "northeast", "caribbean"):
        ks = [k for k in range(n) if reg[k] == r]
        ks.sort(key=lambda k: -Q["slon"][k] if r in ("gulf",) else Q["slat"][k])
        pages = [ks[i:i + 20] for i in range(0, len(ks), 20)]
        if len(pages) == 2 and len(pages[1]) < 6:
            pages = [ks[:len(ks) - len(pages[1])] + [], pages[1]]
        for pi, pg in enumerate(pages):
            ttls = [f"{Q['names'][k]} ({Q['ids'][k]})\nmax |diff| {mxs[k]:.2g} m, node depth {Q['ndepth'][k]:.1f} m"
                    for k in pg]
            suf = f"_{pi + 1}" if len(pages) > 1 else ""
            ts_panels(T, pg, Q, ttls, os.path.join(outdir, f"out2d_wl_ts_{r}{suf}.png"),
                      f"Hourly elevation (out2d) at the nearest wet node to each station, {RN[r]}"
                      f"{f' ({pi + 1}/{len(pages)})' if len(pages) > 1 else ''}, 24 h nowcast, {title}")
        lines.append(f"   {RN[r]}: {len(ks)} stations, > 1 cm: {int((mxs[ks] > 1e-2).sum())}, > 1 mm: "
                     f"{int((mxs[ks] > 1e-3).sum())}")
    offi = list(range(n, len(Q["idx"])))
    mo = np.nanmax(np.abs(d), axis=0)
    ttls = [f"{'deep' if Q['ndepth'][k] > 1000 else 'shelf'} node, depth {Q['ndepth'][k]:.0f} m\n"
            f"({Q['nlat'][k]:.1f}N, {abs(Q['nlon'][k]):.1f}W), max |diff| {mo[k]:.2g} m" for k in offi]
    ts_panels(T, offi, Q, ttls, os.path.join(outdir, "out2d_wl_ts_offshore.png"),
              f"Hourly elevation (out2d) at open-ocean and shelf nodes, 24 h nowcast, {title}", ncol=4)
    srt = np.argsort(-mxs[:n])
    L = ["", "6. STATION-NODE TIME SERIES (nearest wet node, depth > 1 m, idmask 0; hourly; dry hours excluded)",
         f"   stations {n}; max|diff| > 1 mm: {int((mxs[:n] > 1e-3).sum())}, > 1 cm: {int((mxs[:n] > 1e-2).sum())}, > 10 cm: "
         f"{int((mxs[:n] > 1e-1).sum())}; median over stations {np.nanmedian(mxs[:n]):.2g} m",
         f"   nearest-node distance to station: median {np.median(Q['dist_km'][:n]):.2f} km, max {Q['dist_km'][:n].max():.2f} km",
         f"   offshore nodes: max|diff| {np.nanmax(mo[n:]):.2g} m over {len(offi)} nodes"] + lines + ["   largest 15:"]
    for k in srt[:15]:
        L.append(f"     {Q['ids'][k]} {Q['names'][k]}: max|diff| {mxs[k]:.3g} m, node depth {Q['ndepth'][k]:.1f} m")
    return L


def pick_nodes(x, y, depth, ids, slon, slat):
    """8 nodes: 2 deep ocean, 2 shelf, 2 estuarine, Wells ME, Fort Point NH (nearest node with depth > 0.5 m)."""
    def near(lon, lat, lo, hi):
        d = np.hypot((x - lon) * np.cos(np.radians(lat)), y - lat)
        d[(depth < lo) | (depth > hi)] = 1e9
        return int(np.argmin(d))
    sel = [("deep open ocean", near(-60.0, 30.0, 4000, 1e9)), ("deep open ocean", near(-72.0, 26.0, 4000, 1e9)),
           ("shelf", near(-73.0, 39.0, 40, 80)), ("shelf", near(-86.5, 29.0, 40, 80)),
           ("estuary: Chesapeake Bay", near(-76.2, 37.8, 5, 30)), ("estuary: Delaware Bay", near(-75.45, 39.15, 3, 15))]
    for sid, nm in (("8419317", "Wells ME"), ("8423898", "Fort Point NH")):
        k = ids.index(sid)
        sel.append((f"nearest wet node to {nm} ({sid})", near(slon[k], slat[k], 0.5, 1e9)))
    return sel


# ------------------------------------------------------------------ pass 1
def compute(ops_files, nos_files, station_in, cache):
    O, U = open_set(ops_files), open_set(nos_files)
    to, tu = [r[2] for r in O], [r[2] for r in U]
    common = sorted(set(to) & set(tu))
    print(f"records: ops {len(to)}, nos-workflow {len(tu)}, matched {len(common)}")
    io = {t: r for r, t in zip(O, to)}
    iu = {t: r for r, t in zip(U, tu)}
    d0 = O[0][0]
    x, y = d0["SCHISM_hgrid_node_x"][:], d0["SCHISM_hgrid_node_y"][:]
    depth = d0["depth"][:].astype(np.float32)
    dd = float(np.abs(depth - U[0][0]["depth"][:]).max())
    n = len(x)
    masked = d0["idmask"][:] != 0          # nodes the operational product publishes as -99999 (idmask == 1)
    ids, slon, slat = load_stations(station_in)
    sel = pick_nodes(x, y, depth, ids, slon, slat)
    sel_idx = [s[1] for s in sel]

    nt = len(common)
    mx_wet = np.full(n, -1.0, np.float32)           # max |diff| over records wet in both (-1 = never wet in both)
    mx_all = np.zeros(n, np.float32)                # raw max |diff| over all records, incl. nodes dry in either
    nwet_both = np.zeros(n, np.int16)
    ndiffdry = np.zeros(n, np.int16)                # records with dryFlagNode different
    dry_o = np.zeros(n, np.int16)
    dry_u = np.zeros(n, np.int16)
    cnt_wet = np.zeros((3, nt), np.int64)
    cnt_all = np.zeros((3, nt), np.int64)
    nwet_rec = np.zeros(nt, np.int64)
    ndiff_rec = np.zeros(nt, np.int64)
    forc = {v: np.zeros(nt) for v in FORCING}
    forc_n = {v: np.zeros(nt, np.int64) for v in FORCING}
    ts_o = np.full((nt, len(sel_idx)), np.nan)
    ts_u = np.full((nt, len(sel_idx)), np.nan)
    ts_dry_o = np.zeros((nt, len(sel_idx)))
    ts_dry_u = np.zeros((nt, len(sel_idx)))
    for k, t in enumerate(common):
        do, i = io[t][0], io[t][1]
        du, j = iu[t][0], iu[t][1]
        fo = do["dryFlagNode"][i] > 0.5
        fu = du["dryFlagNode"][j] > 0.5
        eo = do["elevation"][i]
        eu = du["elevation"][j]
        ts_o[k], ts_u[k] = eo[sel_idx], eu[sel_idx]
        ts_dry_o[k], ts_dry_u[k] = fo[sel_idx], fu[sel_idx]
        wb = ~fo & ~fu & ~masked
        assert (eo[masked] < -9000).all()
        ad = np.abs(eu.astype(np.float32) - eo.astype(np.float32))
        ad_w = np.where(wb, ad, np.float32(-1))
        np.maximum(mx_wet, ad_w, out=mx_wet)
        np.maximum(mx_all, np.where(np.isfinite(ad), ad, 0), out=mx_all)
        nwet_both += wb
        ndiffdry += fo != fu
        dry_o += fo
        dry_u += fu
        nwet_rec[k] = wb.sum()
        ndiff_rec[k] = (fo != fu).sum()
        for q, th in enumerate(TH):
            cnt_wet[q, k] = (ad_w > th).sum()
            cnt_all[q, k] = (ad > th).sum()
        del eo, eu, ad, ad_w, fo, fu, wb
        for v in FORCING:
            a = do[v][i]
            b = du[v][j]
            df = np.abs(b.astype(np.float64) - a.astype(np.float64))
            forc[v][k] = df.max()
            forc_n[v][k] = (df > 0).sum()
            del a, b, df
        print(f"  record {k + 1}/{nt} t={t:.0f} s done", flush=True)
    # one-ring neighbours of intermittently wet nodes / nodes with differing dryFlag
    inter = ((dry_o > 0) & (dry_o < nt)) | ((dry_u > 0) & (dry_u < nt))
    flag = inter | (ndiffdry > 0)
    fn = d0["SCHISM_hgrid_face_nodes"][:]
    valid = fn > 0
    fnz = np.where(valid, fn - 1, 0)
    fl = (flag[fnz] & valid).any(axis=1)
    ring = np.zeros(n, bool)
    ring[fnz[fl][valid[fl]]] = True
    del fn, valid, fnz, fl
    np.savez_compressed(cache, x=x, y=y, depth=depth, mx_wet=mx_wet, mx_all=mx_all, nwet_both=nwet_both,
                        ndiffdry=ndiffdry, dry_o=dry_o, dry_u=dry_u, cnt_wet=cnt_wet, cnt_all=cnt_all,
                        nwet_rec=nwet_rec, ndiff_rec=ndiff_rec, common=np.array(common), ring=ring,
                        ts_o=ts_o, ts_u=ts_u, masked=masked, ts_dry_o=ts_dry_o, ts_dry_u=ts_dry_u, sel_idx=np.array(sel_idx),
                        sel_lab=np.array([s[0] for s in sel]), depth_maxdiff=dd,
                        forc_names=np.array(FORCING), forc_max=np.array([forc[v] for v in FORCING]),
                        forc_n=np.array([forc_n[v] for v in FORCING]))


# ------------------------------------------------------------------ figures
def overlay(ax):
    import cartopy.feature as cf
    ax.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#e6f0f7", zorder=0)
    ax.add_feature(cf.LAND.with_scale("50m"), facecolor="0.85", zorder=1)
    ax.add_feature(cf.COASTLINE.with_scale("50m"), edgecolor="0.3", lw=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.5)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}


def inbox(x, y, ext, pad=0.0):
    return (x > ext[0] - pad) & (x < ext[1] + pad) & (y > ext[2] - pad) & (y < ext[3] + pad)


def fig_map(S, out, title):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    x, y, mx = S["x"], S["y"], S["mx_wet"]
    fig = plt.figure(figsize=(15, 9.4))
    a1 = fig.add_axes([0.03, 0.40, 0.50, 0.50], projection=pc)
    a2 = fig.add_axes([0.54, 0.40, 0.37, 0.50], projection=pc)
    a3 = fig.add_axes([0.03, 0.04, 0.50, 0.30], projection=pc)
    a4 = fig.add_axes([0.54, 0.04, 0.37, 0.30])
    norm = LogNorm(vmin=FLOOR, vmax=1.0)
    ident = mx == 0
    pos = mx > 0
    sc = None
    for ax, ext, s in ((a1, [-98, -52, 7, 52], 0.25), (a2, NE, 0.8), (a3, GULF, 0.8)):
        ax.set_extent(ext, crs=pc)
        overlay(ax)
        m = inbox(x, y, ext)
        ax.scatter(x[m & ident], y[m & ident], s=s, c="0.45", marker=".", lw=0, zorder=3, transform=pc,
                   rasterized=True)
        mm = m & pos
        o = np.argsort(mx[mm])
        sc = ax.scatter(x[mm][o], y[mm][o], c=np.clip(mx[mm][o], FLOOR, None), s=s * 1.5, cmap="plasma_r",
                        norm=norm, lw=0, zorder=4, transform=pc, rasterized=True)
    for ext, c in ((NE, "crimson"), (GULF, "crimson")):
        a1.plot([ext[0], ext[1], ext[1], ext[0], ext[0]], [ext[2], ext[2], ext[3], ext[3], ext[2]], color=c, lw=1.1,
                transform=pc, zorder=7)
    a1.set_title("Full domain", fontsize=11)
    a2.set_title("Northeast US (Delaware to Gulf of Maine)", fontsize=11)
    a3.set_title("Northern Gulf of Mexico (Louisiana / Texas coast)", fontsize=11)
    # share panel
    w = mx >= 0
    tot = int(w.sum())
    nid = int((mx == 0).sum())
    bins = [(0, "bit-identical (0)"), (1e-3, "0 < diff <= 1 mm"), (1e-2, "1 mm - 1 cm"), (1e-1, "1 cm - 10 cm"),
            (np.inf, "> 10 cm")]
    cnt = [nid]
    lo = 0
    for hi, _ in bins[1:]:
        cnt.append(int(((mx > lo) & (mx <= hi)).sum()) if lo > 0 or hi != 1e-3 else int(((mx > 0) & (mx <= hi)).sum()))
        lo = hi
    a4.barh(range(len(cnt)), np.array(cnt) / tot * 100, color=["0.45", "#FDE0A3", "#F59E5B", "#D1495B", "#7A1F5C"])
    a4.set_yticks(range(len(cnt)))
    a4.set_yticklabels([b[1] for b in bins], fontsize=9)
    a4.invert_yaxis()
    a4.set_xscale("symlog", linthresh=0.01)
    a4.set_xlim(0, 100)
    for i, c in enumerate(cnt):
        a4.text(max(c / tot * 100, 0.002) * 1.15 + 0.002, i, f"{c:,} ({c / tot * 100:.3g}%)", va="center", fontsize=8.5)
    a4.set_xlabel("share of nodes wet in both runs at some record (%)", fontsize=9)
    a4.set_title(f"Per-node max |diff| over 24 h ({tot:,} nodes compared)", fontsize=11)
    a4.grid(alpha=0.3, axis="x")
    cax = fig.add_axes([0.925, 0.42, 0.012, 0.46])
    cb = fig.colorbar(sc, cax=cax, extend="min")
    cb.set_label("max |nos-workflow - operational| elevation over 24 h (m)", fontsize=9.5)
    a1.legend(handles=[Line2D([], [], marker=".", ls="", color="0.45", ms=8, label="bit-identical at every wet record")],
              loc="lower left", fontsize=8.5, framealpha=0.9)
    fig.suptitle(f"Elevation (out2d): largest difference between nos-workflow standalone and operational "
                 f"STOFS-3D-ATL, {title}\n(nodes wet in both runs; hourly records)", fontsize=12.5, y=0.985)
    save_png(fig, out)


def attribution(S, thr):
    mx = S["mx_wet"]
    dd = S["ndiffdry"] > 0
    nt = len(S["common"])
    inter = ((S["dry_o"] > 0) & (S["dry_o"] < nt)) | ((S["dry_u"] > 0) & (S["dry_u"] < nt))
    ring = S["ring"]
    m = mx > thr
    a = m & dd
    b = m & ~dd & inter
    c = m & ~dd & ~inter & ring
    d = m & ~dd & ~inter & ~ring
    return [int(a.sum()), int(b.sum()), int(c.sum()), int(d.sum())], int(m.sum())


def near_stats(S, thr, radii=(1.0, 5.0)):
    """share of nodes with max|diff| > thr within each radius (km) of an intermittently wet / dryFlag-differing node;
    also the same share for a 1-in-20 sample of all compared nodes (baseline). Returns (shares, baseline shares, n)."""
    from scipy.spatial import cKDTree
    nt = len(S["common"])
    inter = ((S["dry_o"] > 0) & (S["dry_o"] < nt)) | ((S["dry_u"] > 0) & (S["dry_u"] < nt))
    flag = inter | (S["ndiffdry"] > 0)
    P = np.c_[S["x"] * np.cos(np.radians(S["y"])) * 111.0, S["y"] * 111.0]
    tree = cKDTree(P[flag])
    mx = S["mx_wet"]
    d, _ = tree.query(P[mx > thr])
    base = np.where(mx >= 0)[0][::20]
    db, _ = tree.query(P[base])
    return ([float((d < r).mean()) for r in radii], [float((db < r).mean()) for r in radii], int((mx > thr).sum()))


def fig_stats(S, out, title):
    mx, depth = S["mx_wet"], S["depth"]
    w = mx >= 0
    v = mx[w]
    fig = plt.figure(figsize=(15, 9.6))
    gs = fig.add_gridspec(2, 2, left=0.065, right=0.985, top=0.89, bottom=0.07, hspace=0.30, wspace=0.30)
    a = fig.add_subplot(gs[0, 0])
    nz = v[v > 0]
    edges = np.logspace(-8, 1, 91)
    a.hist(np.clip(nz, 1e-8, None), bins=edges, color="#56B4E9", alpha=0.85)
    a.set_xscale("log")
    a.set_yscale("log")
    a.set_xlabel("per-node max |nos-workflow - operational| over 24 h (m)", fontsize=9)
    a.set_ylabel("nodes", fontsize=9)
    a2 = a.twinx()
    xs = np.sort(v)
    cdf = np.arange(1, len(xs) + 1) / len(xs) * 100
    xp = np.maximum(xs, 1e-9)
    sub = np.unique(np.linspace(0, len(xs) - 1, 4000).astype(int))
    a2.plot(xp[sub], cdf[sub], color="0.15", lw=1.4)
    a2.set_ylim(0, 100)
    a2.set_ylabel("cumulative share of nodes (%)", fontsize=9)
    for th, lb in zip(TH, ("1 mm", "1 cm", "10 cm")):
        a.axvline(th, color="crimson", lw=0.8, ls="--")
        a.text(th, 0.03, lb, color="crimson", fontsize=8, rotation=90, va="bottom", ha="right",
               transform=a.get_xaxis_transform())
    a.set_title(f"(a) Distribution; {int((v == 0).sum()):,} nodes ({(v == 0).mean() * 100:.2f}%) bit-identical "
                f"(not drawn)", fontsize=10, loc="left")
    a.grid(alpha=0.3, which="both")

    b = fig.add_subplot(gs[0, 1])
    sd = np.sign(depth[w]) * np.log10(1 + np.abs(depth[w]))
    ly = np.log10(np.maximum(v, 1e-9))
    h = b.hist2d(sd, ly, bins=[140, 90], range=[[-1.8, 4.2], [-9, 3]], norm=LogNorm(), cmap="viridis")
    tk = [-10, -1, 0, 1, 10, 100, 1000, 5000]
    b.set_xticks([np.sign(t) * np.log10(1 + abs(t)) for t in tk])
    b.set_xticklabels([str(t) for t in tk], fontsize=8)
    b.set_yticks(range(-9, 4, 1))
    b.set_yticklabels([f"1e{k}" if k > -9 else "0 / <=1e-9" for k in range(-9, 4)], fontsize=8)
    b.set_xlabel("node depth (m; negative = above datum / land side, symlog)", fontsize=9)
    b.set_ylabel("per-node max |diff| (m)", fontsize=9)
    for th in TH:
        b.axhline(np.log10(th), color="w", lw=0.6, ls="--")
    fig.colorbar(h[3], ax=b, pad=0.01).set_label("nodes", fontsize=9)
    b.set_title("(b) Max |diff| vs node depth", fontsize=10, loc="left")

    c = fig.add_subplot(gs[1, 0])
    hrs = (S["common"] - S["common"][0]) / 3600.0 + 1
    for q, (lb, col) in enumerate((("> 1 mm", "#E69F00"), ("> 1 cm", "#CC3311"), ("> 10 cm", "#7A1F5C"))):
        c.step(hrs, S["cnt_wet"][q], where="mid", color=col, lw=1.6, label=lb)
    c.set_yscale("log")
    c.set_xlabel("hours since 2026-09-30 12z (nowcast hour)", fontsize=9)
    c.set_ylabel("nodes with |diff| above threshold", fontsize=9)
    c.legend(fontsize=9, loc="lower right")
    c.grid(alpha=0.3, which="both")
    c.set_title(f"(c) Nodes above threshold per hourly record (of ~{int(S['nwet_rec'].mean()):,} wet in both)",
                fontsize=10, loc="left")

    d = fig.add_subplot(gs[1, 1])
    labs = ["dryFlagNode differs\nbetween runs (some record)", "intermittently wet in either run\n(dryFlag identical)",
            "1-ring neighbour of such a node\n(otherwise always wet)", "none of these"]
    cols = ["#CC3311", "#E69F00", "#F2D16B", "0.55"]
    wid = 0.38
    rows = ((1e-3, "> 1 mm"), (1e-2, "> 1 cm"), (1e-1, "> 10 cm"))
    for k, (thr, lb) in enumerate(rows):
        cnt, tot = attribution(S, thr)
        ns, bs, _ = near_stats(S, thr)
        y0 = 2 - k
        left = 0
        for q in range(4):
            sh = cnt[q] / max(tot, 1) * 100
            d.barh(y0, sh, left=left, height=0.7, color=cols[q], edgecolor="w", label=labs[q] if k == 0 else None)
            if sh > 4:
                d.text(left + sh / 2, y0, f"{sh:.0f}%\n({cnt[q]:,})", ha="center", va="center", fontsize=8.5)
            left += sh
        d.text(101, y0, f"n={tot:,}\n{ns[1] * 100:.0f}% within 5 km of a\nwet/dry-changing node", va="center", fontsize=8)
    d.set_yticks([2, 1, 0])
    d.set_yticklabels(["max|diff| > 1 mm", "max|diff| > 1 cm", "max|diff| > 10 cm"], fontsize=9)
    d.set_xlim(0, 140)
    d.set_xlabel("share of nodes (%)", fontsize=9)
    d.set_ylim(-0.6, 2.6)
    d.legend(fontsize=8, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.42), frameon=False)
    d.set_title("(d) Attribution of the nodes above threshold", fontsize=10, loc="left")
    fig.suptitle(f"Elevation (out2d) difference statistics, nos-workflow standalone minus operational STOFS-3D-ATL, "
                 f"{title}", fontsize=12.5, y=0.975)
    save_png(fig, out)


def fig_ts(S, out, title):
    th = (S["common"] - S["common"][0]) / 3600.0 + 1
    sel = S["sel_idx"]
    labs = S["sel_lab"]
    fig = plt.figure(figsize=(15, 9.8))
    gs = fig.add_gridspec(4, 4, height_ratios=[3, 1.3, 3, 1.3], hspace=0.6, wspace=0.34, left=0.055, right=0.99,
                          top=0.85, bottom=0.06)
    for k in range(len(sel)):
        r, c = divmod(k, 4)
        a1 = fig.add_subplot(gs[2 * r, c])
        a2 = fig.add_subplot(gs[2 * r + 1, c], sharex=a1)
        o = np.where(S["ts_dry_o"][:, k] > 0.5, np.nan, S["ts_o"][:, k])
        u = np.where(S["ts_dry_u"][:, k] > 0.5, np.nan, S["ts_u"][:, k])
        a1.plot(th, o, color=COL["ops"], lw=2.8, alpha=0.55, marker="o", ms=3)
        a1.plot(th, u, color=COL["ours"], lw=1.1, marker="o", ms=2)
        df = u - o
        a2.plot(th, df, color="0.15", lw=0.9, marker=".", ms=3)
        a2.axhline(0, color="0.6", lw=0.6)
        nd = int(((S["ts_dry_o"][:, k] > 0.5) | (S["ts_dry_u"][:, k] > 0.5)).sum())
        mxk = np.nanmax(np.abs(df)) if np.isfinite(df).any() else np.nan
        a1.set_title(f"{labs[k]}\ndepth {S['depth'][sel[k]]:.1f} m, max |diff| {mxk:.2g} m"
                     + (f", dry {nd} h" if nd else ""), fontsize=8.5)
        a1.set_ylabel("elevation (m)", fontsize=8)
        a2.set_ylabel("nos-workflow -\noperational (m)", fontsize=7.5)
        a2.set_xlabel("nowcast hour", fontsize=8)
        a1.grid(alpha=0.3)
        a2.grid(alpha=0.3)
        a1.tick_params(labelbottom=False, labelsize=8)
        a2.tick_params(labelsize=8)
        if mxk < 1e-3:
            a2.ticklabel_format(axis="y", style="sci", scilimits=(-3, -3))
    h = [Line2D([], [], color=COL["ops"], lw=2.8, alpha=0.55, label=LAB["ops"]),
         Line2D([], [], color=COL["ours"], lw=1.1, label=LAB["ours"])]
    fig.legend(handles=h, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.915), fontsize=10, frameon=False)
    fig.suptitle(f"Hourly elevation (out2d), 24 h nowcast, {title}", fontsize=13, y=0.975)
    save_png(fig, out)


def fig_dry(S, out, title):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    x, y, mx, nd = S["x"], S["y"], S["mx_wet"], S["ndiffdry"]
    fig = plt.figure(figsize=(13, 8.6))
    ax = fig.add_axes([0.05, 0.06, 0.80, 0.84], projection=pc)
    ax.set_extent(NE, crs=pc)
    overlay(ax)
    m = inbox(x, y, NE) & (nd > 0)
    o = np.argsort(nd[m])
    sc = ax.scatter(x[m][o], y[m][o], c=nd[m][o], s=14, cmap="YlOrRd_r", vmin=1, vmax=max(int(nd.max()), 2), lw=0,
                    zorder=4, transform=pc, rasterized=True)
    b = inbox(x, y, NE) & (mx > 1e-2)
    ax.scatter(x[b], y[b], s=2.5, color="#0072B2", lw=0, zorder=6, transform=pc, rasterized=True)
    cax = fig.add_axes([0.88, 0.2, 0.014, 0.6])
    fig.colorbar(sc, cax=cax).set_label("hourly records (of 24) with different dryFlagNode", fontsize=10)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color="#0072B2", ms=5,
                              label="max |elevation diff| > 1 cm (wet in both)")], loc="lower left", fontsize=9)
    ax.set_title(f"Nodes whose wet/dry state differs between nos-workflow standalone and operational STOFS-3D-ATL, "
                 f"Northeast US\n{title}; {int((nd > 0).sum()):,} nodes differ in the full domain", fontsize=11)
    save_png(fig, out)


# ------------------------------------------------------------------ summary
def summary(S, out, title):
    mx, mxa, depth = S["mx_wet"], S["mx_all"], S["depth"]
    nt = len(S["common"])
    w = mx >= 0
    v = mx[w]
    L = [f"out2d comparison, nos-workflow (standalone, ops SCHISM 5.14) minus operational STOFS-3D-ATL, {title}",
         f"records matched on absolute time: {nt} hourly (t = {S['common'][0]:.0f}..{S['common'][-1]:.0f} s since "
         f"2026-09-30 12:00)",
         f"node depth max |diff| between files: {float(S['depth_maxdiff']):.3g} m (grids identical)",
         f"nodes with idmask == 1 (published as -99999 in the operational files, excluded): {int(S['masked'].sum()):,}", "",
         "1. FORCING AS SEEN BY SCHISM (max |diff| over all nodes and records; nodes with diff > 0)"]
    for k, nm in enumerate(S["forc_names"]):
        L.append(f"   {nm:18s} max |diff| = {S['forc_max'][k].max():.6g}   max nodes differing in a record = "
                 f"{int(S['forc_n'][k].max()):,} (records with any diff: {int((S['forc_n'][k] > 0).sum())}/{nt})")
    L += ["", "2. ELEVATION (compared only where idmask == 0 and dryFlagNode == 0 in BOTH runs at that record; ops S3 files store "
              "-99999 at dry nodes and at idmask == 1 nodes)",
          f"   nodes total {len(mx):,}; wet in both at >= 1 record {int(w.sum()):,}; never wet in both "
          f"{int((~w).sum()):,}",
          f"   bit-identical over all wet-in-both records: {int((v == 0).sum()):,} ({(v == 0).mean() * 100:.3f}%)",
          f"   max |diff| > 0   : {int((v > 0).sum()):,} ({(v > 0).mean() * 100:.3f}%)"]
    for th, lb in zip(TH, ("1 mm", "1 cm", "10 cm")):
        L.append(f"   max |diff| > {lb:5s}: {int((v > th).sum()):,} ({(v > th).mean() * 100:.4f}%)")
    L.append(f"   max |diff| over everything: {float(v.max()):.4f} m; percentiles of per-node max (50/90/99/99.9): "
             + " / ".join(f"{np.percentile(v, p):.3g}" for p in (50, 90, 99, 99.9)) + " m")
    L.append(f"   raw (unmasked) max |diff| incl. dry-in-one-run nodes: {float(mxa.max()):.4g} (not meaningful: ops "
             f"dry = -99999)")
    L.append("   per-hour nodes above threshold (1 mm / 1 cm / 10 cm), wet in both:")
    for k in range(nt):
        L.append(f"     hour {k + 1:2d}: {S['cnt_wet'][0][k]:>8,} {S['cnt_wet'][1][k]:>8,} {S['cnt_wet'][2][k]:>8,}"
                 f"   (wet in both {S['nwet_rec'][k]:,}; dryFlag differs at {S['ndiff_rec'][k]:,} nodes)")
    L += ["", "3. ATTRIBUTION of nodes above threshold (mutually exclusive, in this order)"]
    for thr, lb in ((1e-3, "1 mm"), (1e-2, "1 cm"), (1e-1, "10 cm")):
        cnt, tot = attribution(S, thr)
        pc = [c / max(tot, 1) * 100 for c in cnt]
        L.append(f"   > {lb}: n = {tot:,}: dryFlagNode differs {cnt[0]:,} ({pc[0]:.1f}%); intermittently wet "
                 f"(dryFlag same) {cnt[1]:,} ({pc[1]:.1f}%); 1-ring neighbour of those {cnt[2]:,} ({pc[2]:.1f}%); "
                 f"none {cnt[3]:,} ({pc[3]:.1f}%)")
    cnt, tot = attribution(S, 1e-2)
    L.append(f"   > 1 cm: neither (i) nor (ii) = {cnt[2] + cnt[3]:,} ({(cnt[2] + cnt[3]) / max(tot, 1) * 100:.1f}%); "
             f"of which within one element of an intermittent/differing node {cnt[2]:,}")
    for thr, lb in ((1e-3, "1 mm"), (1e-2, "1 cm"), (1e-1, "10 cm")):
        ns, bs, _ = near_stats(S, thr)
        L.append(f"   distance to nearest intermittent/differing-dryFlag node, nodes > {lb}: within 1 km {ns[0] * 100:.1f}%, "
                 f"within 5 km {ns[1] * 100:.1f}%  (baseline, all compared nodes: {bs[0] * 100:.1f}% / {bs[1] * 100:.1f}%)")
    nt_ = nt
    inter = ((S["dry_o"] > 0) & (S["dry_o"] < nt_)) | ((S["dry_u"] > 0) & (S["dry_u"] < nt_))
    L.append(f"   context: intermittently wet nodes in either run {int(inter.sum()):,}; nodes with differing dryFlag "
             f"{int((S['ndiffdry'] > 0).sum()):,} (max records {int(S['ndiffdry'].max())}); 1-ring set {int(S['ring'].sum()):,}")
    for nm, msk in (("intermittent", inter), ("not intermittent", ~inter & w)):
        vv = mx[msk & w]
        L.append(f"   max|diff| for {nm} nodes (n={len(vv):,}): bit-identical {(vv == 0).mean() * 100:.2f}%, "
                 f"> 1 cm {(vv > 1e-2).mean() * 100:.3f}%, median {np.median(vv):.3g} m")
    L += ["", "4. DEPTH STATISTICS (per-node max |diff|, nodes wet in both)"]
    for lo, hi, lb in ((-1e9, 0, "depth <= 0 (above datum)"), (0, 5, "0-5 m"), (5, 20, "5-20 m"),
                       (20, 200, "20-200 m (shelf)"), (200, 1000, "200-1000 m"), (1000, 1e9, "> 1000 m (deep)")):
        m = w & (depth > lo) & (depth <= hi)
        vv = mx[m]
        if len(vv):
            L.append(f"   {lb:28s} n={len(vv):>9,}  bit-identical {(vv == 0).mean() * 100:6.2f}%  >1mm "
                     f"{(vv > 1e-3).mean() * 100:7.3f}%  >1cm {(vv > 1e-2).mean() * 100:7.4f}%  max {vv.max():.3g} m")
    L += ["", "5. TIME-SERIES NODES"]
    for k in range(len(S["sel_idx"])):
        d_o = np.where(S["ts_dry_o"][:, k] > 0.5, np.nan, S["ts_o"][:, k])
        d_u = np.where(S["ts_dry_u"][:, k] > 0.5, np.nan, S["ts_u"][:, k])
        L.append(f"   {S['sel_lab'][k]}: node {int(S['sel_idx'][k]) + 1} depth {S['depth'][S['sel_idx'][k]]:.1f} m "
                 f"max|diff| {np.nanmax(np.abs(d_u - d_o)):.3g} m")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ops-files", nargs="+", required=True)
    ap.add_argument("--nos-files", nargs="+", required=True)
    ap.add_argument("--station-in", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--names-csv", default=None)
    ap.add_argument("--cycle-title", default="PDY 2026-10-01 12z")
    ap.add_argument("--recompute", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    cache = a.cache or os.path.join(a.outdir, "out2d_stats_cache.npz")
    if a.recompute or not os.path.exists(cache):
        compute(a.ops_files, a.nos_files, a.station_in, cache)
    S = dict(np.load(cache))
    o = lambda n: os.path.join(a.outdir, n)
    fig_map(S, o("out2d_wl_maxdiff_map.png"), a.cycle_title)
    fig_stats(S, o("out2d_wl_diff_stats.png"), a.cycle_title)
    fig_ts(S, o("out2d_wl_ts.png"), a.cycle_title)
    fig_dry(S, o("out2d_dryflag_diff_map.png"), a.cycle_title)
    scache = os.path.join(a.outdir, "out2d_station_cache.npz")
    if a.recompute or not os.path.exists(scache):
        compute_stations(a.ops_files, a.nos_files, a.station_in, a.names_csv, scache)
    extra = fig_station_ts(dict(np.load(scache)), a.outdir, a.cycle_title)
    summary(S, o("out2d_summary.txt"), a.cycle_title)
    with open(o("out2d_summary.txt"), "a") as f:
        f.write("\n".join(extra) + "\n")


if __name__ == "__main__":
    main()
