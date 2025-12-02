#!/usr/bin/env python3
"""
Generate RMSE maps for STOFS-2D Global Bias Correction Validation (v2 - Faster)

This version only processes stations that have existing comparison plots,
significantly reducing the time needed to fetch CO-OPS data.

Creates geographic maps showing RMSE at each station location,
color-coded by RMSE value (0-0.5m scale).

Two maps per cycle:
  - WITHOUT Anomaly Correction
  - WITH Anomaly Correction

Usage:
    python generate_rmse_maps_v2.py --date 20251122
    python generate_rmse_maps_v2.py --date 20251122 --cycles 00 06 12 18

Author: Generated for STOFS-2D validation
"""

import os
import sys
import re
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from datetime import datetime
from netCDF4 import Dataset
from glob import glob

# Set backend before other imports
import matplotlib
matplotlib.use('Agg')

# Try to import cartopy for geographic plots
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.feature import GSHHSFeature
    HAS_CARTOPY = True
except ImportError:
    HAS_CARTOPY = False
    print("Warning: cartopy not installed. Using simple scatter plot instead.")

from stofs2d_obs import Fort61Reader, ModelObsComparison
from stofs2d_obs.observations import COOPSMatcher
from searvey import fetch_coops_station


def get_stations_from_plots(plots_dir):
    """
    Extract station indices from existing comparison plot filenames.
    Filenames are like: station_0000_8410140_comparison.png
    Returns list of (station_idx, coops_id) tuples.
    """
    png_files = glob(os.path.join(plots_dir, 'station_*_comparison.png'))
    stations = []
    for f in png_files:
        basename = os.path.basename(f)
        # station_0000_8410140_comparison.png
        match = re.match(r'station_(\d+)_(\d+)_comparison\.png', basename)
        if match:
            stations.append({
                'station_idx': int(match.group(1)),
                'coops_id': match.group(2)
            })
    return stations


def collect_rmse_statistics(cwl_file, noanomaly_file, station_list, datum='MSL'):
    """
    Collect RMSE statistics for specified stations only.

    Args:
        cwl_file: Path to WITH anomaly NetCDF file
        noanomaly_file: Path to WITHOUT anomaly NetCDF file
        station_list: List of dicts with 'station_idx' and 'coops_id'
        datum: Vertical datum (default: MSL)

    Returns:
        DataFrame with RMSE statistics for each station
    """
    print(f"Collecting RMSE statistics for {len(station_list)} stations...")
    print(f"  WITH anomaly: {cwl_file}")
    print(f"  WITHOUT anomaly: {noanomaly_file}")

    # Read station info from WITH anomaly file
    reader1 = Fort61Reader(cwl_file)
    reader2 = Fort61Reader(noanomaly_file)

    matcher = COOPSMatcher()
    results = []

    total = len(station_list)
    for i, station in enumerate(station_list):
        station_idx = station['station_idx']
        coops_id = station['coops_id']

        try:
            # Get station info from WITH anomaly file
            station_info = reader1.get_station_info(station_idx)

            # Find matching station in noanomaly file by name
            found_idx = None
            for j in range(reader2.n_stations):
                info = reader2.get_station_info(j)
                if info['name'] == station_info['name']:
                    found_idx = j
                    break

            if found_idx is None:
                continue

            # Read model data
            model_data1 = reader1.get_station_data(station_idx)  # WITH anomaly
            model_data2 = reader2.get_station_data(found_idx)  # WITHOUT anomaly

            # Fetch observation data
            try:
                obs_data = fetch_coops_station(
                    station_id=coops_id,
                    start_date=station_info['time_range'][0],
                    end_date=station_info['time_range'][1],
                    product='water_level',
                    datum=datum,
                )
            except:
                try:
                    obs_data = fetch_coops_station(
                        station_id=coops_id,
                        start_date=station_info['time_range'][0],
                        end_date=station_info['time_range'][1],
                        product='water_level',
                        datum='MSL',
                    )
                except:
                    continue

            if obs_data is None or len(obs_data) == 0:
                continue

            # Create comparison objects and calculate statistics
            comp1 = ModelObsComparison(model_data1, obs_data, station_info['name'], "STOFS2D", datum)
            comp2 = ModelObsComparison(model_data2, obs_data, station_info['name'], "STOFS2D", datum)

            stats1 = comp1.calculate_statistics()
            stats2 = comp2.calculate_statistics()

            if stats1 is None or stats2 is None:
                continue

            if len(comp1.aligned) == 0 or len(comp2.aligned) == 0:
                continue

            results.append({
                'station_idx': station_idx,
                'station_name': station_info['name'],
                'coops_id': coops_id,
                'lon': station_info['lon'],
                'lat': station_info['lat'],
                'with_rmse': stats1['rmse'],
                'with_corr': stats1['correlation'],
                'without_rmse': stats2['rmse'],
                'without_corr': stats2['correlation'],
                'n_points': stats1['n_points']
            })

            if (i + 1) % 50 == 0 or (i + 1) == total:
                print(f"  Processed {i+1}/{total} stations... ({len(results)} successful)")

        except Exception as e:
            continue

    reader1.close()
    reader2.close()

    print(f"  Collected statistics for {len(results)} stations")
    return pd.DataFrame(results)


def create_rmse_map(df, rmse_column, title, output_file, init_time=None):
    """
    Create a geographic RMSE map.

    Args:
        df: DataFrame with lon, lat, and RMSE columns
        rmse_column: Column name for RMSE values ('with_rmse' or 'without_rmse')
        title: Plot title
        output_file: Output PNG file path
        init_time: Initial time string for info box
    """

    if HAS_CARTOPY:
        # Create figure with cartopy projection
        fig = plt.figure(figsize=(16, 10))
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        # Set map extent to cover US coastlines (including Alaska, Hawaii, PR)
        ax.set_extent([-180, -50, 15, 75], crs=ccrs.PlateCarree())

        # Add GSHHS high-resolution coastlines
        # GSHHS scale options: 'c' (coarse), 'l' (low), 'i' (intermediate), 'h' (high), 'f' (full)
        # Using 'h' (high) resolution for good detail without being too slow
        gshhs_coast = GSHHSFeature(scale='h', levels=[1], facecolor='lightgray', edgecolor='black', linewidth=0.5)
        ax.add_feature(gshhs_coast)

        # Add ocean background
        ax.add_feature(cfeature.OCEAN, facecolor='white', zorder=0)

        # Add borders and states with standard resolution (GSHHS doesn't include these)
        ax.add_feature(cfeature.BORDERS, linewidth=0.3, linestyle=':')
        ax.add_feature(cfeature.STATES, linewidth=0.2, edgecolor='gray')

        # Add gridlines
        gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5, linestyle='--')
        gl.top_labels = False
        gl.right_labels = False

        transform = ccrs.PlateCarree()
    else:
        # Simple scatter plot without cartopy
        fig, ax = plt.subplots(figsize=(16, 10))
        ax.set_xlim(-180, -50)
        ax.set_ylim(15, 75)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.grid(True, alpha=0.3)
        transform = None

    # Create colormap (yellow to red)
    cmap = plt.cm.YlOrRd
    norm = mcolors.Normalize(vmin=0, vmax=0.5)

    # Plot stations
    rmse_values = df[rmse_column].values
    lons = df['lon'].values
    lats = df['lat'].values

    if HAS_CARTOPY:
        scatter = ax.scatter(lons, lats, c=rmse_values, cmap=cmap, norm=norm,
                           s=80, edgecolors='black', linewidths=0.5,
                           transform=transform, zorder=10)
    else:
        scatter = ax.scatter(lons, lats, c=rmse_values, cmap=cmap, norm=norm,
                           s=80, edgecolors='black', linewidths=0.5, zorder=10)

    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, orientation='vertical', shrink=0.7, pad=0.02)
    cbar.set_label('RMSE (m)', fontsize=12)

    # Add title
    ax.set_title(title, fontsize=14, fontweight='bold')

    # Add info boxes
    # Station count box (top left)
    station_text = f"Stations: {len(df)}"
    ax.text(0.02, 0.98, station_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', alpha=0.9))

    # Initial time box (top right)
    if init_time:
        time_text = f"Initial Time: {init_time}"
        ax.text(0.98, 0.98, time_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', alpha=0.9))

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_file}")


def get_initial_time_from_nc(nc_file):
    """Extract initial time from NetCDF file."""
    try:
        nc = Dataset(nc_file, 'r')
        time_var = nc.variables['time']
        time_units = time_var.units  # e.g., "seconds since 2025-11-22 00:00:00"

        # Parse the reference time
        if 'since' in time_units:
            ref_time_str = time_units.split('since')[1].strip()
            ref_time = datetime.strptime(ref_time_str, "%Y-%m-%d %H:%M:%S")
            nc.close()
            return ref_time.strftime("%Y-%m-%d %H:%M UTC")
        nc.close()
    except:
        pass
    return None


def generate_rmse_maps_for_cycle(date_str, cycle, plots_dir, data_dir, output_dir):
    """
    Generate RMSE maps for a single cycle.
    Creates two maps: WITHOUT and WITH anomaly correction.
    """
    print(f"\n{'='*60}")
    print(f"Generating RMSE maps for {date_str} {cycle}Z")
    print(f"{'='*60}")

    # Get station list from existing plots
    station_list = get_stations_from_plots(plots_dir)
    if not station_list:
        print(f"  No comparison plots found in {plots_dir}")
        return None

    print(f"  Found {len(station_list)} comparison plots")

    # Define file patterns
    if cycle == '00':
        cwl_file = os.path.join(data_dir, f'stofs_2d_glo.t{cycle}z.points.cwl.nc')
        noanomaly_file = os.path.join(data_dir, f'stofs_2d_glo.t{cycle}z.points.cwl.noanomaly.nc')
        if not os.path.exists(noanomaly_file):
            noanomaly_file = os.path.join(data_dir, f'stofs_2d_glo.t{cycle}z.points.autoval.cwl.noanomaly.nc')
    else:
        cwl_file = os.path.join(data_dir, f'stofs_2d_glo.t{cycle}z.points.cwl.nc')
        noanomaly_file = os.path.join(data_dir, f'stofs_2d_glo.t{cycle}z.points.cwl.noanomaly.nc')

    if not os.path.exists(cwl_file):
        print(f"  CWL file not found: {cwl_file}")
        return None

    if not os.path.exists(noanomaly_file):
        print(f"  NoAnomaly file not found: {noanomaly_file}")
        return None

    os.makedirs(output_dir, exist_ok=True)

    # Get initial time from NetCDF
    init_time = get_initial_time_from_nc(cwl_file)

    # Collect RMSE statistics for stations with existing plots
    df = collect_rmse_statistics(cwl_file, noanomaly_file, station_list)

    if len(df) == 0:
        print("  No valid stations found")
        return None

    # Save statistics to CSV
    csv_file = os.path.join(output_dir, f'rmse_stats_{date_str}_{cycle}z.csv')
    df.to_csv(csv_file, index=False)
    print(f"  Saved statistics: {csv_file}")

    # Generate WITHOUT anomaly map
    without_title = f"STOFS2D Barotropic {cycle}z Forecast Performance (WITHOUT Anomaly Correction)"
    without_file = os.path.join(output_dir, f'rmse_map_{date_str}_{cycle}z_without.png')
    create_rmse_map(df, 'without_rmse', without_title, without_file, init_time)

    # Generate WITH anomaly map
    with_title = f"STOFS2D Barotropic {cycle}z Forecast Performance (WITH Anomaly Correction)"
    with_file = os.path.join(output_dir, f'rmse_map_{date_str}_{cycle}z_with.png')
    create_rmse_map(df, 'with_rmse', with_title, with_file, init_time)

    return df


def combine_maps_to_pdf(output_dir, date_str, cycles):
    """Combine all RMSE maps into a single PDF."""
    from PIL import Image

    png_files = []
    for cycle in cycles:
        without_file = os.path.join(output_dir, f'rmse_map_{date_str}_{cycle}z_without.png')
        with_file = os.path.join(output_dir, f'rmse_map_{date_str}_{cycle}z_with.png')
        if os.path.exists(without_file):
            png_files.append(without_file)
        if os.path.exists(with_file):
            png_files.append(with_file)

    if len(png_files) == 0:
        print("No PNG files found to combine")
        return None

    print(f"\nCombining {len(png_files)} maps into PDF...")

    images = []
    for png_file in png_files:
        img = Image.open(png_file)
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        images.append(img)

    pdf_file = os.path.join(output_dir, f'rmse_maps_{date_str}.pdf')
    if images:
        images[0].save(pdf_file, save_all=True, append_images=images[1:])
        print(f"PDF saved: {pdf_file}")
        return pdf_file

    return None


def main():
    parser = argparse.ArgumentParser(description='Generate RMSE maps for STOFS-2D validation (v2 - faster)')
    parser.add_argument('--date', required=True, help='Date in YYYYMMDD format')
    parser.add_argument('--cycles', nargs='+', default=['00', '06', '12', '18'],
                       help='Cycles to process (default: 00 06 12 18)')
    parser.add_argument('--output-dir', default=None,
                       help='Output directory (default: rmse_maps_{date})')

    args = parser.parse_args()

    date_str = args.date
    cycles = args.cycles

    # Set directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = args.output_dir or os.path.join(script_dir, f'rmse_maps_{date_str}')

    print("="*60)
    print("STOFS-2D RMSE MAP GENERATOR (v2 - Faster)")
    print("="*60)
    print(f"Date:       {date_str}")
    print(f"Cycles:     {', '.join([c + 'Z' for c in cycles])}")
    print(f"Output dir: {output_dir}")

    # Check for cartopy
    if HAS_CARTOPY:
        print("Cartopy:    Available (using geographic projection)")
    else:
        print("Cartopy:    Not available (using simple scatter plot)")

    all_results = {}
    for cycle in cycles:
        # Look for comparison plots directory
        plots_dir = os.path.join(script_dir, f'comparison_plots_{date_str}_{cycle}z')
        data_dir = os.path.join(script_dir, 'stofs_data', date_str, 'raw')

        if not os.path.exists(plots_dir):
            print(f"\n  Plots directory not found: {plots_dir}")
            continue

        if not os.path.exists(data_dir):
            print(f"\n  Data directory not found: {data_dir}")
            continue

        df = generate_rmse_maps_for_cycle(date_str, cycle, plots_dir, data_dir, output_dir)
        if df is not None:
            all_results[cycle] = df

    # Combine to PDF
    if all_results:
        combine_maps_to_pdf(output_dir, date_str, cycles)

    print("\n" + "="*60)
    print("RMSE MAP GENERATION COMPLETE")
    print("="*60)
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
