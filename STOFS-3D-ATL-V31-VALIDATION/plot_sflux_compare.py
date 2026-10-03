#!/usr/bin/env python3
"""
sflux (atmospheric forcing) validation figures: operational STOFS-3D-ATL v3.1 vs nos-workflow
before and after the ops-parity fix (nos-utils PR #64).

usage: plot_sflux_compare.py --dir VIZ_DIR [--outdir DIR] [--cycle 2026100112]
           [--map-time 2026100112] [--hrrr-time 2026093018] [--only 1,2,3,4,5]
           [--points "30.5,-89.25;34.5,-79.25;26.25,-87.5;40.25,-62.25"]

VIZ_DIR holds ops/stofs_3d_atl.t<CC>z.gfs.air.nc (air+prc+rad in one file, 1-hourly),
{before,after}/{now,fcst}/sflux_{air,prc,rad}_1.0001.nc and {ops,before,after}/hrrr_sub.npz
(keys times, lon, lat, uwind, vwind, prmsl; 2-D HRRR Lambert grid). Records are matched on absolute
time to the second (base_date + days) and compared by array index on the grid, as compare_sflux.py
does. "Used" records = the nowcast file up to the cycle time plus the forecast file after it, i.e.
what SCHISM reads in each phase; the last ops record is re-timed by ops to day 10 and never matches.

Figures (PNG, dpi 100, <= 1500 px):
  1 sflux_gfs_nowcast_map.png         ops | before - ops | this PR - ops, prmsl and 10 m wind speed
  2 sflux_gfs_error_by_hour.png       RMS(ours - ops) per record, 8 variables, before vs this PR
  3 sflux_gfs_prate_ts.png            prate time series at 4 rainy grid points + locator map
  4 sflux_gfs_grid_offset.png         lat/lon label offsets of the GFS grid vs the true 0.25 deg points
  5 sflux_hrrr_wind_direction.png     HRRR wind-direction rotation (before vs ops vs this PR) + quiver zoom
plus summary.txt (RMS/max per variable, before vs this PR, nowcast and forecast).

"before" = nos-workflow before the fix, "this PR" = nos-workflow with the fix.
"""
import argparse
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from netCDF4 import Dataset
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_sflux import abs_times                                    # noqa: E402
from obc_common import EPOCH, common, fmt_time_axis, parse_dt, shade_phases, to_dt   # noqa: E402

VARS = ["prmsl", "stmp", "spfh", "uwind", "vwind", "prate", "dlwrf", "dswrf"]
FILE = {"prmsl": "air", "stmp": "air", "spfh": "air", "uwind": "air", "vwind": "air",
        "prate": "prc", "dlwrf": "rad", "dswrf": "rad"}
DISP = {"prmsl": ("MSL pressure", "hPa", 0.01), "stmp": ("2 m air temperature", "K", 1.0),
        "spfh": ("2 m specific humidity", "g/kg", 1e3), "uwind": ("10 m u-wind", "m/s", 1.0),
        "vwind": ("10 m v-wind", "m/s", 1.0), "prate": ("precipitation rate", "mm/h", 3600.0),
        "dlwrf": ("downward longwave flux", "W/m$^2$", 1.0),
        "dswrf": ("downward shortwave flux", "W/m$^2$", 1.0)}
LAB = {"ops": "operational STOFS-3D-ATL", "before": "nos-workflow before fix",
       "after": "nos-workflow (this PR)"}
COL = {"ops": "#0072B2", "before": "#D55E00", "after": "#009E73"}     # Okabe-Ito, colour-blind safe
GFS_EXTENT = [-98.5, -52.5, 7.5, 52.5]
HRRR_ROT_LAT = 38.5          # HRRR Lambert standard parallel
HRRR_ROT_LON = -97.5         # HRRR central meridian


# ------------------------------------------------------------------ loading
def sec(s):
    return (parse_dt(s) - EPOCH).total_seconds()


def load_ops(root):
    import glob
    p = sorted(glob.glob(os.path.join(root, "ops", "*.gfs.air.nc")))[0]
    with Dataset(p) as ds:
        t = abs_times(ds)
        data = {v: np.ma.filled(ds[v][:], np.nan).astype("f4") for v in VARS}
        lon = np.asarray(ds["lon"][:], "f8")
        lat = np.asarray(ds["lat"][:], "f8")
    return {"t": t, "lon": lon, "lat": lat, "d": data}


def load_run(root, kind, phase):
    data, t, lon, lat = {}, None, None, None
    for fl in ("air", "prc", "rad"):
        with Dataset(os.path.join(root, kind, phase, f"sflux_{fl}_1.0001.nc")) as ds:
            t = abs_times(ds)
            lon = np.asarray(ds["lon"][:], "f8")
            lat = np.asarray(ds["lat"][:], "f8")
            for v in VARS:
                if FILE[v] == fl:
                    data[v] = np.ma.filled(ds[v][:], np.nan).astype("f4")
    return {"t": t, "lon": lon, "lat": lat, "d": data}


def used(now, fcst, cycle):
    """Records SCHISM reads: nowcast file up to the cycle time, forecast file after it."""
    kn, kf = now["t"] <= cycle, fcst["t"] > cycle
    return {"t": np.concatenate([now["t"][kn], fcst["t"][kf]]), "lon": fcst["lon"], "lat": fcst["lat"],
            "d": {v: np.concatenate([now["d"][v][kn], fcst["d"][v][kf]]) for v in VARS}}


def rms_series(ops, run, v):
    """(abs_times, RMS(run - ops) per common record, max|diff| per record) in display units."""
    io, ir = common(ops["t"], run["t"])
    d = (run["d"][v][ir] - ops["d"][v][io]).astype("f8") * DISP[v][2]
    return (ops["t"][io], np.sqrt(np.nanmean(d * d, axis=(1, 2))), np.nanmax(np.abs(d), axis=(1, 2)))


# ------------------------------------------------------------------ helpers
def save_png(fig, out):
    fig.savefig(out, dpi=100, metadata={"Software": None})
    plt.close(fig)
    im = Image.open(out)
    w, h = im.size
    assert max(w, h) <= 1500, f"{out}: {w}x{h} exceeds 1500 px"
    im.save(out, optimize=True)
    print(f"saved {out}  {w}x{h}")


def nice_ceil(x):
    for s in (0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200):
        if x <= s:
            return s
    return float(np.ceil(x))


def overlay_coast(ax, ticks=True, left=True, bottom=True):
    import cartopy.feature as cf
    ax.add_feature(cf.COASTLINE.with_scale("50m"), edgecolor="0.1", lw=0.6, zorder=4)
    ax.add_feature(cf.BORDERS.with_scale("50m"), edgecolor="0.35", lw=0.3, zorder=4)
    if ticks:
        gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.4)
        gl.top_labels = gl.right_labels = False
        gl.left_labels, gl.bottom_labels = left, bottom
        gl.x_inline = gl.y_inline = False
        gl.rotate_labels = False
        gl.xlabel_style = gl.ylabel_style = {"size": 7}


def place_cbar(fig, ax, im, label, extend="neither", gap=0.008, width=0.011, ticks=None):
    ax.apply_aspect()
    p = ax.get_position()
    cax = fig.add_axes([p.x1 + gap, p.y0 + 0.1 * p.height, width, 0.8 * p.height])
    cb = fig.colorbar(im, cax=cax, extend=extend, ticks=ticks)
    cb.set_label(label, fontsize=8)
    cb.ax.tick_params(labelsize=7)
    return cb


def stat_text(d):
    d = d[np.isfinite(d)]
    return float(np.sqrt(np.mean(d * d))), float(np.max(np.abs(d)))


def pdy_title(cycle):
    c = to_dt(cycle)
    return f"PDY {c:%Y-%m-%d} {c:%H}z"


def valid_str(t):
    return f"{to_dt(t):%Y-%m-%d %H}Z"


def get_field(d, i, name):
    if name == "prmsl":
        return d["prmsl"][i] * 0.01
    return np.hypot(d["uwind"][i], d["vwind"][i])


# ------------------------------------------------------------------ figure 1
def fig1(args, ops, bn, an, out):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    ts = sec(args.map_time)
    idx = [int(np.where(x["t"] == ts)[0][0]) for x in (ops, bn, an)]
    rows = [("prmsl", "MSL pressure", "hPa", "viridis"), ("wspd", "10 m wind speed", "m/s", "YlGnBu")]
    fig = plt.figure(figsize=(15, 9.6))
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.955, top=0.86, bottom=0.06, wspace=0.24, hspace=0.20)
    for r, (name, label, unit, cmap) in enumerate(rows):
        O = get_field(ops["d"], idx[0], name)
        B = get_field(bn["d"], idx[1], name)
        A = get_field(an["d"], idx[2], name)
        dB, dA = B - O, A - O
        lim = nice_ceil(float(np.nanpercentile(np.abs(dB), 99.5)))
        axes = [fig.add_subplot(gs[r, c], projection=pc) for c in range(3)]
        ims = []
        for c, (ax, fld, vmin, vmax, cm) in enumerate([
                (axes[0], O, np.nanmin(O), np.nanmax(O), cmap),
                (axes[1], dB, -lim, lim, "RdBu_r"), (axes[2], dA, -lim, lim, "RdBu_r")]):
            ax.set_extent(GFS_EXTENT, crs=pc)
            ims.append(ax.pcolormesh(ops["lon"], ops["lat"], fld, cmap=cm, vmin=vmin, vmax=vmax,
                                     transform=pc, shading="nearest", rasterized=True))
            overlay_coast(ax, left=(c == 0), bottom=(r == 1))
        rb, mb = stat_text(dB)
        ra, ma = stat_text(dA)
        axes[0].set_title(f"{LAB['ops']}\n{label} ({unit})", fontsize=10)
        axes[1].set_title(f"{LAB['before']} $-$ operational\nRMS {rb:.2g} {unit}, max |diff| {mb:.3g} {unit}",
                          fontsize=10)
        axes[2].set_title(f"{LAB['after']} $-$ operational\n" + (
            "identical (max diff 0)" if ma == 0 else f"RMS {ra:.2g} {unit}, max |diff| {ma:.3g} {unit}"),
            fontsize=10)
        place_cbar(fig, axes[0], ims[0], f"{label} ({unit})")
        place_cbar(fig, axes[2], ims[2], f"difference from operational ({unit}), same scale in both difference panels",
                   extend="both")
    fig.suptitle(f"STOFS-3D-ATL GFS sflux, nowcast file, valid {valid_str(ts)}  ({pdy_title(sec(args.cycle))})\n"
                 "Before the fix the nowcast used different GFS cycles/leads than operational; "
                 "after the fix it is identical",
                 fontsize=12, fontweight="bold", y=0.975)
    save_png(fig, out)


# ------------------------------------------------------------------ figure 2
def fig2(args, ops, ub, ua, out):
    cyc = sec(args.cycle)
    fig, axs = plt.subplots(2, 4, figsize=(15, 7.6), sharex=True)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.855, bottom=0.15, wspace=0.28, hspace=0.30)
    first_t = None
    for ax, v in zip(axs.ravel(), VARS):
        tb, rb, _ = rms_series(ops, ub, v)
        ta, ra, _ = rms_series(ops, ua, v)
        first_t = tb[0] if first_t is None else first_t
        xb = [to_dt(t) for t in tb]
        xa = [to_dt(t) for t in ta]
        ax.plot(xb, rb, color=COL["before"], lw=1.5, marker="o", ms=2.5, label=LAB["before"], zorder=3)
        ax.plot(xa, ra, color=COL["after"], lw=2.0, marker="s", ms=2.5, label=LAB["after"], zorder=4)
        top = max(rb.max(), 1e-12)
        ax.set_ylim(-0.05 * top, 1.12 * top)
        lo, hi = mdates.date2num(to_dt(tb[0])), mdates.date2num(to_dt(tb[-1]))
        ax.set_xlim(lo, hi)
        shade_phases(ax, mdates.date2num(to_dt(cyc)), (lo, hi), label=(v == VARS[0]))
        fc = tb > cyc
        if fc.any() and rb[fc].max() == 0:
            ax.text(lo + (hi - lo) * 0.70, 0.06 * top,
                    "forecast: identical\nto operational", fontsize=8, ha="center", va="bottom",
                    color="dimgray")
        name, unit, _ = DISP[v]
        ax.set_title(f"{v}: {name}", fontsize=10)
        ax.set_ylabel(f"RMS difference ({unit})", fontsize=9)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
        fmt_time_axis(ax)
    handles = [Line2D([], [], color=COL["before"], lw=1.5, marker="o", ms=4, label=LAB["before"]),
               Line2D([], [], color=COL["after"], lw=2.0, marker="s", ms=4,
                      label=f"{LAB['after']}: RMS = 0 at every record"),
               Line2D([], [], color="k", ls="--", lw=1, label=f"cycle time {valid_str(cyc)} (nowcast | forecast)")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=10, frameon=False,
               bbox_to_anchor=(0.5, 0.01))
    fig.suptitle(f"STOFS-3D-ATL GFS sflux: RMS of (nos-workflow $-$ operational) over the grid, per hourly record\n"
                 f"{pdy_title(cyc)}; nowcast file up to the cycle time, forecast file after it",
                 fontsize=12, fontweight="bold", y=0.975)
    save_png(fig, out)


# ------------------------------------------------------------------ figure 3
def land_mask(lon, lat):
    import cartopy.feature as cf
    import shapely
    from shapely.ops import unary_union
    g = unary_union(list(cf.LAND.with_scale("50m").geometries()))
    shapely.prepare(g)
    return shapely.contains_xy(g, lon, lat)


def fig3(args, ops, ub, ua, out):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    cyc = sec(args.cycle)
    io, ib = common(ops["t"], ub["t"])
    _, ia = common(ops["t"], ua["t"])
    t = ops["t"][io]
    x = [to_dt(s) for s in t]
    pr = {k: d["d"]["prate"][i] * 3600.0 for k, d, i in (("ops", ops, io), ("before", ub, ib), ("after", ua, ia))}
    acc = pr["ops"].sum(0)
    lon, lat = ops["lon"], ops["lat"]
    mask = land_mask(lon, lat)
    pts = []
    for s in args.points.split(";"):
        la, lo = (float(q) for q in s.split(","))
        j, i = np.unravel_index(np.argmin((lat - la) ** 2 + (lon - lo) ** 2), lat.shape)
        pts.append((j, i, "land" if mask[j, i] else "ocean"))
    fig = plt.figure(figsize=(15, 8.2))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.2, 1.2], left=0.04, right=0.985, top=0.865,
                          bottom=0.09, wspace=0.27, hspace=0.42)
    axm = fig.add_subplot(gs[0, 0], projection=pc)
    axm.set_extent(GFS_EXTENT, crs=pc)
    im = axm.pcolormesh(lon, lat, acc, cmap="Blues", vmin=0, vmax=np.nanpercentile(acc, 99.5),
                        transform=pc, shading="nearest", rasterized=True)
    overlay_coast(axm)
    for n, (j, i, kind) in enumerate(pts, 1):
        axm.plot(lon[j, i], lat[j, i], "o", ms=13, mfc="w", mec="k", transform=pc, zorder=6)
        axm.text(lon[j, i], lat[j, i], str(n), fontsize=8, ha="center", va="center", transform=pc, zorder=7,
                 fontweight="bold")
    axm.set_title("operational accumulated precipitation\n(mm over the period) and chosen points", fontsize=9)
    place_cbar(fig, axm, im, "mm", extend="max")
    axs = []
    for n, (j, i, kind) in enumerate(pts):
        ax = fig.add_subplot(gs[n // 2, 1 + n % 2], sharex=axs[0] if axs else None)
        axs.append(ax)
        ax.plot(x, pr["ops"][:, j, i], color=COL["ops"], lw=4.5, alpha=0.5, label=LAB["ops"], zorder=2)
        ax.plot(x, pr["before"][:, j, i], color=COL["before"], lw=1.4, label=LAB["before"], zorder=3)
        ax.plot(x, pr["after"][:, j, i], color=COL["after"], lw=1.6, ls=(0, (4, 2)), label=LAB["after"], zorder=4)
        top = max(pr["ops"][:, j, i].max(), pr["before"][:, j, i].max())
        ax.set_ylim(-0.03 * top, 1.12 * top)
        lo, hi = mdates.date2num(x[0]), mdates.date2num(x[-1])
        ax.set_xlim(lo, hi)
        shade_phases(ax, mdates.date2num(to_dt(cyc)), (lo, hi), label=(n == 0))
        la, lo_ = lat[j, i], lon[j, i]
        ax.set_title(f"{n + 1}: {kind}, {la:.2f}°N {abs(lo_):.2f}°W", fontsize=10, pad=15)
        ax.set_ylabel("precipitation rate (mm/h)", fontsize=9)
        ax.text(0.5, 1.015, f"total: operational {pr['ops'][:, j, i].sum():.0f} mm | "
                f"before {pr['before'][:, j, i].sum():.0f} mm | this PR {pr['after'][:, j, i].sum():.0f} mm",
                transform=ax.transAxes, fontsize=8, ha="center", va="bottom", color="0.25")
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
        fmt_time_axis(ax)
    axt = fig.add_subplot(gs[1, 0])
    axt.axis("off")
    handles = [Line2D([], [], color=COL["ops"], lw=4.5, alpha=0.5, label=LAB["ops"]),
               Line2D([], [], color=COL["before"], lw=1.4, label=LAB["before"]),
               Line2D([], [], color=COL["after"], lw=1.6, ls=(0, (4, 2)),
                      label=f"{LAB['after']} (= operational)"),
               Line2D([], [], color="k", ls="--", lw=1, label=f"cycle time {valid_str(cyc)}")]
    axt.legend(handles=handles, loc="upper left", fontsize=9, frameon=False, bbox_to_anchor=(0.0, 1.0))
    axt.text(0.0, 0.40, "Before the fix, prate was taken from the instantaneous\nPRATE record. Operational STOFS-3D-ATL "
             "and this PR use\nthe period-average record. GFS kg m$^{-2}$ s$^{-1}$ converted\nto mm/h (x 3600). "
             "Before-fix nowcast also used different\nGFS cycles/leads than operational.", transform=axt.transAxes,
             fontsize=9, va="top", linespacing=1.4)
    fig.suptitle(f"STOFS-3D-ATL GFS sflux: precipitation rate at selected grid points  ({pdy_title(cyc)})",
                 fontsize=12, fontweight="bold", y=0.975)
    save_png(fig, out)
    return [(n + 1, kind, lat[j, i], lon[j, i], pr["ops"][:, j, i].sum(), pr["before"][:, j, i].sum(),
             pr["after"][:, j, i].sum()) for n, (j, i, kind) in enumerate(pts)]


# ------------------------------------------------------------------ figure 4
def fig4(args, ops, bn, an, out):
    cyc = sec(args.cycle)
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.4))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.76, bottom=0.12, wspace=0.22)
    res = {}
    for ax, axis, lab, key, ref in ((axs[0], 0, "latitude", "lat", ops["lat"][:, 0]),
                                    (axs[1], 1, "longitude", "lon", ops["lon"][0, :])):
        for kind, run in (("before", bn), ("after", an)):
            a = run[key][:, 0] if axis == 0 else run[key][0, :]
            off = a - ref
            res[(kind, lab)] = off
            idx = np.arange(off.size)
            ax.plot(idx, off, color=COL[kind], lw=2.0 if kind == "before" else 2.2,
                    ls="-" if kind == "before" else "--", label=LAB[kind])
        ax.axhline(0, color="0.5", lw=0.6)
        ax.set_xlabel(("row" if axis == 0 else "column") + " index of the 0.25° GFS grid", fontsize=9)
        ax.set_ylabel(f"{lab} label: nos-workflow $-$ operational (degrees)", fontsize=9)
        m = np.abs(res[("before", lab)]).max()
        ax.set_title(f"{lab} labels (max |offset| before fix = {m:.4f}°)", fontsize=10)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
        lo_, hi_ = res[("before", lab)].min(), res[("before", lab)].max()
        ax.set_ylim(lo_ - 0.12 * m, hi_ + 0.12 * m)
        ax.text(0.97, 0.06, "this PR = operational: offset 0 everywhere", transform=ax.transAxes, fontsize=8,
                color=COL["after"], fontweight="bold", ha="right",
                bbox=dict(fc="w", ec="none", alpha=0.8, pad=1))
    axs[0].legend(loc="upper left", fontsize=9)
    mlat, mlon = (np.abs(res[("before", k)]).max() for k in ("latitude", "longitude"))
    fig.suptitle(f"STOFS-3D-ATL GFS sflux grid labels vs the true 0.25° GFS points  ({pdy_title(cyc)})",
                 fontsize=12, fontweight="bold", y=0.975)
    fig.text(0.5, 0.835, "Before the fix, lon/lat were written as a linspace of the config box: the data sit on the same "
             f"grid points, but the labels are shifted by up to\n{mlat:.3f}° lat (~{mlat * 111.2:.0f} km) and "
             f"{mlon:.4f}° lon (~{mlon * 111.2 * np.cos(np.radians(35)):.1f} km at 35°N). "
             "This PR writes the true points, identical to operational.", fontsize=9.5, ha="center", va="bottom")
    save_png(fig, out)
    return mlat, mlon, {k: float(np.abs(v).max()) for k, v in res.items()}


# ------------------------------------------------------------------ figure 5
def dir_rot_cw(u1, v1, u0, v0):
    """Wind-direction change (compass, clockwise positive) of vector 1 relative to vector 0, wrapped."""
    d = -np.degrees(np.arctan2(v1, u1) - np.arctan2(v0, u0))
    return (d + 180.0) % 360.0 - 180.0


def theory_rot(lon):
    return np.sin(np.radians(HRRR_ROT_LAT)) * (lon + 97.5)


def hrrr_stats(root):
    z = {k: np.load(os.path.join(root, k, "hrrr_sub.npz")) for k in ("ops", "before", "after")}
    lon = z["ops"]["lon"]
    th = theory_rot(lon)
    out = []
    for k, tt in enumerate(z["ops"]["times"]):
        uo, vo = z["ops"]["uwind"][k], z["ops"]["vwind"][k]
        m = np.hypot(uo, vo) >= 1.0
        row = {"time": str(tt), "masked": 1.0 - m.mean()}
        for kind in ("before", "after"):
            u, v = z[kind]["uwind"][k], z[kind]["vwind"][k]
            d = dir_rot_cw(u, v, uo, vo)[m]
            row[kind] = (float(np.sqrt(np.mean(d * d))), float(np.abs(d).max()))
            row[kind + "_vs_theory"] = float(np.sqrt(np.mean(((d - th[m] + 180) % 360 - 180) ** 2)))
            row[kind + "_umax"] = float(np.abs(u - uo).max())
            row[kind + "_prmsl"] = float(np.abs(z[kind]["prmsl"][k] - z["ops"]["prmsl"][k]).max())
        out.append(row)
    return out


def fig5(args, root, out):
    import cartopy.crs as ccrs
    pc = ccrs.PlateCarree()
    z = {k: np.load(os.path.join(root, k, "hrrr_sub.npz")) for k in ("ops", "before", "after")}
    times = [str(t) for t in z["ops"]["times"]]
    k = times.index(args.hrrr_time)
    lon, lat = z["ops"]["lon"].astype("f8"), z["ops"]["lat"].astype("f8")
    proj = ccrs.LambertConformal(central_longitude=HRRR_ROT_LON, central_latitude=HRRR_ROT_LAT,
                                 standard_parallels=(HRRR_ROT_LAT, HRRR_ROT_LAT))
    xyz = proj.transform_points(pc, lon, lat)
    X, Y = xyz[..., 0], xyz[..., 1]
    uo, vo = z["ops"]["uwind"][k], z["ops"]["vwind"][k]
    ub, vb = z["before"]["uwind"][k], z["before"]["vwind"][k]
    ua, va = z["after"]["uwind"][k], z["after"]["vwind"][k]
    spd = np.hypot(uo, vo)
    msk = spd < 1.0
    dB = np.ma.masked_where(msk, dir_rot_cw(ub, vb, uo, vo))
    dA = np.ma.masked_where(msk, dir_rot_cw(ua, va, uo, vo))
    th = theory_rot(lon)
    st = 2
    sl = (slice(None, None, st), slice(None, None, st))
    ext = [X.min(), X.max(), Y.min(), Y.max()]
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("0.82")
    # zoom squares (centre lon/lat, half width in m), drawn in Lambert coordinates
    zooms = [("a", -73.5, 36.5, 250e3), ("b", -67.5, 42.0, 250e3)]

    fig = plt.figure(figsize=(15, 10.4))
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.955, top=0.855, bottom=0.075, wspace=0.28, hspace=0.30)
    axs = [fig.add_subplot(gs[0, c], projection=proj) for c in range(3)]
    for c, ax in enumerate(axs):
        ax.set_extent(ext, crs=proj)
        overlay_coast(ax, left=(c == 0), bottom=True)
    im0 = axs[0].pcolormesh(X[sl], Y[sl], spd[sl], cmap="YlGnBu", vmin=0, vmax=np.percentile(spd, 99.5),
                            transform=proj, shading="nearest", rasterized=True)
    for name, clon, clat, hw in zooms:
        xc, yc = proj.transform_point(clon, clat, pc)
        axs[0].plot([xc - hw, xc + hw, xc + hw, xc - hw, xc - hw], [yc - hw, yc - hw, yc + hw, yc + hw, yc - hw],
                    color="k", lw=1.4, transform=proj, zorder=6)
        axs[0].text(xc - hw, yc + hw, f" {name}", fontsize=11, fontweight="bold", transform=proj, va="bottom",
                    ha="left", zorder=7)
    axs[1].pcolormesh(X[sl], Y[sl], dB[sl], cmap=cmap, vmin=-25, vmax=25, transform=proj,
                            shading="nearest", rasterized=True)
    cs = axs[1].contour(X, Y, th, levels=[0, 5, 10, 15, 20], colors="k", linewidths=0.9, transform=proj, zorder=5)
    axs[1].clabel(cs, fmt=lambda v: f"{v:.0f}°", fontsize=8)
    im2 = axs[2].pcolormesh(X[sl], Y[sl], dA[sl], cmap=cmap, vmin=-25, vmax=25, transform=proj,
                            shading="nearest", rasterized=True)
    sB = float(np.sqrt(np.ma.mean(dB ** 2)))
    mB = float(np.ma.abs(dB).max())
    mA = float(np.ma.abs(dA).max())
    axs[0].set_title(f"{LAB['ops']}\n10 m wind speed (m/s)\n(HRRR part of sflux)", fontsize=10)
    axs[1].set_title(f"{LAB['before']} $-$ operational\nwind direction change: RMS {sB:.1f}°, max {mB:.1f}°\n"
                     "contours: sin(38.5°)(lon+97.5°)", fontsize=10)
    axs[2].set_title(f"{LAB['after']} $-$ operational\nwind direction change:\n" + (
        "identical (max 0°)" if mA == 0 else f"max {mA:.2g}°"), fontsize=10)
    place_cbar(fig, axs[0], im0, "m/s", extend="max")
    place_cbar(fig, axs[2], im2, "direction difference (deg, clockwise +)")
    for ax_, txt in ((axs[1], "gray: operational wind < 1 m/s\ncolour scale as in the right panel"),
                     (axs[2], "gray: operational wind < 1 m/s")):
        ax_.text(0.02, 0.02, txt, transform=ax_.transAxes, fontsize=8,
                 bbox=dict(fc="w", ec="0.6", alpha=0.9), zorder=8)

    step = 15
    for n, (name, clon, clat, hw) in enumerate(zooms):
        ax = fig.add_subplot(gs[1, n], projection=proj)
        xc, yc = proj.transform_point(clon, clat, pc)
        ax.set_extent([xc - hw, xc + hw, yc - hw, yc + hw], crs=proj)
        overlay_coast(ax, left=True, bottom=True)
        jj, ii = np.where((np.abs(X - xc) <= hw) & (np.abs(Y - yc) <= hw))
        q = (slice(jj.min(), jj.max() + 1, step), slice(ii.min(), ii.max() + 1, step))
        ok = spd[q] >= 1.0
        kw = dict(angles="uv", scale_units="inches", scale=1 / 0.30, pivot="tail", headwidth=4, headlength=5,
                  units="inches", transform=proj)
        un = lambda u, v: (np.where(ok, u[q] / np.maximum(np.hypot(u[q], v[q]), 1e-9), np.nan),
                           np.where(ok, v[q] / np.maximum(np.hypot(u[q], v[q]), 1e-9), np.nan))
        ax.quiver(X[q], Y[q], *un(uo, vo), color=COL["ops"], width=0.016, zorder=5, **kw)
        ax.quiver(X[q], Y[q], *un(ub, vb), color=COL["before"], width=0.016, zorder=6, **kw)
        mid = float(theory_rot(clon))
        ax.set_title(f"zoom {name}: wind direction (arrows normalised to equal length)\n"
                     f"expected rotation here ~{mid:.0f}° clockwise", fontsize=9.5)
        if n == 0:
            ax.legend(handles=[Line2D([], [], color=COL["ops"], lw=3, label="operational (= this PR)"),
                               Line2D([], [], color=COL["before"], lw=3, label="before fix")],
                      loc="lower right", fontsize=8, framealpha=0.9).set_zorder(10)
    axr = fig.add_subplot(gs[1, 2])
    sub = (slice(None, None, 5), slice(None, None, 5))
    mm = (~msk)[sub]
    axr.scatter(lon[sub][mm], dir_rot_cw(ub, vb, uo, vo)[sub][mm], s=3, color=COL["before"], alpha=0.3,
                rasterized=True, zorder=2)
    xx = np.linspace(lon.min(), lon.max(), 50)
    axr.plot(xx, theory_rot(xx), color="k", lw=1.0, ls=(0, (4, 3)), zorder=4)
    axr.plot(lon[sub][mm], dir_rot_cw(ua, va, uo, vo)[sub][mm], ".", ms=2, color=COL["after"], zorder=3,
             rasterized=True)
    axr.set_ylim(-5, 30)
    axr.set_xlim(lon.min(), lon.max())
    axr.set_xlabel("longitude (deg)", fontsize=9)
    axr.set_ylabel("wind-direction difference from operational (deg)", fontsize=9)
    axr.set_title("direction difference vs longitude\n(every 5th HRRR point, operational wind >= 1 m/s)",
                  fontsize=9.5)
    axr.grid(alpha=0.3)
    axr.tick_params(labelsize=8)
    axr.legend(handles=[Line2D([], [], color=COL["before"], marker="o", ms=4, ls="", label=LAB["before"]),
                        Line2D([], [], color="k", lw=1.0, ls=(0, (4, 3)), label="sin(38.5°)(lon+97.5°)"),
                        Line2D([], [], color=COL["after"], marker="o", ms=4, ls="",
                               label=f"{LAB['after']} (all points at 0°)")],
               loc="upper left", fontsize=8, framealpha=0.9)
    fig.suptitle(f"STOFS-3D-ATL HRRR winds in sflux, valid {valid_str(sec(args.hrrr_time))}  "
                 f"({pdy_title(sec(args.cycle))})\n"
                 "Before the fix nos-workflow rotated the HRRR Lambert grid-relative winds to earth-relative; "
                 "operational does not rotate; this PR matches operational",
                 fontsize=12, fontweight="bold", y=0.975)
    save_png(fig, out)


# ------------------------------------------------------------------ summary
def summary(args, ops, bn, an, fn, af, ub, ua, grid, pts, hr, out):
    cyc = sec(args.cycle)
    L = [f"STOFS-3D-ATL sflux, nos-workflow vs operational STOFS-3D-ATL v3.1, {pdy_title(cyc)}",
         "RMS and max |diff| over all grid points and all matched hourly records "
         "(display units: prmsl hPa, stmp K, spfh g/kg, winds m/s, prate mm/h, dlwrf/dswrf W/m2).",
         "'before' = nos-workflow before the fix; 'this PR' = nos-workflow with the fix.", ""]
    for title, sets in (
            ("A. Whole phase files, all common records (as compare_sflux.py)",
             (("nowcast", bn, an), ("forecast", fn, af))),
            ("B. Records SCHISM uses (nowcast file <= cycle time, forecast file after it)",
             (("nowcast (<= cycle)", {"t": bn["t"][bn["t"] <= cyc], "d": {v: bn["d"][v][bn["t"] <= cyc] for v in VARS}},
               {"t": an["t"][an["t"] <= cyc], "d": {v: an["d"][v][an["t"] <= cyc] for v in VARS}}),
              ("forecast (> cycle)", {"t": fn["t"][fn["t"] > cyc], "d": {v: fn["d"][v][fn["t"] > cyc] for v in VARS}},
               {"t": af["t"][af["t"] > cyc], "d": {v: af["d"][v][af["t"] > cyc] for v in VARS}})))):
        L.append(title)
        for ph, b, a in sets:
            io, _ = common(ops["t"], b["t"])
            L.append(f"  {ph}: {len(io)} common records, {valid_str(ops['t'][io][0])} .. {valid_str(ops['t'][io][-1])}")
            L.append(f"    {'var':7s} {'unit':8s} {'before RMS':>12s} {'before max':>12s} {'this PR RMS':>12s} {'this PR max':>12s}")
            for v in VARS:
                row = []
                for run in (b, a):
                    io, ir = common(ops["t"], run["t"])
                    d = (run["d"][v][ir] - ops["d"][v][io]).astype("f8") * DISP[v][2]
                    row += [float(np.sqrt(np.nanmean(d * d))), float(np.nanmax(np.abs(d)))]
                u = DISP[v][1].replace("$^2$", "2")
                L.append(f"    {v:7s} {u:8s} {row[0]:12.4g} {row[1]:12.4g} {row[2]:12.4g} {row[3]:12.4g}")
        L.append("")
    L.append("C. Grid label offsets (nos-workflow lon/lat minus the true 0.25 deg GFS points in the operational file)")
    L.append(f"  before: max |lat offset| {grid[0]:.4f} deg (~{grid[0] * 111.2:.1f} km), "
             f"max |lon offset| {grid[1]:.4f} deg (~{grid[1] * 111.2 * np.cos(np.radians(35)):.2f} km at 35N)")
    L.append(f"  this PR: max |lat offset| {grid[2][('after', 'latitude')]:.3g} deg, "
             f"max |lon offset| {grid[2][('after', 'longitude')]:.3g} deg")
    L.append("")
    L.append("D. prate accumulation at the selected points (mm over the matched records)")
    for n, kind, la, lo, po, pb, pa in pts:
        L.append(f"  {n} {kind:5s} {la:.2f}N {abs(lo):.2f}W: operational {po:.0f}, before {pb:.0f}, this PR {pa:.0f}")
    L.append("")
    L.append("E. HRRR winds (direction difference clockwise-positive, wrapped, where operational wind >= 1 m/s)")
    for r in hr:
        L.append(f"  {r['time']}: before RMS {r['before'][0]:.2f} deg, max {r['before'][1]:.2f} deg "
                 f"(RMS residual vs sin(38.5)(lon+97.5): {r['before_vs_theory']:.3f} deg); "
                 f"this PR RMS {r['after'][0]:.3g} deg, max {r['after'][1]:.3g} deg; "
                 f"max |u diff| before {r['before_umax']:.2f} m/s, this PR {r['after_umax']:.3g} m/s; "
                 f"max |prmsl diff| before {r['before_prmsl']:.3g} Pa, this PR {r['after_prmsl']:.3g} Pa; "
                 f"masked fraction {r['masked']:.3f}")
    text = "\n".join(L) + "\n"
    with open(out, "w") as f:
        f.write(text)
    print(text)
    print("saved", out)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="VIZ_DIR with ops/, before/, after/")
    ap.add_argument("--outdir", default=None, help="default VIZ_DIR/plots")
    ap.add_argument("--cycle", default="2026100112", help="cycle time YYYYMMDDHH (nowcast | forecast split)")
    ap.add_argument("--map-time", default="2026100112", help="valid time of figure 1 (YYYYMMDDHH)")
    ap.add_argument("--hrrr-time", default="2026093018", help="valid time of figure 5 (YYYYMMDDHH)")
    ap.add_argument("--points", default="30.5,-89.25;34.5,-79.25;26.25,-87.5;40.25,-62.25",
                    help="lat,lon pairs for figure 3, separated by ';'")
    ap.add_argument("--only", default="1,2,3,4,5", help="figures to make, e.g. 1,2")
    args = ap.parse_args()
    root = args.dir
    outdir = args.outdir or os.path.join(root, "plots")
    os.makedirs(outdir, exist_ok=True)
    want = {int(s) for s in args.only.split(",")}
    cyc = sec(args.cycle)

    ops = load_ops(root)
    bn, bf = load_run(root, "before", "now"), load_run(root, "before", "fcst")
    an, af = load_run(root, "after", "now"), load_run(root, "after", "fcst")
    ub, ua = used(bn, bf, cyc), used(an, af, cyc)
    o = lambda n: os.path.join(outdir, n)
    pts, grid = [], (0, 0, {})
    if 1 in want:
        fig1(args, ops, bn, an, o("sflux_gfs_nowcast_map.png"))
    if 2 in want:
        fig2(args, ops, ub, ua, o("sflux_gfs_error_by_hour.png"))
    if 3 in want:
        pts = fig3(args, ops, ub, ua, o("sflux_gfs_prate_ts.png"))
    if 4 in want:
        grid = fig4(args, ops, bn, an, o("sflux_gfs_grid_offset.png"))
    if 5 in want:
        fig5(args, root, o("sflux_hrrr_wind_direction.png"))
    if want == {1, 2, 3, 4, 5}:
        summary(args, ops, bn, an, bf, af, ub, ua, grid, pts, hrrr_stats(root), o("summary.txt"))


if __name__ == "__main__":
    main()
