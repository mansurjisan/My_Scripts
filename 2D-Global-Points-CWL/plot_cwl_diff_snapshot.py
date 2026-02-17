#!/usr/bin/env python3
"""
STOFS-2D Water Elevation Difference Snapshot Script
Creates a single snapshot visualization of water elevation differences.
"""

import matplotlib
matplotlib.use('Agg')

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from netCDF4 import Dataset, num2date
import warnings
import argparse
import sys
import os
from datetime import datetime

warnings.filterwarnings('ignore')

# Try to import geopandas for coastlines
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    print("Warning: geopandas not available. Coastlines will not be drawn.")


def extract_regional_mesh(x, y, elements, lon_min, lon_max, lat_min, lat_max, buffer=0.1):
    """
    Extract mesh subset for a specific region with remapped indices.
    """
    node_mask = ((x >= lon_min - buffer) & (x <= lon_max + buffer) &
                 (y >= lat_min - buffer) & (y <= lat_max + buffer))
    regional_indices = np.where(node_mask)[0]
    index_set = set(regional_indices)

    # Create index mapping
    index_map = {old_idx: new_idx for new_idx, old_idx in enumerate(regional_indices)}

    # Filter elements
    valid_triangles = []
    for elem in elements:
        if elem[0] in index_set and elem[1] in index_set and elem[2] in index_set:
            new_tri = [index_map[elem[0]], index_map[elem[1]], index_map[elem[2]]]
            valid_triangles.append(new_tri)

    if len(valid_triangles) == 0:
        return None, None, None, None

    elements_reg = np.array(valid_triangles)
    x_reg = x[regional_indices]
    y_reg = y[regional_indices]

    return x_reg, y_reg, elements_reg, regional_indices


def generate_snapshot(noanomaly_file, anomaly_file, output_file,
                      lon_min, lon_max, lat_min, lat_max,
                      location_name, timestep=0,
                      vmin=-0.3, vmax=0.3):
    """
    Generate a single snapshot of water elevation difference.
    """
    print(f"Loading data files...")

    # Load data
    nc1 = Dataset(noanomaly_file, 'r')
    nc2 = Dataset(anomaly_file, 'r')

    x = nc1.variables['x'][:]
    y = nc1.variables['y'][:]
    elements = nc1.variables['element'][:] - 1  # 0-based

    # Get time info
    time_var = nc1.variables['time']
    times = time_var[:]
    try:
        time_units = time_var.units
        time_dates = num2date(times, time_units)
    except:
        time_dates = [f"Step {i}" for i in range(len(times))]

    n_times = len(times)
    print(f"Found {n_times} time steps")

    # Validate timestep
    if timestep < 0 or timestep >= n_times:
        print(f"Error: timestep {timestep} out of range [0, {n_times-1}]")
        nc1.close()
        nc2.close()
        return False

    # Extract regional mesh
    print(f"Extracting regional mesh for {location_name}...")
    x_reg, y_reg, elements_reg, regional_indices = extract_regional_mesh(
        x, y, elements, lon_min, lon_max, lat_min, lat_max
    )

    if x_reg is None:
        print(f"Error: No triangles in region for {location_name}!")
        nc1.close()
        nc2.close()
        return False

    print(f"Regional mesh: {len(x_reg)} nodes, {len(elements_reg)} triangles")

    # Load coastline
    coastline_gdf = None
    coastline_path = "/mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL/GSHHS_shp/f/GSHHS_f_L1.shp"
    if GEOPANDAS_AVAILABLE and os.path.exists(coastline_path):
        try:
            print("Loading coastline data...")
            coastline_gdf = gpd.read_file(coastline_path, bbox=(lon_min-0.5, lat_min-0.5, lon_max+0.5, lat_max+0.5))
            print("Coastline loaded")
        except Exception as e:
            print(f"Warning: Could not load coastline: {e}")

    # Read zeta for specified time step
    print(f"Reading time step {timestep}...")
    zeta1 = nc1.variables['zeta'][timestep, :]
    zeta2 = nc2.variables['zeta'][timestep, :]

    # Handle masked arrays
    if hasattr(zeta1, 'mask'):
        zeta1 = np.where(zeta1.mask, np.nan, zeta1.data)
    if hasattr(zeta2, 'mask'):
        zeta2 = np.where(zeta2.mask, np.nan, zeta2.data)

    # Calculate difference (bias-corrected - non-bias-corrected)
    diff = zeta2 - zeta1
    diff_reg = diff[regional_indices]

    # Get time string
    try:
        time_str = time_dates[timestep].strftime('%Y-%m-%d %H:%M UTC')
    except:
        time_str = str(time_dates[timestep])

    nc1.close()
    nc2.close()

    # Create triangulation
    triang = tri.Triangulation(x_reg, y_reg, triangles=elements_reg)

    # Setup colormap
    colors_neg = plt.cm.Blues_r(np.linspace(0.2, 0.9, 128))
    colors_pos = plt.cm.YlOrRd(np.linspace(0.1, 0.9, 128))
    colors = np.vstack([colors_neg, colors_pos])
    cmap = LinearSegmentedColormap.from_list('custom_diverging', colors)
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 16), dpi=300)
    ax.set_facecolor('#E6F3F7')

    # Mask bad values
    mask_nan = np.isnan(diff_reg)
    mask_outlier = np.abs(diff_reg) > 1.5
    mask_bad = mask_nan | mask_outlier
    tri_has_bad = mask_bad[triang.triangles].any(axis=1)
    triang.set_mask(tri_has_bad)
    data_clean = np.where(mask_bad, 0, diff_reg)

    # Plot
    levels = np.linspace(vmin, vmax, 61)
    im = ax.tricontourf(triang, data_clean, levels=levels, cmap=cmap, norm=norm, extend='both')

    # Add coastline
    if coastline_gdf is not None:
        coastline_gdf.plot(ax=ax, facecolor='#D4D4D4', edgecolor='#404040', linewidth=0.8, zorder=5)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('equal')

    # Determine if nowcast or forecast
    nowcast_hours = 6
    if timestep < nowcast_hours:
        period_label = "NOWCAST"
        period_color = "#1E90FF"
        hour_in_period = timestep + 1
        period_text = f"{period_label} (Hour {hour_in_period}/6)"
    else:
        period_label = "FORECAST"
        period_color = "#FF6347"
        hour_in_period = timestep - nowcast_hours + 1
        total_forecast_hours = n_times - nowcast_hours
        period_text = f"{period_label} (Hour {hour_in_period}/{total_forecast_hours})"

    ax.set_title(f'Difference in Water Elevation ({location_name}):\nBias-Corrected vs Non-Bias-Corrected\n{time_str}',
                 fontsize=14, fontweight='bold', pad=10)
    ax.set_xlabel('Longitude (degrees)', fontsize=12)
    ax.set_ylabel('Latitude (degrees)', fontsize=12)
    ax.tick_params(axis='both', labelsize=10)

    # Add nowcast/forecast label
    ax.text(0.02, 0.98, period_text,
            transform=ax.transAxes, fontsize=11, fontweight='bold',
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=period_color, edgecolor='black', alpha=0.9),
            color='white', zorder=20)

    # Add colorbar - larger size
    cbar = fig.colorbar(im, ax=ax, orientation='vertical', shrink=0.7, pad=0.02, aspect=25)
    cbar.set_label('Difference (m)', fontsize=14, fontweight='bold')
    cbar.ax.tick_params(labelsize=12)
    cbar.set_ticks([vmin, -0.2, -0.1, 0, 0.1, 0.2, vmax])

    # Save
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"Snapshot saved: {output_file}")

    return True


def main():
    parser = argparse.ArgumentParser(description='Generate STOFS-2D water elevation difference snapshot')
    parser.add_argument('noanomaly_file', help='Path to non-bias-corrected NetCDF file')
    parser.add_argument('anomaly_file', help='Path to bias-corrected NetCDF file')
    parser.add_argument('--output', '-o', required=True, help='Output PNG file path')
    parser.add_argument('--lon-range', nargs=2, type=float, default=[-82, -65], help='Longitude range (min max)')
    parser.add_argument('--lat-range', nargs=2, type=float, default=[24, 45], help='Latitude range (min max)')
    parser.add_argument('--location-name', default='US East Coast', help='Location name for title')
    parser.add_argument('--timestep', '-t', type=int, default=0, help='Time step index to plot (0-based)')
    parser.add_argument('--vmin', type=float, default=-0.3, help='Color scale minimum')
    parser.add_argument('--vmax', type=float, default=0.3, help='Color scale maximum')

    args = parser.parse_args()

    # Check input files exist
    if not os.path.exists(args.noanomaly_file):
        print(f"Error: File not found: {args.noanomaly_file}")
        sys.exit(1)
    if not os.path.exists(args.anomaly_file):
        print(f"Error: File not found: {args.anomaly_file}")
        sys.exit(1)

    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print(f"Generating snapshot for: {args.location_name}")
    print(f"  Region: [{args.lon_range[0]}, {args.lon_range[1]}] x [{args.lat_range[0]}, {args.lat_range[1]}]")
    print(f"  Time step: {args.timestep}")

    success = generate_snapshot(
        args.noanomaly_file,
        args.anomaly_file,
        args.output,
        args.lon_range[0], args.lon_range[1],
        args.lat_range[0], args.lat_range[1],
        args.location_name,
        args.timestep,
        args.vmin,
        args.vmax
    )

    if success:
        print("Snapshot generation complete!")
    else:
        print("Snapshot generation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
