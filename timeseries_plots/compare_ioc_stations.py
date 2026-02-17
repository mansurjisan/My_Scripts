#!/usr/bin/env python3
"""
IOC Station Bias Correction Analysis

Generates side-by-side comparison plots (same style as compare_side_by_side.py)
for non-CO-OPS (IOC/international) stations, verifying that bias correction
is NOT being applied to them after the Dec 18, 2025 fix.

For each non-CO-OPS station that previously showed bias correction, generates:
  - Side-by-side: WITH Anomaly vs WITHOUT Anomaly (should be identical)
  - Difference timeseries

Usage:
    python compare_ioc_stations.py \
        --cwl stofs_data/20260215/stofs_2d_glo.t00z.points.cwl.nc \
        --noanomaly stofs_data/20260215/stofs_2d_glo.t00z.points.cwl.noanomaly.nc
"""

import os
import sys
import re
import argparse
import numpy as np
import netCDF4 as nc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from PIL import Image


# ============================================================================
# 26 previously-affected IOC stations (from Dec 11 analysis)
# ============================================================================
PREV_IOC_STATIONS = {
    'Puerto Madryn': 4.85,
    'Puerto Montt': 2.93,
    'Puerto Deseado': 2.28,
    'Port Hedland': 1.94,
    'Esperance': 1.39,
    'Fortaleza': 1.35,
    'Nuku Hiva': 1.27,
    'Cocos Australia': 1.20,
    'Port Stanley': 1.19,
    'Port Vila': 1.17,
    'Tanjung Lesung': 1.17,
    'Santa Cruz Ecuador': 1.10,
    'Port Louis': 0.93,
    'Port Elizabeth': 0.90,
    'Port-aux-basques': 0.88,
    'Portu-Prince': 0.82,
    'Portland, S.Aus': 0.81,
    'Palmyra Island': 0.79,
    'Nukuoro East': 0.79,
    'Saipan North': 0.73,
    'Fort de France': 0.72,
    'Kushiro': 0.63,
    'Faraulep East': 0.56,
    'Christmas': 0.56,
    'Port Sonara': 0.46,
    'Pohnpei FSM UHSLC': 0.02,
}


def is_coops_station(station_name):
    """CO-OPS stations have 7-digit IDs not starting with 0."""
    matches = re.findall(r'\b([1-9]\d{6})\b', station_name.strip())
    return (True, matches[0]) if matches else (False, None)


def read_stations(filepath):
    """Read station names from NetCDF file."""
    ds = nc.Dataset(filepath, 'r')
    n = ds.variables['station_name'].shape[0]
    names = []
    for i in range(n):
        raw = ds.variables['station_name'][i]
        if hasattr(raw, 'tobytes'):
            name = raw.tobytes().decode('utf-8', errors='replace').strip()
        elif isinstance(raw, np.ndarray):
            name = ''.join(c.decode('utf-8', errors='replace') if isinstance(c, bytes) else str(c) for c in raw).strip()
        else:
            name = str(raw).strip()
        names.append(name)
    ds.close()
    return names


def find_prev_ioc_index(station_name):
    """Check if station matches one of the 26 previously-affected IOC stations."""
    for key, prev_bias in PREV_IOC_STATIONS.items():
        keywords = key.split()
        if all(w.lower() in station_name.lower() for w in keywords):
            return key, prev_bias
    return None, None


def create_ioc_comparison_plot(idx, station_name, lon, lat, zeta_cwl, zeta_noa,
                                times, prev_name, prev_bias, output_dir):
    """
    Create side-by-side comparison plot for an IOC station,
    matching the style from compare_side_by_side.py.
    """
    cwl_ts = zeta_cwl[:, idx]
    noa_ts = zeta_noa[:, idx]
    diff_ts = cwl_ts - noa_ts

    max_abs_diff = np.nanmax(np.abs(diff_ts))
    mean_diff = np.nanmean(diff_ts)

    # Convert times to matplotlib-friendly
    time_dates = []
    for t in times:
        if hasattr(t, 'year'):
            time_dates.append(datetime(t.year, t.month, t.day, t.hour, t.minute, t.second))
        else:
            time_dates.append(t)

    fig, axes = plt.subplots(1, 3, figsize=(22, 5))
    ax1, ax2, ax3 = axes

    # ---- Panel 1: WITH Anomaly ----
    ax1.plot(time_dates, cwl_ts, 'b-', linewidth=1.5, label='STOFS2D Model', alpha=0.8)
    ax1.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax1.set_ylabel('Water Level (m, MSL)', fontsize=11)
    ax1.set_xlabel('Date/Time', fontsize=11)
    ax1.set_title('WITH Anomaly', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right', fontsize=9, framealpha=0.9)

    stats_text = f"Max: {np.nanmax(cwl_ts):.3f} m\nMin: {np.nanmin(cwl_ts):.3f} m"
    ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))

    # ---- Panel 2: WITHOUT Anomaly ----
    ax2.plot(time_dates, noa_ts, 'b-', linewidth=1.5, label='STOFS2D Model', alpha=0.8)
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax2.set_ylabel('Water Level (m, MSL)', fontsize=11)
    ax2.set_xlabel('Date/Time', fontsize=11)
    ax2.set_title('WITHOUT Anomaly', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right', fontsize=9, framealpha=0.9)

    stats_text = f"Max: {np.nanmax(noa_ts):.3f} m\nMin: {np.nanmin(noa_ts):.3f} m"
    ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))

    # ---- Panel 3: Difference ----
    ax3.plot(time_dates, diff_ts, 'g-', linewidth=1.5, label='Difference', alpha=0.8)
    ax3.fill_between(time_dates, diff_ts, 0, alpha=0.15, color='green')
    ax3.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax3.set_ylabel('Difference (m)', fontsize=11)
    ax3.set_xlabel('Date/Time', fontsize=11)
    ax3.set_title('DIFFERENCE (With - Without)', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper right', fontsize=9, framealpha=0.9)

    diff_stats = f"Max |diff|: {max_abs_diff:.6f} m\nMean diff: {mean_diff:.6f} m"
    if max_abs_diff < 0.001:
        box_color = '#90EE90'  # light green = good
        diff_stats += "\n\nNO BIAS APPLIED"
    else:
        box_color = '#FFB6C1'  # light red = problem
        diff_stats += f"\n\nWARNING: BIAS DETECTED"
    ax3.text(0.02, 0.98, diff_stats, transform=ax3.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor=box_color, alpha=0.9))

    # Set y-lim on diff panel
    if max_abs_diff < 0.01:
        ax3.set_ylim(-0.01, 0.01)

    # Match y-axis for panels 1 and 2
    y_min = min(ax1.get_ylim()[0], ax2.get_ylim()[0])
    y_max = max(ax1.get_ylim()[1], ax2.get_ylim()[1])
    ax1.set_ylim(y_min, y_max)
    ax2.set_ylim(y_min, y_max)

    # Format dates
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Title
    fig.suptitle(
        f'{station_name}\n'
        f'Lon: {lon:.3f}, Lat: {lat:.3f}',
        fontsize=13, fontweight='bold', y=1.03
    )

    plt.tight_layout()

    safe_name = re.sub(r'[^\w\-]', '_', station_name[:40])
    plot_file = os.path.join(output_dir, f'ioc_station_{idx:04d}_{safe_name}_comparison.png')
    fig.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return plot_file


def create_summary_plot(results, output_dir):
    """Create summary bar chart of all non-CO-OPS stations analyzed."""
    # Filter to previously-affected stations
    prev_affected = [r for r in results if r['prev_name'] is not None]

    if not prev_affected:
        return None

    # De-duplicate by prev_name (keep the one with highest prev_bias)
    seen = {}
    for r in prev_affected:
        key = r['prev_name']
        if key not in seen or r['prev_bias'] > seen[key]['prev_bias']:
            seen[key] = r
    prev_affected = sorted(seen.values(), key=lambda x: x['prev_bias'], reverse=True)

    fig, ax = plt.subplots(figsize=(16, max(10, len(prev_affected) * 0.45)))

    y_pos = np.arange(len(prev_affected))
    bar_width = 0.35

    prev_biases = [r['prev_bias'] for r in prev_affected]
    curr_biases = [r['max_diff'] for r in prev_affected]
    labels = [r['prev_name'] for r in prev_affected]

    bars1 = ax.barh(y_pos + bar_width/2, prev_biases, bar_width,
                    label='Dec 11, 2025 (Before Fix)', color='#EF5350', alpha=0.85,
                    edgecolor='darkred', linewidth=0.5)
    bars2 = ax.barh(y_pos - bar_width/2, curr_biases, bar_width,
                    label='Feb 15, 2026 (After Fix)', color='#4CAF50', alpha=0.85,
                    edgecolor='darkgreen', linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel('Maximum Bias Correction Difference (m)', fontsize=13)
    ax.set_title(
        'IOC Station Bias Correction: Before vs After Fix\n'
        '26 Previously-Affected Non-CO-OPS Stations | para4 | 2026-02-15 00Z',
        fontsize=15, fontweight='bold'
    )
    ax.legend(fontsize=12, loc='lower right')
    ax.axvline(x=0.001, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)

    for bar, val in zip(bars1, prev_biases):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}m', va='center', fontsize=9, color='#C62828')
    for bar, val in zip(bars2, curr_biases):
        label = f'{val:.6f}m' if val > 0 else '0.0m'
        ax.text(max(bar.get_width(), 0) + 0.02, bar.get_y() + bar.get_height()/2,
                label, va='center', fontsize=9, color='#2E7D32')

    plt.tight_layout()
    out_path = os.path.join(output_dir, 'summary_ioc_bias_before_vs_after.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved summary: {out_path}")
    return out_path


def create_all_non_coops_table_plot(all_non_coops, output_dir):
    """Create a table showing ALL non-CO-OPS stations and their max diff."""
    n = len(all_non_coops)
    rows_per_page = 50
    n_pages = (n + rows_per_page - 1) // rows_per_page

    plot_files = []
    for page in range(n_pages):
        start = page * rows_per_page
        end = min(start + rows_per_page, n)
        subset = all_non_coops[start:end]

        fig, ax = plt.subplots(figsize=(18, 0.35 * len(subset) + 2))
        ax.axis('off')

        col_labels = ['Index', 'Max |Diff| (m)', 'Lon', 'Lat', 'Station Name', 'Status']
        table_data = []
        for s in subset:
            status = 'OK' if s['max_diff'] < 0.001 else 'BIAS DETECTED!'
            table_data.append([
                str(s['index']),
                f"{s['max_diff']:.6f}",
                f"{s['lon']:.3f}",
                f"{s['lat']:.3f}",
                s['name'][:55],
                status,
            ])

        table = ax.table(
            cellText=table_data,
            colLabels=col_labels,
            loc='center',
            cellLoc='left',
            colWidths=[0.05, 0.10, 0.07, 0.07, 0.55, 0.12]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.3)

        # Color header
        for j in range(len(col_labels)):
            table[0, j].set_facecolor('#4472C4')
            table[0, j].set_text_props(color='white', fontweight='bold')

        # Color rows
        for i, s in enumerate(subset):
            row_color = '#E8F5E9' if s['max_diff'] < 0.001 else '#FFCDD2'
            for j in range(len(col_labels)):
                table[i+1, j].set_facecolor(row_color)

        ax.set_title(
            f'Non-CO-OPS Station Bias Check (Page {page+1}/{n_pages})\n'
            f'Total: {n} stations | para4 | 2026-02-15 00Z',
            fontsize=13, fontweight='bold', pad=20
        )

        plt.tight_layout()
        out_path = os.path.join(output_dir, f'non_coops_table_page{page+1:02d}.png')
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        plot_files.append(out_path)

    print(f"Saved {len(plot_files)} table pages")
    return plot_files


def combine_plots_to_pdf(plots_dir, output_pdf, extra_files=None):
    """Combine all PNG plots into a single PDF file."""
    # Gather all pngs in order
    png_files = sorted([
        os.path.join(plots_dir, f)
        for f in os.listdir(plots_dir)
        if f.endswith('.png') and f.startswith('ioc_station_')
    ])

    # Prepend summary and table files
    all_files = []
    if extra_files:
        all_files.extend([f for f in extra_files if f and os.path.exists(f)])
    all_files.extend(png_files)

    if not all_files:
        print("No PNG files found to combine")
        return False

    print(f"\nCombining {len(all_files)} plots into PDF...")

    images = []
    for img_path in all_files:
        img = Image.open(img_path)
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        images.append(img)

    if images:
        images[0].save(output_pdf, save_all=True, append_images=images[1:])
        print(f"PDF saved: {output_pdf}")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description='IOC Station Bias Correction Analysis')
    parser.add_argument('--cwl', required=True, help='WITH anomaly file (bias-corrected)')
    parser.add_argument('--noanomaly', required=True, help='WITHOUT anomaly file')
    parser.add_argument('--output-dir', default=None, help='Output directory')
    parser.add_argument('--output-pdf', default=None, help='Output PDF filename')

    args = parser.parse_args()

    # Auto output dir
    if args.output_dir is None:
        date_match = re.search(r'(\d{8})', args.cwl)
        date_str = date_match.group(1) if date_match else 'unknown'
        cycle_match = re.search(r'\.t(\d{2})z\.', args.cwl)
        cycle = cycle_match.group(1) + 'z' if cycle_match else '00z'
        args.output_dir = f'ioc_analysis_{date_str}_{cycle}'

    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 80)
    print("IOC STATION BIAS CORRECTION ANALYSIS")
    print("=" * 80)
    print(f"WITH anomaly:    {args.cwl}")
    print(f"WITHOUT anomaly: {args.noanomaly}")
    print(f"Output:          {args.output_dir}/")

    # Load data
    ds_cwl = nc.Dataset(args.cwl, 'r')
    ds_noa = nc.Dataset(args.noanomaly, 'r')

    n_stations = ds_cwl.variables['station_name'].shape[0]
    print(f"\nTotal stations: {n_stations}")

    # Read station names
    station_names = []
    for i in range(n_stations):
        raw = ds_cwl.variables['station_name'][i]
        if hasattr(raw, 'tobytes'):
            name = raw.tobytes().decode('utf-8', errors='replace').strip()
        elif isinstance(raw, np.ndarray):
            name = ''.join(c.decode('utf-8', errors='replace') if isinstance(c, bytes) else str(c) for c in raw).strip()
        else:
            name = str(raw).strip()
        station_names.append(name)

    lons = np.array(ds_cwl.variables['x'][:])
    lats = np.array(ds_cwl.variables['y'][:])

    zeta_cwl = ds_cwl.variables['zeta'][:]
    zeta_noa = ds_noa.variables['zeta'][:]
    if isinstance(zeta_cwl, np.ma.MaskedArray):
        zeta_cwl = zeta_cwl.filled(np.nan)
    if isinstance(zeta_noa, np.ma.MaskedArray):
        zeta_noa = zeta_noa.filled(np.nan)

    time_var = ds_cwl.variables['time']
    times = nc.num2date(time_var[:], time_var.units)

    ds_cwl.close()
    ds_noa.close()

    diff = zeta_cwl - zeta_noa

    # Identify all non-CO-OPS stations
    all_non_coops = []
    prev_affected_indices = []

    for i in range(n_stations):
        is_coops, coops_id = is_coops_station(station_names[i])
        if is_coops:
            continue

        station_diff = diff[:, i]
        max_abs_diff = float(np.nanmax(np.abs(station_diff)))

        prev_name, prev_bias = find_prev_ioc_index(station_names[i])

        entry = {
            'index': i,
            'name': station_names[i],
            'lon': float(lons[i]),
            'lat': float(lats[i]),
            'max_diff': max_abs_diff,
            'prev_name': prev_name,
            'prev_bias': prev_bias if prev_bias else 0.0,
        }
        all_non_coops.append(entry)

        if prev_name is not None:
            prev_affected_indices.append(entry)

    n_non_coops = len(all_non_coops)
    n_with_diff = sum(1 for s in all_non_coops if s['max_diff'] > 0.001)

    print(f"\nNon-CO-OPS stations: {n_non_coops}")
    print(f"With bias correction (> 1mm): {n_with_diff}")
    print(f"Matched to previous 26 IOC: {len(prev_affected_indices)}")

    if n_with_diff == 0:
        print("\nSUCCESS: No non-CO-OPS stations show bias correction differences!")
    else:
        print(f"\nWARNING: {n_with_diff} non-CO-OPS stations still show differences!")

    # De-duplicate prev_affected by prev_name
    seen_prev = {}
    for entry in prev_affected_indices:
        key = entry['prev_name']
        if key not in seen_prev or entry['prev_bias'] > seen_prev[key]['prev_bias']:
            seen_prev[key] = entry
    unique_prev = sorted(seen_prev.values(), key=lambda x: x['prev_bias'], reverse=True)

    # Generate side-by-side plots for the 26 previously-affected stations
    print(f"\nGenerating plots for {len(unique_prev)} previously-affected IOC stations...")
    plot_files = []
    results = []

    for entry in unique_prev:
        i = entry['index']
        print(f"  Station {i:4d}: {entry['name'][:50]} (prev: {entry['prev_bias']:.2f}m, now: {entry['max_diff']:.6f}m)")

        plot_file = create_ioc_comparison_plot(
            i, station_names[i], float(lons[i]), float(lats[i]),
            zeta_cwl, zeta_noa, times,
            entry['prev_name'], entry['prev_bias'],
            args.output_dir
        )
        plot_files.append(plot_file)
        results.append(entry)

    # Create summary bar chart
    summary_file = create_summary_plot(results, args.output_dir)

    # Create table of ALL non-CO-OPS stations
    table_files = create_all_non_coops_table_plot(all_non_coops, args.output_dir)

    # Combine into PDF
    extra = []
    if summary_file:
        extra.append(summary_file)
    extra.extend(table_files)

    pdf_file = args.output_pdf or os.path.join(args.output_dir, 'IOC_Station_Analysis.pdf')
    combine_plots_to_pdf(args.output_dir, pdf_file, extra_files=extra)

    # Print final summary
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")
    print(f"Total non-CO-OPS stations: {n_non_coops}")
    print(f"Stations with bias (> 1mm): {n_with_diff}")
    print(f"Previously-affected IOC stations plotted: {len(unique_prev)}")
    print(f"Plots saved to: {args.output_dir}/")
    print(f"PDF: {pdf_file}")


if __name__ == '__main__':
    main()
