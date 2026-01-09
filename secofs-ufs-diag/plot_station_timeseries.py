#!/usr/bin/env python3
"""
Plot station timeseries from SCHISM staout files
"""

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

# Configuration
STATION_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_out'
OUTPUT_DIR = '/mnt/f/SECOFS_TEST_RUN_OUTPUTS/00z_20260107/station_plots'
BASE_DATE = datetime(2026, 1, 7, 0, 0, 0)

def parse_station_in(filepath):
    """Parse station.in file to get station names and coordinates"""
    stations = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        # First line is flags
        n_stations = int(lines[1].strip())
        for i in range(2, 2 + n_stations):
            parts = lines[i].split()
            idx = int(parts[0])
            lon = float(parts[1])
            lat = float(parts[2])
            # Extract name from comment
            comment = ' '.join(parts[4:]) if len(parts) > 4 else f'Station_{idx}'
            name = comment.split(':')[0] if ':' in comment else comment
            stations.append({
                'idx': idx,
                'lon': lon,
                'lat': lat,
                'name': name
            })
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
                # Only take first n_stations values (rest may be duplicates or other data)
                station_vals = [float(v) for v in values[1:n_stations+1]]
                times.append(time_sec)
                data.append(station_vals)
    return np.array(times), np.array(data)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse station info
    station_file = os.path.join(STATION_DIR, 'station.in')
    stations = parse_station_in(station_file)
    n_stations = len(stations)
    print(f"Found {n_stations} stations")

    # Parse elevation data (staout_1)
    print("Reading elevation data...")
    times, elev_data = parse_staout(os.path.join(STATION_DIR, 'staout_1'), n_stations)
    print(f"  Time steps: {len(times)}")
    print(f"  Time range: {times[0]/3600:.1f} to {times[-1]/3600:.1f} hours")

    # Convert time to datetime
    datetimes = [BASE_DATE + timedelta(seconds=t) for t in times]

    # Replace fill values with NaN
    elev_data = np.where(np.abs(elev_data) > 1e6, np.nan, elev_data)

    # Select key stations to plot (well-known tide gauges)
    key_stations = [
        'Key_West', 'Virginia_Key', 'Fort_Pulaski', 'Charleston',
        'Wilmington', 'Duck', 'Chesapeake_Bay_Bridge', 'Baltimore',
        'Atlantic_City', 'The_Battery', 'Boston', 'Portland'
    ]

    # Find matching station indices
    station_map = {}
    for i, s in enumerate(stations):
        for key in key_stations:
            if key.lower().replace('_', '') in s['name'].lower().replace('_', '').replace(' ', ''):
                station_map[s['name']] = i
                break

    print(f"\nFound {len(station_map)} key stations:")
    for name in station_map:
        print(f"  {name}")

    # Plot 1: Multi-station water level timeseries
    fig, axes = plt.subplots(4, 3, figsize=(16, 14))
    axes = axes.flatten()

    plot_stations = list(station_map.items())[:12]

    for i, (name, idx) in enumerate(plot_stations):
        ax = axes[i]
        elev = elev_data[:, idx]
        valid = ~np.isnan(elev)

        if np.any(valid):
            ax.plot(datetimes, elev, 'b-', linewidth=1)
            ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
            ax.set_ylabel('Water Level (m)', fontsize=9)
            ax.set_title(name.replace('_', ' '), fontsize=10, fontweight='bold')
            ax.tick_params(axis='x', rotation=45)
            ax.grid(True, alpha=0.3)

            # Set reasonable y-limits
            ymin, ymax = np.nanmin(elev), np.nanmax(elev)
            margin = (ymax - ymin) * 0.1
            ax.set_ylim(ymin - margin, ymax + margin)
        else:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(name.replace('_', ' '), fontsize=10)

    # Hide unused subplots
    for i in range(len(plot_stations), len(axes)):
        axes[i].set_visible(False)

    fig.suptitle(f'UFS-SECOFS Water Level at NOAA Tide Gauges\n{BASE_DATE.strftime("%Y-%m-%d")} Forecast',
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUTPUT_DIR, 'water_level_timeseries.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nSaved: water_level_timeseries.png")

    # Plot 2: All stations on one plot (subset)
    fig, ax = plt.subplots(figsize=(14, 8))

    colors = plt.cm.tab20(np.linspace(0, 1, len(plot_stations)))
    for i, (name, idx) in enumerate(plot_stations):
        elev = elev_data[:, idx]
        valid = ~np.isnan(elev)
        if np.any(valid):
            ax.plot(datetimes, elev, color=colors[i], linewidth=1.5, label=name.replace('_', ' '))

    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    ax.set_xlabel('Time (UTC)', fontsize=12)
    ax.set_ylabel('Water Level (m)', fontsize=12)
    ax.set_title(f'UFS-SECOFS Water Level at Selected Tide Gauges\n{BASE_DATE.strftime("%Y-%m-%d")} Forecast',
                 fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'water_level_combined.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: water_level_combined.png")

    # Plot 3: Gulf of Mexico stations
    gulf_keywords = ['Panama', 'Cedar', 'Tampa', 'Clearwater', 'Naples', 'Key_West', 'Fort_Myers', 'Manatee']
    gulf_stations = []
    for i, s in enumerate(stations):
        for kw in gulf_keywords:
            if kw.lower() in s['name'].lower():
                gulf_stations.append((s['name'], i))
                break

    if gulf_stations:
        fig, ax = plt.subplots(figsize=(14, 8))
        colors = plt.cm.Set2(np.linspace(0, 1, len(gulf_stations)))
        for i, (name, idx) in enumerate(gulf_stations[:10]):
            elev = elev_data[:, idx]
            valid = ~np.isnan(elev)
            if np.any(valid):
                ax.plot(datetimes, elev, color=colors[i % len(colors)], linewidth=1.5,
                       label=name.replace('_', ' ').split('(')[0])

        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        ax.set_xlabel('Time (UTC)', fontsize=12)
        ax.set_ylabel('Water Level (m)', fontsize=12)
        ax.set_title(f'UFS-SECOFS Water Level - Gulf of Mexico Stations\n{BASE_DATE.strftime("%Y-%m-%d")} Forecast',
                     fontsize=14, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, 'water_level_gulf.png'), dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved: water_level_gulf.png")

    # Plot 4: Puerto Rico stations
    pr_keywords = ['Puerto', 'San_Juan', 'Magueyes', 'Fajardo', 'Mayaguez', 'Arecibo', 'Ponce']
    pr_stations = []
    for i, s in enumerate(stations):
        for kw in pr_keywords:
            if kw.lower() in s['name'].lower():
                pr_stations.append((s['name'], i))
                break

    if pr_stations:
        fig, ax = plt.subplots(figsize=(14, 8))
        colors = plt.cm.Set1(np.linspace(0, 1, len(pr_stations)))
        for i, (name, idx) in enumerate(pr_stations):
            elev = elev_data[:, idx]
            valid = ~np.isnan(elev)
            if np.any(valid):
                ax.plot(datetimes, elev, color=colors[i % len(colors)], linewidth=1.5,
                       label=name.replace('_', ' ').split('(')[0])

        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        ax.set_xlabel('Time (UTC)', fontsize=12)
        ax.set_ylabel('Water Level (m)', fontsize=12)
        ax.set_title(f'UFS-SECOFS Water Level - Puerto Rico Stations\n{BASE_DATE.strftime("%Y-%m-%d")} Forecast',
                     fontsize=14, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, 'water_level_puerto_rico.png'), dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved: water_level_puerto_rico.png")

    print(f"\nAll plots saved to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
