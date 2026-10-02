#!/usr/bin/env python3
"""Cut a small plotting subset out of SCHISM nudging files (TEM_nu/SAL_nu or ops temnu/salnu).

usage: extract_nudge_subset.py --out SUBSET.npz --label NAME --start YYYYMMDDHH \
           --tem TEM.nc [--sal SAL.nc] [--ts-nodes 8] [--ts-ids 1,2,3]

For every record it keeps the surface and bottom levels at all nodes, plus the full
vertical profile at a few nodes for time series. Records are streamed one at a time,
so the ~745 MB ops files are fine on a login node. YYYYMMDDHH is the absolute time of
the file's time=0. Node ids (map_to_global_node) are saved, so different files can be
matched node by node; --ts-ids picks the same profile nodes in every subset.
"""
import argparse
from datetime import datetime

import numpy as np
from netCDF4 import Dataset


def time_seconds(ds):
    t = np.asarray(ds["time"][:], dtype=float)
    return t * 86400.0 if t.size and t.max() < 1000.0 else t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--start", required=True, help="YYYYMMDDHH of time=0")
    ap.add_argument("--tem", required=True)
    ap.add_argument("--sal")
    ap.add_argument("--ts-nodes", type=int, default=8, help="profile nodes spread over the node list")
    ap.add_argument("--ts-ids", default=None, help="comma list of global node ids for profiles")
    a = ap.parse_args()

    out = {"label": a.label, "start": a.start}
    for var, path in (("tem", a.tem), ("sal", a.sal)):
        if not path:
            continue
        with Dataset(path) as ds:
            ids = np.asarray(ds["map_to_global_node"][:]).astype(np.int64)
            t = time_seconds(ds)
            v = ds["tracer_concentration"]
            nt = v.shape[0]
            if a.ts_ids:
                want = np.array([int(x) for x in a.ts_ids.split(",")])
                pos = np.array([int(np.where(ids == w)[0][0]) for w in want if w in ids])
            else:
                pos = np.unique(np.linspace(0, len(ids) - 1, a.ts_nodes).astype(int))
            surf = np.empty((nt, len(ids)), np.float32)
            bot = np.empty((nt, len(ids)), np.float32)
            prof = np.empty((nt, len(pos), v.shape[2]), np.float32)
            for k in range(nt):
                rec = np.ma.filled(v[k, :, :, 0], np.nan).astype(np.float32)
                surf[k] = rec[:, -1]
                bot[k] = rec[:, 0]
                prof[k] = rec[pos]
                print(f"{var} record {k + 1}/{nt}", end="\r", flush=True)
            print()
        out.update({"ids": ids, "time": t, f"{var}_surf": surf, f"{var}_bot": bot,
                    f"{var}_prof": prof, "prof_ids": ids[pos]})
    np.savez_compressed(a.out, **out)
    print(f"saved {a.out}: {len(out['ids'])} nodes, {len(out['time'])} records, "
          f"profile nodes {list(out['prof_ids'])}")


if __name__ == "__main__":
    main()
