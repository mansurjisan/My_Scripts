"""Shared helpers for the plot_obc_*.py scripts (STOFS-3D-ATL open-boundary files).

Each data file is given as PATH:YYYYMMDDHH, the absolute UTC time of the
file's time=0 (as in compare_th3d.py). Several PATH:YYYYMMDDHH items can be
given for one series (e.g. nowcast + forecast); records are merged on the
absolute time axis and a later file overrides an earlier one where they overlap.
Differences are only taken at records whose absolute times match exactly.
"""
import csv
import os
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import numpy as np
from netCDF4 import Dataset

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
UNITS = {"TEM": "degC", "SAL": "psu", "uv": "m/s"}
NAMES = {"ops": "operational STOFS-3D-ATL",
         "ours": "nos-workflow (nos-utils)",
         "before": "nos-workflow before ops-parity fix"}
COLORS = {"ops": "tab:blue", "ours": "tab:red", "before": "tab:gray"}
NODE_COLORS = ["tab:blue", "tab:orange", "tab:green", "tab:purple", "tab:brown"]
DEFAULT_NODES = "8,200,500,728,766"   # shelf S, deep, deep, shelf N, Belle Isle


def parse_dt(s):
    return datetime.strptime(s, "%Y%m%d%H").replace(tzinfo=timezone.utc)


def to_dt(sec):
    return EPOCH + timedelta(seconds=float(sec))


def detect_var(path, override="auto"):
    if override and override != "auto":
        return override
    b = os.path.basename(path).upper()
    return "TEM" if "TEM" in b else "SAL" if "SAL" in b else "uv" if "UV" in b else "TEM"


def metric(ts, var, comp):
    """Collapse the component axis of (..., C) to one scalar field."""
    if ts.shape[-1] == 1:
        return ts[..., 0]
    if var == "uv" and comp is None:
        return np.hypot(ts[..., 0], ts[..., 1])
    return ts[..., 0 if comp is None else comp]


def load_series(args, var="elev", comp=None, level=None, nodes=None):
    """Merge PATH:YYYYMMDDHH items -> (abs_seconds[T], data) with data (T, N) for
    elev, (T, N, L) for 3D (or (T, N) if level is an int). Only the requested
    nodes/level are kept in memory."""
    if isinstance(args, str):
        args = [args]
    recs = {}
    for a in args:
        path, start = a.rsplit(":", 1)
        t0 = (parse_dt(start) - EPOCH).total_seconds()
        with Dataset(path) as ds:
            t = np.asarray(ds["time"][:], dtype="f8")
            v = ds["time_series"]
            for j, s in enumerate(t):
                x = np.ma.filled(v[j], np.nan).astype("f8")        # (N, L, C)
                x = metric(x, var, comp)                            # (N, L)
                if nodes is not None:
                    x = x[nodes]
                if var == "elev":
                    x = x[..., 0]
                elif level is not None:
                    x = x[..., level]
                recs[round(t0 + s)] = x
    keys = np.array(sorted(recs))
    return keys, np.array([recs[k] for k in keys])


def common(ta, tb):
    """Index pairs of records with identical absolute times."""
    ib = {int(k): i for i, k in enumerate(tb)}
    pairs = [(i, ib[int(k)]) for i, k in enumerate(ta) if int(k) in ib]
    if not pairs:
        raise SystemExit("no common record times between the series")
    a, b = zip(*pairs)
    return np.array(a), np.array(b)


def load_nodes(csv_path, nmax=778):
    """lon, lat, depth, seg of the elevation/3D nodes (segments 1-2, file order)."""
    rows = [r for r in csv.DictReader(open(csv_path)) if int(r["seg"]) in (1, 2)][:nmax]
    return (np.array([float(r["lon"]) for r in rows]),
            np.array([float(r["lat"]) for r in rows]),
            np.array([float(r["depth"]) for r in rows]),
            np.array([int(r["seg"]) for r in rows]))


def stats(d):
    d = d[np.isfinite(d)]
    if d.size == 0:
        return 0.0, 0.0
    return float(np.max(np.abs(d))), float(np.sqrt(np.mean(d * d)))


def fmt(x):
    return f"{x:.3g}"


def shade_phases(ax, cycle, xlim, label=True):
    """Faint nowcast/forecast shading, dashed divider at the cycle time, text labels."""
    lo, hi = xlim
    if cycle is None:
        return
    ax.axvspan(lo, cycle, color="tab:blue", alpha=0.05, lw=0)
    ax.axvspan(cycle, hi, color="tab:orange", alpha=0.07, lw=0)
    ax.axvline(cycle, color="k", ls="--", lw=1.0)
    if label:
        tr = ax.get_xaxis_transform()
        ax.text(lo + (cycle - lo) * 0.5, 0.97, "nowcast", transform=tr, ha="center",
                va="top", fontsize=9, color="dimgray",
                bbox=dict(fc="w", ec="none", alpha=0.7, pad=1))
        ax.text(cycle + (hi - cycle) * 0.5, 0.97, "forecast", transform=tr, ha="center",
                va="top", fontsize=9, color="dimgray",
                bbox=dict(fc="w", ec="none", alpha=0.7, pad=1))


def fmt_time_axis(ax, fig=None):
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %HZ"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    for l in ax.get_xticklabels():
        l.set_rotation(20); l.set_ha("right")


def node_label(i, lon, lat, depth, seg):
    return (f"node {i} (bnd {seg}): {abs(lon):.2f}{'W' if lon < 0 else 'E'} "
            f"{lat:.2f}N, depth {depth:.0f} m")


def cycle_label(cycle):
    return f"cycle {cycle:%Y-%m-%d %H}Z"


def save(fig, out):
    """Save at dpi=100 (figsize <= 16 in) with no metadata."""
    fig.savefig(out, dpi=100, metadata={"Software": None})
    print("saved", out)


def add_coast(ax, extent):
    import cartopy.crs as ccrs
    import cartopy.feature as cf
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cf.OCEAN.with_scale("10m"), facecolor="#e6f0f7", zorder=0)
    ax.add_feature(cf.LAND.with_scale("10m"), facecolor="0.75", zorder=1)
    ax.add_feature(cf.COASTLINE.with_scale("10m"), edgecolor="0.25", lw=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.5)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}
    return gl


MAIN_EXTENT = [-67, -47, 5, 49]


def boundary_map(out, lon, lat, seg, times, O, U, unit, name, title, cmap="viridis",
                 symmetric=False, vmin=None, vmax=None, cycle=None):
    """ops / ours / diff maps on the boundary nodes, one row per common time.

    O, U: (n_snap, N). Main boundary in the left sub-panel, Belle Isle strait in
    the right sub-panel of each cell. Ops/ours share one colour scale; the diff
    scale is symmetric and auto-scaled to the actual max |diff| over all rows."""
    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt
    pc = ccrs.PlateCarree()
    D = U - O
    dmax = max(float(np.nanmax(np.abs(D))), 1e-12)
    if vmin is None or vmax is None:
        lo = float(min(np.nanmin(O), np.nanmin(U))); hi = float(max(np.nanmax(O), np.nanmax(U)))
        if symmetric:
            hi = max(abs(lo), abs(hi)); lo = -hi
        if hi - lo < 1e-12:
            lo, hi = lo - 1e-6, hi + 1e-6
        vmin, vmax = lo, hi
    n = len(times)
    b2 = seg == 2
    bi_ext = ([lon[b2].min() - 1.0, lon[b2].max() + 1.0, lat[b2].min() - 0.7, lat[b2].max() + 0.7]
              if b2.any() else [-58.6, -54.0, 51.0, 53.0])
    fig = plt.figure(figsize=(16, min(16, 4.6 * n + 1.8)))
    gs = fig.add_gridspec(n, 3, left=0.04, right=0.98, top=0.90, bottom=0.08,
                          hspace=0.22, wspace=0.12)
    cols = [[], [], []]
    mains = [None, None, None]
    for r in range(n):
        for c, (dat, ttl, cm, lo, hi) in enumerate([
                (O[r], oc_name("ops"), cmap, vmin, vmax),
                (U[r], oc_name("ours"), cmap, vmin, vmax),
                (D[r], "nos-workflow minus operational", "bwr", -dmax, dmax)]):
            sub = gs[r, c].subgridspec(1, 2, width_ratios=[1, 1.25], wspace=0.08)
            axm = fig.add_subplot(sub[0], projection=pc)
            axb = fig.add_subplot(sub[1], projection=pc)
            add_coast(axm, MAIN_EXTENT); add_coast(axb, bi_ext)
            for ax, s, sel in ((axm, 9, slice(None)), (axb, 40, seg == 2)):
                sc = ax.scatter(lon[sel], lat[sel], c=dat[sel], s=s, cmap=cm, vmin=lo, vmax=hi,
                                transform=pc, zorder=3, edgecolors="none")
            axm.set_title(f"{ttl}\n{times[r]:%Y-%m-%d %H}Z" + ("  (cycle)" if cycle == times[r] else ""),
                          fontsize=9, loc="left")
            axb.set_title("Strait of Belle Isle", fontsize=8)
            if c == 2:
                mx, rm = stats(D[r])
                axb.text(0.02, 0.03, f"max |diff| = {fmt(mx)} {unit}\nRMS = {fmt(rm)} {unit}",
                         transform=axb.transAxes, fontsize=8, va="bottom", zorder=5,
                         bbox=dict(fc="w", ec="0.6", alpha=0.9))
            cols[c] += [axm, axb]; mains[c] = sc
    labs = [f"{name} ({unit})", f"{name} ({unit})",
            f"difference ({unit}), symmetric colour scale auto-scaled to max |diff| = {fmt(dmax)}"]
    for c in range(3):
        cb = fig.colorbar(mains[c], ax=cols[c], orientation="horizontal", fraction=0.025,
                          pad=0.05, aspect=30)
        if c == 2:
            from matplotlib.ticker import FormatStrFormatter
            cb.formatter = FormatStrFormatter("%.2g"); cb.update_ticks()
        cb.set_label(labs[c], fontsize=8); cb.ax.tick_params(labelsize=7)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.97)
    save(fig, out)
    return dmax


def oc_name(k):
    return NAMES[k]
