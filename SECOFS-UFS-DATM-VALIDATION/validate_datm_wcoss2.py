#!/usr/bin/env python3
"""
Validate a SECOFS-UFS DATM forcing run ON WCOSS2 (no plotting required).

Designed for WCOSS2's limited python: it degrades gracefully by what is
importable.

  CHECK 1 - MANIFEST  (Python standard library only -> runs on ANY python)
      Reads <ofs>.t<cyc>z.<pdy>.inputs.prep.json and inspects the HRRR file
      list that fed the DATM blend:
        * first HRRR file should be valid AT model_t0 (= cyc - nowcast_hours)
          -> confirms the t0 fix (nos-utils #29)
        * last  HRRR file should reach cyc + forecast_hours
          -> confirms the cron-timing / full-coverage fix
        * prints prep timing (generated_at - cycle)

  CHECK 2 - DATM      (needs numpy + netCDF4, present in the prep python env)
      Reads datm_forcing.nc and, per timestep, measures wind-speed sharpness
      over the HRRR-coverage cells (data_source==1). Fine HRRR ~0.2, coarse
      GFS ~0.06. Confirms t0 is HRRR and coverage runs to +forecast_hours.

USAGE on WCOSS2:
    module load python/3.8.6                 # same python the prep uses
    COMOUT=/path/to/com/.../secofs_ufs.<pdy>
    python3 validate_datm_wcoss2.py \
        --manifest $COMOUT/secofs_ufs.t06z.20260606.inputs.prep.json \
        --datm     $COMOUT/secofs_ufs.t06z.datm_input/datm_forcing.nc \
        --cyc 6 --pdy 20260606 --nowcast-hours 6 --forecast-hours 48

Either --manifest or --datm may be given alone. --cyc/--pdy are read from the
manifest when present, so for a manifest-only run you can omit them.
"""
import argparse
import datetime as dt
import json
import re
import sys

SHARP_THRESH = 0.13       # fine HRRR (~0.2) vs coarse GFS (~0.06) on the 0.025deg grid
OK, BAD = "PASS", "FAIL"


# --------------------------------------------------------------------------
# CHECK 1: manifest (stdlib only)
# --------------------------------------------------------------------------
def parse_hrrr(path):
    """hrrr.YYYYMMDD/.../hrrr.tHHz.wrfsfcfFF.grib2 -> (valid_datetime, cyc, fhr)."""
    m = re.search(r"hrrr\.(\d{8})/.*?hrrr\.t(\d{2})z\.wrfsfcf(\d{2,3})", path)
    if not m:
        return None
    base = dt.datetime.strptime(m.group(1), "%Y%m%d") + dt.timedelta(hours=int(m.group(2)))
    return base + dt.timedelta(hours=int(m.group(3))), int(m.group(2)), int(m.group(3))


def check_manifest(path, nowcast_hours, forecast_hours):
    with open(path) as fh:
        man = json.load(fh)
    pdy, cyc = man["pdy"], int(man["cyc"])
    cycle = dt.datetime.strptime(pdy, "%Y%m%d") + dt.timedelta(hours=cyc)
    model_t0 = cycle - dt.timedelta(hours=nowcast_hours)
    want_last = cycle + dt.timedelta(hours=forecast_hours)

    hrrr = [e for e in man["inputs"] if (e.get("source") or "").upper() == "HRRR"]
    files = hrrr[0]["files"] if hrrr else []
    parsed = sorted(filter(None, (parse_hrrr(f) for f in files)), key=lambda x: x[0])

    print("=" * 70)
    print(f"CHECK 1  MANIFEST  {pdy} t{cyc:02d}z")
    print("=" * 70)
    gen = man.get("generated_at")
    if gen:
        try:
            off = (dt.datetime.fromisoformat(gen) - cycle.replace(tzinfo=dt.timezone.utc)).total_seconds() / 3600
            print(f"  prep generated_at : {gen}  (+{off:.2f}h after cycle)")
        except Exception:
            print(f"  prep generated_at : {gen}")
    print(f"  HRRR files        : {len(files)}")
    if not parsed:
        print(f"  {BAD}: no HRRR files in manifest")
        return False

    first_valid, _, _ = parsed[0]
    last_valid, last_cyc, last_fhr = parsed[-1]
    t0_ok = first_valid == model_t0
    cov_ok = last_valid >= want_last
    print(f"  first HRRR valid  : {first_valid:%Y-%m-%d %H:%M}  "
          f"(want model_t0 {model_t0:%Y-%m-%d %H:%M})  -> {OK if t0_ok else BAD}")
    print(f"  last  HRRR valid  : {last_valid:%Y-%m-%d %H:%M}  (t{last_cyc:02d}z f{last_fhr:02d})  "
          f"(want >= {want_last:%Y-%m-%d %H:%M})  -> {OK if cov_ok else BAD}")
    print(f"  t0 fix  (#29)     : {OK if t0_ok else BAD}")
    print(f"  full coverage     : {OK if cov_ok else BAD}")
    return t0_ok and cov_ok


# --------------------------------------------------------------------------
# CHECK 2: datm_forcing.nc (numpy + netCDF4)
# --------------------------------------------------------------------------
def check_datm(path, cyc, pdy, nowcast_hours, forecast_hours):
    import numpy as np
    from netCDF4 import Dataset, num2date

    cycle = dt.datetime.strptime(pdy, "%Y%m%d") + dt.timedelta(hours=cyc)
    model_t0 = cycle - dt.timedelta(hours=nowcast_hours)

    ds = Dataset(path)
    uname = "UGRD_10maboveground" if "UGRD_10maboveground" in ds.variables else "uwind"
    vname = "VGRD_10maboveground" if "VGRD_10maboveground" in ds.variables else "vwind"
    tv = ds.variables["time"]
    times = list(num2date(tv[:], tv.units, only_use_cftime_datetimes=False,
                          only_use_python_datetimes=True))
    if "data_source" in ds.variables:
        src = np.asarray(ds.variables["data_source"][:]) == 1   # HRRR cells
    else:
        src = None

    print("=" * 70)
    print(f"CHECK 2  DATM  {path.split('/')[-1]}")
    print("=" * 70)
    print(f"  steps {len(times)} : {times[0]:%Y-%m-%d %H:%M} .. {times[-1]:%Y-%m-%d %H:%M}")
    print(f"  {'lead':>5}  {'time':<16} {'sharp':>7}  source")
    hrrr_leads = []
    U, V = ds.variables[uname], ds.variables[vname]
    for i, t in enumerate(times):
        u = np.asarray(U[i], dtype="f8"); v = np.asarray(V[i], dtype="f8")
        ws = np.hypot(u, v)
        gy, gx = np.gradient(ws)
        g = np.hypot(gy, gx)
        sharp = float(np.nanmean(g[src])) if src is not None else float(np.nanmean(g))
        lead = (t - cycle).total_seconds() / 3600
        is_hrrr = sharp > SHARP_THRESH
        if is_hrrr:
            hrrr_leads.append(lead)
        if i < 2 or i % 6 == 0 or i == len(times) - 1:
            print(f"  {lead:+5.0f}  {t:%m-%d %H:%M}    {sharp:.4f}  {'HRRR' if is_hrrr else 'GFS'}")
    ds.close()

    t0_ok = bool(hrrr_leads) and min(hrrr_leads) <= (model_t0 - cycle).total_seconds() / 3600 + 0.01
    cov_ok = bool(hrrr_leads) and max(hrrr_leads) >= forecast_hours - 0.01
    print(f"  HRRR coverage     : lead {min(hrrr_leads):+.0f}h .. {max(hrrr_leads):+.0f}h "
          f"({len(hrrr_leads)} steps)" if hrrr_leads else "  no HRRR steps")
    print(f"  t0 (model_t0) HRRR: {OK if t0_ok else BAD}")
    print(f"  reaches +{forecast_hours}h : {OK if cov_ok else BAD}")
    return t0_ok and cov_ok


def main():
    ap = argparse.ArgumentParser(description="Validate a SECOFS-UFS DATM run on WCOSS2.")
    ap.add_argument("--manifest", help="path to *.inputs.prep.json")
    ap.add_argument("--datm", help="path to datm_forcing.nc")
    ap.add_argument("--cyc", type=int, help="cycle hour (read from manifest if omitted)")
    ap.add_argument("--pdy", help="YYYYMMDD (read from manifest if omitted)")
    ap.add_argument("--nowcast-hours", type=int, default=6)
    ap.add_argument("--forecast-hours", type=int, default=48)
    a = ap.parse_args()
    if not a.manifest and not a.datm:
        ap.error("give --manifest and/or --datm")

    results = []
    if a.manifest:
        results.append(check_manifest(a.manifest, a.nowcast_hours, a.forecast_hours))
        if (a.cyc is None or a.pdy is None):
            man = json.load(open(a.manifest))
            a.cyc = a.cyc if a.cyc is not None else int(man["cyc"])
            a.pdy = a.pdy or man["pdy"]

    if a.datm:
        if a.cyc is None or a.pdy is None:
            ap.error("--datm needs --cyc and --pdy (or pass --manifest too)")
        try:
            import numpy, netCDF4  # noqa: F401
        except ImportError as e:
            print(f"\n[skip CHECK 2] numpy/netCDF4 not importable: {e}")
            print("  -> run with the prep python:  module load python/3.8.6")
            print("     export PYTHONPATH=$HOMEnos/ush/python:$PYTHONPATH")
        else:
            results.append(check_datm(a.datm, a.cyc, a.pdy, a.nowcast_hours, a.forecast_hours))

    print("=" * 70)
    print("OVERALL:", OK if results and all(results) else BAD)
    sys.exit(0 if results and all(results) else 1)


if __name__ == "__main__":
    main()
