#!/usr/bin/env python
"""
ADCIRC Fort.61.nc Timeseries Data Extractor and Plotter
Extracts and visualizes water elevation timeseries data from ADCIRC fort.61.nc files
Output format: datetime string | water elevation
"""
import sys
import matplotlib
matplotlib.use('Agg')  # Force non-interactive backend
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
from datetime import datetime, timedelta
import argparse
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import warnings
warnings.filterwarnings('ignore')

def extract_station_data(nc_file, station_idx=None, station_name=None,
                        output_file=None, time_format='%Y-%m-%d %H:%M:%S',
                        plot=False, save_plot=None, plot_title=None,
                        start_time=None, end_time=None, ylim=None):
    """
    Extract timeseries data from fort.61.nc file

    Parameters:
    -----------
    nc_file : str
        Path to fort.61.nc file
    station_idx : int or list
        Station index/indices to extract (0-based)
    station_name : str or list
        Station name(s) to extract
    output_file : str
        Output file path (if None, prints to stdout)
    time_format : str
        DateTime format string
    plot : bool
        Whether to create plots
    save_plot : str
        Path to save plot image
    plot_title : str
        Custom plot title
    start_time : str
        Start time for filtering (format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
    end_time : str
        End time for filtering (format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
    ylim : tuple
        Y-axis limits (min, max)
    """

    # Open NetCDF file
    try:
        ds = nc.Dataset(nc_file, 'r')
    except Exception as e:
        print(f"Error opening file: {e}", file=sys.stderr)
        return

    # Get dimensions and variables
    time_var = ds.variables['time']
    zeta_var = ds.variables['zeta']
    station_names = ds.variables['station_name']
    x_var = ds.variables['x']
    y_var = ds.variables['y']

    # Parse base date from time units
    time_units = time_var.units
    base_date_str = time_units.split('since ')[-1]
    base_date = datetime.strptime(base_date_str, '%Y-%m-%d %H:%M')

    # Get time values and convert to datetime
    time_seconds = time_var[:]
    datetimes = [base_date + timedelta(seconds=float(t)) for t in time_seconds]

    # Parse time filters if provided
    time_mask = np.ones(len(datetimes), dtype=bool)
    if start_time:
        try:
            if len(start_time) == 10:  # Date only
                start_dt = datetime.strptime(start_time, '%Y-%m-%d')
            else:
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            time_mask = time_mask & np.array([dt >= start_dt for dt in datetimes])
        except:
            print(f"Warning: Invalid start_time format: {start_time}", file=sys.stderr)

    if end_time:
        try:
            if len(end_time) == 10:  # Date only
                end_dt = datetime.strptime(end_time, '%Y-%m-%d')
            else:
                end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            time_mask = time_mask & np.array([dt <= end_dt for dt in datetimes])
        except:
            print(f"Warning: Invalid end_time format: {end_time}", file=sys.stderr)

    # Determine which stations to extract
    stations_to_extract = []

    if station_idx is not None:
        if isinstance(station_idx, int):
            stations_to_extract.append(station_idx)
        else:
            stations_to_extract.extend(station_idx)

    if station_name is not None:
        # Convert station names from char array to strings
        station_name_list = [''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                             for c in name).strip()
                             for name in station_names[:]]

        if isinstance(station_name, str):
            station_name = [station_name]

        for name in station_name:
            try:
                idx = station_name_list.index(name)
                stations_to_extract.append(idx)
            except ValueError:
                print(f"Warning: Station '{name}' not found", file=sys.stderr)

    # If no stations specified, extract all
    if not stations_to_extract:
        print("No specific stations requested. Use --station-idx or --station-name to select stations.")
        print(f"Total stations available: {len(station_names)}")
        print("\nFirst 10 stations:")
        station_name_list = [''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                             for c in name).strip()
                             for name in station_names[:10]]
        for i, name in enumerate(station_name_list):
            lon = x_var[i]
            lat = y_var[i]
            print(f"  {i}: {name} (lon: {lon:.4f}, lat: {lat:.4f})")
        ds.close()
        return

    # Remove duplicates and sort
    stations_to_extract = sorted(list(set(stations_to_extract)))

    # Prepare output and plotting data
    output_lines = []
    plot_data = []

    for station_idx in stations_to_extract:
        if station_idx >= len(station_names):
            print(f"Warning: Station index {station_idx} out of range", file=sys.stderr)
            continue

        # Get station info
        name = ''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                      for c in station_names[station_idx]).strip()
        lon = x_var[station_idx]
        lat = y_var[station_idx]

        # Add header
        output_lines.append(f"# Station: {name}")
        output_lines.append(f"# Index: {station_idx}")
        output_lines.append(f"# Location: {lon:.6f}, {lat:.6f}")
        output_lines.append(f"# DateTime | Water Elevation (m)")
        output_lines.append("#" + "="*50)

        # Extract water elevation for this station
        zeta_values = zeta_var[:, station_idx]

        # Apply time filter
        filtered_datetimes = np.array(datetimes)[time_mask]
        filtered_zeta = zeta_values[time_mask]

        # Prepare data for plotting
        valid_times = []
        valid_zeta = []

        # Process each time step
        valid_count = 0
        for dt, zeta in zip(filtered_datetimes, filtered_zeta):
            # Check for fill values (dry cells or missing data)
            if not np.isclose(zeta, -99999.0):
                output_lines.append(f"{dt.strftime(time_format)} | {zeta:.4f}")
                valid_times.append(dt)
                valid_zeta.append(zeta)
                valid_count += 1
            else:
                # Optionally include dry/missing values
                output_lines.append(f"{dt.strftime(time_format)} | NaN")

        output_lines.append(f"# Valid data points: {valid_count}/{len(filtered_datetimes)}")
        output_lines.append("")  # Empty line between stations

        # Store plotting data
        if valid_times:
            plot_data.append({
                'name': name,
                'idx': station_idx,
                'lon': lon,
                'lat': lat,
                'times': valid_times,
                'zeta': valid_zeta
            })

    # Close NetCDF file
    ds.close()

    # Output results
    output_text = '\n'.join(output_lines)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(output_text)
        print(f"Data written to {output_file}")
    else:
        print(output_text)

    # Create plots if requested
    if plot and plot_data:
        create_plots(plot_data, save_plot, plot_title, ylim)

def create_plots(plot_data, save_plot=None, plot_title=None, ylim=None):
    """
    Create plots for the extracted data
    
    Parameters:
    -----------
    plot_data : list
        List of dictionaries containing plot data
    save_plot : str
        Path to save the plot
    plot_title : str
        Title for the plot
    ylim : tuple
        Y-axis limits (min, max)
    """

    n_stations = len(plot_data)

    if n_stations == 0:
        print("No data to plot", file=sys.stderr)
        return

    # Create figure with subplots
    if n_stations == 1:
        fig, axes = plt.subplots(1, 1, figsize=(14, 6))
        axes = [axes]  # Make it iterable
    else:
        fig, axes = plt.subplots(n_stations, 1, figsize=(14, 4*n_stations),
                                sharex=True)
        if n_stations == 1:
            axes = [axes]

    # Set main title
    if plot_title:
        fig.suptitle(plot_title, fontsize=16, fontweight='bold')
    else:
        fig.suptitle('ADCIRC Water Elevation Timeseries', fontsize=16, fontweight='bold')

    # Plot each station
    for i, (ax, data) in enumerate(zip(axes, plot_data)):
        times = data['times']
        zeta = data['zeta']

        # Main plot
        ax.plot(times, zeta, 'b-', linewidth=1.5, label='Water Elevation')

        # Add zero reference line
        ax.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)

        # Calculate statistics
        mean_zeta = np.mean(zeta)
        max_zeta = np.max(zeta)
        min_zeta = np.min(zeta)
        std_zeta = np.std(zeta)

        # Add mean line
        ax.axhline(y=mean_zeta, color='r', linestyle='--', linewidth=1,
                  alpha=0.7, label=f'Mean: {mean_zeta:.3f}m')

        # Format the plot
        ax.set_ylabel('Water Elevation (m)', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"{data['name']} (Index: {data['idx']}, "
                    f"Lon: {data['lon']:.3f}, Lat: {data['lat']:.3f})",
                    fontsize=11, fontweight='bold')

        # Add statistics text box
        stats_text = f'Max: {max_zeta:.3f}m\nMin: {min_zeta:.3f}m\nStd: {std_zeta:.3f}m'
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round',
                facecolor='wheat', alpha=0.5))

        # Add legend
        ax.legend(loc='upper right', fontsize=9)
        
        # Set y-axis limits if provided
        if ylim:
            ax.set_ylim(ylim)

        # Format x-axis (only for bottom plot)
        if i == n_stations - 1:
            ax.set_xlabel('Date/Time', fontsize=10)
            # Format dates on x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()

    # Save or show plot
    if save_plot:
        plt.savefig(save_plot, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {save_plot}")
    else:
        plt.show()

def plot_comparison(nc_file, station_indices=None, station_names=None,
                   save_plot=None, plot_title=None, start_time=None, end_time=None,
                   ylim=None, xlim=None):
    """Plot multiple stations on the same axes for comparison"""

    # Open NetCDF file
    try:
        ds = nc.Dataset(nc_file, 'r')
    except Exception as e:
        print(f"Error opening file: {e}", file=sys.stderr)
        return

    # Get dimensions and variables
    time_var = ds.variables['time']
    zeta_var = ds.variables['zeta']
    station_names_var = ds.variables['station_name']
    x_var = ds.variables['x']
    y_var = ds.variables['y']

    # Parse base date from time units
    time_units = time_var.units
    base_date_str = time_units.split('since ')[-1]
    base_date = datetime.strptime(base_date_str, '%Y-%m-%d %H:%M')

    # Get time values and convert to datetime
    time_seconds = time_var[:]
    datetimes = [base_date + timedelta(seconds=float(t)) for t in time_seconds]

    # Parse time filters if provided
    time_mask = np.ones(len(datetimes), dtype=bool)
    if start_time:
        try:
            if len(start_time) == 10:
                start_dt = datetime.strptime(start_time, '%Y-%m-%d')
            else:
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            time_mask = time_mask & np.array([dt >= start_dt for dt in datetimes])
        except:
            print(f"Warning: Invalid start_time format: {start_time}", file=sys.stderr)

    if end_time:
        try:
            if len(end_time) == 10:
                end_dt = datetime.strptime(end_time, '%Y-%m-%d')
            else:
                end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            time_mask = time_mask & np.array([dt <= end_dt for dt in datetimes])
        except:
            print(f"Warning: Invalid end_time format: {end_time}", file=sys.stderr)

    # Determine which stations to plot
    stations_to_plot = []

    if station_indices:
        stations_to_plot.extend(station_indices)

    if station_names:
        station_name_list = [''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                             for c in name).strip()
                             for name in station_names_var[:]]

        if isinstance(station_names, str):
            station_names = [station_names]

        for name in station_names:
            try:
                idx = station_name_list.index(name)
                stations_to_plot.append(idx)
            except ValueError:
                print(f"Warning: Station '{name}' not found", file=sys.stderr)

    if not stations_to_plot:
        print("No stations specified for comparison plot", file=sys.stderr)
        ds.close()
        return

    # Remove duplicates
    stations_to_plot = list(set(stations_to_plot))

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # Colors for different stations
    colors = plt.cm.tab10(np.linspace(0, 1, len(stations_to_plot)))

    # Apply time filter
    filtered_datetimes = np.array(datetimes)[time_mask]

    # Plot each station
    for i, station_idx in enumerate(stations_to_plot):
        # Get station info
        name = ''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                      for c in station_names_var[station_idx]).strip()

        # Extract water elevation
        zeta_values = zeta_var[:, station_idx][time_mask]

        # Filter out invalid values
        valid_mask = ~np.isclose(zeta_values, -99999.0)
        valid_times = filtered_datetimes[valid_mask]
        valid_zeta = zeta_values[valid_mask]

        if len(valid_zeta) > 0:
            # Plot on first axis (all together)
            ax1.plot(valid_times, valid_zeta, color=colors[i],
                    linewidth=1.5, label=f'{name} (idx: {station_idx})', alpha=0.8)

            # Plot on second axis (normalized)
            normalized_zeta = (valid_zeta - np.mean(valid_zeta)) / np.std(valid_zeta)
            ax2.plot(valid_times, normalized_zeta, color=colors[i],
                    linewidth=1.5, label=f'{name} (idx: {station_idx})', alpha=0.8)

    # Format first axis
    ax1.set_ylabel('Water Elevation (m)', fontsize=11)
    ax1.set_title(plot_title if plot_title else 'Water Elevation Comparison',
                 fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax1.legend(loc='upper left', fontsize=9, ncol=2)
    
    # Set axis limits if provided
    if ylim:
        ax1.set_ylim(ylim)
    if xlim:
        try:
            # Parse xlim strings to datetime
            xlim_dt = []
            for x in xlim:
                if len(x) == 10:  # Date only
                    xlim_dt.append(datetime.strptime(x, '%Y-%m-%d'))
                else:
                    xlim_dt.append(datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
            ax1.set_xlim(xlim_dt)
            ax2.set_xlim(xlim_dt)
        except Exception as e:
            print(f"Warning: Could not parse xlim dates: {e}", file=sys.stderr)

    # Format second axis
    ax2.set_ylabel('Normalized Water Elevation (σ)', fontsize=11)
    ax2.set_xlabel('Date/Time', fontsize=11)
    ax2.set_title('Normalized Water Elevation Comparison', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax2.legend(loc='upper left', fontsize=9, ncol=2)

    # Format dates on x-axis
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()

    # Close NetCDF file
    ds.close()

    # Save or show plot
    if save_plot:
        plt.savefig(save_plot, dpi=150, bbox_inches='tight')
        print(f"Comparison plot saved to {save_plot}")
    else:
        plt.show()

def plot_statistics(nc_file, save_plot=None):
    """Create statistical plots for all stations"""

    try:
        ds = nc.Dataset(nc_file, 'r')
    except Exception as e:
        print(f"Error opening file: {e}", file=sys.stderr)
        return

    zeta_var = ds.variables['zeta']
    station_names = ds.variables['station_name']
    x_var = ds.variables['x']
    y_var = ds.variables['y']

    n_stations = len(station_names)

    # Calculate statistics for each station
    max_elevations = []
    min_elevations = []
    mean_elevations = []
    std_elevations = []
    lons = []
    lats = []

    print("Calculating statistics for all stations...")
    for i in range(n_stations):
        zeta = zeta_var[:, i]
        valid_zeta = zeta[~np.isclose(zeta, -99999.0)]

        if len(valid_zeta) > 0:
            max_elevations.append(np.max(valid_zeta))
            min_elevations.append(np.min(valid_zeta))
            mean_elevations.append(np.mean(valid_zeta))
            std_elevations.append(np.std(valid_zeta))
            lons.append(x_var[i])
            lats.append(y_var[i])

    ds.close()

    # Create statistical plots
    fig = plt.figure(figsize=(16, 12))

    # Geographic distribution of max elevations
    ax1 = plt.subplot(2, 3, 1)
    scatter1 = ax1.scatter(lons, lats, c=max_elevations, cmap='RdYlBu_r',
                          s=20, alpha=0.6)
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    ax1.set_title('Maximum Water Elevation Distribution')
    plt.colorbar(scatter1, ax=ax1, label='Max Elevation (m)')
    ax1.grid(True, alpha=0.3)

    # Geographic distribution of mean elevations
    ax2 = plt.subplot(2, 3, 2)
    scatter2 = ax2.scatter(lons, lats, c=mean_elevations, cmap='viridis',
                          s=20, alpha=0.6)
    ax2.set_xlabel('Longitude')
    ax2.set_ylabel('Latitude')
    ax2.set_title('Mean Water Elevation Distribution')
    plt.colorbar(scatter2, ax=ax2, label='Mean Elevation (m)')
    ax2.grid(True, alpha=0.3)

    # Geographic distribution of std elevations
    ax3 = plt.subplot(2, 3, 3)
    scatter3 = ax3.scatter(lons, lats, c=std_elevations, cmap='plasma',
                          s=20, alpha=0.6)
    ax3.set_xlabel('Longitude')
    ax3.set_ylabel('Latitude')
    ax3.set_title('Water Elevation Std Dev Distribution')
    plt.colorbar(scatter3, ax=ax3, label='Std Dev (m)')
    ax3.grid(True, alpha=0.3)

    # Histogram of max elevations
    ax4 = plt.subplot(2, 3, 4)
    ax4.hist(max_elevations, bins=50, edgecolor='black', alpha=0.7)
    ax4.set_xlabel('Maximum Elevation (m)')
    ax4.set_ylabel('Number of Stations')
    ax4.set_title('Distribution of Maximum Elevations')
    ax4.grid(True, alpha=0.3)

    # Histogram of mean elevations
    ax5 = plt.subplot(2, 3, 5)
    ax5.hist(mean_elevations, bins=50, edgecolor='black', alpha=0.7, color='green')
    ax5.set_xlabel('Mean Elevation (m)')
    ax5.set_ylabel('Number of Stations')
    ax5.set_title('Distribution of Mean Elevations')
    ax5.grid(True, alpha=0.3)

    # Range plot (max - min)
    ax6 = plt.subplot(2, 3, 6)
    ranges = [max_e - min_e for max_e, min_e in zip(max_elevations, min_elevations)]
    ax6.hist(ranges, bins=50, edgecolor='black', alpha=0.7, color='orange')
    ax6.set_xlabel('Elevation Range (m)')
    ax6.set_ylabel('Number of Stations')
    ax6.set_title('Distribution of Elevation Ranges')
    ax6.grid(True, alpha=0.3)

    plt.suptitle('ADCIRC Fort.61 Statistical Analysis', fontsize=16, fontweight='bold')
    plt.tight_layout()

    if save_plot:
        plt.savefig(save_plot, dpi=150, bbox_inches='tight')
        print(f"Statistics plot saved to {save_plot}")
    else:
        plt.show()

def plot_overlay(nc_files, station_idx=None, station_name=None,
                 save_plot=None, plot_title=None, start_time=None, end_time=None,
                 ylim=None, xlim=None, labels=None):
    """
    Overlay water elevation data from multiple fort.61.nc files for the same station
    
    Parameters:
    -----------
    nc_files : list
        List of paths to fort.61.nc files to compare
    station_idx : int
        Station index to extract (0-based)
    station_name : str
        Station name to extract
    save_plot : str
        Path to save plot
    plot_title : str
        Custom plot title
    start_time : str
        Start time for filtering
    end_time : str
        End time for filtering
    ylim : tuple
        Y-axis limits (min, max)
    xlim : tuple
        X-axis time limits
    labels : list
        Custom labels for each file (default: filenames)
    """
    print(f"DEBUG: plot_overlay called with files: {nc_files}, station_idx: {station_idx}")  # ADD THIS LINE
    
    if not nc_files or len(nc_files) < 2:
        print("Error: Need at least 2 files to overlay", file=sys.stderr)
        return
    
    # Prepare data storage
    all_data = []
    
    # Process each file
    for i, nc_file in enumerate(nc_files):
        try:
            ds = nc.Dataset(nc_file, 'r')
        except Exception as e:
            print(f"Error opening file {nc_file}: {e}", file=sys.stderr)
            continue
        
        # Get dimensions and variables
        time_var = ds.variables['time']
        zeta_var = ds.variables['zeta']
        station_names = ds.variables['station_name']
        x_var = ds.variables['x']
        y_var = ds.variables['y']
        
        # Parse base date from time units
        time_units = time_var.units
        base_date_str = time_units.split('since ')[-1]
        base_date = datetime.strptime(base_date_str, '%Y-%m-%d %H:%M')
        
        # Get time values and convert to datetime
        time_seconds = time_var[:]
        datetimes = [base_date + timedelta(seconds=float(t)) for t in time_seconds]
        
        # Determine which station to extract
        target_idx = None
        
        if station_idx is not None:
            target_idx = station_idx
        elif station_name is not None:
            # Convert station names from char array to strings
            station_name_list = [''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                                 for c in name).strip()
                                 for name in station_names[:]]
            try:
                target_idx = station_name_list.index(station_name)
            except ValueError:
                print(f"Warning: Station '{station_name}' not found in {nc_file}", file=sys.stderr)
                ds.close()
                continue
        else:
            print("Error: Must specify either station_idx or station_name", file=sys.stderr)
            ds.close()
            return
        
        # Get station info
        name = ''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                      for c in station_names[target_idx]).strip()
        lon = x_var[target_idx]
        lat = y_var[target_idx]
        
        # Extract water elevation
        zeta_values = zeta_var[:, target_idx]
        
        # Parse time filters if provided
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
        
        # Apply time filter
        filtered_datetimes = np.array(datetimes)[time_mask]
        filtered_zeta = zeta_values[time_mask]
        
        # Filter out invalid values
        valid_mask = ~np.isclose(filtered_zeta, -99999.0)
        valid_times = filtered_datetimes[valid_mask]
        valid_zeta = filtered_zeta[valid_mask]
        
        # Store data
        if labels and i < len(labels):
            label = labels[i]
        else:
            label = nc_file.replace('.nc', '').replace('fort.61_', '').replace('fort.61', 'Run')
        
        all_data.append({
            'file': nc_file,
            'label': label,
            'name': name,
            'idx': target_idx,
            'lon': lon,
            'lat': lat,
            'times': valid_times,
            'zeta': valid_zeta
        })
        
        ds.close()
    
    if not all_data:
        print("Error: No valid data extracted from files", file=sys.stderr)
        return
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    #fig, ax1 = plt.subplots(1, 1, figsize=(14, 6))

    # Colors for different files
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
    
    # Plot each dataset
    for i, data in enumerate(all_data):
        color = colors[i % len(colors)]
        
        # Top plot: Overlay of water elevations
        ax1.plot(data['times'], data['zeta'], color=color, 
                linewidth=1.5, label=data['label'], alpha=0.8)
        
        # Calculate statistics
        max_zeta = np.max(data['zeta'])
        min_zeta = np.min(data['zeta'])
        mean_zeta = np.mean(data['zeta'])
        
        print(f"\n{data['label']} Statistics:")
        print(f"  Station: {data['name']} (Index: {data['idx']})")
        print(f"  Location: ({data['lon']:.4f}, {data['lat']:.4f})")
        print(f"  Max: {max_zeta:.3f}m")
        print(f"  Min: {min_zeta:.3f}m")
        print(f"  Mean: {mean_zeta:.3f}m")
    
    # Calculate differences (if exactly 2 files)
    if len(all_data) == 2 and len(all_data[0]['zeta']) == len(all_data[1]['zeta']):
        # Simple difference calculation (assuming same time grid)
        diff = all_data[1]['zeta'] - all_data[0]['zeta']
        times = all_data[0]['times']
        
        # Plot difference in bottom panel
        ax2.plot(times, diff, 'k-', linewidth=1.5, 
                label=f"{all_data[1]['label']} - {all_data[0]['label']}")
        ax2.fill_between(times, diff, 0, where=(diff >= 0), 
                        color='red', alpha=0.3, label='Higher')
        ax2.fill_between(times, diff, 0, where=(diff < 0), 
                        color='blue', alpha=0.3, label='Lower')
        
        # Add statistics for difference
        max_diff = np.max(diff)
        min_diff = np.min(diff)
        mean_diff = np.mean(diff)
        rmse = np.sqrt(np.mean(diff**2))
        
        stats_text = f'Max Diff: {max_diff:.3f}m\nMin Diff: {min_diff:.3f}m\n'
        stats_text += f'Mean Diff: {mean_diff:.3f}m\nRMSE: {rmse:.3f}m'
        ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round',
                facecolor='wheat', alpha=0.5))
        
        print(f"\nDifference ({all_data[1]['label']} - {all_data[0]['label']}):")
        print(f"  Max Difference: {max_diff:.3f}m")
        print(f"  Min Difference: {min_diff:.3f}m")
        print(f"  Mean Difference: {mean_diff:.3f}m")
        print(f"  RMSE: {rmse:.3f}m")
    else:
        # If more than 2 files or different lengths, show message
        if len(all_data) > 2:
            ax2.text(0.5, 0.5, 'Difference plot only available for exactly 2 files', 
                    transform=ax2.transAxes, ha='center', va='center', fontsize=12)
        else:
            ax2.text(0.5, 0.5, 'Different time grids - difference not calculated', 
                    transform=ax2.transAxes, ha='center', va='center', fontsize=12)
        ax2.set_ylabel('Difference (m)', fontsize=11)
    
    # Format top plot
    ax1.set_ylabel('Water Elevation (m)', fontsize=11)
    station_info = all_data[0]
    if plot_title:
        ax1.set_title(plot_title, fontsize=14, fontweight='bold')
    else:
        ax1.set_title(f"Water Elevation: {station_info['name']} "
                     f"(Index: {station_info['idx']}, Lon: {station_info['lon']:.3f}, "
                     f"Lat: {station_info['lat']:.3f})", fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
    ax1.legend(loc='upper left', fontsize=10)
    
    # Format bottom plot (difference)
    if len(all_data) == 2 and len(all_data[0]['zeta']) == len(all_data[1]['zeta']):
        ax2.set_ylabel('Elevation Difference (m)', fontsize=11)
        ax2.set_xlabel('Date/Time', fontsize=11)
        ax2.set_title(' ', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)
        ax2.legend(loc='upper left', fontsize=10)
    else:
        ax2.set_xlabel('Date/Time', fontsize=11)
        ax2.grid(True, alpha=0.3)
    
    # Set axis limits if provided
    if ylim:
        ax1.set_ylim(ylim)
    if xlim:
        try:
            xlim_dt = []
            for x in xlim:
                if len(x) == 10:
                    xlim_dt.append(datetime.strptime(x, '%Y-%m-%d'))
                else:
                    xlim_dt.append(datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
            ax1.set_xlim(xlim_dt)
            ax2.set_xlim(xlim_dt)
        except Exception as e:
            print(f"Warning: Could not parse xlim dates: {e}", file=sys.stderr)
    
    # Format dates on x-axis
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()

# Save or show plot
    if save_plot:
        plt.savefig(save_plot, dpi=150, bbox_inches='tight')
        print(f"\nOverlay plot saved to {save_plot}")
        sys.stdout.flush()
    else:
        plt.show()        

def list_stations(nc_file, search_term=None, near_point=None, radius=1.0):
    """
    List all available stations in the file

    Parameters:
    -----------
    nc_file : str
        Path to fort.61.nc file
    search_term : str
        Search term for station names
    near_point : tuple
        (lon, lat) to find nearby stations
    radius : float
        Search radius in degrees for nearby stations
    """
    try:
        ds = nc.Dataset(nc_file, 'r')
    except Exception as e:
        print(f"Error opening file: {e}", file=sys.stderr)
        return

    station_names = ds.variables['station_name']
    x_var = ds.variables['x']
    y_var = ds.variables['y']

    if near_point:
        target_lon, target_lat = near_point
        print(f"Stations within {radius} degrees of ({target_lon:.2f}, {target_lat:.2f}):")
    else:
        print(f"Total stations: {len(station_names)}")

    print("\nStation List:")
    print("-" * 70)
    print(f"{'Index':<8} {'Name':<30} {'Lon':<12} {'Lat':<12} {'Dist':<8}")
    print("-" * 70)

    stations_found = []

    for i, name_array in enumerate(station_names[:]):
        name = ''.join(c.decode('utf-8') if isinstance(c, bytes) else c
                      for c in name_array).strip()

        lon = x_var[i]
        lat = y_var[i]

        # Filter by search term if provided
        if search_term and search_term.lower() not in name.lower():
            continue

        # Calculate distance if near_point is provided
        if near_point:
            dist = np.sqrt((lon - target_lon)**2 + (lat - target_lat)**2)
            if dist <= radius:
                stations_found.append((i, name, lon, lat, dist))
        else:
            stations_found.append((i, name, lon, lat, None))

    # Sort by distance if near_point was provided
    if near_point:
        stations_found.sort(key=lambda x: x[4])

    # Print results
    for station in stations_found:
        i, name, lon, lat, dist = station
        if dist is not None:
            print(f"{i:<8} {name:<30} {lon:<12.6f} {lat:<12.6f} {dist:<8.4f}")
        else:
            print(f"{i:<8} {name:<30} {lon:<12.6f} {lat:<12.6f}")

    if not stations_found:
        if search_term:
            print(f"No stations found matching '{search_term}'")
        elif near_point:
            print(f"No stations found within {radius} degrees of the specified point")

    ds.close()

def main():
    parser = argparse.ArgumentParser(
        description='Extract and plot timeseries data from ADCIRC fort.61.nc files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all stations
  python extract_fort61.py fort.61.nc --list

  # Find stations near Cape Hatteras, NC
  python extract_fort61.py fort.61.nc --list --near -75.5 35.2 --radius 2.0

  # Extract data for station index 0
  python extract_fort61.py fort.61.nc --station-idx 0

  # Extract and plot data for multiple stations
  python extract_fort61.py fort.61.nc --station-idx 0 10 20 --plot

  # Extract data by station name with plot
  python extract_fort61.py fort.61.nc --station-name "StationName" --plot --save-plot output.png

  # Save extracted data to file
  python extract_fort61.py fort.61.nc --station-idx 0 -o output.txt

  # Extract data for specific time range
  python extract_fort61.py fort.61.nc --station-idx 0 --start-time "2025-04-05" --end-time "2025-04-10"

  # Extract and plot with custom axis limits
  python extract_fort61.py fort.61.nc --station-idx 0 --plot --ylim -2 2

  # Overlay water elevation from multiple files
  python extract_fort61.py --overlay fort.61.nc fort.61_yuji.nc \\
      --station-idx 46 --labels "Original" "Yuji" --save-plot overlay.png

  # Comparison plot with both x and y limits
  python extract_fort61.py fort.61.nc --compare --station-idx 0 10 20 \\
      --ylim -1.5 1.5 --xlim "2025-04-05" "2025-04-10" --save-plot compare.png

  # Generate statistical plots for all stations
  python extract_fort61.py fort.61.nc --stats --save-plot statistics.png
        """)

    parser.add_argument('nc_file', nargs='?', help='Path to fort.61.nc file')
    parser.add_argument('--overlay', type=str, nargs='+', metavar='FILES',
                       help='Overlay data from multiple fort.61.nc files')
    parser.add_argument('--labels', type=str, nargs='+',
                       help='Custom labels for overlay files')
    parser.add_argument('--list', action='store_true',
                       help='List all available stations')
    parser.add_argument('--search', type=str,
                       help='Search term for station names (use with --list)')
    parser.add_argument('--near', type=float, nargs=2, metavar=('LON', 'LAT'),
                       help='Find stations near a point (lon lat)')
    parser.add_argument('--radius', type=float, default=1.0,
                       help='Search radius in degrees for --near option (default: 1.0)')
    parser.add_argument('--station-idx', type=int, nargs='+',
                       help='Station index/indices to extract (0-based)')
    parser.add_argument('--station-name', type=str, nargs='+',
                       help='Station name(s) to extract')
    parser.add_argument('-o', '--output', type=str,
                       help='Output file path (default: stdout)')
    parser.add_argument('--time-format', type=str, default='%Y-%m-%d %H:%M:%S',
                       help='DateTime format string (default: %%Y-%%m-%%d %%H:%%M:%%S)')
    parser.add_argument('--plot', action='store_true',
                       help='Create plots of the extracted data')
    parser.add_argument('--save-plot', type=str,
                       help='Save plot to file (e.g., output.png)')
    parser.add_argument('--plot-title', type=str,
                       help='Custom title for the plot')
    parser.add_argument('--start-time', type=str,
                       help='Start time filter (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end-time', type=str,
                       help='End time filter (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--ylim', type=float, nargs=2, metavar=('MIN', 'MAX'),
                       help='Y-axis limits for plots (min max)')
    parser.add_argument('--xlim', type=str, nargs=2, metavar=('START', 'END'),
                       help='X-axis time limits (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--compare', action='store_true',
                       help='Create comparison plot with multiple stations on same axes')
    parser.add_argument('--stats', action='store_true',
                       help='Generate statistical plots for all stations')

    args = parser.parse_args()
    print(f"DEBUG: args.overlay = {args.overlay}")  # ADD THIS LINE
    print(f"DEBUG: args.nc_file = {args.nc_file}")  # ADD THIS LINE

    # Handle overlay mode
    if args.overlay:
        print(f"DEBUG: Entering overlay mode")  # ADD THIS LINE
        plot_overlay(args.overlay,
                    station_idx=args.station_idx[0] if args.station_idx else None,
                    station_name=args.station_name[0] if args.station_name else None,
                    save_plot=args.save_plot,
                    plot_title=args.plot_title,
                    start_time=args.start_time,
                    end_time=args.end_time,
                    ylim=args.ylim if hasattr(args, 'ylim') else None,
                    xlim=args.xlim if hasattr(args, 'xlim') else None,
                    labels=args.labels)
    elif args.nc_file:  # Original functionality
        if args.list:
            list_stations(args.nc_file, args.search, args.near, args.radius)
        elif args.compare:
            plot_comparison(args.nc_file,
                           station_indices=args.station_idx,
                           station_names=args.station_name,
                           save_plot=args.save_plot,
                           plot_title=args.plot_title,
                           start_time=args.start_time,
                           end_time=args.end_time,
                           ylim=args.ylim if hasattr(args, 'ylim') else None,
                           xlim=args.xlim if hasattr(args, 'xlim') else None)
        elif args.stats:
            plot_statistics(args.nc_file, save_plot=args.save_plot)
        else:
            extract_station_data(
                args.nc_file,
                station_idx=args.station_idx,
                station_name=args.station_name,
                output_file=args.output,
                time_format=args.time_format,
                plot=args.plot,
                save_plot=args.save_plot,
                plot_title=args.plot_title,
                start_time=args.start_time,
                end_time=args.end_time,
                ylim=args.ylim if hasattr(args, 'ylim') else None
            )
    else:
        print("Error: Must provide either nc_file or use --overlay with multiple files")
        parser.print_help()
if __name__ == '__main__':
    main()

