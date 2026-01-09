#!/usr/bin/env python3
"""
Compare UFS-SECOFS output with standalone SCHISM output
Creates side-by-side difference plots for zeta and wind speed
Parallelized with 4 workers
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
from glob import glob
from multiprocessing import Pool

# Configuration
BASE_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107'
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/comparison_plots'
BASE_DATE = datetime(2026, 1, 7, 0, 0, 0)

# Domains
US_LON_MIN, US_LON_MAX = -87.0, -70.0
US_LAT_MIN, US_LAT_MAX = 24.0, 40.0


def load_ufs_data_at_hour(hour, var_type='elev'):
    """Load UFS data for a specific forecast hour (1-indexed)"""
    if var_type == 'elev':
        pattern = 'schout_elev_*.nc'
        var_name = 'elev'
    else:
        pattern = 'schout_wind_*.nc'
        var_name = 'wind_speed'

    files = sorted(glob(os.path.join(BASE_DIR, pattern)))

    # Each file has 6 time steps
    file_idx = (hour - 1) // 6
    time_idx = (hour - 1) % 6

    if file_idx >= len(files):
        return None, None, None, None

    fpath = files[file_idx]
    if os.path.getsize(fpath) < 1000:
        return None, None, None, None

    nc = Dataset(fpath, 'r')
    lon = np.array(nc.variables['SCHISM_hgrid_node_x'][:])
    lat = np.array(nc.variables['SCHISM_hgrid_node_y'][:])
    face_nodes = np.array(nc.variables['SCHISM_hgrid_face_nodes'][:]) - 1

    times = nc.variables['time'][:]
    if time_idx >= len(times):
        nc.close()
        return None, None, None, None

    if var_type == 'elev':
        data = np.array(nc.variables[var_name][time_idx, :])
    else:
        wind = nc.variables[var_name][time_idx, :, :]
        wind_u = np.array(wind[:, 0])
        wind_v = np.array(wind[:, 1])
        wind_u = np.where(np.abs(wind_u) > 1e10, np.nan, wind_u)
        wind_v = np.where(np.abs(wind_v) > 1e10, np.nan, wind_v)
        data = np.sqrt(wind_u**2 + wind_v**2)

    nc.close()

    # Handle fill values
    data = np.where(np.abs(data) > 1e10, np.nan, data)

    return lon, lat, face_nodes, data


def load_schism_data_at_hour(hour, var_type='elev'):
    """Load standalone SCHISM data for a specific forecast hour"""
    fname = f'secofs.t00z.20260107.fields.f{hour:03d}.nc.old'
    fpath = os.path.join(BASE_DIR, fname)

    if not os.path.exists(fpath):
        return None, None, None, None

    nc = Dataset(fpath, 'r')
    lon = np.array(nc.variables['lon'][:])
    lat = np.array(nc.variables['lat'][:])
    ele = np.array(nc.variables['ele'][:]) - 1  # 0-indexed

    if var_type == 'elev':
        data = np.array(nc.variables['zeta'][0, :])
    else:
        uwind = np.array(nc.variables['uwind_speed'][0, :])
        vwind = np.array(nc.variables['Vwind_speed'][0, :])
        data = np.sqrt(uwind**2 + vwind**2)

    nc.close()
    return lon, lat, ele.T, data


def create_triangles(face_nodes):
    """Convert face nodes to triangles (handling quads)"""
    triangles = []
    for face in face_nodes:
        valid = face[face >= 0]
        if len(valid) == 3:
            triangles.append(valid)
        elif len(valid) == 4:
            triangles.append([valid[0], valid[1], valid[2]])
            triangles.append([valid[0], valid[2], valid[3]])
    return np.array(triangles)


def plot_comparison(hour, var_type='elev'):
    """Create comparison plot for a specific hour"""

    # Load data
    ufs_lon, ufs_lat, ufs_faces, ufs_data = load_ufs_data_at_hour(hour, var_type)
    sch_lon, sch_lat, sch_ele, sch_data = load_schism_data_at_hour(hour, var_type)

    if ufs_data is None or sch_data is None:
        print(f"  Hour {hour}: Missing data (UFS={ufs_data is not None}, SCHISM={sch_data is not None})")
        return None

    # Create triangles for UFS data
    ufs_triangles = create_triangles(ufs_faces)

    # Calculate difference (SCHISM uses same grid, so direct subtraction works)
    diff = ufs_data - sch_data

    # Compute stats
    valid_diff = diff[~np.isnan(diff)]
    diff_min, diff_max = np.nanmin(diff), np.nanmax(diff)
    diff_mean, diff_std = np.nanmean(diff), np.nanstd(diff)

    # Create masks for plotting
    triang_ufs = tri.Triangulation(ufs_lon, ufs_lat, ufs_triangles)
    triang_sch = tri.Triangulation(sch_lon, sch_lat, sch_ele)

    # Mask for US region
    def create_mask(triang, lon):
        mask = np.any(lon[triang.triangles] < US_LON_MIN - 1, axis=1)
        mask |= np.any(lon[triang.triangles] > US_LON_MAX + 1, axis=1)
        mask |= np.any(triang.y[triang.triangles] < US_LAT_MIN - 1, axis=1)
        mask |= np.any(triang.y[triang.triangles] > US_LAT_MAX + 1, axis=1)
        return mask

    mask_ufs = create_mask(triang_ufs, ufs_lon)
    mask_sch = create_mask(triang_sch, sch_lon)

    triang_ufs_masked = tri.Triangulation(ufs_lon, ufs_lat, ufs_triangles, mask=mask_ufs)
    triang_sch_masked = tri.Triangulation(sch_lon, sch_lat, sch_ele, mask=mask_sch)

    # Set up colormaps and ranges
    if var_type == 'elev':
        cmap = 'RdYlBu_r'
        vmin, vmax = -1.0, 3.0
        diff_cmap = 'RdBu_r'
        diff_vmin, diff_vmax = -0.5, 0.5
        var_label = 'Water Level (m)'
        var_title = 'Water Level'
    else:
        cmap = 'jet'
        vmin, vmax = 0, 15
        diff_cmap = 'RdBu_r'
        diff_vmin, diff_vmax = -3, 3
        var_label = 'Wind Speed (m/s)'
        var_title = 'Wind Speed'

    # Create figure
    fig, axes = plt.subplots(1, 3, figsize=(18, 8),
                             subplot_kw={'projection': ccrs.PlateCarree()})

    timestamp = BASE_DATE + timedelta(hours=hour)
    time_str = timestamp.strftime('%Y-%m-%d %H:%M UTC')

    for ax in axes:
        ax.set_extent([US_LON_MIN, US_LON_MAX, US_LAT_MIN, US_LAT_MAX], crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.GSHHSFeature(scale='high', levels=[1],
                       facecolor='#D4D4D4', edgecolor='#404040', linewidth=0.5))
        ax.add_feature(cfeature.STATES, edgecolor='gray', linewidth=0.3)
        ax.set_facecolor('white')

    # Plot Operational SECOFS
    c1 = axes[0].tripcolor(triang_sch_masked, sch_data, cmap=cmap, vmin=vmin, vmax=vmax,
                           shading='flat', transform=ccrs.PlateCarree())
    axes[0].set_title(f'Operational SECOFS\n{var_title}', fontsize=12, fontweight='bold')

    # Plot UFS-SECOFS
    c2 = axes[1].tripcolor(triang_ufs_masked, ufs_data, cmap=cmap, vmin=vmin, vmax=vmax,
                           shading='flat', transform=ccrs.PlateCarree())
    axes[1].set_title(f'UFS-SECOFS\n{var_title}', fontsize=12, fontweight='bold')

    # Plot difference
    c3 = axes[2].tripcolor(triang_ufs_masked, diff, cmap=diff_cmap, vmin=diff_vmin, vmax=diff_vmax,
                           shading='flat', transform=ccrs.PlateCarree())
    axes[2].set_title(f'Difference\n(UFS - Operational)',
                      fontsize=12, fontweight='bold')

    # Colorbars
    cbar1 = fig.colorbar(c1, ax=axes[0], orientation='horizontal', pad=0.05, shrink=0.8)
    cbar1.set_label(var_label, fontsize=10)

    cbar2 = fig.colorbar(c2, ax=axes[1], orientation='horizontal', pad=0.05, shrink=0.8)
    cbar2.set_label(var_label, fontsize=10)

    cbar3 = fig.colorbar(c3, ax=axes[2], orientation='horizontal', pad=0.05, shrink=0.8)
    cbar3.set_label(f'Difference ({var_label.split()[0]})', fontsize=10)

    # Suptitle
    fig.suptitle(f'Forecast Hour {hour:02d} | {time_str}',
                 fontsize=14, fontweight='bold', y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    # Save
    output_file = os.path.join(OUTPUT_DIR, f'{var_type}_compare_{hour:02d}_{timestamp.strftime("%Y%m%d_%H%M")}.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return f"Hour {hour:02d}: diff min={diff_min:.4f}, max={diff_max:.4f}, mean={diff_mean:.4f}, std={diff_std:.4f}"


def plot_comparison_wrapper(args):
    """Wrapper for multiprocessing"""
    hour, var_type = args
    return plot_comparison(hour, var_type)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Check available hours
    old_files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.old')])
    max_hour = len(old_files)
    print(f"Found {max_hour} standalone SCHISM files")

    # Prepare all tasks (both elev and wind for all hours)
    tasks = []
    for hour in range(1, max_hour + 1):
        tasks.append((hour, 'elev'))
        tasks.append((hour, 'wind'))

    total = len(tasks)
    print(f"Creating {total} comparison plots with 4 workers...\n")

    # Run with multiprocessing
    with Pool(processes=4) as pool:
        results = pool.map(plot_comparison_wrapper, tasks)

    # Print results
    print("\n=== Results ===")
    for result in results:
        if result:
            print(f"  {result}")

    print(f"\nDone! Plots saved to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
