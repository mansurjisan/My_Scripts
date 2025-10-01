#!/usr/bin/env python3
"""
Generate timeseries for all points along a transect

python transect_timeseries_fort63.py fort.63_UND.nc     -75.705 35.208 -76.670 34.717     --points 30     --stations "Hatteras" "Beaufort"     --output-dir hatteras_beaufort

"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import netCDF4 as nc
from datetime import datetime, timedelta
import argparse
import os
import sys

def extract_transect_timeseries(nc_file, start_point, end_point, n_points=20,
                               output_dir='transect_timeseries', 
                               start_time=None, end_time=None, 
                               station_names=None, save_csv=False):
    """
    Extract timeseries for all points along a transect and create plots
    """
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    try:
        ds = nc.Dataset(nc_file, 'r')
    except Exception as e:
        print(f"Error opening file: {e}", file=sys.stderr)
        return
    
    # Get node coordinates
    x = ds.variables['x'][:]
    y = ds.variables['y'][:]
    
    # Get time and zeta variables
    time_var = ds.variables['time']
    zeta_var = ds.variables['zeta']
    
    # Parse time
    time_units = time_var.units
    if 'since' in time_units:
        base_date_str = time_units.split('since ')[-1].strip()
        base_date_str = base_date_str.split('+')[0].strip()
        
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
            try:
                base_date = datetime.strptime(base_date_str, fmt)
                break
            except ValueError:
                continue
        else:
            base_date = datetime(1990, 1, 1)
    else:
        base_date = datetime(1990, 1, 1)
    
    time_seconds = time_var[:]
    datetimes = [base_date + timedelta(seconds=float(t)) for t in time_seconds]
    
    # Parse time filters
    time_mask = np.ones(len(datetimes), dtype=bool)
    if start_time:
        try:
            if len(start_time) == 10:
                start_dt = datetime.strptime(start_time, '%Y-%m-%d')
            else:
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            time_mask = time_mask & np.array([dt >= start_dt for dt in datetimes])
        except:
            pass
    
    if end_time:
        try:
            if len(end_time) == 10:
                end_dt = datetime.strptime(end_time, '%Y-%m-%d')
            else:
                end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            time_mask = time_mask & np.array([dt <= end_dt for dt in datetimes])
        except:
            pass
    
    filtered_times = np.array(datetimes)[time_mask]
    
    # Create transect points
    lon1, lat1 = start_point
    lon2, lat2 = end_point
    
    transect_lons = np.linspace(lon1, lon2, n_points)
    transect_lats = np.linspace(lat1, lat2, n_points)
    
    # Calculate total transect distance
    total_distance = np.sqrt((lon2 - lon1)**2 + (lat2 - lat1)**2) * 111.0  # km
    
    # Extract data for each transect point
    transect_data = []
    all_zeta_min = float('inf')
    all_zeta_max = float('-inf')
    
    print(f"\nExtracting timeseries for {n_points} points along transect")
    print(f"From ({lon1:.3f}, {lat1:.3f}) to ({lon2:.3f}, {lat2:.3f})")
    print(f"Total distance: {total_distance:.1f} km\n")
    
    # Write statistics to file only if requested
    stats_file = None
    if save_csv:
        stats_file = os.path.join(output_dir, 'transect_statistics.csv')
        with open(stats_file, 'w') as f:
            f.write("Point,Distance_km,Node_Index,Lon,Lat,Max_m,Min_m,Mean_m,Range_m,Std_m\n")
    
    for i, (tlon, tlat) in enumerate(zip(transect_lons, transect_lats)):
        # Find nearest node
        distances = np.sqrt((x - tlon)**2 + (y - tlat)**2)
        nearest_idx = np.argmin(distances)
        
        # Extract timeseries
        zeta_values = zeta_var[:, nearest_idx][time_mask]
        
        # Filter out invalid values
        valid_mask = ~np.isnan(zeta_values) & ~np.isclose(zeta_values, -99999.0)
        
        if np.any(valid_mask):
            valid_zeta = zeta_values[valid_mask]
            valid_times = filtered_times[valid_mask]
            
            # Update global min/max for consistent y-axis
            all_zeta_min = min(all_zeta_min, np.min(valid_zeta))
            all_zeta_max = max(all_zeta_max, np.max(valid_zeta))
            
            # Calculate distance along transect
            if i == 0:
                distance_km = 0.0
            else:
                dx = tlon - transect_lons[0]
                dy = tlat - transect_lats[0]
                distance_km = np.sqrt(dx**2 + dy**2) * 111.0
            
            stats = {
                'point_idx': i,
                'distance_km': distance_km,
                'node_idx': nearest_idx,
                'lon': float(x[nearest_idx]),
                'lat': float(y[nearest_idx]),
                'times': valid_times,
                'zeta': valid_zeta,
                'max': float(np.max(valid_zeta)),
                'min': float(np.min(valid_zeta)),
                'mean': float(np.mean(valid_zeta)),
                'std': float(np.std(valid_zeta))
            }
            
            transect_data.append(stats)
            
            # Write to statistics file if CSV is requested
            if save_csv:
                with open(stats_file, 'a') as f:
                    f.write(f"{i+1},{distance_km:.1f},{nearest_idx},"
                           f"{stats['lon']:.4f},{stats['lat']:.4f},"
                           f"{stats['max']:.3f},{stats['min']:.3f},{stats['mean']:.3f},"
                           f"{stats['max']-stats['min']:.3f},{stats['std']:.3f}\n")
            
            print(f"Point {i+1}/{n_points}: {distance_km:.1f} km, "
                  f"Node {nearest_idx}, Max: {stats['max']:.3f}m")
    
    ds.close()
    
    if save_csv:
        print(f"\nStatistics saved to: {stats_file}")
    
    # Add a buffer to y-axis limits
    y_buffer = (all_zeta_max - all_zeta_min) * 0.1
    ylim = (all_zeta_min - y_buffer, all_zeta_max + y_buffer)
    
    # Create individual timeseries plots
    print(f"\nGenerating timeseries plots in {output_dir}/")
    
    for i, td in enumerate(transect_data):
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot timeseries
        ax.plot(td['times'], td['zeta'], 'b-', linewidth=1.5, alpha=0.8)
        
        # Add zero reference line
        ax.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
        
        # Add mean line
        #ax.axhline(y=td['mean'], color='r', linestyle='--', linewidth=1,
        #          alpha=0.7, label=f"Mean: {td['mean']:.3f}m")
        
        # Determine if this is a station point
        point_label = f"Point {i+1}/{n_points}"
        if station_names:
            if i == 0:
                point_label = f"{station_names[0]} (Start)"
            elif i == len(transect_data) - 1:
                point_label = f"{station_names[1]} (End)"
        
        # Title and labels
        ax.set_title(f'Water Elevation - {point_label}\n'
                    f'Distance: {td["distance_km"]:.1f} km, '
                    f'Location: ({td["lon"]:.3f}, {td["lat"]:.3f})',
                    fontsize=12, fontweight='bold')
        ax.set_xlabel('Date/Time', fontsize=10)
        ax.set_ylabel('Water Elevation (m)', fontsize=10)
        
        # Add statistics box
        stats_text = (f'Max: {td["max"]:.3f}m\n'
                     f'Min: {td["min"]:.3f}m')
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round',
                facecolor='wheat', alpha=0.7))
        
        # Format dates on x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Set consistent y-axis limits
        ax.set_ylim(ylim)
        
        # Grid and legend
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=9)
        
        plt.tight_layout()
        
        # Save plot
        filename = f"timeseries_{i:03d}_km{td['distance_km']:.0f}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
    
    print(f"Generated {len(transect_data)} timeseries plots")
    
    # Create comparison plot
    create_comparison_plot(transect_data, output_dir, station_names, ylim)
    
    return transect_data

def create_comparison_plot(transect_data, output_dir, station_names, ylim):
    """Create a single plot comparing selected timeseries"""
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    
    # Select points to compare (start, middle, end)
    n_points = len(transect_data)
    indices = [0, n_points//2, n_points-1]
    colors = ['blue', 'green', 'red']
    labels = []
    
    if station_names:
        labels = [f"{station_names[0]} (Start)", 
                 f"Midpoint ({transect_data[n_points//2]['distance_km']:.0f} km)",
                 f"{station_names[1]} (End)"]
    else:
        labels = [f"Point 1 (0 km)",
                 f"Point {n_points//2+1} ({transect_data[n_points//2]['distance_km']:.0f} km)",
                 f"Point {n_points} ({transect_data[-1]['distance_km']:.0f} km)"]
    
    # Plot 1: All three timeseries overlaid
    for idx, color, label in zip(indices, colors, labels):
        td = transect_data[idx]
        axes[0].plot(td['times'], td['zeta'], color=color, linewidth=1.5,
                    alpha=0.7, label=label)
    
    axes[0].axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    axes[0].set_ylabel('Water Elevation (m)', fontsize=11)
    axes[0].set_title('Comparison of Water Elevation at Key Points Along Transect',
                     fontsize=12, fontweight='bold')
    axes[0].legend(loc='upper right')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_ylim(ylim)
    
    # Plot 2: Difference from start point
    start_zeta_interp = np.interp([t.timestamp() for t in transect_data[n_points//2]['times']],
                                  [t.timestamp() for t in transect_data[0]['times']],
                                  transect_data[0]['zeta'])
    end_zeta_interp = np.interp([t.timestamp() for t in transect_data[-1]['times']],
                               [t.timestamp() for t in transect_data[0]['times']],
                               transect_data[0]['zeta'])
    
    axes[1].plot(transect_data[n_points//2]['times'],
                transect_data[n_points//2]['zeta'] - start_zeta_interp,
                'green', linewidth=1.5, label='Midpoint - Start')
    axes[1].plot(transect_data[-1]['times'],
                transect_data[-1]['zeta'] - end_zeta_interp,
                'red', linewidth=1.5, label='End - Start')
    
    axes[1].axhline(y=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)
    axes[1].set_ylabel('Elevation Difference (m)', fontsize=11)
    axes[1].set_title('Water Elevation Difference Relative to Start Point',
                     fontsize=12, fontweight='bold')
    axes[1].legend(loc='upper right')
    axes[1].grid(True, alpha=0.3)
    
    # Plot 3: Spatial gradient visualization (heatmap-style)
    n_times = len(transect_data[0]['times'])
    n_space = len(transect_data)
    zeta_array = np.zeros((n_space, n_times))
    
    for i, td in enumerate(transect_data):
        # Interpolate to common time grid if needed
        zeta_interp = np.interp([t.timestamp() for t in transect_data[0]['times']],
                               [t.timestamp() for t in td['times']],
                               td['zeta'])
        zeta_array[i, :] = zeta_interp
    
    # Create contour plot
    times_plot = transect_data[0]['times']
    distances_plot = [td['distance_km'] for td in transect_data]
    
    im = axes[2].contourf(times_plot, distances_plot, zeta_array,
                         levels=20, cmap='RdBu_r', extend='both')
    
    # Add station markers
    if station_names:
        axes[2].axhline(y=0, color='black', linestyle='--', linewidth=2,
                       label=station_names[0])
        axes[2].axhline(y=transect_data[-1]['distance_km'], color='black',
                       linestyle='--', linewidth=2, label=station_names[1])
    
    axes[2].set_ylabel('Distance Along Transect (km)', fontsize=11)
    axes[2].set_xlabel('Date/Time', fontsize=11)
    axes[2].set_title('Spatial-Temporal Water Elevation Pattern',
                     fontsize=12, fontweight='bold')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=axes[2], orientation='vertical', pad=0.02)
    cbar.set_label('Water Elevation (m)', fontsize=10)
    
    # Format dates on x-axis
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
#    filepath = os.path.join(output_dir, 'transect_comparison.png')
#    plt.savefig(filepath, dpi=150, bbox_inches='tight')
#    plt.close()
    
#    print(f"Created comparison plot: {filepath}")

def main():
    parser = argparse.ArgumentParser(
        description='Generate timeseries for all points along a transect ',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate timeseries for 20 points along transect
  python transect_timeseries_simple.py fort.63.nc \\
      -75.705 35.208 -76.670 34.717 \\
      --points 20 --output-dir hatteras_beaufort
  
  # With station names and time filtering
  python transect_timeseries_simple.py fort.63.nc \\
      -75.705 35.208 -76.670 34.717 \\
      --points 30 --stations "Hatteras_NC" "Beaufort_NC" \\
      --start-time "2025-09-16" --end-time "2025-09-20" \\
      --output-dir transect_analysis
        """)
    
    parser.add_argument('nc_file', help='Path to fort.63.nc file')
    parser.add_argument('lon1', type=float, help='Starting longitude')
    parser.add_argument('lat1', type=float, help='Starting latitude')
    parser.add_argument('lon2', type=float, help='Ending longitude')
    parser.add_argument('lat2', type=float, help='Ending latitude')
    
    parser.add_argument('--points', type=int, default=20,
                       help='Number of points along transect (default: 20)')
    parser.add_argument('--stations', type=str, nargs=2,
                       help='Names of start and end stations')
    parser.add_argument('--output-dir', type=str, default='transect_timeseries',
                       help='Output directory for plots')
    parser.add_argument('--start-time', type=str,
                       help='Start time filter (YYYY-MM-DD)')
    parser.add_argument('--end-time', type=str,
                       help='End time filter (YYYY-MM-DD)')
    parser.add_argument('--save-csv', action='store_true',
                       help='Save statistics to CSV file')
    
    args = parser.parse_args()
    
    # Run analysis
    extract_transect_timeseries(
        args.nc_file,
        start_point=(args.lon1, args.lat1),
        end_point=(args.lon2, args.lat2),
        n_points=args.points,
        output_dir=args.output_dir,
        start_time=args.start_time,
        end_time=args.end_time,
        station_names=tuple(args.stations) if args.stations else None,
        save_csv=args.save_csv
    )
    
    print(f"\nAnalysis complete! Check {args.output_dir}/ for plots")
    if args.save_csv:
        print(f"Statistics saved to {args.output_dir}/transect_statistics.csv")

if __name__ == '__main__':
    main()
