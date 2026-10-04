#!/usr/bin/env python3
"""
Water-level validation against NOAA CO-OPS observations: operational STOFS-3D-ATL v3.1 vs the
nos-workflow standalone nowcast (ops SCHISM 5.14 executable), PDY 2026-10-01 12z (24 h nowcast).

usage: plot_wl_obs_compare.py --ops OPS_STAOUT_1 --nos-workflow NOS_STAOUT_1 --station-in STATION_IN
           --msl-nco XGEOID_TO_MSL_NCO --obs-dir DIR --outdir DIR [--names-csv STAOUT_NC_CSV]
           [--start 2026093012] [--ids 8423898,...]

OPS_STAOUT_1   operational station series (column 0 = seconds since --start, then 166 stations; first 288 rows used)
NOS_STAOUT_1   nos-workflow station series, same layout (288 rows, 300 s output)
STATION_IN     stofs_3d_atl_station.in ("i lon lat z !ID")
XGEOID_TO_MSL_NCO  stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco; ops applies it with ncap2 as
               zeta(:,k) = zeta(:,k) - offset_k (k = station.in row), i.e. WL(MSL) = model elevation - offset_k.
               The same conversion is applied to BOTH model series. Stations without an offset
               (none in the 166-station file) would be compared de-meaned.
OBS_DIR        cache for CO-OPS water_level JSON (datum=MSL, GMT, metric, 6 min); downloaded if missing.

Errors are computed on the common (observed) times: the model is interpolated to the 6-min obs times.

Figures (PNG, dpi 100, <= 1500 px) plus wl_obs_summary.txt:
  wl_obs_ts.png     one panel per station: observed, operational, nos-workflow (MSL)
  wl_obs_stats.png  RMSE vs obs (both runs) and max|nos-workflow - operational| per station, log axis
"""
import argparse
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

LAB = {"obs": "observed (NOAA CO-OPS)", "ops": "operational STOFS-3D-ATL",
       "ours": "nos-workflow (standalone, ops SCHISM 5.14)"}
DEFAULT_IDS = "8423898,8419317,8443970,8447435,8418150,8518750,8534720,8651370,8670870,8761724,9755371,8665530"
TITLE = "PDY 2026-10-01 12z nowcast"
API = ("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&application=nos_workflow"
       "&begin_date={b}&end_date={e}&datum=MSL&station={s}&time_zone=gmt&units=metric&format=json")


def save_png(fig, out):
    fig.savefig(out, dpi=100, metadata={"Software": None})
    plt.close(fig)
    w, h = Image.open(out).size
    assert max(w, h) <= 1500, f"{out}: {w}x{h} exceeds 1500 px"
    print(f"saved {out}  {w}x{h}")


def load_stations(path, names_csv):
    ids = []
    with open(path) as f:
        f.readline()
        n = int(f.readline().split()[0])
        for _ in range(n):
            ids.append(f.readline().partition("!")[2].strip())
    names = {}
    if names_csv:
        with open(names_csv) as f:
            next(f)
            for line in f:
                t = line.rstrip("\n").split(";")[1].split()
                if len(t) >= 5:
                    names[t[2]] = f"{' '.join(t[4:])}, {t[3]}"
    return ids, names


def load_offsets(path):
    off = {}
    for m in re.finditer(r"zeta\(:,(\d+)\)\s*=\s*zeta\(:,\d+\)\s*-\s*float\(([-+0-9.eE]+)\)", open(path).read()):
        off[int(m.group(1))] = float(m.group(2))
    return off


def fetch_obs(sid, start, end, cache):
    fn = os.path.join(cache, f"wl_msl_{sid}.json")
    if not os.path.exists(fn):
        url = API.format(b=start.strftime("%Y%m%d%%20%H:%M"), e=end.strftime("%Y%m%d%%20%H:%M"), s=sid)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                txt = r.read().decode()
        except Exception as ex:
            print(f"{sid}: obs download failed ({ex})")
            return None, None
        open(fn, "w").write(txt)
    js = json.load(open(fn))
    if "data" not in js:
        print(f"{sid}: no obs ({js.get('error', {}).get('message', '?')})")
        return None, None
    t, v = [], []
    for d in js["data"]:
        if d["v"].strip() == "":
            continue
        t.append(datetime.strptime(d["t"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())
        v.append(float(d["v"]))
    return (np.array(t), np.array(v)) if len(t) > 10 else (None, None)


def stats(m, o):
    e = m - o
    return dict(rmse=float(np.sqrt(np.mean(e ** 2))), bias=float(np.mean(e)),
                r=float(np.corrcoef(m, o)[0, 1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ops", required=True)
    ap.add_argument("--nos-workflow", required=True)
    ap.add_argument("--station-in", required=True)
    ap.add_argument("--msl-nco", required=True)
    ap.add_argument("--obs-dir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--names-csv")
    ap.add_argument("--start", default="2026093012")
    ap.add_argument("--ids", default=DEFAULT_IDS)
    a = ap.parse_args()
    os.makedirs(a.obs_dir, exist_ok=True)
    os.makedirs(a.outdir, exist_ok=True)

    start = datetime.strptime(a.start, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=24)
    o = np.loadtxt(a.ops, max_rows=288)
    u = np.loadtxt(a.nos_workflow, max_rows=288)
    assert o.shape == u.shape and np.allclose(o[:, 0], u[:, 0]), "series differ in shape/time"
    ts = start.timestamp() + o[:, 0]
    sids, names = load_stations(a.station_in, a.names_csv)
    off = load_offsets(a.msl_nco)

    rows, data = [], []
    for sid in a.ids.split(","):
        if sid not in sids:
            print(f"{sid}: not in station.in, skipped")
            continue
        k = sids.index(sid) + 1
        ot, ov = fetch_obs(sid, start, end, a.obs_dir)
        has_off = k in off
        mo, mu = o[:, k].copy(), u[:, k].copy()
        if has_off:
            mo -= off[k]
            mu -= off[k]
        nm = names.get(sid, sid)
        if ot is None:
            r = dict(sid=sid, name=nm, obs=False, off=has_off, maxdiff=float(np.abs(mu - mo).max()),
                     ops=dict(rmse=np.nan), ours=dict(rmse=np.nan))
            rows.append(r)
            data.append((r, None, None, ts, mo, mu))
            continue
        io, iu = np.interp(ot, ts, mo), np.interp(ot, ts, mu)
        ok = (ot >= ts[0]) & (ot <= ts[-1])
        ov_c, io, iu = ov[ok], io[ok], iu[ok]
        if not has_off:
            io, iu = io - io.mean() + ov_c.mean(), iu - iu.mean() + ov_c.mean()
        r = dict(sid=sid, name=nm, obs=True, off=has_off, n=int(ok.sum()), ops=stats(io, ov_c),
                 ours=stats(iu, ov_c), maxdiff=float(np.abs(mu - mo).max()))
        rows.append(r)
        data.append((r, ot, ov, ts, mo, mu))

    # figure 1
    n = len(data)
    nc = 3
    nr = int(np.ceil(n / nc))
    fig, axs = plt.subplots(nr, nc, figsize=(15, 3.0 * nr + 1.3), sharex=True)
    for ax, (r, ot, ov, tt, mo, mu) in zip(axs.flat, data):
        x = lambda s: mdates.date2num([datetime.fromtimestamp(v, timezone.utc) for v in s])
        if ot is not None:
            ax.plot(x(ot), ov, color="k", lw=1.0, label=LAB["obs"])
        ax.plot(x(tt), mo, color="#0072B2", lw=2.4, alpha=0.85, label=LAB["ops"])
        ax.plot(x(tt), mu, color="#D55E00", lw=1.0, ls="--", label=LAB["ours"])
        if ot is None:
            ax.set_title(f"{r['name']} ({r['sid']})\nno observations available; max|nos-wf - op| {r['maxdiff']:.1e} m",
                         fontsize=8.5)
        else:
            ax.set_title(f"{r['name']} ({r['sid']})\nRMSE op {r['ops']['rmse']:.3f} m, nos-wf {r['ours']['rmse']:.3f} m, "
                         f"max|nos-wf - op| {r['maxdiff']:.1e} m" + ("" if r["off"] else "\n(de-meaned)"), fontsize=8.5)
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %Hz\n%b"))
        ax.tick_params(labelsize=8)
        ax.grid(alpha=0.3)
    for ax in axs.flat[n:]:
        ax.axis("off")
    for ax in axs[:, 0]:
        ax.set_ylabel("water level, MSL (m)", fontsize=9)
    h, l = axs.flat[2].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle(f"Water level vs NOAA CO-OPS observations, {TITLE} (MSL datum)", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    save_png(fig, os.path.join(a.outdir, "wl_obs_ts.png"))

    # figure 2
    fig, ax = plt.subplots(figsize=(14, 6))
    xi = np.arange(n)
    w = 0.27
    ax.bar(xi - w, [r["ops"]["rmse"] for r, *_ in data], w, color="#0072B2", label="RMSE vs obs, " + LAB["ops"])
    ax.bar(xi, [r["ours"]["rmse"] for r, *_ in data], w, color="#D55E00", label="RMSE vs obs, " + LAB["ours"])
    ax.bar(xi + w, [max(r["maxdiff"], 1e-6) for r, *_ in data], w, color="0.45",
           label="max|nos-workflow - operational|")
    ax.set_yscale("log")
    ax.set_xticks(xi)
    ax.set_xticklabels([f"{r['name'].split(',')[0]}\n{r['sid']}" for r, *_ in data], fontsize=8, rotation=35, ha="right")
    ax.set_ylabel("m (log scale)")
    ax.grid(axis="y", alpha=0.3, which="both")
    ax.legend(fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False)
    ax.set_title(f"Model error vs observations compared with run-to-run difference, {TITLE} (MSL datum)")
    fig.tight_layout()
    save_png(fig, os.path.join(a.outdir, "wl_obs_stats.png"))

    # summary
    with open(os.path.join(a.outdir, "wl_obs_summary.txt"), "w") as f:
        f.write(f"Water level vs NOAA CO-OPS observations, {TITLE}, {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC\n")
        f.write("Datum: model elevation converted to MSL with stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco (WL = zeta - offset_k,\n"
                "as ops ncap2 applies it), same conversion for both runs; obs = CO-OPS water_level datum=MSL, 6 min, GMT.\n"
                "Model (5 min) linearly interpolated to obs times. Stations without an offset would be de-meaned (none).\n\n")
        f.write(f"{'ID':8s} {'name':28s} {'n':>4s} | {'ops RMSE':>8s} {'bias':>7s} {'r':>6s} | "
                f"{'nos-wf RMSE':>11s} {'bias':>7s} {'r':>6s} | {'max|nos-wf-op|':>14s}\n")
        for r in rows:
            if not r["obs"]:
                f.write(f"{r['sid']:8s} {r['name'][:28]:28s} no observations | max|diff| {r['maxdiff']:.3e}\n")
                continue
            p, q = r["ops"], r["ours"]
            f.write(f"{r['sid']:8s} {r['name'][:28]:28s} {r['n']:4d} | {p['rmse']:8.3f} {p['bias']:7.3f} {p['r']:6.3f} | "
                    f"{q['rmse']:11.3f} {q['bias']:7.3f} {q['r']:6.3f} | {r['maxdiff']:14.3e}\n")
        if data:
            f.write(f"\nmean RMSE (stations with obs): operational {np.nanmean([r['ops']['rmse'] for r,*_ in data]):.3f} m, "
                    f"nos-workflow {np.nanmean([r['ours']['rmse'] for r,*_ in data]):.3f} m; "
                    f"largest max|diff| {max(r['maxdiff'] for r,*_ in data):.3e} m\n")
    print(open(os.path.join(a.outdir, "wl_obs_summary.txt")).read())


if __name__ == "__main__":
    main()
