#!/usr/bin/env python3
"""
Create side-by-side comparison plots of anomaly vs noanomaly
Without the difference panel - uses ModelObsComparison class

Modified to work with:
  - stofs_2d_glo.t00z.points.cwl.nc (WITH anomaly / bias-corrected)
  - stofs_2d_glo.t00z.points.autoval.cwl.noanomaly.nc (WITHOUT anomaly)
"""
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set backend before importing stofs2d_obs
import matplotlib
matplotlib.use('Agg')

from stofs2d_obs import Fort61Reader, ModelObsComparison
from stofs2d_obs.observations import COOPSMatcher
from searvey import fetch_coops_station

def create_side_by_side_plot(station_idx, datum='MSL', output_dir='comparison_plots',
                             cwl_file=None, noanomaly_file=None):
    """
    Create side-by-side comparison plot for a single station
    """
    # Default file paths
    if cwl_file is None:
        cwl_file = 'stofs_2d_glo.t00z.points.cwl.nc'
    if noanomaly_file is None:
        noanomaly_file = 'stofs_2d_glo.t00z.points.autoval.cwl.noanomaly.nc'

    files = {
        'WITH Anomaly': cwl_file,
        'WITHOUT Anomaly': noanomaly_file
    }

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Processing Station {station_idx}")
    print('='*80)

    # Read station info from WITH anomaly file (has more stations)
    reader1 = Fort61Reader(files['WITH Anomaly'])
    station_info = reader1.get_station_info(station_idx)
    print(f"Station: {station_info['name']}")
    print(f"Location: ({station_info['lon']:.4f}, {station_info['lat']:.4f})")

    # Find CO-OPS station
    matcher = COOPSMatcher()
    coops_match = matcher.get_best_match(station_info['lon'], station_info['lat'])

    if not coops_match:
        print(f"X No CO-OPS station found")
        reader1.close()
        return False

    print(f"CO-OPS: {coops_match['name']} (ID: {coops_match['nos_id']})")

    # Read model data from WITH anomaly
    model_data1 = reader1.get_station_data(station_idx)
    reader1.close()

    # Find matching station in WITHOUT anomaly file by name
    reader2 = Fort61Reader(files['WITHOUT Anomaly'])

    # Search for station by name in noanomaly file
    found_idx = None
    for i in range(reader2.n_stations):
        info = reader2.get_station_info(i)
        if info['name'] == station_info['name']:
            found_idx = i
            break

    if found_idx is None:
        print(f"X Station not found in noanomaly file")
        reader2.close()
        return False

    model_data2 = reader2.get_station_data(found_idx)
    reader2.close()

    # Fetch observation data
    try:
        obs_data = fetch_coops_station(
            station_id=coops_match['nos_id'],
            start_date=station_info['time_range'][0],
            end_date=station_info['time_range'][1],
            product='water_level',
            datum=datum,
        )
    except:
        # Try MSL if requested datum fails
        try:
            obs_data = fetch_coops_station(
                station_id=coops_match['nos_id'],
                start_date=station_info['time_range'][0],
                end_date=station_info['time_range'][1],
                product='water_level',
                datum='MSL',
            )
            datum = 'MSL'
        except Exception as e:
            print(f"X Error fetching observations: {e}")
            return False

    if obs_data is None or len(obs_data) == 0:
        print(f"X No observation data")
        return False

    # Create comparison objects (they handle data alignment and stats)
    comp1 = ModelObsComparison(model_data1, obs_data, station_info['name'], "STOFS2D", datum)
    comp2 = ModelObsComparison(model_data2, obs_data, station_info['name'], "STOFS2D", datum)

    stats1 = comp1.calculate_statistics()
    stats2 = comp2.calculate_statistics()

    if len(comp1.aligned) == 0 or len(comp2.aligned) == 0:
        print(f"X No aligned data")
        return False

    # Create side-by-side plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Plot 1: WITH Anomaly
    ax1.plot(
        model_data1.index,
        model_data1['water_level'],
        'b-',
        linewidth=1.5,
        label='STOFS2D Model',
        alpha=0.8
    )
    ax1.plot(
        comp1.obs_data.index,
        comp1.obs_data['obs_water_level'],
        'r-',
        linewidth=1.5,
        label='CO-OPS Observation',
        alpha=0.8
    )
    ax1.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax1.set_ylabel(f'Water Level (m, {datum})', fontsize=11)
    ax1.set_xlabel('Date/Time', fontsize=11)
    ax1.set_title('WITH Anomaly', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right', fontsize=9, framealpha=0.9)

    # Add stats box
    if stats1:
        stats_text = f"RMSE: {stats1['rmse']:.3f} m\nCorr: {stats1['correlation']:.3f}"
        ax1.text(
            0.02, 0.98,
            stats_text,
            transform=ax1.transAxes,
            fontsize=9,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9)
        )

    # Plot 2: WITHOUT Anomaly
    ax2.plot(
        model_data2.index,
        model_data2['water_level'],
        'b-',
        linewidth=1.5,
        label='STOFS2D Model',
        alpha=0.8
    )
    ax2.plot(
        comp2.obs_data.index,
        comp2.obs_data['obs_water_level'],
        'r-',
        linewidth=1.5,
        label='CO-OPS Observation',
        alpha=0.8
    )
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax2.set_ylabel(f'Water Level (m, {datum})', fontsize=11)
    ax2.set_xlabel('Date/Time', fontsize=11)
    ax2.set_title('WITHOUT Anomaly', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right', fontsize=9, framealpha=0.9)

    # Add stats box
    if stats2:
        stats_text = f"RMSE: {stats2['rmse']:.3f} m\nCorr: {stats2['correlation']:.3f}"
        ax2.text(
            0.02, 0.98,
            stats_text,
            transform=ax2.transAxes,
            fontsize=9,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9)
        )

    # Format dates for both axes
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Match y-axis limits between panels
    y_min = min(ax1.get_ylim()[0], ax2.get_ylim()[0])
    y_max = max(ax1.get_ylim()[1], ax2.get_ylim()[1])
    ax1.set_ylim(y_min, y_max)
    ax2.set_ylim(y_min, y_max)

    # Overall title
    fig.suptitle(
        f'{station_info["name"]}',
        fontsize=14,
        fontweight='bold',
        y=1.02
    )

    plt.tight_layout()

    # Save plot
    # Extract CO-OPS ID from station name if possible
    parts = station_info['name'].split()
    coops_id = coops_match['nos_id']
    plot_file = f'{output_dir}/station_{station_idx:04d}_{coops_id}_comparison.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"+ Saved: {plot_file}")
    print(f"  WITH Anomaly:    RMSE={stats1['rmse']:.3f}m, Corr={stats1['correlation']:.3f}")
    print(f"  WITHOUT Anomaly: RMSE={stats2['rmse']:.3f}m, Corr={stats2['correlation']:.3f}")

    return {
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
    }


def combine_plots_to_pdf(plots_dir, output_pdf):
    """Combine all PNG plots into a single PDF file."""
    from PIL import Image

    png_files = sorted([f for f in os.listdir(plots_dir) if f.endswith('.png')])

    if len(png_files) == 0:
        print("No PNG files found to combine")
        return False

    print(f"\nCombining {len(png_files)} plots into PDF...")

    images = []
    for png_file in png_files:
        img_path = os.path.join(plots_dir, png_file)
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


if __name__ == '__main__':
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description='Create side-by-side comparison plots')
    parser.add_argument('--station-range', nargs=2, type=int, metavar=('START', 'END'),
                        help='Range of stations to process')
    parser.add_argument('--station-idx', type=int, help='Single station index')
    parser.add_argument('--datum', default='MSL', help='Vertical datum')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: auto from filename)')
    parser.add_argument('--cwl', default='stofs_2d_glo.t00z.points.cwl.nc',
                        help='WITH anomaly file (bias-corrected)')
    parser.add_argument('--noanomaly', default='stofs_2d_glo.t00z.points.autoval.cwl.noanomaly.nc',
                        help='WITHOUT anomaly file')
    parser.add_argument('--output-pdf', default=None, help='Output PDF filename')

    args = parser.parse_args()

    if args.station_idx is not None:
        stations = [args.station_idx]
    elif args.station_range:
        stations = range(args.station_range[0], args.station_range[1])
    else:
        # Default: process all stations in noanomaly file (834 stations)
        print("No station range specified. Use --station-range START END or --station-idx IDX")
        sys.exit(1)

    # Auto-generate output directory from filename if not specified
    if args.output_dir is None:
        # Extract cycle from filename (e.g., stofs_2d_glo.t00z.points.cwl.nc -> 00z)
        import re
        match = re.search(r'\.t(\d{2})z\.', args.cwl)
        if match:
            cycle = match.group(1) + 'z'
            args.output_dir = f'comparison_plots_{cycle}'
        else:
            args.output_dir = 'comparison_plots'

    print("="*80)
    print("Side-by-Side Comparison: WITH Anomaly vs WITHOUT Anomaly")
    print("="*80)
    print(f"WITH anomaly file:    {args.cwl}")
    print(f"WITHOUT anomaly file: {args.noanomaly}")
    print(f"Datum: {args.datum}")
    print(f"Output: {args.output_dir}/")
    print(f"Stations: {len(list(stations))}")

    results = []
    success = 0
    for idx in stations:
        try:
            result = create_side_by_side_plot(
                idx, args.datum, args.output_dir,
                cwl_file=args.cwl, noanomaly_file=args.noanomaly
            )
            if result:
                results.append(result)
                success += 1
        except Exception as e:
            print(f"X Error processing station {idx}: {e}")

    # Print summary
    if results:
        df = pd.DataFrame(results)
        print(f"\n{'='*80}")
        print("SUMMARY STATISTICS")
        print(f"{'='*80}")
        print(f"Stations processed: {success}/{len(list(stations))}")
        print(f"\nWITH Anomaly (Bias-Corrected):")
        print(f"  Mean RMSE: {df['with_rmse'].mean():.4f} m")
        print(f"  Mean Corr: {df['with_corr'].mean():.4f}")
        print(f"\nWITHOUT Anomaly (Non-Bias-Corrected):")
        print(f"  Mean RMSE: {df['without_rmse'].mean():.4f} m")
        print(f"  Mean Corr: {df['without_corr'].mean():.4f}")
        print(f"\nImprovement:")
        rmse_improvement = df['without_rmse'].mean() - df['with_rmse'].mean()
        print(f"  RMSE reduction: {rmse_improvement:.4f} m ({100*rmse_improvement/df['without_rmse'].mean():.1f}%)")

    # Combine to PDF if requested
    if args.output_pdf or success > 0:
        if args.output_pdf:
            pdf_file = args.output_pdf
        else:
            # Auto-generate PDF name from cycle (e.g., barotropic_20251122_00z.pdf)
            import re
            match = re.search(r'\.t(\d{2})z\.', args.cwl)
            cycle = match.group(1) + 'z' if match else '00z'
            # Try to extract date from file modification time or use current date
            pdf_file = os.path.join(args.output_dir, f'barotropic_20251122_{cycle}.pdf')
        combine_plots_to_pdf(args.output_dir, pdf_file)

    print(f"\n{'='*80}")
    print(f"+ Completed: {success}/{len(list(stations))} stations")
    print(f"+ Plots saved to: {args.output_dir}/")
    print("="*80)
