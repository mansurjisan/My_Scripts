#!/usr/bin/env python3
"""
=============================================================================
SECOFS Station Timeseries Comparison Plot
=============================================================================

Compare water level timeseries between UFS-SECOFS and Operational SECOFS
at NOAA tide gauge stations.

Usage:
    python plot_station_comparison.py

Configuration:
    Edit the USER CONFIGURATION section below to:
    - Set input/output directories
    - Choose stations to plot
    - Customize plot appearance

Author: SECOFS Team
Date: January 2026
=============================================================================
"""

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

#=============================================================================
# USER CONFIGURATION - Edit these settings
#=============================================================================

# Forecast cycle date and time
FORECAST_DATE = "2026-01-07"
FORECAST_CYCLE = "00Z"

# Input directories
UFS_STATION_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out'
OP_STATION_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out_op_secofs'

# Output directory for plots
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_plots'

# Stations to plot (use partial names - script will find matching stations)
# Examples: 'Duck', 'Key_West', 'Virginia_Key', 'Charleston', 'Baltimore'
STATIONS_TO_PLOT = [
    'Duck',
    'Key_West',
    'Virginia_Key',
    'Charleston',
    'Cedar_Key',
    'Baltimore',
    'Mayport',
    'Fort_Pulaski',
]

# Plot settings
FIGURE_WIDTH = 12        # inches
FIGURE_HEIGHT = 6        # inches
DPI = 150                # resolution
LINE_WIDTH = 2           # line thickness
GRID_ALPHA = 0.3         # grid transparency (0-1)

# Line colors and labels
OP_COLOR = 'blue'
OP_LABEL = 'Operational SECOFS'
UFS_COLOR = 'red'
UFS_LABEL = 'UFS-SECOFS (no restart)'

#=============================================================================
# END OF USER CONFIGURATION
#=============================================================================


def parse_station_file(filepath):
    """
    Parse SCHISM station.in file
    Returns: list of station names
    """
    stations = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        n_stations = int(lines[1].strip())
        for i in range(2, 2 + n_stations):
            parts = lines[i].split()
            if len(parts) > 4:
                name = ' '.join(parts[4:]).split(':')[0]
            else:
                name = f'Station_{i-1}'
            stations.append(name)
    return stations


def read_staout_file(filepath, n_stations):
    """
    Read SCHISM staout file (elevation timeseries)
    Returns: times (seconds), data (n_times x n_stations)
    """
    times = []
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            values = line.split()
            if len(values) > 1:
                times.append(float(values[0]))
                data.append([float(v) for v in values[1:n_stations+1]])
    return np.array(times), np.array(data)


def find_station_index(stations, search_term):
    """
    Find station index by partial name match
    Returns: (index, full_name) or (None, None)
    """
    search_lower = search_term.lower().replace('_', '').replace(' ', '')
    for i, name in enumerate(stations):
        name_lower = name.lower().replace('_', '').replace(' ', '')
        if search_lower in name_lower:
            return i, name
    return None, None


def clean_station_name(name):
    """Clean station name for display"""
    return name.replace('!', '').split('(')[0].replace('_', ' ').strip()


def plot_station(datetimes, op_data, ufs_data, station_name, output_path):
    """
    Create comparison plot for a single station
    """
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))

    # Plot both timeseries
    ax.plot(datetimes, op_data, color=OP_COLOR, linewidth=LINE_WIDTH,
            label=OP_LABEL)
    ax.plot(datetimes, ufs_data, color=UFS_COLOR, linewidth=LINE_WIDTH,
            label=UFS_LABEL)

    # Reference line at zero
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    # Labels and title
    ax.set_xlabel('Time (UTC)', fontsize=12)
    ax.set_ylabel('Water Level (m)', fontsize=12)
    ax.set_title(f'Water Level at {station_name}\nForecast Cycle: {FORECAST_DATE} {FORECAST_CYCLE}',
                 fontsize=14, fontweight='bold')

    # Legend and grid
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=GRID_ALPHA)

    # Rotate x-axis labels
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
    plt.close()


def main():
    """Main function"""

    print("="*60)
    print("SECOFS Station Timeseries Comparison")
    print("="*60)
    print(f"Forecast Cycle: {FORECAST_DATE} {FORECAST_CYCLE}")
    print(f"UFS Data: {UFS_STATION_DIR}")
    print(f"Operational Data: {OP_STATION_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print("="*60)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse station file
    station_file = os.path.join(UFS_STATION_DIR, 'station.in')
    if not os.path.exists(station_file):
        print(f"ERROR: Station file not found: {station_file}")
        return

    stations = parse_station_file(station_file)
    n_stations = len(stations)
    print(f"\nFound {n_stations} stations in station.in")

    # Read elevation data
    print("\nReading data...")
    ufs_file = os.path.join(UFS_STATION_DIR, 'staout_1')
    op_file = os.path.join(OP_STATION_DIR, 'staout_1')

    if not os.path.exists(ufs_file):
        print(f"ERROR: UFS staout file not found: {ufs_file}")
        return
    if not os.path.exists(op_file):
        print(f"ERROR: Operational staout file not found: {op_file}")
        return

    ufs_times, ufs_elev = read_staout_file(ufs_file, n_stations)
    op_times, op_elev = read_staout_file(op_file, n_stations)

    print(f"  UFS-SECOFS: {len(ufs_times)} time steps ({ufs_times[-1]/3600:.1f} hours)")
    print(f"  Operational: {len(op_times)} time steps ({op_times[-1]/3600:.1f} hours)")

    # Use common time range
    min_len = min(len(ufs_times), len(op_times))
    ufs_times = ufs_times[:min_len]
    ufs_elev = ufs_elev[:min_len, :]
    op_elev = op_elev[:min_len, :]

    # Replace fill values with NaN
    ufs_elev = np.where(np.abs(ufs_elev) > 1e6, np.nan, ufs_elev)
    op_elev = np.where(np.abs(op_elev) > 1e6, np.nan, op_elev)

    # Convert times to datetime
    base_date = datetime.strptime(FORECAST_DATE, "%Y-%m-%d")
    datetimes = [base_date + timedelta(seconds=t) for t in ufs_times]

    # Generate plots
    print(f"\nGenerating plots for {len(STATIONS_TO_PLOT)} stations...")
    print("-"*60)

    success_count = 0
    for search_term in STATIONS_TO_PLOT:
        idx, full_name = find_station_index(stations, search_term)

        if idx is None:
            print(f"  [SKIP] Station '{search_term}' not found")
            continue

        clean_name = clean_station_name(full_name)

        # Create output filename
        safe_name = search_term.lower().replace(' ', '_')
        output_file = os.path.join(OUTPUT_DIR, f'station_{safe_name}_comparison.png')

        # Generate plot
        plot_station(datetimes, op_elev[:, idx], ufs_elev[:, idx],
                    clean_name, output_file)

        print(f"  [OK] {clean_name} -> {os.path.basename(output_file)}")
        success_count += 1

    print("-"*60)
    print(f"\nComplete! Generated {success_count} plots in {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
