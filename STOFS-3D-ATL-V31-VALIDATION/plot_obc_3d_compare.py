#!/usr/bin/env python3
"""
OBC 3D boundary forcing comparison (TEM, SAL or uv): operational STOFS-3D-ATL vs
nos-workflow (nowcast + forecast as one series), optional "before the ops-parity
fix" series.

Panels: time series at one vertical level for a few nodes (+ difference), and a
depth profile (vertical level index, 0 = bottom, -1 = surface) at one node and
one time (+ difference vs level). uv defaults to speed; --component 0/1 gives u/v.

Files are PATH:YYYYMMDDHH (absolute UTC time of time=0). Differences use only
records whose absolute times match exactly (no interpolation).

Usage:
  python3 plot_obc_3d_compare.py --nodes-csv obc_nodes.csv \
      --ops OPS_tem3dth.nc:2026092612 \
      --ours NOW_TEM_3D.th.nc:2026092612 FCST_tem3dth.nc:2026092712 \
      [--before PORT_tem3dth.nc:2026092712] [--var auto|TEM|SAL|uv] [--component 0] \
      [--level -1] [--nodes 8,200,500,728,766] [--profile-node 200] \
      [--profile-time 2026092712] [--cycle 2026092712] [--out tem_surface.png]
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import obc_common as oc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ops", nargs="+", required=True)
    ap.add_argument("--ours", nargs="+", required=True)
    ap.add_argument("--before", nargs="+", default=None)
    ap.add_argument("--nodes-csv", required=True)
    ap.add_argument("--var", default="auto")
    ap.add_argument("--component", type=int, default=None, help="uv: 0=u, 1=v (default speed)")
    ap.add_argument("--level", type=int, default=-1, help="vertical level index (0=bottom, -1=surface)")
    ap.add_argument("--nodes", default=oc.DEFAULT_NODES, help="0-based node indices")
    ap.add_argument("--profile-node", type=int, default=None)
    ap.add_argument("--profile-time", default=None, help="YYYYMMDDHH (default: cycle time)")
    ap.add_argument("--cycle", default="2026092712")
    ap.add_argument("--out", default="obc_3d_compare.png")
    a = ap.parse_args()

    var = oc.detect_var(a.ops[0].rsplit(":", 1)[0], a.var)
    unit = oc.UNITS[var]
    what = ("speed" if (var == "uv" and a.component is None) else
            f"component {a.component} ({'u' if a.component == 0 else 'v'})" if var == "uv" else "")
    cyc = oc.parse_dt(a.cycle)
    lon, lat, dep, seg = oc.load_nodes(a.nodes_csv)
    nodes = [int(x) for x in a.nodes.split(",")]
    pn = a.profile_node if a.profile_node is not None else nodes[1]

    to, O = oc.load_series(a.ops, var, a.component)          # (T, N, L)
    tu, U = oc.load_series(a.ours, var, a.component)
    io, iu = oc.common(to, tu)
    nL = O.shape[2]
    lv = a.level % nL
    Dall = U[iu] - O[io]
    mx, rms = oc.stats(Dall)                                  # all nodes, all levels
    mxl, rmsl = oc.stats(Dall[:, :, lv])
    td = [oc.to_dt(s) for s in to[io]]
    B = None
    if a.before:
        tb, B = oc.load_series(a.before, var, a.component)
        jo, jb = oc.common(to, tb)
        bmx, brms = oc.stats(B[jb] - O[jo])

    pt = oc.parse_dt(a.profile_time) if a.profile_time else cyc
    ps = round((pt - oc.EPOCH).total_seconds())
    ip_o = int(np.where(to == ps)[0][0]); ip_u = int(np.where(tu == ps)[0][0])

    fig, ax = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    xlo, xhi = oc.to_dt(min(to[0], tu[0])), oc.to_dt(max(to[-1], tu[-1]))
    lvname = "surface" if lv == nL - 1 else "bottom" if lv == 0 else f"level {lv}"

    p = ax[0, 0]
    for k, nd in enumerate(nodes):
        c = oc.NODE_COLORS[k % 5]
        lab = f"node {nd}: {abs(lon[nd]):.1f}W {lat[nd]:.1f}N, {dep[nd]:.0f} m"
        p.plot([oc.to_dt(s) for s in to], O[:, nd, lv], color=c, lw=1.8, label=lab)
        p.plot([oc.to_dt(s) for s in tu], U[:, nd, lv], color="k", lw=1.0, ls="--")
        if B is not None:
            p.plot([oc.to_dt(s) for s in tb], B[:, nd, lv], color=c, lw=1.0, ls=":")
    p.plot([], [], color="0.3", lw=1.8, label=f"solid: {oc.NAMES['ops']}")
    p.plot([], [], color="k", lw=1.0, ls="--", label=f"dashed: {oc.NAMES['ours']}")
    if B is not None:
        p.plot([], [], color="0.3", lw=1.0, ls=":", label=f"dotted: {oc.NAMES['before']}")
    p.set_xlim(xlo, xhi); oc.shade_phases(p, cyc, (xlo, xhi)); oc.fmt_time_axis(p)
    p.set_title(f"{(var + chr(32) + what).strip()} at the {lvname} level (index {lv}), 5 boundary nodes", fontsize=10)
    p.set_ylabel(f"{var} ({unit})"); p.grid(True, alpha=0.25); p.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)

    p = ax[0, 1]
    for k, nd in enumerate(nodes):
        p.plot(td, Dall[:, nd, lv], color=oc.NODE_COLORS[k % 5], lw=1.2, marker="o", ms=3, label=f"node {nd}")
    p.fill_between(td, np.nanmin(Dall[:, :, lv], axis=1), np.nanmax(Dall[:, :, lv], axis=1),
                   color="0.85", zorder=0, label=f"range over all {Dall.shape[1]} nodes")
    p.axhline(0, color="k", lw=0.5)
    lim = max(mxl, 1e-12) * 1.15
    p.set_ylim(-lim, lim); p.set_xlim(xlo, xhi)
    oc.shade_phases(p, cyc, (xlo, xhi), label=False); oc.fmt_time_axis(p)
    p.set_ylabel(f"nos-workflow - operational ({unit})")
    p.set_title(f"Difference at the {lvname} level, common record times (y-axis symmetric, auto-scaled)", fontsize=10)
    txt = (f"{lvname} level, all nodes: max |diff| = {oc.fmt(mxl)} {unit}, RMS = {oc.fmt(rmsl)} {unit}\n"
           f"all levels, all nodes: max |diff| = {oc.fmt(mx)} {unit}, RMS = {oc.fmt(rms)} {unit}")
    if B is not None:
        txt += f"\nbefore fix vs operational (all): max |diff| = {oc.fmt(bmx)}, RMS = {oc.fmt(brms)} {unit}"
    p.text(0.02, 0.04, txt, transform=p.transAxes, fontsize=8, va="bottom",
           bbox=dict(fc="w", ec="0.6", alpha=0.9))
    p.grid(True, alpha=0.25); p.legend(fontsize=7, ncol=3, loc="upper right")

    lev = np.arange(nL)
    p = ax[1, 0]
    p.plot(O[ip_o, pn, :], lev, color=oc.COLORS["ops"], lw=1.8, marker="o", ms=3, label=oc.NAMES["ops"])
    p.plot(U[ip_u, pn, :], lev, color=oc.COLORS["ours"], lw=1.2, ls="--", marker="s", ms=3, label=oc.NAMES["ours"])
    if B is not None and ps in tb:
        p.plot(B[int(np.where(tb == ps)[0][0]), pn, :], lev, color=oc.COLORS["before"], lw=1.2, ls=":", label=oc.NAMES["before"])
    p.set_title(f"Depth profile at {oc.node_label(pn, lon[pn], lat[pn], dep[pn], seg[pn])}, {pt:%Y-%m-%d %H}Z", fontsize=10)
    p.set_xlabel(f"{var} ({unit})"); p.set_ylabel("vertical level index (0 = bottom, %d = surface)" % (nL - 1))
    p.grid(True, alpha=0.25); p.legend(fontsize=8)

    p = ax[1, 1]
    dprof = U[ip_u, pn, :] - O[ip_o, pn, :]
    p.plot(dprof, lev, color="purple", lw=1.4, marker="o", ms=3, label=f"node {pn}, {pt:%m-%d %H}Z")
    p.plot(np.sqrt(np.nanmean(Dall[:, pn, :] ** 2, axis=0)), lev, color="0.4", lw=1.0, ls="--",
           label=f"node {pn}: RMS over time")
    p.axvline(0, color="k", lw=0.5)
    lim = max(float(np.nanmax(np.abs(dprof))), float(np.nanmax(np.sqrt(np.nanmean(Dall[:, pn, :] ** 2, axis=0)))), 1e-12) * 1.15
    p.set_xlim(-lim, lim)
    pm, pr = oc.stats(dprof)
    p.set_title("Profile difference, nos-workflow - operational (x-axis symmetric, auto-scaled)", fontsize=10)
    p.set_xlabel(f"{unit}"); p.set_ylabel("vertical level index")
    p.text(0.02, 0.04, f"profile: max |diff| = {oc.fmt(pm)} {unit}, RMS = {oc.fmt(pr)} {unit}",
           transform=p.transAxes, fontsize=8, bbox=dict(fc="w", ec="0.6", alpha=0.9))
    p.grid(True, alpha=0.25); p.legend(fontsize=8, loc="upper right")

    fig.suptitle(f"Open-boundary {var}{' (' + what + ')' if what else ''}: {oc.NAMES['ops']} vs {oc.NAMES['ours']}, "
                 f"{oc.cycle_label(cyc)}", fontsize=14, fontweight="bold")
    oc.save(fig, a.out)
    print(f"{var} {what}: ours-ops all levels/nodes max|diff|={mx:.4g} RMS={rms:.4g} {unit} "
          f"({len(io)} common records)" + (f"; before-ops max={bmx:.4g}" if B is not None else ""))


if __name__ == "__main__":
    main()
