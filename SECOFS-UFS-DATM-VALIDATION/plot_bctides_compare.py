#!/usr/bin/env python3
"""
Plot bctides.in: nodal factors / equilibrium args + ocean-boundary harmonics,
operational (secofs) vs UFS (secofs_ufs). Parses the file (no hardcoded values).

Usage:
  python3 plot_bctides_compare.py OPS_bctides.in UFS_bctides.in [--out out.png] [--label "..."]
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CONS = ["M2", "S2", "N2", "K2", "K1", "O1", "P1", "Q1"]


def parse_bctides(path):
    L = open(path).read().splitlines()
    i = 0
    date = L[i].strip(); i += 1
    ntip = int(L[i].split()[0]); i += 1
    pot = {}                       # name -> (nodal_f, eq_arg)
    for _ in range(ntip):
        name = L[i].split()[0].upper(); i += 1
        d = L[i].split(); i += 1
        pot[name] = (float(d[3]), float(d[4]))
    nbfr = int(L[i].split()[0]); i += 1
    bfr_names = []
    for _ in range(nbfr):
        name = L[i].split()[0].upper(); i += 1
        i += 1                     # skip the "freq f eqarg" line
        bfr_names.append(name)
    int(L[i].split()[0]); i += 1   # nope
    hdr = L[i].split(); i += 1     # first boundary header: nnodes iettype ifltype ...
    nnodes, iettype = int(hdr[0]), int(hdr[1])
    elev = {}                      # name -> (amp[], phase[])
    if iettype in (3, 5):
        for _ in range(nbfr):
            cname = L[i].split()[0].upper(); i += 1
            amp, ph = [], []
            for _ in range(nnodes):
                p = L[i].split(); i += 1
                amp.append(float(p[0])); ph.append(float(p[1]))
            elev[cname] = (np.array(amp), np.array(ph))
    return {"date": date, "pot": pot, "nnodes": nnodes, "elev": elev}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ops"); ap.add_argument("ufs")
    ap.add_argument("--out", default="bctides_compare.png")
    ap.add_argument("--label", default="operational (secofs) vs UFS (secofs_ufs)")
    a = ap.parse_args()
    O, U = parse_bctides(a.ops), parse_bctides(a.ufs)

    cons = [c for c in CONS if c in O["pot"]]
    x = np.arange(len(cons)); w = 0.38
    of = [O["pot"][c][0] for c in cons]; uf = [U["pot"][c][0] for c in cons]
    ov = [O["pot"][c][1] for c in cons]; uv = [U["pot"][c][1] for c in cons]

    fig, ax = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)

    ax[0, 0].bar(x - w/2, of, w, color="#2166ac", label="operational", edgecolor="white")
    ax[0, 0].bar(x + w/2, uf, w, color="#1a9850", label="UFS", edgecolor="white")
    ax[0, 0].set_xticks(x); ax[0, 0].set_xticklabels(cons, fontweight="bold")
    ax[0, 0].set_title(f"Nodal factors (f)   max|diff|={max(abs(a-b) for a,b in zip(of,uf)):.1e}")
    ax[0, 0].set_ylabel("f"); ax[0, 0].axhline(1, color="k", ls="--", lw=0.7, alpha=0.4)
    ax[0, 0].legend(); ax[0, 0].grid(True, axis="y", alpha=0.2)

    ax[0, 1].bar(x - w/2, ov, w, color="#2166ac", label="operational", edgecolor="white")
    ax[0, 1].bar(x + w/2, uv, w, color="#1a9850", label="UFS", edgecolor="white")
    ax[0, 1].set_xticks(x); ax[0, 1].set_xticklabels(cons, fontweight="bold")
    ax[0, 1].set_title(f"Equilibrium args (V0+u, deg)   max|diff|={max(abs(a-b) for a,b in zip(ov,uv)):.1e}")
    ax[0, 1].set_ylabel("deg"); ax[0, 1].legend(); ax[0, 1].grid(True, axis="y", alpha=0.2)

    show = [c for c in ("M2", "S2", "K1", "O1") if c in O["elev"]]
    colors = {"M2": "#d73027", "S2": "#fc8d59", "K1": "#4575b4", "O1": "#91bfdb"}
    if show:
        n = O["nnodes"]; xn = np.arange(n)
        for c in show:
            ax[1, 0].plot(xn, O["elev"][c][0], color=colors[c], lw=1.4, label=f"{c} ops")
            ax[1, 0].plot(xn, U["elev"][c][0], color="k", lw=0.8, ls="--", alpha=0.7)
        ax[1, 0].set_title(f"Ocean-boundary elevation AMPLITUDE per node ({n} nodes)\n"
                           "ops=color, ufs=black dashed")
        ax[1, 0].set_xlabel("boundary node index"); ax[1, 0].set_ylabel("amplitude (m)")
        ax[1, 0].legend(fontsize=9, ncol=2); ax[1, 0].grid(True, alpha=0.2)

        for c in ("M2", "K1"):
            if c in O["elev"]:
                ax[1, 1].plot(xn, O["elev"][c][1], color=colors[c], lw=1.4, label=f"{c} ops")
                ax[1, 1].plot(xn, U["elev"][c][1], color="k", lw=0.8, ls="--", alpha=0.7)
        # max amp diff across shown constituents
        md = max(float(np.max(np.abs(O["elev"][c][0] - U["elev"][c][0]))) for c in show)
        ax[1, 1].set_title(f"Ocean-boundary PHASE per node (M2, K1)   max|amp diff|={md:.1e} m")
        ax[1, 1].set_xlabel("boundary node index"); ax[1, 1].set_ylabel("phase (deg)")
        ax[1, 1].legend(fontsize=9); ax[1, 1].grid(True, alpha=0.2)

    fig.suptitle(f"bctides.in  -  {a.label}\nops date: {O['date']}   |   ufs date: {U['date']}",
                 fontsize=14, fontweight="bold")
    fig.savefig(a.out, dpi=130, bbox_inches="tight")
    print("saved", a.out)


if __name__ == "__main__":
    main()
