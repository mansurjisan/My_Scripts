#!/usr/bin/env python3
"""Extract SCHISM open-boundary nodes from a large mesh into small CSV files.

usage: extract_obc_nodes.py HGRID.gr3 [-l HGRID.ll] [-v VGRID.in] [-o PREFIX]

Writes PREFIX_nodes.csv with one row per open-boundary node, in hgrid order:
    seg,k,node,x,y,depth[,lon,lat]
With -v (LSC2 vgrid.in, ivcor=1), also writes PREFIX_vgrid.csv:
    node,kbp,sigma_1,...,sigma_nvrt
Only the boundary nodes are kept, so the outputs are small even for a
multi-million-node mesh.
"""
import argparse
import csv


def first_int(line):
    return int(line.split("!", 1)[0].split("=", 1)[0].split()[0])


def read_open_boundaries(path):
    with open(path) as f:
        f.readline()
        ne, nn = (int(v) for v in f.readline().split()[:2])
        for _ in range(nn + ne):
            f.readline()
        nope = first_int(f.readline())
        f.readline()
        segs = []
        for _ in range(nope):
            n = first_int(f.readline())
            segs.append([first_int(f.readline()) for _ in range(n)])
    return nn, segs


def read_node_coords(path, wanted):
    out = {}
    with open(path) as f:
        f.readline()
        nn = int(f.readline().split()[1])
        for _ in range(nn):
            parts = f.readline().split()
            nid = int(parts[0])
            if nid in wanted:
                out[nid] = (float(parts[1]), float(parts[2]), float(parts[3]))
    return out


def read_vgrid_columns(path, nodes, nn):
    idx = [n - 1 for n in nodes]
    with open(path) as f:
        ivcor = first_int(f.readline())
        if ivcor != 1:
            raise SystemExit(f"vgrid ivcor={ivcor}; only LSC2 (ivcor=1) is supported")
        nvrt = first_int(f.readline())
        kbp_all = f.readline().split("!", 1)[0].split()
        kbp = [int(kbp_all[i]) for i in idx]
        sig = []
        for _ in range(nvrt):
            vals = f.readline().split()
            if len(vals) == nn + 1:
                vals = vals[1:]
            sig.append([float(vals[i]) for i in idx])
    return nvrt, kbp, sig


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("hgrid")
    ap.add_argument("-l", "--hgrid-ll")
    ap.add_argument("-v", "--vgrid")
    ap.add_argument("-o", "--prefix", default="obc")
    a = ap.parse_args()

    nn, segs = read_open_boundaries(a.hgrid)
    nodes = [n for s in segs for n in s]
    wanted = set(nodes)
    xyz = read_node_coords(a.hgrid, wanted)
    ll = read_node_coords(a.hgrid_ll, wanted) if a.hgrid_ll else None

    with open(f"{a.prefix}_nodes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seg", "k", "node", "x", "y", "depth"] + (["lon", "lat"] if ll else []))
        for si, s in enumerate(segs, 1):
            for k, n in enumerate(s, 1):
                row = [si, k, n, *xyz[n]]
                if ll:
                    row += list(ll[n][:2])
                w.writerow(row)
    print(f"{len(segs)} open boundaries, {len(nodes)} nodes -> {a.prefix}_nodes.csv "
          f"(segment sizes {[len(s) for s in segs]})")

    if a.vgrid:
        nvrt, kbp, sig = read_vgrid_columns(a.vgrid, nodes, nn)
        with open(f"{a.prefix}_vgrid.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["node", "kbp"] + [f"sigma_{k}" for k in range(1, nvrt + 1)])
            for j, n in enumerate(nodes):
                w.writerow([n, kbp[j]] + [sig[k][j] for k in range(nvrt)])
        print(f"nvrt={nvrt} -> {a.prefix}_vgrid.csv")


if __name__ == "__main__":
    main()
