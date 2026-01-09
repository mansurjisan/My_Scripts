#!/usr/bin/env python3
"""
Compare station timeseries between SECOFS (standalone SCHISM) and UFS-SECOFS
Both runs have wind forcing disabled for sensitivity testing.
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
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_plots/no_wind_comparison'
BASE_DATE = datetime(2026, 1, 7, 0, 0, 0)

# Labels
SECOFS_LABEL = 'SECOFS (no wind)'
UFS_LABEL = 'UFS-SECOFS (no wind)'


def parse_station_in(filepath):
    """Parse station.in file to get station names"""
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


def compute_stats(data1, data2):
    """Compute comparison statistics"""
    valid = ~np.isnan(data1) & ~np.isnan(data2)
    if np.sum(valid) < 2:
        return {'rmse': np.nan, 'bias': np.nan, 'corr': np.nan, 'max_diff': np.nan, 'n': 0}

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

    return {'rmse': rmse, 'bias': bias, 'corr': corr, 'max_diff': max_diff, 'n': len(d1)}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("NO-WIND SENSITIVITY TEST COMPARISON")
    print("SECOFS (standalone SCHISM) vs UFS-SECOFS")
    print("=" * 70)

    # Parse station info
    stations = parse_station_in(STATION_FILE)
    n_stations = len(stations)
    print(f"\nFound {n_stations} stations")

    # Read elevation data
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
    print(f"\nUsing common time range: {min_len} time steps ({secofs_times[min_len-1]/3600:.1f} hours)")

    secofs_times = secofs_times[:min_len]
    ufs_times = ufs_times[:min_len]
    secofs_elev = secofs_elev[:min_len, :]
    ufs_elev = ufs_elev[:min_len, :]

    # Check if times match
    time_diff = np.max(np.abs(secofs_times - ufs_times))
    print(f"Max time difference: {time_diff} seconds")

    # Convert to datetime
    datetimes = [BASE_DATE + timedelta(seconds=t) for t in secofs_times]

    # Select key stations
    key_names = ['Key_West', 'Virginia_Key', 'Fort_Pulaski', 'Charleston',
                 'Wilmington', 'Duck', 'Baltimore', 'Atlantic_City',
                 'The_Battery', 'Boston', 'Mayport', 'Cedar_Key']

    station_map = {}
    for i, s in enumerate(stations):
        for key in key_names:
            if key.lower().replace('_', '') in s['name'].lower().replace('_', '').replace(' ', ''):
                station_map[s['name']] = i
                break

    print(f"\nFound {len(station_map)} key stations for detailed plots")

    # Compute overall statistics
    print("\n" + "=" * 70)
    print("STATION-BY-STATION COMPARISON")
    print("=" * 70)
    print(f"{'Station':<35} {'RMSE (m)':<12} {'Bias (m)':<12} {'Max Diff':<12} {'Corr':<8}")
    print("-" * 70)

    all_stats = []
    for name, idx in station_map.items():
        stats = compute_stats(secofs_elev[:, idx], ufs_elev[:, idx])
        all_stats.append((name, stats))
        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')[:33]
        if not np.isnan(stats['rmse']):
            print(f"{clean_name:<35} {stats['rmse']:<12.6f} {stats['bias']:<12.6f} {stats['max_diff']:<12.6f} {stats['corr']:<8.6f}")

    # Summary statistics
    rmse_vals = [s['rmse'] for _, s in all_stats if not np.isnan(s['rmse'])]
    bias_vals = [s['bias'] for _, s in all_stats if not np.isnan(s['bias'])]
    max_diff_vals = [s['max_diff'] for _, s in all_stats if not np.isnan(s['max_diff'])]

    print("-" * 70)
    print(f"{'MEAN':<35} {np.mean(rmse_vals):<12.6f} {np.mean(bias_vals):<12.6f} {np.mean(max_diff_vals):<12.6f}")
    print(f"{'MAX':<35} {np.max(rmse_vals):<12.6f} {np.max(np.abs(bias_vals)):<12.6f} {np.max(max_diff_vals):<12.6f}")
    print("=" * 70)

    # Check if files are identical
    total_diff = np.nansum(np.abs(ufs_elev - secofs_elev))
    if total_diff < 1e-10:
        print("\n*** FILES ARE IDENTICAL ***")
    else:
        print(f"\nTotal absolute difference: {total_diff:.6e}")
        print(f"Mean absolute difference per value: {np.nanmean(np.abs(ufs_elev - secofs_elev)):.6e}")

    # Plot 1: Multi-panel comparison (4x3 grid)
    fig, axes = plt.subplots(4, 3, figsize=(16, 14))
    axes = axes.flatten()

    plot_stations = list(station_map.items())[:12]

    for i, (name, idx) in enumerate(plot_stations):
        ax = axes[i]
        secofs = secofs_elev[:, idx]
        ufs = ufs_elev[:, idx]

        ax.plot(datetimes, secofs, 'b-', linewidth=1.2, label=SECOFS_LABEL, alpha=0.8)
        ax.plot(datetimes, ufs, 'r--', linewidth=1.2, label=UFS_LABEL, alpha=0.8)
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

        stats = compute_stats(secofs, ufs)
        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')
        ax.set_title(f'{clean_name}\nRMSE={stats["rmse"]:.6f}m, Max Diff={stats["max_diff"]:.6f}m',
                     fontsize=10, fontweight='bold')
        ax.set_ylabel('Water Level (m)', fontsize=9)
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)

        if i == 0:
            ax.legend(loc='upper right', fontsize=8)

    for i in range(len(plot_stations), len(axes)):
        axes[i].set_visible(False)

    fig.suptitle(f'No-Wind Sensitivity Test: SECOFS vs UFS-SECOFS\nForecast Cycle: {BASE_DATE.strftime("%Y-%m-%d")} 00Z',
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUTPUT_DIR, 'no_wind_comparison_timeseries.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nSaved: no_wind_comparison_timeseries.png")

    # Plot 2: Difference timeseries
    fig, axes = plt.subplots(4, 3, figsize=(16, 14))
    axes = axes.flatten()

    for i, (name, idx) in enumerate(plot_stations):
        ax = axes[i]
        diff = ufs_elev[:, idx] - secofs_elev[:, idx]

        ax.plot(datetimes, diff, 'k-', linewidth=1)
        ax.axhline(y=0, color='r', linestyle='--', linewidth=1)
        ax.fill_between(datetimes, diff, 0, where=diff > 0, color='red', alpha=0.3)
        ax.fill_between(datetimes, diff, 0, where=diff < 0, color='blue', alpha=0.3)

        clean_name = name.replace('!', '').split('(')[0].replace('_', ' ')
        diff_valid = diff[~np.isnan(diff)]
        ax.set_title(f'{clean_name}\nmin={np.min(diff_valid):.6f}m, max={np.max(diff_valid):.6f}m',
                     fontsize=10, fontweight='bold')
        ax.set_ylabel('Difference (m)', fontsize=9)
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)

    for i in range(len(plot_stations), len(axes)):
        axes[i].set_visible(False)

    fig.suptitle(f'Water Level Difference (UFS - SECOFS) - No Wind Forcing\nForecast Cycle: {BASE_DATE.strftime("%Y-%m-%d")} 00Z',
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUTPUT_DIR, 'no_wind_comparison_difference.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: no_wind_comparison_difference.png")

    # Plot 3: Scatter plot of all stations
    fig, ax = plt.subplots(figsize=(10, 10))

    # Flatten and filter valid data
    secofs_flat = secofs_elev.flatten()
    ufs_flat = ufs_elev.flatten()
    valid = ~np.isnan(secofs_flat) & ~np.isnan(ufs_flat)
    secofs_valid = secofs_flat[valid]
    ufs_valid = ufs_flat[valid]

    # Plot scatter with density coloring
    ax.scatter(secofs_valid, ufs_valid, c='blue', alpha=0.1, s=1)

    # 1:1 line
    lims = [min(secofs_valid.min(), ufs_valid.min()), max(secofs_valid.max(), ufs_valid.max())]
    ax.plot(lims, lims, 'r-', linewidth=2, label='1:1 Line')

    # Statistics
    overall_stats = compute_stats(secofs_valid, ufs_valid)
    ax.text(0.05, 0.95, f"RMSE: {overall_stats['rmse']:.6f} m\n"
                        f"Bias: {overall_stats['bias']:.6f} m\n"
                        f"Corr: {overall_stats['corr']:.6f}\n"
                        f"N: {overall_stats['n']:,}",
            transform=ax.transAxes, fontsize=12, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax.set_xlabel(f'{SECOFS_LABEL} Water Level (m)', fontsize=12)
    ax.set_ylabel(f'{UFS_LABEL} Water Level (m)', fontsize=12)
    ax.set_title(f'No-Wind Sensitivity Test: Scatter Comparison\nAll Stations, All Time Steps',
                 fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'no_wind_comparison_scatter.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: no_wind_comparison_scatter.png")

    print(f"\nAll plots saved to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
