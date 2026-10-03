#!/usr/bin/env python3
"""
Dynamic SSH bias adjustment validation figures: operational STOFS-3D-ATL v3.1 vs nos-workflow before
and after the fix (nos-utils PR #63).

usage: plot_dynadj_compare.py --dir VIZ_DIR --fix-dir OPS_FIX_DIR --nodes-csv obc_nodes.csv
           [--outdir DIR] [--cycle 2026100112] [--lats 10,22,34,46]
           [--pr-src PATH_TO_nos-utils] [--only 1,2,3]

VIZ_DIR holds
  ops/stofs_3d_atl.t<CC>z.elev2dth.nc          adjusted elev2D, hourly, from the nowcast start
  ops/stofs_3d_atl.t<CC>z.elev2dth_non_adj.nc  non-adjusted elev2D, 6-hourly
  ops/stofs_3d_atl.t<CC>z.avg_bias             today's operational bias (adj1)
  {before,after}/{now,fcst}/elev2D.th.nc       nos-workflow elev2D, nowcast file + forecast file
  obs/<id>.xml                                 NOAA gauge water levels (space-separated text, NAVD88)
  seed/staout_1, seed/*.param.nml, seed/*.avg_bias   previous-cycle model run and its bias (adj0)
OPS_FIX_DIR holds stofs_3d_atl_station.in, stofs_3d_atl_obc_adjust_station.bp and
stofs_3d_atl_obc_adjust_msl_geoid.bp (per-gauge datum offset in column 4).

Ops algorithm (stofs_3d_atl_create_obc_3d_th_dynamic_adjust.sh + derive_bias.py): today's bias adj1 is the
mean over the 11 bias gauges of (previous-cycle staout_1 - (observed NAVD88 + datum offset)) over
PDY-2 12:00 .. PDY 12:00, hourly-averaged, gauges with > 20 % NaN hours dropped, rounded to 3 decimals.
elev2D (hourly) = non-adjusted - adj0 at hour 0, - (adj0 + adj1) / 2 at hour 1, - adj1 from hour 2 on, where
adj0 is yesterday's bias. Before the fix nos-workflow never computed adj1 (obs parser and staout column
mapping bugs) and applied adj1 = 0.

Figures (PNG, dpi 100, <= 1500 px):
  1 dynadj_elev2d_ts.png          boundary SSH at 4 open-boundary nodes: operational adjusted / non-adjusted,
                                  before, this PR, and the difference from operational
  2 dynadj_offset_steps.png       the offset applied to elev2D during the first hours (-adj0, -(adj0+adj1)/2, -adj1)
  3 dynadj_station_bias.png       the bias computation at the 11 gauges (model vs observed, hourly bias, mean)
plus dynadj_summary.txt (per-gauge bias, NaN ratio, average, elev2D difference statistics).

The station bias is recomputed here with plain numpy/pandas and cross-checked against the PR code
(nos_utils.forcing.dynamic_adjust.compute_bias) when --pr-src is importable.

"before" = nos-workflow before the fix, "this PR" = nos-workflow with the fix.
"""
import argparse
import glob
import os
import re
import sys
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from obc_common import EPOCH, common, load_nodes, load_series, parse_dt, to_dt   # noqa: E402

LAB = {"ops": "operational STOFS-3D-ATL", "before": "nos-workflow before fix",
       "after": "nos-workflow (this PR)"}
COL = {"ops": "#0072B2", "before": "#D55E00", "after": "#009E73", "nonadj": "0.55"}   # Okabe-Ito, colour-blind safe
GAUGE = {"8670870": "Fort Pulaski GA", "8665530": "Charleston SC", "8661070": "Springmaid Pier SC",
         "8658163": "Wrightsville Beach NC", "8651370": "Duck NC", "8632200": "Kiptopeke VA",
         "8557380": "Lewes DE", "8536110": "Cape May NJ", "8534720": "Atlantic City NJ",
         "8531680": "Sandy Hook NJ", "8452660": "Newport RI"}
NAN_LIMIT = 0.20
WINDOW_DAYS = 2
POS_NAMES = ["south", "south-middle", "north-middle", "north"]


# ------------------------------------------------------------------ helpers
def sec(s):
    return (parse_dt(s) - EPOCH).total_seconds()


def pdy_title(cyc):
    c = to_dt(sec(cyc))
    return f"PDY {c:%Y-%m-%d} {c:%H}z"


def save_png(fig, out):
    fig.savefig(out, dpi=100, metadata={"Software": None})
    plt.close(fig)
    im = Image.open(out)
    w, h = im.size
    assert max(w, h) <= 1500, f"{out}: {w}x{h} exceeds 1500 px"
    im.save(out, optimize=True)
    print(f"saved {out}  {w}x{h}")
    return w, h


def first(pattern):
    p = sorted(glob.glob(pattern))
    if not p:
        raise SystemExit(f"no file matches {pattern}")
    return p[0]


def read_scalar(path):
    return float(open(path).read().split()[0])


def sgn(x, nd=3):
    return f"{x:+.{nd}f}".replace("-", "−")


def day_axis(ax, rot=False):
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[12]))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[0, 6, 18]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    if rot:
        for l in ax.get_xticklabels():
            l.set_rotation(0)


# ------------------------------------------------------------------ elev2D data
def load_elev(root, cyc):
    """{name: (abs_seconds, (T, 778) float64)} for ops adjusted / non-adjusted and before / this PR (merged
    nowcast + forecast, forecast file overriding from the cycle time as SCHISM reads them) plus the raw files."""
    cs = sec(cyc)
    start = (to_dt(cs) - timedelta(hours=24)).strftime("%Y%m%d%H")
    f = lambda p, s: f"{p}:{s}"
    d = {"ops": load_series(f(first(f"{root}/ops/*.elev2dth.nc"), start)),
         "nonadj": load_series(f(first(f"{root}/ops/*.elev2dth_non_adj.nc"), start))}
    for k in ("before", "after"):
        now, fc = f(f"{root}/{k}/now/elev2D.th.nc", start), f(f"{root}/{k}/fcst/elev2D.th.nc", cyc)
        d[k] = load_series([now, fc])
        d[k + "_now"], d[k + "_fcst"] = load_series(now), load_series(fc)
    return d, start


def hourly_nonadj(d):
    """Operational non-adjusted records linearly interpolated to the operational hourly times
    (what ops `cdo inttime,1hour` does before the ramp)."""
    to, _ = d["ops"]
    tn, N = d["nonadj"]
    return np.array([np.interp(to, tn, N[:, i]) for i in range(N.shape[1])]).T


def pick_nodes(lats, nodes_csv):
    lon, lat, dep, seg = load_nodes(nodes_csv)
    idx = [int(np.argmin(np.where(seg == 1, np.abs(lat - t), 1e9))) for t in lats]
    return idx, lon, lat, dep


# ------------------------------------------------------------------ figure 1
def fig1(args, d, out, adj0, adj1):
    idx, lon, lat, dep = pick_nodes(args.lat_list, args.nodes_csv)
    to, O = d["ops"]
    tn, N = d["nonadj"]
    tb, B = d["before"]
    ta, A = d["after"]
    io, ib = common(to, tb)
    ia, ib2 = common(to, ta)
    DB, DA = B[ib] - O[io], A[ib2] - O[ia]
    cyc = to_dt(sec(args.cycle))
    dt = lambda t: [to_dt(x) for x in t]
    xlim = (to_dt(min(to[0], tb[0])), to_dt(max(to[-1], tb[-1])))
    xlim = (xlim[0], to_dt(tb[-1]) + timedelta(hours=3))
    fig = plt.figure(figsize=(15, 9.4))
    gs = fig.add_gridspec(2, 4, left=0.06, right=0.985, top=0.795, bottom=0.085, wspace=0.22, hspace=0.12,
                          height_ratios=[3, 2])
    for c, k in enumerate(idx):
        ax = fig.add_subplot(gs[0, c])
        ax.plot(dt(tn), N[:, k], color=COL["nonadj"], lw=4.5, alpha=0.5, marker=".", ms=4, mec="0.35", zorder=2)
        ax.plot(dt(to), O[:, k], color=COL["ops"], lw=3.0, alpha=0.85, zorder=3)
        ax.plot(dt(tb), B[:, k], color=COL["before"], lw=1.3, zorder=4)
        ax.plot(dt(ta), A[:, k], color=COL["after"], lw=1.3, ls=(0, (4, 2)), zorder=5)
        ax.axvline(cyc, color="k", ls="--", lw=0.9)
        ax.set_xlim(xlim)
        ax.set_title(f"{'ABCD'[c]}  {POS_NAMES[c]}: {lat[k]:.1f}N {abs(lon[k]):.1f}W, depth {dep[k]:.0f} m",
                     fontsize=10, loc="left")
        ax.grid(alpha=0.3)
        day_axis(ax)
        ax.tick_params(labelbottom=False)
        if c == 0:
            ax.set_ylabel("boundary SSH, elev2D (m)")
        ax2 = fig.add_subplot(gs[1, c], sharex=ax)
        ax2.axhline(0, color="k", lw=0.6)
        ax2.plot(dt(to[io]), DB[:, k], color=COL["before"], lw=1.3, marker=".", ms=3)
        ax2.plot(dt(to[ia]), DA[:, k], color=COL["after"], lw=1.3, ls=(0, (4, 2)))
        ax2.axvline(cyc, color="k", ls="--", lw=0.9)
        ax2.set_ylim(-0.055, 0.02)
        ax2.grid(alpha=0.3)
        day_axis(ax2)
        ax2.set_xlabel("UTC date (ticks at 12Z)")
        if c == 0:
            ax2.set_ylabel("nos-workflow $-$ operational (m)")
        else:
            ax2.tick_params(labelleft=True)
        h = np.round((to[io] - to[0]) / 3600).astype(int)
        v = lambda hh: DB[h == hh, k][0]
        ax2.text(0.015, 0.05, f"before: 0 m at hour 0, {sgn(v(1), 4)} m at hour 1,\n"
                              f"{sgn(v(2), 3)} m from hour 2 on", transform=ax2.transAxes, fontsize=8,
                 color=COL["before"], va="bottom", bbox=dict(fc="w", ec="none", alpha=0.8, pad=1))
        ax2.text(0.985, 0.42, f"this PR: max |diff| {np.abs(DA).max():.1e} m\n(all 778 nodes, all hours)",
                 transform=ax2.transAxes, fontsize=8, color=COL["after"], va="bottom", ha="right",
                 fontweight="bold", bbox=dict(fc="w", ec="none", alpha=0.8, pad=1))
        tr2 = ax2.get_xaxis_transform()
        ax2.text(to_dt(to[0]) + (cyc - to_dt(to[0])) / 2, 0.96, "nowcast", transform=tr2, ha="center", va="top",
                 fontsize=9, color="dimgray")
        ax2.text(cyc + (xlim[1] - cyc) / 2, 0.96, "forecast", transform=tr2, ha="center", va="top", fontsize=9,
                 color="dimgray")
        xa = to_dt(sec("2026100312"))
        ya, yb = np.interp(sec("2026100312"), tn, N[:, k]), np.interp(sec("2026100312"), to, O[:, k])
        ax.annotate("", xy=(xa, yb), xytext=(xa, ya), arrowprops=dict(arrowstyle="<->", color="0.2", lw=1.0))
        ax.text(xa + timedelta(hours=3), (ya + yb) / 2, f"{yb - ya:.3f} m", fontsize=8.5, va="center", color="0.2")
    handles = [Line2D([], [], color=COL["ops"], lw=3.0, alpha=0.85, label=f"{LAB['ops']}, adjusted (hourly)"),
               Line2D([], [], color=COL["nonadj"], lw=4.5, alpha=0.5, marker=".", ms=4, mec="0.35",
                      label=f"{LAB['ops']}, non-adjusted (6-hourly records, linear between)"),
               Line2D([], [], color=COL["before"], lw=1.3, label=LAB["before"]),
               Line2D([], [], color=COL["after"], lw=1.3, ls=(0, (4, 2)), label=LAB["after"]),
               Line2D([], [], color="k", ls="--", lw=0.9, label=f"cycle time {cyc:%m-%d %H}Z")]
    fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.865), fontsize=9.5,
               frameon=False)
    fig.suptitle(f"STOFS-3D-ATL dynamic SSH bias adjustment: open-boundary SSH (elev2D), {pdy_title(args.cycle)}\n"
                 f"adj0 (yesterday's bias) = {sgn(adj0)} m,  adj1 (today's bias) = {sgn(adj1)} m",
                 fontsize=12.5, fontweight="bold", y=0.985)
    fig.text(0.06, 0.915, "elev2D = non-adjusted $-$ adj0 at hour 0, $-$ (adj0 + adj1)/2 at hour 1, $-$ adj1 from hour 2 on "
             "(the non-adjusted SSH is constant in time at each node, so the steps are the whole signal).\n"
             "Before the fix adj1 was left at 0, so SSH stayed on the non-adjusted line, 0.039 m too low, from hour 2 on; "
             "with this PR it equals operational to float precision (green dashes sit on zero).",
             fontsize=9.5, color="0.2", va="center")
    return save_png(fig, out)


# ------------------------------------------------------------------ figure 2
def offset_rows(d, n):
    """{run: offset (n hours, node mean)} = run elev2D minus the hourly-interpolated operational non-adjusted."""
    to, _ = d["ops"]
    NH = hourly_nonadj(d)
    rows = {}
    for k in ("ops", "before", "after"):
        t, X = d[k]
        io, ik = common(to, t)
        rows[k] = np.array([(X[ik[i]] - NH[io[i]]).mean() for i in range(n)])
    return rows


def fig2(args, d, out, adj0, adj1):
    to, _ = d["ops"]
    n = 9
    rows = offset_rows(d, n)
    mid = (adj0 + adj1) / 2
    h = np.arange(n)
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    fig.subplots_adjust(left=0.1, right=0.97, top=0.76, bottom=0.17)
    ax.axhline(0, color="k", lw=0.6)
    ax.step(h, rows["ops"], where="post", color=COL["ops"], lw=6, alpha=0.4, label=LAB["ops"])
    ax.plot(h, rows["ops"], "o", color=COL["ops"], ms=11, mfc="none", mew=1.8)
    ax.step(h, rows["before"], where="post", color=COL["before"], lw=1.6, label=LAB["before"])
    ax.plot(h, rows["before"], "s", color=COL["before"], ms=6)
    ax.step(h, rows["after"], where="post", color=COL["after"], lw=1.6, ls=(0, (4, 2)), label=LAB["after"])
    ax.plot(h, rows["after"], "^", color=COL["after"], ms=6)
    ax.set_xticks(h)
    ax.set_xlim(-0.3, n - 0.3)
    ax.set_ylim(-0.007, 0.056)
    ax.set_xlabel(f"hour of elev2D (0 = {to_dt(to[0]):%Y-%m-%d %H}Z, the nowcast start)")
    ax.set_ylabel("offset applied to the SSH boundary (m)\nadjusted $-$ non-adjusted, node mean")
    ax.grid(alpha=0.3)
    ax.text(0.015, 0.97, f"hour 0:  $-$adj0 = {sgn(-adj0)} m\n"
                         f"hour 1:  $-$(adj0 + adj1)/2 = {sgn(-mid)} m\n"
                         f"hour 2 on:  $-$adj1 = {sgn(-adj1)} m", transform=ax.transAxes, fontsize=10, va="top",
            color=COL["ops"], fontweight="bold", linespacing=1.5)
    ax.annotate(f"hour 1: $-$(adj0 + 0)/2 = {sgn(-adj0 / 2, 4)} m", (1, rows["before"][1]), (1.08, 0.0215),
                fontsize=9.5, color=COL["before"], va="center")
    ax.annotate("before the fix: adj1 = 0, so\nthe offset is 0 from hour 2 on", (4, 0.0), (3.7, 0.012),
                fontsize=9.5, color=COL["before"], arrowprops=dict(arrowstyle="-", color=COL["before"]))
    ax.legend(loc="center right", fontsize=9.5, frameon=True, bbox_to_anchor=(1.0, 0.42))
    fig.suptitle(f"STOFS-3D-ATL dynamic SSH bias adjustment: offset ramp in the first hours\n{pdy_title(args.cycle)}",
                 fontsize=12, fontweight="bold", y=0.985)
    fig.text(0.1, 0.835, "Same offset at every boundary node (spread < 1e-7 m). Operational and this PR coincide at all "
             "hours;\nthe fix only changes hours 1 and later, because adj1 is now computed instead of left at 0.",
             fontsize=9.5, color="0.2", va="center")
    return save_png(fig, out), rows


# ------------------------------------------------------------------ station bias (independent)
def read_obs_text(path):
    t, v = [], []
    for ln in open(path, errors="replace"):
        p = ln.split()
        if len(p) < 6:
            continue
        try:
            val = float(p[5])
            ts = np.datetime64(f"{p[3]}T{p[4]}", "ns")
        except ValueError:
            continue
        t.append(ts)
        v.append(val)
    o = np.argsort(t)
    return np.array(t)[o], np.array(v)[o]


def interp_gapped(t_obs, y, t_new, gap_mult=10):
    """Linear interpolation inside runs of obs, NaN across gaps longer than gap_mult x the modal interval."""
    ts = t_obs.astype("datetime64[s]").astype("i8")
    tn = t_new.astype("datetime64[s]").astype("i8")
    out = np.full(len(tn), np.nan)
    if len(ts) < 2:
        return out
    dtv = np.diff(ts)
    u, c = np.unique(dtv, return_counts=True)
    cut = np.where(dtv > gap_mult * u[np.argmax(c)])[0]
    for s, e in zip(np.r_[0, cut + 1], np.r_[cut + 1, len(ts)]):
        if e - s < 2:
            continue
        m = (tn >= ts[s]) & (tn <= ts[e - 1])
        out[m] = np.interp(tn[m], ts[s:e], y[s:e])
    return out


def parse_bp(path):
    """(ids, lon, lat, z) of a SCHISM .bp with '!id' comments."""
    L = open(path).read().splitlines()
    n = int(L[1].split()[0])
    ids, lon, lat, z = [], [], [], []
    for ln in L[2:2 + n]:
        a, _, cmt = ln.partition("!")
        p = a.split()
        ids.append(cmt.strip().split()[0])
        lon.append(float(p[1])); lat.append(float(p[2])); z.append(float(p[3]))
    return ids, np.array(lon), np.array(lat), np.array(z)


def station_in_ids(path):
    L = open(path).read().splitlines()
    n = int(L[1].split()[0])
    return [ln.rsplit("!", 1)[1].strip() if "!" in ln else "" for ln in L[2:2 + n]]


def station_bias(args):
    root, cyc = args.dir, to_dt(sec(args.cycle)).replace(tzinfo=None)
    t_end = cyc
    t_start = t_end - timedelta(days=WINDOW_DAYS)
    ids, glon, glat, _ = parse_bp(f"{args.fix_dir}/stofs_3d_atl_obc_adjust_station.bp")
    dids, _, _, doff = parse_bp(f"{args.fix_dir}/stofs_3d_atl_obc_adjust_msl_geoid.bp")
    datum = dict(zip(dids, doff))
    rows = station_in_ids(f"{args.fix_dir}/stofs_3d_atl_station.in")
    nml = open(first(f"{root}/seed/*.param.nml")).read()
    g = lambda k: int(re.search(rf"{k}\s*=\s*(\d+)", nml).group(1))
    start = pd.Timestamp(g("start_year"), g("start_month"), g("start_day"), g("start_hour"))
    st = np.loadtxt(f"{root}/seed/staout_1")
    mt = (start + pd.to_timedelta(st[:, 0], unit="s")).to_numpy("datetime64[ns]")
    win = (mt >= np.datetime64(t_start)) & (mt < np.datetime64(t_end))
    disp = (mt >= np.datetime64(t_start)) & (mt <= np.datetime64(t_end))
    mt_w = mt[win]
    res = {}
    for k, sid in enumerate(ids):
        t_o, v_o = read_obs_text(f"{root}/obs/{sid}.xml")
        v_adj = v_o + datum[sid]
        sel = (t_o >= np.datetime64(t_start)) & (t_o <= np.datetime64(t_end))
        interp = interp_gapped(t_o[sel], v_adj[sel], mt_w)
        col = rows.index(sid) + 1
        mod = st[win, col]
        res[sid] = dict(k=k, lon=glon[k], lat=glat[k], datum=datum[sid], col=col, mod_t=mt[disp],
                        mod=st[disp, col], obs_t=t_o[sel], obs=v_adj[sel], bias5=mod - interp, t5=mt_w)
    df = pd.DataFrame({s: pd.Series(r["bias5"], index=pd.to_datetime(mt_w)) for s, r in res.items()})
    hourly = df.resample("h").mean()
    nan_ratio = hourly.isna().sum() / len(hourly)
    used = [s for s in hourly.columns if nan_ratio[s] <= NAN_LIMIT]
    avg_hour = hourly[used].mean(axis=1)
    avg_full = float(avg_hour.mean())
    avg_round = float(f"{avg_full:.3f}")
    for s, r in res.items():
        r["hourly"] = hourly[s]
        r["nan"] = float(nan_ratio[s])
        r["used"] = s in used
        r["mean_h"] = float(np.nanmean(hourly[s]))
        r["mean_5"] = float(np.nanmean(r["bias5"]))
    return res, dict(avg_full=avg_full, avg_round=avg_round, used=used, n_hours=len(hourly),
                     t_start=t_start, t_end=t_end, start=start, avg_hour=avg_hour)


def pr_crosscheck(args, res):
    """Run the PR's compute_bias on the same inputs. Returns (avg, per_station_mean) or None."""
    try:
        sys.path.insert(0, args.pr_src)
        from pathlib import Path
        from nos_utils.forcing import dynamic_adjust as da
    except Exception as exc:                                                    # pragma: no cover
        print("PR code not importable, cross-check skipped:", exc)
        return None
    fx, root = Path(args.fix_dir), Path(args.dir)
    ids, lons, lats = da.read_bp_stations(fx / "stofs_3d_atl_obc_adjust_station.bp")
    obs = da.load_observations(root / "obs", ids, lons, lats)
    stn = da.read_staout_1(root / "seed" / "staout_1")
    start = da.read_model_start(Path(first(f"{args.dir}/seed/*.param.nml")))
    cyc = to_dt(sec(args.cycle)).replace(tzinfo=None)
    avg, per = da.compute_bias(obs, stn, start, ids, da.read_diff_bp(fx / "stofs_3d_atl_obc_adjust_msl_geoid.bp"),
                               cyc - timedelta(days=WINDOW_DAYS), cyc, model_station_ids=da.read_station_in(
                                   fx / "stofs_3d_atl_station.in"))
    return avg, per


# ------------------------------------------------------------------ figure 3
def coast_map(ax, extent, ticks=True, fs=7):
    import cartopy.crs as ccrs
    import cartopy.feature as cf
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#e6f0f7", zorder=0)
    ax.add_feature(cf.LAND.with_scale("50m"), facecolor="0.8", zorder=1)
    ax.add_feature(cf.COASTLINE.with_scale("50m"), edgecolor="0.3", lw=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=ticks, lw=0.3, color="gray", alpha=0.5)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": fs}


def fig3(args, res, tot, adj1_ops, adj0, pr, out):
    import cartopy.crs as ccrs
    order = sorted(res, key=lambda s: res[s]["lat"])
    cyc = to_dt(sec(args.cycle)).replace(tzinfo=None)
    t0, t1 = cyc - timedelta(days=WINDOW_DAYS), cyc
    ok = abs(tot["avg_round"] - adj1_ops) < 5e-4
    green, red = "#009E73", "#D55E00"
    fig = plt.figure(figsize=(15, 14.2))
    outer = fig.add_gridspec(1, 2, width_ratios=[1, 3.25], left=0.045, right=0.965, top=0.875, bottom=0.04,
                             wspace=0.075)
    left = outer[0].subgridspec(3, 1, height_ratios=[4.3, 3.0, 3.0], hspace=0.16)
    right = outer[1].subgridspec(4, 3, hspace=0.50, wspace=0.28)
    pc = ccrs.PlateCarree()

    # --- overview map
    axm = fig.add_subplot(left[0], projection=pc)
    coast_map(axm, [-86, -48, 5, 54])
    lon, lat, _, _ = load_nodes(args.nodes_csv)
    axm.scatter(lon, lat, s=3, color=COL["ops"], transform=pc, zorder=3)
    axm.scatter([r["lon"] for r in res.values()], [r["lat"] for r in res.values()], s=9, color=green,
                edgecolor="k", linewidth=0.4, transform=pc, zorder=5)
    idx, _, _, _ = pick_nodes(args.lat_list, args.nodes_csv)
    for c, k in zip("ABCD", idx):
        axm.plot(lon[k], lat[k], "D", color="k", ms=5, transform=pc, zorder=5)
        axm.text(lon[k] + 0.9, lat[k], c, fontsize=9, fontweight="bold", transform=pc, zorder=5, va="center")
    zx, zy = [-83, -69], [31, 43]
    axm.plot([zx[0], zx[1], zx[1], zx[0], zx[0]], [zy[0], zy[0], zy[1], zy[1], zy[0]], color="k", lw=0.9,
             transform=pc, zorder=6)
    axm.set_title("open boundary (blue), bias gauges (green)\nA-D: boundary nodes of the elev2D time-series figure",
                  fontsize=9)
    # --- zoom map with numbered gauges
    axz = fig.add_subplot(left[1], projection=pc)
    coast_map(axz, zx + zy)
    for n, s in enumerate(order, 1):
        r = res[s]
        axz.plot(r["lon"], r["lat"], "o" if r["used"] else "X", ms=6.5, mfc=green if r["used"] else red,
                 mec="k", mew=0.6, transform=pc, zorder=5)
        axz.text(r["lon"] - 0.45, r["lat"] + (0.25 if n in (8, 10) else 0.0), str(n), fontsize=9, ha="right",
                 va="center", fontweight="bold", transform=pc, zorder=6)
    axz.set_title("gauge locations (zoom of the box)", fontsize=9)
    axz.legend(handles=[Line2D([], [], marker="o", ls="", mfc=green, mec="k", label="gauge used in the average"),
                        Line2D([], [], marker="X", ls="", mfc=red, mec="k", label="gauge excluded (> 20% NaN hours)")],
               loc="lower right", fontsize=7.5, framealpha=0.9)
    # --- per-gauge table
    axt = fig.add_subplot(left[2])
    axt.axis("off")
    T = [f"{'#':>2} {'gauge':<22}{'mean bias':>9}{'NaN':>6}  used"]
    for n, s in enumerate(order, 1):
        r = res[s]
        T.append(f"{n:>2} {GAUGE[s]:<22}{sgn(r['mean_h'], 3):>9}{r['nan']:>6.0%}  " + ("yes" if r["used"] else "NO"))
    axt.text(0.0, 1.0, "\n".join(T), family="monospace", fontsize=8, va="top", transform=axt.transAxes)
    axt.text(0.0, 0.0, "mean bias (m) = model $-$ observed, mean of\nthe 48 hourly values; NaN = share of\n"
                       "hours without observations.",
             fontsize=7.5, va="bottom", color="0.25", transform=axt.transAxes)

    # --- gauge panels
    for n, s in enumerate(order, 1):
        r = res[s]
        sub = right[(n - 1) // 3, (n - 1) % 3].subgridspec(2, 1, height_ratios=[3, 2], hspace=0.12)
        a1 = fig.add_subplot(sub[0])
        a2 = fig.add_subplot(sub[1], sharex=a1)
        if not r["used"]:
            for a in (a1, a2):
                a.set_facecolor("#fbe3e3")
        to_, vo = r["obs_t"], r["obs"]
        gap = np.where(np.diff(to_.astype("datetime64[s]").astype("i8")) > 3600)[0]
        to_p, vo_p = np.insert(to_, gap + 1, np.datetime64("NaT")), np.insert(vo, gap + 1, np.nan)
        a1.plot(r["mod_t"], r["mod"], color=COL["ops"], lw=1.4)
        a1.plot(to_p, vo_p, color="k", lw=0.9)
        a1.set_xlim(t0, t1)
        a1.grid(alpha=0.3)
        a1.tick_params(labelbottom=False, labelsize=8)
        mh = r["hourly"]
        a2.axhline(0, color="k", lw=0.6)
        a2.plot(mh.index + pd.Timedelta(minutes=30), mh.values, color="0.25", lw=1.0, marker=".", ms=3)
        a2.axhline(r["mean_h"], color="#CC79A7", lw=1.8, ls="--")
        a2.grid(alpha=0.3)
        a2.tick_params(labelsize=8)
        a2.xaxis.set_major_locator(mdates.HourLocator(byhour=[12]))
        a2.xaxis.set_minor_locator(mdates.HourLocator(byhour=[0, 6, 18]))
        a2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %HZ"))
        if (n - 1) % 3 == 0:
            a1.set_ylabel("water level (m)", fontsize=8)
            a2.set_ylabel("model $-$ obs (m)", fontsize=8)
        ttl = f"{n}  {GAUGE[s]} ({s})\nmean bias {sgn(r['mean_h'], 3)} m"
        if not r["used"]:
            ttl += f"   EXCLUDED, {r['nan']:.0%} NaN hours"
        a1.set_title(ttl, fontsize=9, loc="left", color="#B00020" if not r["used"] else "k")

    # --- result box in the free 12th cell
    axb = fig.add_subplot(right[3, 2])
    axb.axis("off")
    lines = [(f"Average bias of the {len(tot['used'])} gauges used", 10.5, "normal"),
             (f"nos-workflow (this PR): {sgn(tot['avg_full'], 4)} m", 9.5, "bold"),
             (f"   rounded to 3 decimals: {sgn(tot['avg_round'])} m", 9.5, "bold"),
             (f"operational avg_bias: {sgn(adj1_ops)} m", 9.5, "bold")]
    if pr is not None:
        lines.append((f"nos-utils compute_bias: {sgn(pr[0])} m", 9.5, "normal"))
    lines.append((f"(yesterday's bias adj0 = {sgn(adj0)} m)", 9.5, "normal"))
    for i, (txt, fs, fw) in enumerate(lines):
        axb.text(0.02, 0.96 - 0.15 * i, txt, fontsize=fs, fontweight=fw, va="top", transform=axb.transAxes)
    axb.add_patch(plt.Rectangle((-0.02, 0.0), 1.04, 1.0, transform=axb.transAxes, fc="#eef7ee" if ok else "#fdeaea",
                                ec="0.5", zorder=-1))
    handles = [Line2D([], [], color=COL["ops"], lw=1.4, label="operational model run of the previous cycle (staout_1)"),
               Line2D([], [], color="k", lw=0.9, label="observed water level (NAVD88) + datum offset"),
               Line2D([], [], color="0.25", lw=1.0, marker=".", ms=3, label="hourly-mean bias, model $-$ observed"),
               Line2D([], [], color="#CC79A7", lw=1.8, ls="--", label="gauge mean bias")]
    fig.legend(handles=handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 0.925), fontsize=9.5, frameon=False)
    fig.suptitle(f"STOFS-3D-ATL dynamic SSH bias adjustment: bias computation at the 11 NOAA gauges, {pdy_title(args.cycle)}\n"
                 f"Window {t0:%m-%d %H}Z to {t1:%m-%d %H}Z.  Average bias: nos-workflow {sgn(tot['avg_round'])} m "
                 f"{'=' if ok else '!='} operational avg_bias {sgn(adj1_ops)} m",
                 fontsize=12.5, fontweight="bold", y=0.985)
    return save_png(fig, out)


# ------------------------------------------------------------------ summary
def summary(args, d, res, tot, pr, adj0, adj1_ops, rows2, sizes, out):
    cyc = sec(args.cycle)
    L = [f"Dynamic SSH bias adjust validation, {pdy_title(args.cycle)}", ""]
    L.append("A. Bias computation (independent numpy/pandas recompute of derive_bias.py, 11 gauges)")
    L.append(f"   window {tot['t_start']:%Y-%m-%d %H}Z .. {tot['t_end']:%Y-%m-%d %H}Z "
             f"(model samples [start, end), {tot['n_hours']} hourly bins); model run start {tot['start']:%Y-%m-%d %H}Z; "
             f"NaN limit {NAN_LIMIT:.0%} of hourly bins")
    L.append(f"   {'gauge':8s}{'name':23s}{'datum off':>10s}{'staout col':>11s}{'mean bias (hourly)':>20s}"
             f"{'mean (5-min)':>14s}{'PR code':>10s}{'NaN ratio':>11s}  status")
    for s in sorted(res, key=lambda s: res[s]["lat"]):
        r = res[s]
        p = f"{pr[1][s]:.5f}" if pr is not None and s in pr[1] else "n/a"
        L.append(f"   {s:8s}{GAUGE[s]:23s}{r['datum']:10.5f}{r['col']:11d}{r['mean_h']:20.5f}{r['mean_5']:14.5f}"
                 f"{p:>10s}{r['nan']:11.3f}  {'included' if r['used'] else 'EXCLUDED'}")
    L.append(f"   gauges included: {len(tot['used'])} of {len(res)}")
    L.append(f"   average (mean over hours of the per-hour mean over included gauges): "
             f"{tot['avg_full']:.8f} m full precision, {tot['avg_round']:.3f} m rounded to 3 decimals")
    L.append(f"   operational avg_bias (today, adj1) = {adj1_ops:.3f} m; yesterday's bias (adj0) = {adj0:.3f} m")
    if pr is not None:
        L.append(f"   PR code compute_bias average = {pr[0]:.3f} m")
    L.append(f"   MATCH: independent {tot['avg_round']:.3f} == operational {adj1_ops:.3f}: "
             f"{abs(tot['avg_round'] - adj1_ops) < 5e-4}" + (
                 f"; PR code == operational: {abs(pr[0] - adj1_ops) < 5e-4}" if pr is not None else ""))
    L.append("")
    L.append("B. Applied offset in the first hours (adjusted - ops non-adjusted linearly interpolated to hourly; node mean, m)")
    mid = (adj0 + adj1_ops) / 2
    L.append(f"   formula: hour 0 {-adj0:+.5f}, hour 1 {-mid:+.5f}, hour >= 2 {-adj1_ops:+.5f}")
    L.append(f"   {'hour':>5s}{'operational':>13s}{'before':>10s}{'this PR':>10s}")
    for h in range(9):
        L.append(f"   {h:5d}{rows2['ops'][h]:13.5f}{rows2['before'][h]:10.5f}{rows2['after'][h]:10.5f}")
    L.append("")
    L.append("C. elev2D difference from operational (nos-workflow - operational), all 778 boundary nodes, metres")
    to, O = d["ops"]
    cases = [("nowcast file, all records", "now", None), ("nowcast file, hours 0-24 (<= cycle, read by SCHISM)", "now", cyc),
             ("forecast file, all records", "fcst", None)]
    L.append(f"   {'phase':55s}{'run':8s}{'records':>8s}{'max |diff|':>13s}{'RMS':>12s}{'equal':>20s}")
    for name, ph, upto in cases:
        for k, lab in (("before", "before"), ("after", "this PR")):
            t, X = d[f"{k}_{ph}"]
            io, ik = common(to, t)
            keep = np.ones(len(io), bool) if upto is None else t[ik] <= upto
            io, ik = io[keep], ik[keep]
            df = X[ik] - O[io]
            ne = int((df == 0).sum())
            L.append(f"   {name:55s}{lab:8s}{len(io):8d}{np.abs(df).max():13.4g}{np.sqrt((df ** 2).mean()):12.4g}"
                     f"{ne:>12d}/{df.size} ({ne / df.size:.1%})")
    L.append("")
    L.append("   by hour since the nowcast start, node-mean difference (before) and max |diff| (this PR):")
    tb, B = d["before"]
    ta, A = d["after"]
    io, ik = common(to, tb)
    h = np.round((to[io] - to[0]) / 3600).astype(int)
    db = (B[ik] - O[io]).mean(axis=1)
    L.append("   before: " + ", ".join(f"h{x}: {db[h == x][0]:+.5f}" for x in (0, 1, 2, 3, 24, 48, 126)))
    L.append(f"   this PR max |diff| over all merged records and nodes: {np.abs(A[common(to, ta)[1]] - O[common(to, ta)[0]]).max():.4g}")
    L.append("")
    L.append("D. Files")
    for k, v in sizes.items():
        L.append(f"   {k}: {v[0]}x{v[1]} px")
    text = "\n".join(L) + "\n"
    with open(out, "w") as f:
        f.write(text)
    print(text)
    print("saved", out)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="VIZ_DIR with ops/, before/, after/, obs/, seed/")
    ap.add_argument("--outdir", default=None, help="default VIZ_DIR/plots")
    ap.add_argument("--cycle", default="2026100112", help="cycle time YYYYMMDDHH")
    ap.add_argument("--fix-dir", required=True, help="operational fix dir (station.in, adjust .bp files)")
    ap.add_argument("--nodes-csv", required=True, help="obc_nodes.csv (seg,k,node,x,y,depth,lon,lat)")
    ap.add_argument("--lats", default="10,22,34,46", help="target latitudes of the 4 boundary nodes of figure 1")
    ap.add_argument("--pr-src", default="", help="nos-utils checkout to cross-check compute_bias ('' to skip)")
    ap.add_argument("--only", default="1,2,3", help="figures to make, e.g. 1,3")
    args = ap.parse_args()
    args.lat_list = [float(x) for x in args.lats.split(",")]
    root = args.dir
    outdir = args.outdir or os.path.join(root, "plots")
    os.makedirs(outdir, exist_ok=True)
    want = {int(s) for s in args.only.split(",")}
    o = lambda n: os.path.join(outdir, n)

    adj1 = read_scalar(first(f"{root}/ops/*.avg_bias"))
    adj0 = read_scalar(first(f"{root}/seed/*.avg_bias"))
    d, _ = load_elev(root, args.cycle)
    res, tot = station_bias(args)
    pr = pr_crosscheck(args, res) if args.pr_src else None
    print(f"average bias: independent {tot['avg_full']:.6f} -> {tot['avg_round']:.3f}, "
          f"PR {pr[0] if pr else 'n/a'}, operational {adj1}")
    sizes = {}
    if 1 in want:
        sizes["dynadj_elev2d_ts.png"] = fig1(args, d, o("dynadj_elev2d_ts.png"), adj0, adj1)
    if 2 in want:
        sizes["dynadj_offset_steps.png"], _ = fig2(args, d, o("dynadj_offset_steps.png"), adj0, adj1)
    if 3 in want:
        sizes["dynadj_station_bias.png"] = fig3(args, res, tot, adj1, adj0, pr, o("dynadj_station_bias.png"))
    if want == {1, 2, 3}:
        summary(args, d, res, tot, pr, adj0, adj1, offset_rows(d, 9), sizes, o("dynadj_summary.txt"))


if __name__ == "__main__":
    main()
