#!/usr/bin/env python3
"""Extra NWM discharge comparisons (operational vs UFS) from vsource.th.

Companion to plot_nwm_vsource_compare.py. vsource.th layout: col0 = time(s),
cols1..N = per-source volume discharge (m3/s).

Fig 1 (<prefix>_top16_hydrographs.png): per-source hydrographs for the top-N
       sources (ops vs ufs, per-panel RMSE / correlation).
Fig 2 (<prefix>_summary_panels.png): total-discharge overlay + residual,
       cumulative delivered volume, and the per-source RMSE distribution (ECDF).

Auto-aligns any nowcast-window offset (cross-correlation on active sources).

Usage:
  python3 plot_discharge_extra.py OPS_vsource.th UFS_vsource.th \
      [--source-sink source_sink.in] [--out-prefix discharge] \
      [--label "..."] [--topn 16] [--maxlag 12]
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ACTIVE = 0.011   # > this (m3/s) counts as an active source (0.01 is the placeholder)


def align(O, U, maxlag):
    """Cross-correlation align on active sources; return trimmed (qo, qu, dt, off_h)."""
    qo, qu = O[:, 1:], U[:, 1:]
    ns = min(qo.shape[1], qu.shape[1]); qo, qu = qo[:, :ns], qu[:, :ns]
    dt = (O[1, 0] - O[0, 0]) if len(O) > 1 else 3600.0
    act = qo.max(0) > ACTIVE
    best = (0, np.inf)
    for lag in range(-maxlag, maxlag + 1):
        if lag >= 0:
            A = qo[lag:][:, act]; B = qu[:A.shape[0]][:, act]
        else:
            A = qo[:qu.shape[0] + lag][:, act]; B = qu[-lag:][:, act]
        n = min(A.shape[0], B.shape[0])
        if n < 5:
            continue
        rr = np.sqrt(np.nanmean((A[:n] - B[:n]) ** 2))
        if rr < best[1]:
            best = (lag, rr)
    lag = best[0]
    if lag >= 0:
        qo, qu = qo[lag:], qu[:qo.shape[0] - lag]
    else:
        qo, qu = qo[:qu.shape[0] + lag], qu[-lag:]
    nt = min(qo.shape[0], qu.shape[0])
    return qo[:nt], qu[:nt], dt, lag * dt / 3600.0


def elem_ids(path, n):
    """Read source element ids from source_sink.in (else fall back to indices)."""
    if not path:
        return list(range(n))
    try:
        with open(path) as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        nsrc = int(lines[0])
        return [int(lines[1 + i]) for i in range(min(nsrc, n))]
    except Exception:
        return list(range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--source-sink", default=None, help="source_sink.in for element-id labels")
    ap.add_argument("--out-prefix", default="discharge")
    ap.add_argument("--label", default="operational vs UFS")
    ap.add_argument("--topn", type=int, default=16)
    ap.add_argument("--maxlag", type=int, default=12)
    a = ap.parse_args()

    O = np.loadtxt(a.ops); U = np.loadtxt(a.ufs)
    qo, qu, dt, offh = align(O, U, a.maxlag)
    nt, ns = qo.shape
    hrs = np.arange(nt) * dt / 3600.0
    eids = elem_ids(a.source_sink, ns)

    # ---- Fig 1: top-N source hydrographs ----------------------------------
    order = np.argsort(np.maximum(qo.mean(0), qu.mean(0)))[::-1]
    top = order[:a.topn]
    ncol = 4; nrow = int(np.ceil(len(top) / ncol))
    fig, ax = plt.subplots(nrow, ncol, figsize=(4 * ncol, 2.7 * nrow),
                           constrained_layout=True, squeeze=False)
    for i, k in enumerate(top):
        axk = ax.flat[i]
        axk.plot(hrs, qo[:, k], color="blue", lw=1.6, label="ops")
        axk.plot(hrs, qu[:, k], color="red", lw=1.1, ls="--", label="ufs")
        rk = np.sqrt(np.nanmean((qu[:, k] - qo[:, k]) ** 2))
        corr = np.corrcoef(qo[:, k], qu[:, k])[0, 1] if qo[:, k].std() > 0 else 1.0
        eid = eids[k] if k < len(eids) else k
        axk.set_title(f"src#{k} elem {eid}  RMSE={rk:.2g}  r={corr:.3f}", fontsize=9)
        axk.grid(True, alpha=0.25); axk.tick_params(labelsize=8)
        if i == 0:
            axk.legend(fontsize=8)
    for j in range(len(top), nrow * ncol):
        ax.flat[j].axis("off")
    fig.suptitle(f"Top-{len(top)} NWM source hydrographs: operational (blue) vs UFS (red dashed)\n"
                 f"{a.label}, aligned {offh:+.1f}h, {nt} steps",
                 fontsize=13, fontweight="bold")
    fig.supxlabel("Time (hours)"); fig.supylabel("discharge (m3/s)")
    fig.savefig(f"{a.out_prefix}_top16_hydrographs.png", dpi=95, bbox_inches="tight")
    plt.close(fig)

    # ---- Fig 2: total / residual / cumulative / error distribution --------
    to, tu = qo.sum(1), qu.sum(1)
    fig, ax = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)

    ax[0, 0].plot(hrs, to, color="blue", lw=1.8, label="operational")
    ax[0, 0].plot(hrs, tu, color="red", lw=1.2, ls="--", label="UFS")
    ax[0, 0].set_title("Total domain discharge"); ax[0, 0].set_ylabel("m3/s")
    ax[0, 0].set_xlabel("Time (hours)"); ax[0, 0].grid(True, alpha=0.25); ax[0, 0].legend()

    resid = tu - to
    ax[0, 1].plot(hrs, resid, color="purple", lw=1.3)
    ax[0, 1].axhline(0, color="k", lw=0.8)
    ax[0, 1].fill_between(hrs, resid, 0, alpha=0.2, color="purple")
    ax[0, 1].set_title(f"Total-discharge residual (UFS - ops)   "
                       f"mean={resid.mean():+.1f}  RMS={np.sqrt((resid**2).mean()):.1f} m3/s")
    ax[0, 1].set_ylabel("m3/s"); ax[0, 1].set_xlabel("Time (hours)"); ax[0, 1].grid(True, alpha=0.25)

    vol_o = np.cumsum(to) * dt / 1e9   # km3
    vol_u = np.cumsum(tu) * dt / 1e9
    ax[1, 0].plot(hrs, vol_o, color="blue", lw=1.8, label="operational")
    ax[1, 0].plot(hrs, vol_u, color="red", lw=1.2, ls="--", label="UFS")
    pct = 100 * (vol_u[-1] - vol_o[-1]) / vol_o[-1] if vol_o[-1] else 0.0
    ax[1, 0].set_title(f"Cumulative delivered volume   "
                       f"final ops={vol_o[-1]:.3f} ufs={vol_u[-1]:.3f} km3 ({pct:+.2f}%)")
    ax[1, 0].set_ylabel("km3"); ax[1, 0].set_xlabel("Time (hours)")
    ax[1, 0].grid(True, alpha=0.25); ax[1, 0].legend()

    per_rmse = np.sqrt(np.mean((qu - qo) ** 2, axis=0))
    active = qo.max(0) > ACTIVE
    pr = np.sort(per_rmse[active])
    ecdf = np.arange(1, len(pr) + 1) / len(pr)
    ax[1, 1].plot(pr, ecdf, lw=1.6)
    med = np.median(pr); p95 = np.percentile(pr, 95)
    ax[1, 1].axvline(med, color="g", ls="--", lw=0.9, label=f"median={med:.3g}")
    ax[1, 1].axvline(p95, color="orange", ls="--", lw=0.9, label=f"95th={p95:.3g}")
    ax[1, 1].set_xscale("log")
    ax[1, 1].set_title(f"Per-source RMSE distribution (ECDF, {int(active.sum())} active sources)")
    ax[1, 1].set_xlabel("per-source RMSE (m3/s)"); ax[1, 1].set_ylabel("cumulative fraction")
    ax[1, 1].grid(True, alpha=0.25); ax[1, 1].legend(fontsize=9)

    fig.suptitle(f"NWM discharge agreement: {a.label}", fontsize=13, fontweight="bold")
    fig.savefig(f"{a.out_prefix}_summary_panels.png", dpi=100, bbox_inches="tight")
    plt.close(fig)

    print(f"aligned {offh:+.1f}h, {nt} steps x {ns} sources")
    print(f"total resid: mean={resid.mean():+.2f} rms={np.sqrt((resid**2).mean()):.2f} m3/s")
    print(f"cumulative volume ops={vol_o[-1]:.4f} ufs={vol_u[-1]:.4f} km3 ({pct:+.3f}%)")
    print(f"per-source RMSE (active): median={med:.4g} 95th={p95:.4g} max={pr.max():.4g} m3/s")
    print(f"saved {a.out_prefix}_top16_hydrographs.png, {a.out_prefix}_summary_panels.png")


if __name__ == "__main__":
    main()
