#!/usr/bin/env python3
"""
Plot sea surface height (zeta) from UFS-Coastal SCHISM output
US East Coast focus + Puerto Rico inset
Adapted for schout_elev_*.nc format
"""

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from netCDF4 import Dataset
import matplotlib.tri as tri
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os
from datetime import datetime, timedelta
from multiprocessing import Pool
from glob import glob

# Global configuration
BASE_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107'
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/plots_us_pr'
BASE_DATE = datetime(2026, 1, 7, 0, 0, 0)

# Domains - extended west, zoomed in from east
US_LON_MIN, US_LON_MAX = -87.0, -70.0
US_LAT_MIN, US_LAT_MAX = 24.0, 40.0
PR_LON_MIN, PR_LON_MAX = -68.0, -64.5
PR_LAT_MIN, PR_LAT_MAX = 17.5, 19.0


def get_all_timesteps():
    """Get all time steps from elev files"""
    elev_files = sorted(glob(os.path.join(BASE_DIR, 'schout_elev_*.nc')))
    timesteps = []

    for fpath in elev_files:
        fname = os.path.basename(fpath)
        # Skip empty/invalid files
        if os.path.getsize(fpath) < 1000:
            continue
        try:
            nc = Dataset(fpath, 'r')
            times = nc.variables['time'][:]
            nc.close()
            for t_idx, t_val in enumerate(times):
                timesteps.append((fpath, t_idx, float(t_val)))
        except Exception as e:
            print(f"Warning: Could not read {fname}: {e}")

    return timesteps


def plot_single_timestep(args, grid_data):
    """Plot a single timestep"""
    idx, fpath, t_idx, t_sec, total = args
    lon, lat, triangles, mask_main, mask_pr = grid_data

    fname = os.path.basename(fpath)

    try:
        ds = Dataset(fpath, 'r')
        zeta = np.array(ds.variables['elev'][t_idx, :])
        ds.close()

        # Handle fill values
        zeta = np.where(np.abs(zeta) > 1e10, np.nan, zeta)

        # Calculate timestamp
        timestamp = BASE_DATE + timedelta(seconds=t_sec)
        time_str = timestamp.strftime('%Y-%m-%d %H:%M UTC')

        # Create figure with explicit axes positions
        fig = plt.figure(figsize=(14, 10), dpi=150)

        # Main axis - US East Coast [left, bottom, width, height]
        ax_main = fig.add_axes([0.1, 0.15, 0.8, 0.75], projection=ccrs.PlateCarree())
        ax_main.set_extent([US_LON_MIN, US_LON_MAX, US_LAT_MIN, US_LAT_MAX], crs=ccrs.PlateCarree())
        ax_main.add_feature(cfeature.GSHHSFeature(scale='high', levels=[1],
                            facecolor='#D4D4D4', edgecolor='#404040', linewidth=0.5))
        ax_main.add_feature(cfeature.STATES, edgecolor='gray', linewidth=0.3)
        ax_main.set_facecolor('#E6F3F7')

        gl = ax_main.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5)
        gl.top_labels = False
        gl.right_labels = False

        # Plot main with pre-computed mask
        triang_main = tri.Triangulation(lon, lat, triangles, mask=mask_main)
        c = ax_main.tripcolor(triang_main, zeta, cmap='RdYlBu_r', vmin=-1.0, vmax=3.0,
                              shading='flat', transform=ccrs.PlateCarree())

        # Puerto Rico inset - larger box, pushed more inside
        ax_pr = fig.add_axes([0.52, 0.22, 0.26, 0.20], projection=ccrs.PlateCarree())
        ax_pr.set_extent([PR_LON_MIN, PR_LON_MAX, PR_LAT_MIN, PR_LAT_MAX], crs=ccrs.PlateCarree())
        ax_pr.add_feature(cfeature.GSHHSFeature(scale='full', levels=[1],
                          facecolor='#D4D4D4', edgecolor='#404040', linewidth=0.5))
        ax_pr.set_facecolor('#E6F3F7')

        # Plot PR with pre-computed mask
        triang_pr = tri.Triangulation(lon, lat, triangles, mask=mask_pr)
        ax_pr.tripcolor(triang_pr, zeta, cmap='RdYlBu_r', vmin=-1.0, vmax=3.0,
                        shading='flat', transform=ccrs.PlateCarree())

        for spine in ax_pr.spines.values():
            spine.set_edgecolor('black')
            spine.set_linewidth(2)
        ax_pr.set_title('Puerto Rico', fontsize=9, fontweight='bold')

        # Colorbar
        cax = fig.add_axes([0.2, 0.08, 0.6, 0.02])
        cbar = fig.colorbar(c, cax=cax, orientation='horizontal')
        cbar.set_label('Water Level (m)', fontsize=11, fontweight='bold')

        # Determine stage based on time
        hours_from_start = t_sec / 3600.0
        stage = 'FORECAST' if hours_from_start >= 6 else 'NOWCAST'

        ax_main.set_title(f'UFS-SECOFS Water Level ({stage})\n{time_str}', fontsize=14, fontweight='bold')

        hour_str = timestamp.strftime('%Y%m%d_%H%M')
        output_file = os.path.join(OUTPUT_DIR, f'zeta_{idx+1:02d}_{stage.lower()}_{hour_str}.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        return f"[{idx+1}/{total}] {fname}[{t_idx}] -> {os.path.basename(output_file)}"
    except Exception as e:
        return f"[{idx+1}/{total}] {fname}[{t_idx}] FAILED: {str(e)}"


def worker_init(grid_data):
    """Initialize worker with grid data"""
    global _grid_data
    _grid_data = grid_data


def worker_func(args):
    """Worker wrapper that uses global grid data"""
    return plot_single_timestep(args, _grid_data)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Get all timesteps from all elev files
    timesteps = get_all_timesteps()
    total = len(timesteps)
    print(f"Found {total} time steps across elevation files")

    if total == 0:
        print("ERROR: No valid time steps found!")
        return

    # Pre-load grid (from first file)
    first_file = timesteps[0][0]
    ds = Dataset(first_file, 'r')
    lon = np.array(ds.variables['SCHISM_hgrid_node_x'][:])
    lat = np.array(ds.variables['SCHISM_hgrid_node_y'][:])
    face_nodes = np.array(ds.variables['SCHISM_hgrid_face_nodes'][:]) - 1  # 0-indexed
    ds.close()

    print(f"Grid loaded: {len(lon)} nodes, {len(face_nodes)} faces")
    print(f"  Lon range: {lon.min():.2f} to {lon.max():.2f}")
    print(f"  Lat range: {lat.min():.2f} to {lat.max():.2f}")

    # Create triangulation (handle quads by splitting into triangles)
    print("Creating triangulation...")
    triangles = []
    for face in face_nodes:
        valid = face[face >= 0]  # Remove fill values
        if len(valid) == 3:
            triangles.append(valid)
        elif len(valid) == 4:
            # Split quad into 2 triangles
            triangles.append([valid[0], valid[1], valid[2]])
            triangles.append([valid[0], valid[2], valid[3]])
    triangles = np.array(triangles)
    print(f"  Triangles: {len(triangles)}")

    # Create triangulation for mask computation
    triang = tri.Triangulation(lon, lat, triangles)

    # Mask for main US plot
    mask_main = np.any(lon[triang.triangles] < US_LON_MIN - 1, axis=1)
    mask_main |= np.any(lon[triang.triangles] > US_LON_MAX + 1, axis=1)
    mask_main |= np.any(lat[triang.triangles] < US_LAT_MIN - 1, axis=1)
    mask_main |= np.any(lat[triang.triangles] > US_LAT_MAX + 1, axis=1)

    # Mask for PR inset
    mask_pr = np.any(lon[triang.triangles] < PR_LON_MIN - 0.5, axis=1)
    mask_pr |= np.any(lon[triang.triangles] > PR_LON_MAX + 0.5, axis=1)
    mask_pr |= np.any(lat[triang.triangles] < PR_LAT_MIN - 0.5, axis=1)
    mask_pr |= np.any(lat[triang.triangles] > PR_LAT_MAX + 0.5, axis=1)

    print("Triangulation and masks ready")

    # Prepare grid data tuple for workers
    grid_data = (lon, lat, triangles, mask_main, mask_pr)

    # Prepare task arguments
    tasks = [(idx, fpath, t_idx, t_sec, total)
             for idx, (fpath, t_idx, t_sec) in enumerate(timesteps)]

    n_workers = min(4, total)
    print(f"\nStarting parallel processing with {n_workers} workers...\n")

    # Run with multiprocessing pool
    with Pool(processes=n_workers, initializer=worker_init, initargs=(grid_data,)) as pool:
        results = pool.map(worker_func, tasks)

    # Print results
    for result in results:
        print(result)

    print(f"\nDone! Generated {total} zeta plots in {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
