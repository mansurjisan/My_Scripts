#!/usr/bin/env python3
"""
Compare station timeseries between UFS-SECOFS and Operational SECOFS
"""

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

# Configuration
UFS_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out'
OP_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out_op_secofs'
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_plots'
BASE_DATE = datetime(2026, 1, 7, 0, 0, 0)


def parse_station_in(filepath):
    """Parse station.in file to get station names and coordinates"""
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
    """Parse staout file to get timeseries data"""
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


def compute_stats(obs, model):
    """Compute comparison statistics"""
    valid = ~np.isnan(obs) & ~np.isnan(model)
    if np.sum(valid) < 2:
        return {'rmse': np.nan, 'bias': np.nan, 'corr': np.nan, 'n': 0}

    o = obs[valid]
    m = model[valid]

    bias = np.mean(m - o)
    rmse = np.sqrt(np.mean((m - o)**2))

    if np.std(o) > 0 and np.std(m) > 0:
        corr = np.corrcoef(o, m)[0, 1]
    else:
        corr = np.nan

    return {'rmse': rmse, 'bias': bias, 'corr': corr, 'n': len(o)}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse station info (use UFS station.in)
    station_file = os.path.join(UFS_DIR, 'station.in')
    stations = parse_station_in(station_file)
    n_stations = len(stations)
    print(f"Found {n_stations} stations")

    # Parse elevation data from both sources
    print("Reading UFS-SECOFS elevation data...")
    ufs_times, ufs_elev = parse_staout(os.path.join(UFS_DIR, 'staout_1'), n_stations)
    print(f"  UFS: {len(ufs_times)} time steps, {ufs_times[-1]/3600:.1f} hours")

    print("Reading Operational SECOFS elevation data...")
    op_times, op_elev = parse_staout(os.path.join(OP_DIR, 'staout_1'), n_stations)
    print(f"  Operational: {len(op_times)} time steps, {op_times[-1]/3600:.1f} hours")

    # Replace fill values with NaN
    ufs_elev = np.where(np.abs(ufs_elev) > 1e6, np.nan, ufs_elev)
    op_elev = np.where(np.abs(op_elev) > 1e6, np.nan, op_elev)

    # Find common time range
    min_len = min(len(ufs_times), len(op_times))
    ufs_times = ufs_times[:min_len]
    op_times = op_times[:min_len]
    ufs_elev = ufs_elev[:min_len, :]
    op_elev = op_elev[:min_len, :]

    # Convert time to datetime
    datetimes = [BASE_DATE + timedelta(seconds=t) for t in ufs_times]

    # Select key NOAA tide gauge stations
    key_names = ['Key_West', 'Virginia_Key', 'Fort_Pulaski', 'Charleston',
                 'Wilmington', 'Duck', 'Baltimore', 'Atlantic_City',
                 'The_Battery', 'Boston', 'Mayport', 'Cedar_Key']

    station_map = {}
    for i, s in enumerate(stations):
        for key in key_names:
            if key.lower().replace('_', '') in s['name'].lower().replace('_', '').replace(' ', ''):
                station_map[s['name']] = i
                break

    print(f"\nFound {len(station_map)} key stations for comparison")

    # Plot 1: Multi-panel comparison (4x3 grid)
    fig, axes = plt.subplots(4, 3, figsize=(16, 14))
    axes = axes.flatten()

    plot_stations = list(station_map.items())[:12]
    all_stats = []

    for i, (name, idx) in enumerate(plot_stations):
        ax = axes[i]
        ufs = ufs_elev[:, idx]
        op = op_elev[:, idx]

        # Plot both timeseries
        ax.plot(datetimes, op, 'b-', linewidth=1.2, label='Operational', alpha=0.8)
        ax.plot(datetimes, ufs, 'r-', linewidth=1.2, label='UFS-SECOFS', alpha=0.8)
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

        # Compute stats
        stats = compute_stats(op, ufs)
        all_stats.append((name, stats))

        # Clean station name for title
        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')
        ax.set_title(f'{clean_name}\nRMSE={stats["rmse"]:.3f}m, Bias={stats["bias"]:.3f}m',
                     fontsize=10, fontweight='bold')
        ax.set_ylabel('Water Level (m)', fontsize=9)
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)

        if i == 0:
            ax.legend(loc='upper right', fontsize=8)

    for i in range(len(plot_stations), len(axes)):
        axes[i].set_visible(False)

    fig.suptitle(f'Water Level Comparison: Operational SECOFS vs UFS-SECOFS\n{BASE_DATE.strftime("%Y-%m-%d")} Forecast',
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUTPUT_DIR, 'comparison_timeseries.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nSaved: comparison_timeseries.png")

    # Plot 2: Difference timeseries
    fig, axes = plt.subplots(4, 3, figsize=(16, 14))
    axes = axes.flatten()

    for i, (name, idx) in enumerate(plot_stations):
        ax = axes[i]
        diff = ufs_elev[:, idx] - op_elev[:, idx]

        ax.plot(datetimes, diff, 'k-', linewidth=1)
        ax.axhline(y=0, color='r', linestyle='--', linewidth=1)
        ax.fill_between(datetimes, diff, 0, where=diff > 0, color='red', alpha=0.3)
        ax.fill_between(datetimes, diff, 0, where=diff < 0, color='blue', alpha=0.3)

        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')
        diff_valid = diff[~np.isnan(diff)]
        ax.set_title(f'{clean_name}\nmin={np.min(diff_valid):.3f}m, max={np.max(diff_valid):.3f}m',
                     fontsize=10, fontweight='bold')
        ax.set_ylabel('Difference (m)', fontsize=9)
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)

    for i in range(len(plot_stations), len(axes)):
        axes[i].set_visible(False)

    fig.suptitle(f'Water Level Difference (UFS - Operational)\n{BASE_DATE.strftime("%Y-%m-%d")} Forecast',
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUTPUT_DIR, 'comparison_difference.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: comparison_difference.png")

    # Plot 3: Combined overlay for key stations
    fig, ax = plt.subplots(figsize=(14, 8))

    colors = plt.cm.tab10(np.linspace(0, 1, min(6, len(plot_stations))))
    for i, (name, idx) in enumerate(plot_stations[:6]):
        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')
        ax.plot(datetimes, op_elev[:, idx], color=colors[i], linestyle='-',
                linewidth=1.5, label=f'{clean_name} (Op)')
        ax.plot(datetimes, ufs_elev[:, idx], color=colors[i], linestyle='--',
                linewidth=1.5, label=f'{clean_name} (UFS)')

    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    ax.set_xlabel('Time (UTC)', fontsize=12)
    ax.set_ylabel('Water Level (m)', fontsize=12)
    ax.set_title(f'Water Level Comparison at Selected Stations\nSolid = Operational, Dashed = UFS-SECOFS',
                 fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'comparison_overlay.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: comparison_overlay.png")

    # Print statistics summary
    print("\n" + "="*60)
    print("COMPARISON STATISTICS SUMMARY")
    print("="*60)
    print(f"{'Station':<30} {'RMSE (m)':<12} {'Bias (m)':<12} {'Corr':<8}")
    print("-"*60)

    rmse_all = []
    bias_all = []
    for name, stats in all_stats:
        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')[:28]
        if not np.isnan(stats['rmse']):
            rmse_all.append(stats['rmse'])
            bias_all.append(stats['bias'])
            print(f"{clean_name:<30} {stats['rmse']:<12.4f} {stats['bias']:<12.4f} {stats['corr']:<8.4f}")

    print("-"*60)
    print(f"{'MEAN':<30} {np.mean(rmse_all):<12.4f} {np.mean(bias_all):<12.4f}")
    print("="*60)

    print(f"\nAll plots saved to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
