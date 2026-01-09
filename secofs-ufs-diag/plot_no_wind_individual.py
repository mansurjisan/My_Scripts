#!/usr/bin/env python3
"""
Plot individual station timeseries comparing SECOFS and UFS-SECOFS (no wind)
"""

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

# Configuration
SECOFS_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out_secofs_no_wind'
UFS_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out_ufs_no_wind'
STATION_FILE = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out/station.in'
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_plots/no_wind_individual'
BASE_DATE = datetime(2026, 1, 7, 0, 0, 0)

# Plot settings
FIGURE_WIDTH = 12
FIGURE_HEIGHT = 6
DPI = 150
LINE_WIDTH = 2

# Labels and colors
SECOFS_COLOR = 'blue'
SECOFS_LABEL = 'SECOFS (no wind)'
UFS_COLOR = 'red'
UFS_LABEL = 'UFS-SECOFS (no wind)'


def parse_station_in(filepath):
    """Parse station.in file"""
    stations = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        n_stations = int(lines[1].strip())
        for i in range(2, 2 + n_stations):
            parts = lines[i].split()
            idx = int(parts[0])
            lon = float(parts[1])
            lat = float(parts[2])
            comment = ' '.join(parts[4:]) if len(parts) > 4 else f'Station_{idx}'
            name = comment.split(':')[0] if ':' in comment else comment
            stations.append({'idx': idx, 'lon': lon, 'lat': lat, 'name': name})
    return stations


def parse_staout(filepath, n_stations):
    """Parse staout file"""
    data = []
    times = []
    with open(filepath, 'r') as f:
        for line in f:
            values = line.split()
            if len(values) > 1:
                time_sec = float(values[0])
                station_vals = [float(v) for v in values[1:n_stations+1]]
                times.append(time_sec)
                data.append(station_vals)
    return np.array(times), np.array(data)


def clean_station_name(name):
    """Clean station name for display"""
    return name.replace('!', '').split('(')[0].replace('_', ' ').strip()


def safe_filename(name):
    """Create safe filename from station name"""
    return name.lower().replace(' ', '_').replace('/', '_').replace('!', '').split('(')[0].strip('_')


def compute_stats(data1, data2):
    """Compute comparison statistics"""
    valid = ~np.isnan(data1) & ~np.isnan(data2)
    if np.sum(valid) < 2:
        return {'rmse': np.nan, 'bias': np.nan, 'corr': np.nan, 'max_diff': np.nan}

    d1 = data1[valid]
    d2 = data2[valid]

    diff = d2 - d1
    bias = np.mean(diff)
    rmse = np.sqrt(np.mean(diff**2))
    max_diff = np.max(np.abs(diff))

    if np.std(d1) > 0 and np.std(d2) > 0:
        corr = np.corrcoef(d1, d2)[0, 1]
    else:
        corr = np.nan

    return {'rmse': rmse, 'bias': bias, 'corr': corr, 'max_diff': max_diff}


def plot_station(datetimes, secofs_data, ufs_data, station_name, output_path):
    """Create comparison plot for a single station"""
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))

    # Plot both timeseries
    ax.plot(datetimes, secofs_data, color=SECOFS_COLOR, linewidth=LINE_WIDTH,
            label=SECOFS_LABEL)
    ax.plot(datetimes, ufs_data, color=UFS_COLOR, linewidth=LINE_WIDTH,
            label=UFS_LABEL, linestyle='--', alpha=0.8)

    # Reference line at zero
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    # Compute stats
    stats = compute_stats(secofs_data, ufs_data)

    # Labels and title
    ax.set_xlabel('Time (UTC)', fontsize=12)
    ax.set_ylabel('Water Level (m)', fontsize=12)
    ax.set_title(f'Water Level at {station_name}\n'
                 f'No-Wind Sensitivity Test | Forecast Cycle: 2026-01-07 00Z\n'
                 f'RMSE={stats["rmse"]:.6f}m, Max Diff={stats["max_diff"]:.6f}m, Corr={stats["corr"]:.6f}',
                 fontsize=12, fontweight='bold')

    # Legend and grid
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=0.3)

    # Rotate x-axis labels
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
    plt.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("No-Wind Individual Station Timeseries Plots")
    print("=" * 60)

    # Parse station info
    stations = parse_station_in(STATION_FILE)
    n_stations = len(stations)
    print(f"Found {n_stations} stations")

    # Read data
    print("\nReading SECOFS (no wind) data...")
    secofs_times, secofs_elev = parse_staout(os.path.join(SECOFS_DIR, 'staout_1'), n_stations)
    print(f"  Time steps: {len(secofs_times)}, Duration: {secofs_times[-1]/3600:.1f} hours")

    print("\nReading UFS-SECOFS (no wind) data...")
    ufs_times, ufs_elev = parse_staout(os.path.join(UFS_DIR, 'staout_1'), n_stations)
    print(f"  Time steps: {len(ufs_times)}, Duration: {ufs_times[-1]/3600:.1f} hours")

    # Replace fill values with NaN
    secofs_elev = np.where(np.abs(secofs_elev) > 1e6, np.nan, secofs_elev)
    ufs_elev = np.where(np.abs(ufs_elev) > 1e6, np.nan, ufs_elev)

    # Use common time range
    min_len = min(len(secofs_times), len(ufs_times))
    secofs_times = secofs_times[:min_len]
    secofs_elev = secofs_elev[:min_len, :]
    ufs_elev = ufs_elev[:min_len, :]

    # Convert to datetime
    datetimes = [BASE_DATE + timedelta(seconds=t) for t in secofs_times]

    print(f"\nUsing common time range: {min_len} time steps ({secofs_times[-1]/3600:.1f} hours)")

    # Generate plots for all stations
    print(f"\nGenerating plots for {n_stations} stations...")
    print("-" * 60)

    for i, station in enumerate(stations):
        name = station['name']
        clean_name = clean_station_name(name)
        safe_name = safe_filename(name)

        # Skip if all NaN
        if np.all(np.isnan(secofs_elev[:, i])) or np.all(np.isnan(ufs_elev[:, i])):
            continue

        output_file = os.path.join(OUTPUT_DIR, f'no_wind_{safe_name}.png')

        plot_station(datetimes, secofs_elev[:, i], ufs_elev[:, i], clean_name, output_file)

        if (i + 1) % 50 == 0:
            print(f"  Generated {i + 1}/{n_stations} plots...")

    print("-" * 60)
    print(f"\nComplete! Plots saved to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
