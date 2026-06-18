#!/usr/bin/env python3
"""
NWM river source comparison: operational vs UFS, from vsource.th
(col0=time(s), cols1..N = per-source volume discharge m3/s). Diagnoses whether
the primary (NWM) river forcing matches source-by-source.

Auto-aligns any nowcast-window offset (cross-correlation on active sources).

Usage:
  python3 plot_nwm_vsource_compare.py OPS_vsource.th UFS_vsource.th \
      [--out nwm.png] [--label "..."] [--maxlag 24] [--topn 6]
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ACTIVE = 0.011   # > this (m3/s) counts as an active source (0.01 is the placeholder)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--out", default="nwm_vsource_compare.png")
    ap.add_argument("--label", default="operational vs UFS")
    ap.add_argument("--maxlag", type=int, default=24, help="max align lag (steps)")
    ap.add_argument("--topn", type=int, default=6)
    a = ap.parse_args()

    O = np.loadtxt(a.ops); U = np.loadtxt(a.ufs)
    qo, qu = O[:, 1:], U[:, 1:]
    ns = min(qo.shape[1], qu.shape[1]); qo, qu = qo[:, :ns], qu[:, :ns]
    dt = (O[1, 0] - O[0, 0]) if len(O) > 1 else 3600.0

    # auto-align on active sources (those that vary in time)
    act = (qo.max(0) > ACTIVE)
    best = (0, np.inf)
    for lag in range(-a.maxlag, a.maxlag + 1):
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
    lag = best[0]; off_h = lag * dt / 3600.0
    if lag >= 0:
        qo, qu = qo[lag:], qu[:qo.shape[0] - lag]
    else:
        qo, qu = qo[:qu.shape[0] + lag], qu[-lag:]
    nt = min(qo.shape[0], qu.shape[0]); qo, qu = qo[:nt], qu[:nt]
    hrs = np.arange(nt) * dt / 3600.0

    diff = qu - qo
    rmse = float(np.sqrt(np.nanmean(diff ** 2)))
    permax = np.nanmax(np.abs(diff), axis=0)        # per-source max|diff|
    n_diff = int((permax > ACTIVE).sum())
    moq = qo.mean(0); muq = qu.mean(0)
    top = np.argsort(np.maximum(moq, muq))[::-1][:a.topn]

    fig, ax = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)

    ax[0, 0].plot(hrs, qo.sum(1), color="blue", lw=1.8, label="operational")
    ax[0, 0].plot(hrs, qu.sum(1), color="red", lw=1.2, ls="--", label="UFS")
    ax[0, 0].set_title(f"Total discharge (sum of {ns} sources)")
    ax[0, 0].set_xlabel("Time (hours)"); ax[0, 0].set_ylabel("m3/s")
    ax[0, 0].grid(True, alpha=0.25); ax[0, 0].legend()

    lim = max(moq.max(), muq.max()) * 1.05
    ax[0, 1].scatter(moq, muq, s=8, alpha=0.5, edgecolors="none")
    ax[0, 1].plot([0, lim], [0, lim], "k--", lw=1, alpha=0.6)
    ax[0, 1].set_title(f"Per-source mean discharge (1:1)   sources differing: {n_diff}/{int(act.sum())} active")
    ax[0, 1].set_xlabel("operational (m3/s)"); ax[0, 1].set_ylabel("UFS (m3/s)")
    ax[0, 1].grid(True, alpha=0.25)

    sp = np.sort(permax[permax > 1e-6])[::-1]
    ax[1, 0].semilogy(np.arange(1, len(sp) + 1), sp, lw=1.4)
    ax[1, 0].axhline(ACTIVE, color="r", ls="--", lw=0.8, label=f"active thresh {ACTIVE}")
    ax[1, 0].set_title("Per-source max|diff| (sorted, log)")
    ax[1, 0].set_xlabel("source rank"); ax[1, 0].set_ylabel("max|diff| m3/s")
    ax[1, 0].grid(True, alpha=0.25); ax[1, 0].legend(fontsize=8)

    for k in top:
        ax[1, 1].plot(hrs, qo[:, k], lw=1.5, label=f"src{k} ops")
        ax[1, 1].plot(hrs, qu[:, k], lw=1.0, ls="--", color="k", alpha=0.6)
    ax[1, 1].set_title(f"Top {a.topn} sources (ops solid, ufs black dashed)")
    ax[1, 1].set_xlabel("Time (hours)"); ax[1, 1].set_ylabel("m3/s")
    ax[1, 1].grid(True, alpha=0.25); ax[1, 1].legend(fontsize=8, ncol=2)

    fig.suptitle(f"NWM vsource discharge: {a.label}\n"
                 f"aligned (offset {off_h:+.1f}h), {nt} steps x {ns} sources   "
                 f"RMSE={rmse:.4g} m3/s   total-Q diff: "
                 f"{abs(qu.sum(1).mean() - qo.sum(1).mean()):.2f} m3/s   "
                 f"sources differing>{ACTIVE}: {n_diff}",
                 fontsize=13, fontweight="bold")
    fig.savefig(a.out, dpi=130, bbox_inches="tight")
    print(f"saved {a.out}  offset={off_h:+.1f}h RMSE={rmse:.4g} n_diff={n_diff} "
          f"totalQ ops={qo.sum(1).mean():.1f} ufs={qu.sum(1).mean():.1f}")


if __name__ == "__main__":
    main()
