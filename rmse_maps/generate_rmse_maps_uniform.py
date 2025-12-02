#!/usr/bin/env python3
"""
Generate RMSE maps with fixed 216 station count across all cycles.

This script uses ALL stations from the union of all cycles.
Stations without data for a specific cycle are shown as gray markers.

Uses GSHHS high-resolution coastlines.

Usage:
    python generate_rmse_maps_uniform.py --date 20251122
    python generate_rmse_maps_uniform.py --date 20251122 --cycles 00 06 12 18

Author: Generated for STOFS-2D validation
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from mpl_toolkits.axes_grid1 import make_axes_locatable
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


def get_forecast_cycle(date_str, cycle):
    """
    Get the forecast cycle time.

    For example:
    - 00z cycle on 20251122 -> Forecast Cycle is 2025-11-22 00:00 UTC
    - 06z cycle on 20251122 -> Forecast Cycle is 2025-11-22 06:00 UTC
    - 12z cycle on 20251122 -> Forecast Cycle is 2025-11-22 12:00 UTC
    - 18z cycle on 20251122 -> Forecast Cycle is 2025-11-22 18:00 UTC
    """
    # Parse date and cycle
    year = int(date_str[:4])
    month = int(date_str[4:6])
    day = int(date_str[6:8])
    hour = int(cycle)

    # Create forecast time
    forecast_time = datetime(year, month, day, hour, 0, 0)

    return forecast_time.strftime("%Y-%m-%d %H:%M UTC")


def build_master_station_list(input_dir, date_str, cycles):
    """
    Build a master station list from the UNION of all cycles.

    Uses model station index as unique identifier (not CO-OPS ID) to preserve
    all stations including those that map to the same CO-OPS station.

    Returns:
        DataFrame with all unique stations by (lat, lon) combination
    """
    all_stations = []

    for cycle in cycles:
        csv_file = os.path.join(input_dir, f'rmse_stats_{date_str}_{cycle}z.csv')
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            # Create unique key from lat/lon (rounded to handle floating point)
            df['lat_round'] = df['lat'].round(5)
            df['lon_round'] = df['lon'].round(5)
            df['station_key'] = df['lat_round'].astype(str) + '_' + df['lon_round'].astype(str)
            # Keep location columns
            station_info = df[['station_key', 'lat', 'lon', 'station_name', 'coops_id']].copy()
            all_stations.append(station_info)
            print(f"  {cycle}z: {len(df)} stations")
        else:
            print(f"  {cycle}z: CSV not found - {csv_file}")

    if not all_stations:
        return None

    # Combine all and drop duplicates by station_key (lat/lon)
    master_df = pd.concat(all_stations, ignore_index=True)
    master_df = master_df.drop_duplicates(subset=['station_key'], keep='first')

    print(f"  Total unique stations (union by lat/lon): {len(master_df)}")
    return master_df


def create_rmse_map(df_with_data, df_no_data, rmse_column, title, output_file, init_time=None, total_stations=216):
    """
    Create a geographic RMSE map with GSHHS high-resolution coastlines.

    Stations with data are colored by RMSE value.
    Stations without data are shown as gray markers.
    """

    if HAS_CARTOPY:
        fig = plt.figure(figsize=(16, 10))
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        ax.set_extent([-180, -50, 15, 75], crs=ccrs.PlateCarree())

        # Add GSHHS high-resolution coastlines
        gshhs_coast = GSHHSFeature(scale='h', levels=[1], facecolor='lightgray', edgecolor='black', linewidth=0.5)
        ax.add_feature(gshhs_coast)

        ax.add_feature(cfeature.OCEAN, facecolor='white', zorder=0)
        ax.add_feature(cfeature.BORDERS, linewidth=0.3, linestyle=':')
        ax.add_feature(cfeature.STATES, linewidth=0.2, edgecolor='gray')

        gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5, linestyle='--')
        gl.top_labels = False
        gl.right_labels = False

        transform = ccrs.PlateCarree()
    else:
        fig, ax = plt.subplots(figsize=(16, 10))
        ax.set_xlim(-180, -50)
        ax.set_ylim(15, 75)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.grid(True, alpha=0.3)
        transform = None

    cmap = plt.cm.YlOrRd
    norm = mcolors.Normalize(vmin=0, vmax=0.5)

    # Plot stations WITHOUT data first (gray markers)
    if df_no_data is not None and len(df_no_data) > 0:
        lons_no = df_no_data['lon'].values
        lats_no = df_no_data['lat'].values
        if HAS_CARTOPY:
            ax.scatter(lons_no, lats_no, c='lightgray', s=80, edgecolors='darkgray',
                      linewidths=0.5, transform=transform, zorder=9, marker='o', label='No data')
        else:
            ax.scatter(lons_no, lats_no, c='lightgray', s=80, edgecolors='darkgray',
                      linewidths=0.5, zorder=9, marker='o', label='No data')

    # Plot stations WITH data (colored by RMSE)
    if df_with_data is not None and len(df_with_data) > 0:
        rmse_values = df_with_data[rmse_column].values
        lons = df_with_data['lon'].values
        lats = df_with_data['lat'].values

        if HAS_CARTOPY:
            scatter = ax.scatter(lons, lats, c=rmse_values, cmap=cmap, norm=norm,
                               s=80, edgecolors='black', linewidths=0.5,
                               transform=transform, zorder=10)
        else:
            scatter = ax.scatter(lons, lats, c=rmse_values, cmap=cmap, norm=norm,
                               s=80, edgecolors='black', linewidths=0.5, zorder=10)

        # Create colorbar with same height as plot
        fig_box = ax.get_position()
        cbar_ax = fig.add_axes([fig_box.x1 + 0.02, fig_box.y0, 0.02, fig_box.height])
        cbar = plt.colorbar(scatter, cax=cbar_ax, orientation='vertical')
        cbar.set_label('RMSE (m)', fontsize=12)

    ax.set_title(title, fontsize=14, fontweight='bold')

    # Station count info - just total number
    station_text = f"Stations: {total_stations}"
    ax.text(0.02, 0.98, station_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', alpha=0.9))

    if init_time:
        time_text = f"Forecast Cycle: {init_time}"
        ax.text(0.98, 0.98, time_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', alpha=0.9))

    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_file}")


def generate_maps_from_csv(date_str, cycle, input_dir, output_dir, data_dir, master_stations):
    """
    Generate RMSE maps from existing CSV file, using master station list.
    Stations without data are shown as gray markers.
    """
    print(f"\n{'='*60}")
    print(f"Generating RMSE maps for {date_str} {cycle}Z (fixed {len(master_stations)} stations)")
    print(f"{'='*60}")

    csv_file = os.path.join(input_dir, f'rmse_stats_{date_str}_{cycle}z.csv')
    if not os.path.exists(csv_file):
        print(f"  CSV file not found: {csv_file}")
        return None

    df = pd.read_csv(csv_file)
    # Create station key from lat/lon
    df['lat_round'] = df['lat'].round(5)
    df['lon_round'] = df['lon'].round(5)
    df['station_key'] = df['lat_round'].astype(str) + '_' + df['lon_round'].astype(str)

    # Get stations WITH data for this cycle
    stations_with_data = set(df['station_key'].values)

    # Get stations WITHOUT data (in master list but not in this cycle)
    master_keys = set(master_stations['station_key'].values)
    stations_without_data = master_keys - stations_with_data

    # Create dataframe for stations without data
    df_no_data = master_stations[master_stations['station_key'].isin(stations_without_data)].copy()

    print(f"  Read {len(df)} stations with data")
    print(f"  {len(df_no_data)} stations without data (shown as gray)")

    os.makedirs(output_dir, exist_ok=True)

    # Calculate Forecast Cycle time
    init_time = get_forecast_cycle(date_str, cycle)

    # Save CSV with all stations (with data having RMSE values, without data having NaN)
    df_all = master_stations.copy()
    df_all = df_all.merge(
        df[['station_key', 'without_rmse', 'with_rmse', 'without_corr', 'with_corr']],
        on='station_key',
        how='left'
    )
    filtered_csv = os.path.join(output_dir, f'rmse_stats_{date_str}_{cycle}z.csv')
    df_all.to_csv(filtered_csv, index=False)
    print(f"  Saved CSV: {filtered_csv}")

    total_stations = len(master_stations)

    without_title = f"STOFS2D Barotropic {cycle}z Forecast Performance (WITHOUT Anomaly Correction)"
    without_file = os.path.join(output_dir, f'rmse_map_{date_str}_{cycle}z_without.png')
    create_rmse_map(df, df_no_data, 'without_rmse', without_title, without_file, init_time, total_stations)

    with_title = f"STOFS2D Barotropic {cycle}z Forecast Performance (WITH Anomaly Correction)"
    with_file = os.path.join(output_dir, f'rmse_map_{date_str}_{cycle}z_with.png')
    create_rmse_map(df, df_no_data, 'with_rmse', with_title, with_file, init_time, total_stations)

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
    parser = argparse.ArgumentParser(description='Generate RMSE maps with fixed station count')
    parser.add_argument('--date', required=True, help='Date in YYYYMMDD format')
    parser.add_argument('--cycles', nargs='+', default=['00', '06', '12', '18'],
                       help='Cycles to process (default: 00 06 12 18)')
    parser.add_argument('--input-dir', default=None,
                       help='Input directory with CSV files (default: rmse_maps_{date})')
    parser.add_argument('--output-dir', default=None,
                       help='Output directory (default: rmse_maps_{date}_uniform)')

    args = parser.parse_args()

    date_str = args.date
    cycles = args.cycles

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = args.input_dir or os.path.join(script_dir, f'rmse_maps_{date_str}')
    output_dir = args.output_dir or os.path.join(script_dir, f'rmse_maps_{date_str}_uniform')
    data_dir = os.path.join(script_dir, 'stofs_data', date_str, 'raw')

    print("="*60)
    print("STOFS-2D RMSE MAP GENERATOR (Fixed Station Count)")
    print("="*60)
    print(f"Date:       {date_str}")
    print(f"Cycles:     {', '.join([c + 'Z' for c in cycles])}")
    print(f"Input dir:  {input_dir}")
    print(f"Output dir: {output_dir}")

    if HAS_CARTOPY:
        print("Cartopy:    Available (using GSHHS high-res coastlines)")
    else:
        print("Cartopy:    Not available (using simple scatter plot)")

    # Build master station list from UNION of all cycles
    print("\nBuilding master station list (union of all cycles)...")
    master_stations = build_master_station_list(input_dir, date_str, cycles)

    if master_stations is None or len(master_stations) == 0:
        print("ERROR: Could not build master station list. Make sure CSV files exist.")
        return

    all_results = {}
    for cycle in cycles:
        df = generate_maps_from_csv(date_str, cycle, input_dir, output_dir, data_dir, master_stations)
        if df is not None:
            all_results[cycle] = df

    if all_results:
        combine_maps_to_pdf(output_dir, date_str, cycles)

    print("\n" + "="*60)
    print("RMSE MAP GENERATION COMPLETE")
    print("="*60)
    print(f"Output directory: {output_dir}")
    print(f"Fixed station count: {len(master_stations)} across all cycles")
    print("Stations without data shown as gray markers")


if __name__ == "__main__":
    main()
