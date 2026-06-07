#!/usr/bin/env python3
"""
Wind speed comparison for the latest SECOFS run (cycle 20260604):
SCHISM sflux (HRRR nest) vs UFS-coastal DATM forcing (blended GFS+HRRR),
one 3-panel frame per matched timestep.

  Left   : SCHISM sflux (HRRR)   (uwind/vwind from sflux_air_2.*.nc, HRRR nest grid)
  Middle : UFS DATM (blended)    (UGRD/VGRD_10maboveground from datm_forcing.nc, native blended grid)
  Right  : Difference            (DATM regridded onto the sflux grid, DATM - sflux)

The two products live on different grids (sflux=HRRR nest 745x630, DATM=blended 0.025 deg),
so the difference panel interpolates the DATM field onto the sflux grid before subtracting.
Consistent colorbars across all frames.
"""

import sys
import tarfile
import argparse
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from netCDF4 import Dataset, num2date
from scipy.interpolate import RegularGridInterpolator

# ---- defaults (used with NO CLI args; the original E: V21 example run) -------
DEFAULT_DATM = ("/mnt/e/secofs_com_outs/PYTHON_V14/V21/"
                "secofs_ufs.t06z.datm_input/datm_forcing.nc")
DEFAULT_SFLUX_SRC = "/mnt/e/secofs_com_outs/PYTHON_V14/V21"
DEFAULT_OUT_BASE = "/mnt/e/secofs_com_outs/comparison_v390_vs_python"
DEFAULT_CYC, DEFAULT_PDY = 6, "20260606"

# Populated by _apply_args() before main() runs; CLI args override the defaults.
#   nest 1 = GFS  (sflux_air_1, met.*.nc.tar,   coarse 0.5 deg)
#   nest 2 = HRRR (sflux_air_2, met.*.nc.2.tar, fine 3km)
SFLUX_SRC = DATM_FILE = OUT = CYCLE = None
SFLUX_TARS = []
SFLUX_NEST = 2
SFLUX_LABEL = "HRRR"

MATCH_TOL_HOURS = 0.5   # match sflux<->DATM timesteps within 30 min
FRAME_STRIDE_HOURS = 3  # emit a frame roughly every 3 hours


def _apply_args():
    """Parse CLI args and populate the module globals used throughout."""
    global SFLUX_SRC, DATM_FILE, OUT, CYCLE, SFLUX_TARS, SFLUX_NEST, SFLUX_LABEL
    global FRAME_STRIDE_HOURS
    ap = argparse.ArgumentParser(
        description="3-panel SCHISM-sflux vs UFS-DATM wind-speed comparison frames.")
    ap.add_argument("--datm", default=DEFAULT_DATM, help="path to datm_forcing.nc")
    ap.add_argument("--sflux-src", default=DEFAULT_SFLUX_SRC,
                    help="dir with the <prefix>.t<cyc>z.<pdy>.met.*.tar files")
    ap.add_argument("--cyc", type=int, default=DEFAULT_CYC, help="cycle hour")
    ap.add_argument("--pdy", default=DEFAULT_PDY, help="YYYYMMDD")
    ap.add_argument("--nest", type=int, choices=(1, 2), default=2,
                    help="1=GFS sflux_air_1, 2=HRRR sflux_air_2 (default 2)")
    ap.add_argument("--sflux-prefix", default="secofs",
                    help="sflux tar prefix (default 'secofs')")
    ap.add_argument("--out", default=None,
                    help="output dir (default <OUT_BASE>/sflux<nest>_<label>_vs_datm_<pdy>_<cyc>z)")
    ap.add_argument("--stride-hours", type=float, default=FRAME_STRIDE_HOURS,
                    help="emit a frame every N hours (default 3)")
    a = ap.parse_args()
    SFLUX_NEST = a.nest
    SFLUX_LABEL = "GFS" if a.nest == 1 else "HRRR"
    suffix = "" if a.nest == 1 else ".2"
    SFLUX_SRC = Path(a.sflux_src)
    DATM_FILE = Path(a.datm)
    CYCLE = datetime.strptime(a.pdy, "%Y%m%d") + timedelta(hours=a.cyc)
    FRAME_STRIDE_HOURS = a.stride_hours
    SFLUX_TARS = [
        f"{a.sflux_prefix}.t{a.cyc:02d}z.{a.pdy}.met.nowcast.nc{suffix}.tar",
        f"{a.sflux_prefix}.t{a.cyc:02d}z.{a.pdy}.met.forecast.nc{suffix}.tar",
    ]
    OUT = Path(a.out) if a.out else (
        Path(DEFAULT_OUT_BASE)
        / f"sflux{a.nest}_{SFLUX_LABEL.lower()}_vs_datm_{a.pdy}_{a.cyc:02d}z")


def extract(tar_path):
    tmp = tempfile.mkdtemp(prefix="sflux_")
    with tarfile.open(str(tar_path)) as tf:
        tf.extractall(tmp, filter="data")
    return Path(tmp)


def load_comf(tar_names):
    """Concatenate sflux_air_2 uwind/vwind across the listed sflux tars."""
    times, us, vs = [], [], []
    lon = lat = None
    for tn in tar_names:
        tar = SFLUX_SRC / tn
        if not tar.exists():
            print(f"  [skip] missing {tar}")
            continue
        d = extract(tar)
        for p in sorted(d.glob(f"sflux_air_{SFLUX_NEST}.*.nc")):
            ds = Dataset(str(p))
            if lon is None:
                lon = np.array(ds.variables["lon"][:])
                lat = np.array(ds.variables["lat"][:])
            tvar = ds.variables["time"]
            tdt = num2date(tvar[:], tvar.units,
                           only_use_cftime_datetimes=False,
                           only_use_python_datetimes=True)
            times.append(np.array(tdt))
            us.append(np.array(ds.variables["uwind"][:]))
            vs.append(np.array(ds.variables["vwind"][:]))
            ds.close()
    return {
        "time": np.concatenate(times),
        "u": np.concatenate(us, axis=0),
        "v": np.concatenate(vs, axis=0),
        "lon": lon, "lat": lat,
    }


def load_datm(path):
    """Read blended UGRD/VGRD plus coords + time from the UFS DATM file."""
    ds = Dataset(str(path))
    uname = "UGRD_10maboveground" if "UGRD_10maboveground" in ds.variables else None
    vname = "VGRD_10maboveground" if "VGRD_10maboveground" in ds.variables else None
    if uname is None:  # fall back to any u/v 10m naming
        for cand in ("uwind", "u10", "Uwind", "UGRD"):
            if cand in ds.variables:
                uname = cand
                break
        for cand in ("vwind", "v10", "Vwind", "VGRD"):
            if cand in ds.variables:
                vname = cand
                break
    lonv = ds.variables["longitude"] if "longitude" in ds.variables else ds.variables["lon"]
    latv = ds.variables["latitude"] if "latitude" in ds.variables else ds.variables["lat"]
    lon = np.array(lonv[:])
    lat = np.array(latv[:])
    tvar = ds.variables["time"]
    tdt = num2date(tvar[:], tvar.units,
                   only_use_cftime_datetimes=False,
                   only_use_python_datetimes=True)
    src = np.array(ds.variables["data_source"][:]) if "data_source" in ds.variables else None
    # NOTE: do NOT load full UGRD/VGRD (5.5 GB file -> ~1.4 GB + page-cache blowup
    # over the /mnt drvfs mount can wedge WSL2). Keep the dataset open and read
    # one timestep at a time in the frame loop; caller closes it.
    return {"time": np.array(tdt), "ds": ds, "uname": uname, "vname": vname,
            "lon": lon, "lat": lat, "src": src}


def datm_uv(p, i):
    """Read a single DATM timestep's (u, v) as float64 (small hyperslab read)."""
    u = np.asarray(p["ds"].variables[p["uname"]][i], dtype=np.float64)
    v = np.asarray(p["ds"].variables[p["vname"]][i], dtype=np.float64)
    return u, v


def axes_1d(lon2d, lat2d):
    """Return (lon_axis, lat_axis, increasing_flags) for a regular 2D coord pair."""
    if lon2d.ndim == 1:
        return lon2d, lat2d
    lon_axis = lon2d[0, :]
    lat_axis = lat2d[:, 0]
    return lon_axis, lat_axis


def regrid_to_comf(datm_field, datm_lon, datm_lat, comf_lon, comf_lat):
    """Interpolate a DATM (y,x) field onto COMF grid points. DATM is regular lat/lon."""
    lon_axis, lat_axis = axes_1d(datm_lon, datm_lat)
    # RegularGridInterpolator needs strictly increasing axes
    flip_lat = lat_axis[0] > lat_axis[-1]
    flip_lon = lon_axis[0] > lon_axis[-1]
    la = lat_axis[::-1] if flip_lat else lat_axis
    lo = lon_axis[::-1] if flip_lon else lon_axis
    f = datm_field
    if flip_lat:
        f = f[::-1, :]
    if flip_lon:
        f = f[:, ::-1]
    interp = RegularGridInterpolator((la, lo), f, bounds_error=False, fill_value=np.nan)
    pts = np.stack([comf_lat.ravel(), comf_lon.ravel()], axis=-1)
    return interp(pts).reshape(comf_lon.shape)


def match_times(t_comf, t_datm, tol_hours):
    pairs = []
    for i, tc in enumerate(t_comf):
        best_j, best_d = None, None
        for j, td in enumerate(t_datm):
            d = abs((tc - td).total_seconds()) / 3600.0
            if best_d is None or d < best_d:
                best_d, best_j = d, j
        if best_d is not None and best_d < tol_hours:
            pairs.append((i, best_j))
    return pairs


def main():
    if not DATM_FILE.exists():
        sys.exit(f"DATM file not present yet: {DATM_FILE}")
    OUT.mkdir(parents=True, exist_ok=True)

    print("Loading SCHISM sflux_air_2 (HRRR) ...")
    c = load_comf(SFLUX_TARS)
    # nowcast/forecast sflux tars OVERLAP in time, and carry DIFFERENT data at
    # the overlap (each prep phase pulls its own GFS cycle -- can differ by
    # several m/s). The DATM file is the forecast-phase product, so prefer the
    # forecast-phase sflux (last tar listed) at overlapping timestamps; keeping
    # the nowcast one produces a spurious non-zero diff in the GFS region.
    last_idx = {}
    for i, t in enumerate(c["time"]):
        last_idx[t.replace(microsecond=0)] = i   # later tar overwrites -> forecast wins
    order = np.array([last_idx[k] for k in sorted(last_idx)])
    c["time"], c["u"], c["v"] = c["time"][order], c["u"][order], c["v"][order]
    print(f"  sflux: {len(c['time'])} unique steps, grid {c['u'].shape[1:]}, "
          f"{c['time'][0]} .. {c['time'][-1]}")

    print("Loading UFS DATM forcing ...")
    p = load_datm(DATM_FILE)
    print(f"  DATM: {len(p['time'])} steps, grid {p['lon'].shape}, "
          f"{p['time'][0]} .. {p['time'][-1]}")

    # --- date-coverage sanity check -------------------------------------------
    overlap_lo = max(c["time"][0], p["time"][0])
    overlap_hi = min(c["time"][-1], p["time"][-1])
    if overlap_hi < overlap_lo:
        print("\n*** WARNING: sflux and DATM time windows DO NOT OVERLAP ***")
        print(f"    sflux: {c['time'][0]} .. {c['time'][-1]}")
        print(f"    DATM:  {p['time'][0]} .. {p['time'][-1]}")
        print("    The two products are from different cycles -- "
              "differences would be meaningless. Aborting.")
        sys.exit(2)
    print(f"  Overlap window: {overlap_lo} .. {overlap_hi}")

    matches = match_times(c["time"], p["time"], MATCH_TOL_HOURS)
    print(f"Matched timesteps: {len(matches)}")
    if not matches:
        sys.exit("No matching timesteps within tolerance.")

    # stride to ~FRAME_STRIDE_HOURS
    if len(matches) > 1:
        dt_h = abs((c["time"][matches[1][0]] - c["time"][matches[0][0]]).total_seconds()) / 3600.0
        step = max(1, round(FRAME_STRIDE_HOURS / dt_h)) if dt_h > 0 else 1
    else:
        step = 1
    selected = matches[::step]
    print(f"Selected {len(selected)} frames (stride={step})")

    comf_lon, comf_lat = c["lon"], c["lat"]

    # DATM cells inside the sflux footprint -- used to gauge effective resolution
    win = ((p["lon"] >= float(comf_lon.min())) & (p["lon"] <= float(comf_lon.max())) &
           (p["lat"] >= float(comf_lat.min())) & (p["lat"] <= float(comf_lat.max())))
    # sharpness (mean |grad ws|) cleanly separates HRRR (~0.2) from GFS fallback (~0.07)
    SHARP_THRESH = 0.13

    # precompute regridded DATM ws + global scales
    print("Regridding DATM -> COMF grid for each selected frame ...")
    ws_comf, ws_datm_native, ws_datm_on_comf, datm_src = [], [], [], []
    for ic, ip in selected:
        wc = np.hypot(c["u"][ic].astype(np.float64), c["v"][ic].astype(np.float64))
        up, vp = datm_uv(p, ip)
        wd_native = np.hypot(up, vp)
        wd_on_comf = regrid_to_comf(wd_native, p["lon"], p["lat"], comf_lon, comf_lat)
        gy, gx = np.gradient(np.where(win, wd_native, np.nan))
        sharp = float(np.nanmean(np.hypot(gy, gx)))
        datm_src.append("HRRR (fine)" if sharp > SHARP_THRESH else "GFS fallback (coarse)")
        ws_comf.append(wc)
        ws_datm_native.append(wd_native)
        ws_datm_on_comf.append(wd_on_comf)

    ws_vmax = np.ceil(max(
        max(np.nanmax(a) for a in ws_comf),
        max(np.nanmax(a) for a in ws_datm_native),
    ))
    diff_max = max(np.nanmax([np.nanmax(np.abs(d - c_)) for d, c_ in
                              zip(ws_datm_on_comf, ws_comf)]), 0.1)
    diff_max = np.ceil(diff_max * 10) / 10
    print(f"Wind speed range: [0, {ws_vmax:.1f}] m/s; diff +/- {diff_max:.2f} m/s")

    d_lon, d_lat = p["lon"], p["lat"]
    # Coarsened HRRR/GFS boundary for the overlay contour: the full 1721^2
    # contour exceeds the memory cap, and the boundary is smooth, so a 4x
    # stride is plenty. Computed once (data_source is time-invariant).
    if p["src"] is not None:
        cs = slice(None, None, 4)
        src_c, slon_c, slat_c = p["src"][cs, cs], p["lon"][cs, cs], p["lat"][cs, cs]
    else:
        src_c = slon_c = slat_c = None
    for frame, (ic, ip) in enumerate(selected):
        tc = c["time"][ic]
        vt_str = tc.strftime("%Y-%m-%d %H:%MZ")
        stage = "Nowcast" if tc <= CYCLE else "Forecast"

        wc = ws_comf[frame]
        wd = ws_datm_native[frame]
        diff = ws_datm_on_comf[frame] - wc
        rmse = float(np.sqrt(np.nanmean(diff ** 2)))

        fig, axes = plt.subplots(1, 3, figsize=(21, 6), constrained_layout=True)

        im0 = axes[0].pcolormesh(comf_lon, comf_lat, wc, vmin=0, vmax=ws_vmax,
                                 cmap="YlOrRd", shading="auto")
        axes[0].set_title(f"SCHISM sflux ({SFLUX_LABEL})", fontsize=12)
        plt.colorbar(im0, ax=axes[0], label="Wind Speed (m/s)", fraction=0.046, pad=0.04)

        im1 = axes[1].pcolormesh(d_lon, d_lat, wd, vmin=0, vmax=ws_vmax,
                                 cmap="YlOrRd", shading="auto")
        axes[1].set_title(f"UFS DATM (blended) - source: {datm_src[frame]}", fontsize=12)
        plt.colorbar(im1, ax=axes[1], label="Wind Speed (m/s)", fraction=0.046, pad=0.04)

        im2 = axes[2].pcolormesh(comf_lon, comf_lat, diff, vmin=-diff_max, vmax=diff_max,
                                 cmap="bwr", shading="auto")
        axes[2].set_title(f"Difference (RMSE={rmse:.3f} m/s)", fontsize=12)
        plt.colorbar(im2, ax=axes[2], label="DATM - sflux (m/s)", fraction=0.046, pad=0.04)

        # Overlay HRRR/GFS boundary (data_source=0.5 contour). Inside the line the
        # DATM uses HRRR; outside it falls back to GFS -> diff should go quiet there.
        if src_c is not None:
            for ax in (axes[1], axes[2]):
                ax.contour(slon_c, slat_c, src_c, levels=[0.5],
                           colors="black", linewidths=0.8)
            axes[2].legend([Line2D([0], [0], color="black", lw=0.8)],
                           ["HRRR domain edge"], loc="lower left", fontsize=8)

        for ax in axes:
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_xlim(float(comf_lon.min()), float(comf_lon.max()))
            ax.set_ylim(float(comf_lat.min()), float(comf_lat.max()))

        fig.suptitle(f"Wind Speed: SCHISM sflux vs UFS DATM  -  {vt_str}  ({stage})",
                     fontsize=15, fontweight="bold")

        fname = f"windspeed_{frame:03d}_{tc.strftime('%Y%m%d_%H%M')}.png"
        fig.savefig(OUT / fname, dpi=130)
        plt.close(fig)
        print(f"  {fname}  (RMSE={rmse:.3f})")

    p["ds"].close()
    print(f"\nSaved {len(selected)} frames to: {OUT}")


if __name__ == "__main__":
    _apply_args()
    main()
