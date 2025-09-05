#!/usr/bin/env python3
"""
Script to plot differences between two fort.11.nc (or bcforcing_ver6p2.nc) files
Compares the same variable across two different files and visualizes the difference
python plot_difference2.py fort.11.nc fort.11_und.nc SigTS --mode snapshots     --vmin -0.000006 --vmax 0.000007 --color-levels 16 --colormap RdBu_r     --max-points 0 --dpi 300 --no-individual --output-dir SigTS_diff_only
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from netCDF4 import Dataset
import argparse
import sys
import os
from datetime import datetime
from matplotlib.colors import BoundaryNorm, TwoSlopeNorm
import warnings
warnings.filterwarnings('ignore', message='.*XRandR.*')

def load_netcdf_data(filename):
    """Load data from NetCDF file"""
    try:
        nc = Dataset(filename, 'r')
        return nc
    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading NetCDF file: {e}")
        sys.exit(1)

def get_available_variables(nc):
    """Get list of plottable variables"""
    variables = []
    for var_name in nc.variables:
        var = nc.variables[var_name]
        if hasattr(var, 'dimensions') and 'time' in var.dimensions and 'node' in var.dimensions:
            variables.append(var_name)
    return variables

def compute_difference(nc1, nc2, var_name, time_index):
    """Compute difference between two datasets for a specific variable and time"""
    
    # Get coordinates from both files
    x1 = nc1.variables['x'][:]
    y1 = nc1.variables['y'][:]
    x2 = nc2.variables['x'][:]
    y2 = nc2.variables['y'][:]
    
    # Check if grids match
    if len(x1) != len(x2) or len(y1) != len(y2):
        print(f"Warning: Grid sizes don't match!")
        print(f"  File 1: {len(x1)} nodes")
        print(f"  File 2: {len(x2)} nodes")
        
        # Use the smaller grid as reference
        if len(x1) <= len(x2):
            x_ref, y_ref = x1, y1
            print(f"  Using File 1 grid as reference")
        else:
            x_ref, y_ref = x2, y2
            print(f"  Using File 2 grid as reference")
    else:
        x_ref, y_ref = x1, y1
    
    # Get variable data
    var_data1 = nc1.variables[var_name]
    var_data2 = nc2.variables[var_name]
    
    # Check time dimensions
    if time_index >= var_data1.shape[0] or time_index >= var_data2.shape[0]:
        max_time = min(var_data1.shape[0], var_data2.shape[0])
        print(f"Error: Time index {time_index} out of range. Maximum common time index: {max_time-1}")
        return None, None, None, None, None
    
    # Get data for specific time
    data1 = var_data1[time_index, :]
    data2 = var_data2[time_index, :]
    
    # Handle fill values
    if hasattr(var_data1, '_FillValue'):
        data1 = np.ma.masked_equal(data1, var_data1._FillValue)
    if hasattr(var_data2, '_FillValue'):
        data2 = np.ma.masked_equal(data2, var_data2._FillValue)
    
    # Compute difference (ensure same size)
    min_len = min(len(data1), len(data2))
    data1 = data1[:min_len]
    data2 = data2[:min_len]
    x_ref = x_ref[:min_len]
    y_ref = y_ref[:min_len]
    
    # Calculate difference
    diff_data = data2 - data1  # File2 - File1
    
    # Get time strings
    time_str1 = nc1.variables['time'][time_index].tobytes().decode('utf-8').strip()
    time_str2 = nc2.variables['time'][time_index].tobytes().decode('utf-8').strip()
    
    return x_ref, y_ref, diff_data, data1, data2, time_str1, time_str2, var_data1

def plot_difference(x, y, diff_data, data1, data2, var_name, var_info,
                   time_str1, time_str2, file1_name, file2_name,
                   output_file=None, region='north_atlantic', 
                   lon_range=None, lat_range=None, max_points=100000,
                   colormap='RdBu_r', point_size=0.5, dpi=150,
                   use_triangulation=False, vmin=None, vmax=None,
                   color_levels=None, symmetric=True, figsize=(18, 12),
                   show_individual=True):
    """Create difference plot with optional individual plots"""
    
    # Define regional bounds
    if region == 'north_atlantic':
        lon_min, lon_max = -80, 20
        lat_min, lat_max = 20, 80
    elif region == 'custom' and lon_range and lat_range:
        lon_min, lon_max = lon_range
        lat_min, lat_max = lat_range
    else:
        lon_min, lon_max = x.min(), x.max()
        lat_min, lat_max = y.min(), y.max()
    
    # Filter for region
    if region != 'global':
        region_mask = ((x >= lon_min) & (x <= lon_max) & 
                      (y >= lat_min) & (y <= lat_max))
        x_region = x[region_mask]
        y_region = y[region_mask]
        diff_region = diff_data[region_mask]
        data1_region = data1[region_mask]
        data2_region = data2[region_mask]
    else:
        x_region = x
        y_region = y
        diff_region = diff_data
        data1_region = data1
        data2_region = data2
    
    # Subsample if needed
    if max_points > 0 and len(x_region) > max_points:
        step = max(1, len(x_region) // max_points)
        indices = np.arange(0, len(x_region), step)
        x_region = x_region[indices]
        y_region = y_region[indices]
        diff_region = diff_region[indices]
        data1_region = data1_region[indices]
        data2_region = data2_region[indices]
    
    print(f"Using {len(x_region)} points for plotting")
    
    # Calculate statistics
    diff_min, diff_max = np.nanmin(diff_region), np.nanmax(diff_region)
    diff_mean = np.nanmean(diff_region)
    diff_std = np.nanstd(diff_region)
    diff_rms = np.sqrt(np.nanmean(diff_region**2))
    
    data1_mean = np.nanmean(data1_region)
    data2_mean = np.nanmean(data2_region)
    
    print(f"\nStatistics for {var_name}:")
    print(f"  File 1 mean: {data1_mean:.6f}")
    print(f"  File 2 mean: {data2_mean:.6f}")
    print(f"  Difference (File2 - File1):")
    print(f"    Min: {diff_min:.6f}")
    print(f"    Max: {diff_max:.6f}")
    print(f"    Mean: {diff_mean:.6f}")
    print(f"    Std: {diff_std:.6f}")
    print(f"    RMS: {diff_rms:.6f}")
    
    # Set color range for difference
    if vmin is not None or vmax is not None:
        plot_vmin = vmin if vmin is not None else diff_min
        plot_vmax = vmax if vmax is not None else diff_max
    elif symmetric:
        abs_max = max(abs(diff_min), abs(diff_max))
        plot_vmin, plot_vmax = -abs_max, abs_max
    else:
        plot_vmin, plot_vmax = diff_min, diff_max
    
    # Create figure
    if show_individual:
        fig = plt.figure(figsize=(figsize[0], figsize[1]))
        gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[1, 1], 
                             hspace=0.25, wspace=0.15)
        
        # File 1 subplot
        ax1 = fig.add_subplot(gs[0, 0])
        # File 2 subplot
        ax2 = fig.add_subplot(gs[0, 1])
        # Difference subplot (spanning bottom)
        ax3 = fig.add_subplot(gs[1, :])
        
        axes = [ax1, ax2, ax3]
        data_list = [data1_region, data2_region, diff_region]
        titles = [f"File 1: {os.path.basename(file1_name)}", 
                 f"File 2: {os.path.basename(file2_name)}", 
                 f"Difference (File 2 - File 1)"]
        cmaps = ['viridis', 'viridis', colormap]
        
    else:
        fig, ax3 = plt.subplots(figsize=figsize, dpi=dpi)
        axes = [ax3]
        data_list = [diff_region]
        titles = [f"Difference: {os.path.basename(file2_name)} - {os.path.basename(file1_name)}"]
        cmaps = [colormap]
    
    # Plot each subplot
    for idx, (ax, data, title, cmap) in enumerate(zip(axes, data_list, titles, cmaps)):
        
        # Determine color scaling
        if idx < 2 and show_individual:  # Individual file plots
            data_min, data_max = np.nanmin(data), np.nanmax(data)
            norm = None
            vmin_use, vmax_use = data_min, data_max
        else:  # Difference plot
            vmin_use, vmax_use = plot_vmin, plot_vmax
            if color_levels is not None:
                levels = np.linspace(plot_vmin, plot_vmax, color_levels + 1)
                norm = BoundaryNorm(levels, ncolors=256, clip=True)
            elif symmetric and 0 >= plot_vmin and 0 <= plot_vmax:
                norm = TwoSlopeNorm(vmin=plot_vmin, vcenter=0, vmax=plot_vmax)
            else:
                norm = None
        
        # Plot data
        if use_triangulation and len(x_region) < 50000:
            triang = tri.Triangulation(x_region, y_region)
            if norm is not None:
                im = ax.tripcolor(triang, data, shading='gouraud', 
                                 cmap=cmap, alpha=0.9, norm=norm)
            else:
                im = ax.tripcolor(triang, data, shading='gouraud', 
                                 cmap=cmap, alpha=0.9, vmin=vmin_use, vmax=vmax_use)
        else:
            if norm is not None:
                im = ax.scatter(x_region, y_region, c=data, 
                               cmap=cmap, s=point_size, alpha=0.8,
                               edgecolors='none', rasterized=True, norm=norm)
            else:
                im = ax.scatter(x_region, y_region, c=data, 
                               cmap=cmap, s=point_size, alpha=0.8,
                               edgecolors='none', rasterized=True,
                               vmin=vmin_use, vmax=vmax_use)
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.ax.tick_params(labelsize=9)
        
        # Labels
        long_name = getattr(var_info, 'long_name', var_name)
        units = getattr(var_info, 'units', '')
        
        ax.set_xlabel('Longitude (degrees)', fontsize=10)
        ax.set_ylabel('Latitude (degrees)', fontsize=10)
        ax.set_title(f'{title}\n{long_name} - Time: {time_str1}', fontsize=11)
        
        if idx < 2 and show_individual:
            cbar.set_label(f'{long_name} ({units})', fontsize=9)
        else:
            cbar.set_label(f'Difference ({units})', fontsize=9)
            # Add statistics to difference plot
            stats_text = (f'Mean: {diff_mean:.3f}, Std: {diff_std:.3f}\n'
                         f'Min: {diff_min:.3f}, Max: {diff_max:.3f}, RMS: {diff_rms:.3f}')
           # ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
           #        fontsize=9, verticalalignment='top',
           #        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Set limits and styling
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, linewidth=0.5)
        
        # Add reference lines for North Atlantic
        if region == 'north_atlantic':
            ax.axhline(y=0, color='gray', linestyle='-', alpha=0.3, linewidth=0.5)
            ax.axvline(x=0, color='gray', linestyle='-', alpha=0.3, linewidth=0.5)
    
#    plt.suptitle(f'Comparison of {long_name} ({var_name})', fontsize=14, y=1.02)
    plt.tight_layout()
    
    # Save or show
    if output_file:
        fig.savefig(output_file, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        print(f"\nPlot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()
    
    return diff_mean, diff_std, diff_rms

def generate_difference_snapshots(file1, file2, variable='MLD', 
                                 output_dir='difference_snapshots',
                                 time_start=None, time_end=None, time_step=1,
                                 **kwargs):
    """Generate difference snapshots for multiple time steps"""
    
    # Load both files
    nc1 = load_netcdf_data(file1)
    nc2 = load_netcdf_data(file2)
    
    # Check variable exists in both files
    vars1 = get_available_variables(nc1)
    vars2 = get_available_variables(nc2)
    
    if variable not in vars1:
        print(f"Variable {variable} not found in {file1}")
        print(f"Available variables: {vars1}")
        nc1.close()
        nc2.close()
        return
    
    if variable not in vars2:
        print(f"Variable {variable} not found in {file2}")
        print(f"Available variables: {vars2}")
        nc1.close()
        nc2.close()
        return
    
    # Get time dimensions
    n_times1 = nc1.variables[variable].shape[0]
    n_times2 = nc2.variables[variable].shape[0]
    n_times = min(n_times1, n_times2)
    
    print(f"File 1 has {n_times1} time steps")
    print(f"File 2 has {n_times2} time steps")
    print(f"Using {n_times} common time steps")
    
    # Set time range
    if time_start is None:
        time_start = 0
    if time_end is None:
        time_end = n_times
    else:
        time_end = min(time_end, n_times)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Statistics file
    stats_file = os.path.join(output_dir, 'difference_statistics.txt')
    with open(stats_file, 'w') as f:
        f.write(f"Difference Statistics for {variable}\n")
        f.write(f"="*60 + "\n")
        f.write(f"File 1: {file1}\n")
        f.write(f"File 2: {file2}\n")
        f.write(f"Variable: {variable}\n")
        f.write(f"Time range: {time_start} to {time_end-1} (step {time_step})\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"="*60 + "\n\n")
        f.write(f"{'Time':<5} {'Time String':<20} {'Mean Diff':<12} {'Std Diff':<12} {'RMS Diff':<12}\n")
        f.write(f"{'-'*5} {'-'*20} {'-'*12} {'-'*12} {'-'*12}\n")
    
    # Process each time step
    all_means = []
    all_stds = []
    all_rms = []
    
    print(f"\nGenerating difference snapshots for {variable}...")
    print(f"Time range: {time_start} to {time_end-1} (step {time_step})")
    
    for t_idx in range(time_start, time_end, time_step):
        print(f"\n{'='*50}")
        print(f"Processing time step {t_idx}/{n_times-1}...")
        
        # Compute difference
        result = compute_difference(nc1, nc2, variable, t_idx)
        if result[0] is None:
            continue
        
        x, y, diff_data, data1, data2, time_str1, time_str2, var_info = result
        
        # Generate output filename
        output_file = os.path.join(output_dir, f"{variable}_diff_t{t_idx:04d}.png")
        
        # Create difference plot
        diff_mean, diff_std, diff_rms = plot_difference(
            x, y, diff_data, data1, data2, variable, var_info,
            time_str1, time_str2, file1, file2,
            output_file=output_file, **kwargs
        )
        
        # Store statistics
        all_means.append(diff_mean)
        all_stds.append(diff_std)
        all_rms.append(diff_rms)
        
        # Update statistics file
        with open(stats_file, 'a') as f:
            f.write(f"{t_idx:<5} {time_str1:<20} {diff_mean:<12.6f} {diff_std:<12.6f} {diff_rms:<12.6f}\n")
    
    # Summary statistics
    if all_means:
        with open(stats_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Summary Statistics:\n")
            f.write(f"  Mean of differences: {np.mean(all_means):.6f}\n")
            f.write(f"  Std of differences: {np.mean(all_stds):.6f}\n")
            f.write(f"  Mean RMS: {np.mean(all_rms):.6f}\n")
            f.write(f"  Max absolute difference: {max(abs(min(all_means)), abs(max(all_means))):.6f}\n")
    
    print(f"\n{'='*50}")
    print(f"Difference snapshot generation complete!")
    print(f"Generated {len(all_means)} snapshots in {output_dir}/")
    print(f"Statistics file: {stats_file}")
    
    nc1.close()
    nc2.close()

def main():
    parser = argparse.ArgumentParser(
        description='Plot differences between two fort.11.nc files')
    
    # Main arguments
    parser.add_argument('file1', help='First NetCDF file')
    parser.add_argument('file2', help='Second NetCDF file')
    parser.add_argument('variable', nargs='?', default='MLD',
                       help='Variable name to compare (default: MLD)')
    
    # Mode selection
    parser.add_argument('--mode', choices=['single', 'snapshots'],
                       default='single', help='Operation mode')
    
    # Time selection
    parser.add_argument('-t', '--time', type=int, default=0,
                       help='Time index for single plot')
    parser.add_argument('--time-start', type=int,
                       help='Starting time index for snapshots')
    parser.add_argument('--time-end', type=int,
                       help='Ending time index for snapshots')
    parser.add_argument('--time-step', type=int, default=1,
                       help='Time step for snapshots')
    
    # Output options
    parser.add_argument('--output-dir', default='difference_snapshots',
                       help='Directory for snapshot output')
    parser.add_argument('--save', type=str, help='Save single plot to file')
    parser.add_argument('--no-individual', action='store_true',
                       help='Only show difference plot, not individual files')
    
    # Region options
    parser.add_argument('-r', '--region', default='north_atlantic',
                       choices=['global', 'north_atlantic', 'custom'],
                       help='Region to plot')
    parser.add_argument('--lon-range', type=float, nargs=2,
                       help='Custom longitude range')
    parser.add_argument('--lat-range', type=float, nargs=2,
                       help='Custom latitude range')
    
    # Plot options
    parser.add_argument('--max-points', type=int, default=100000,
                       help='Maximum points to plot (0 for all)')
    parser.add_argument('--colormap', default='RdBu_r',
                       help='Matplotlib colormap for difference')
    parser.add_argument('--point-size', type=float, default=0.5,
                       help='Size of scatter points')
    parser.add_argument('--dpi', type=int, default=150,
                       help='Plot resolution DPI')
    parser.add_argument('--triangulation', action='store_true',
                       help='Use triangulated surface')
    parser.add_argument('--vmin', type=float,
                       help='Minimum value for difference color scale')
    parser.add_argument('--vmax', type=float,
                       help='Maximum value for difference color scale')
    parser.add_argument('--color-levels', type=int,
                       help='Number of discrete color levels')
    parser.add_argument('--no-symmetric', action='store_true',
                       help='Do not use symmetric color scale')
    
    # Utility options
    parser.add_argument('-l', '--list', action='store_true',
                       help='List common variables between files')
    
    args = parser.parse_args()
    
    # List variables if requested
    if args.list:
        nc1 = load_netcdf_data(args.file1)
        nc2 = load_netcdf_data(args.file2)
        
        vars1 = set(get_available_variables(nc1))
        vars2 = set(get_available_variables(nc2))
        common_vars = vars1.intersection(vars2)
        
        print(f"\nVariables in {os.path.basename(args.file1)}: {sorted(vars1)}")
        print(f"\nVariables in {os.path.basename(args.file2)}: {sorted(vars2)}")
        print(f"\nCommon variables: {sorted(common_vars)}")
        
        print("\nCommon variable details:")
        for var in sorted(common_vars):
            var_obj = nc1.variables[var]
            long_name = getattr(var_obj, 'long_name', 'No description')
            units = getattr(var_obj, 'units', 'No units')
            shape1 = var_obj.shape
            shape2 = nc2.variables[var].shape
            print(f"\n{var}:")
            print(f"  Description: {long_name}")
            print(f"  Units: {units}")
            print(f"  Shape in file1: {shape1}")
            print(f"  Shape in file2: {shape2}")
        
        nc1.close()
        nc2.close()
        return
    
    # Prepare kwargs for plotting
    plot_kwargs = {
        'region': args.region,
        'lon_range': args.lon_range,
        'lat_range': args.lat_range,
        'max_points': args.max_points,
        'colormap': args.colormap,
        'point_size': args.point_size,
        'dpi': args.dpi,
        'use_triangulation': args.triangulation,
        'vmin': args.vmin,
        'vmax': args.vmax,
        'color_levels': args.color_levels,
        'symmetric': not args.no_symmetric,
        'show_individual': not args.no_individual
    }
    
    # Execute based on mode
    if args.mode == 'snapshots':
        print(f"\n{'='*50}")
        print("DIFFERENCE SNAPSHOT GENERATION MODE")
        print(f"{'='*50}")
        generate_difference_snapshots(
            args.file1, args.file2, args.variable, args.output_dir,
            args.time_start, args.time_end, args.time_step,
            **plot_kwargs
        )
    else:  # Single plot mode
        print(f"\n{'='*50}")
        print("SINGLE DIFFERENCE PLOT MODE")
        print(f"{'='*50}")
        
        # Load files and compute difference
        nc1 = load_netcdf_data(args.file1)
        nc2 = load_netcdf_data(args.file2)
        
        result = compute_difference(nc1, nc2, args.variable, args.time)
        if result[0] is not None:
            x, y, diff_data, data1, data2, time_str1, time_str2, var_info = result
            
            plot_difference(
                x, y, diff_data, data1, data2, args.variable, var_info,
                time_str1, time_str2, args.file1, args.file2,
                output_file=args.save, **plot_kwargs
            )
        
        nc1.close()
        nc2.close()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Fort.11 Difference Plotter")
        print("="*50)
        print("\nExamples:")
        print("\n# List common variables between two files:")
        print("python plot_difference.py file1.nc file2.nc --list")
        print("\n# Single difference plot for MLD at time 0:")
        print("python plot_difference.py file1.nc file2.nc MLD --time 0")
        print("\n# Generate difference snapshots for all time steps:")
        print("python plot_difference.py file1.nc file2.nc MLD --mode snapshots")
        print("\n# High-quality difference with custom range:")
        print("python plot_difference.py file1.nc file2.nc MLD --mode snapshots \\")
        print("    --vmin -10 --vmax 10 --color-levels 20 --max-points 0 --dpi 300")
        print("\n# Compare BPGX with symmetric scale:")
        print("python plot_difference.py file1.nc file2.nc BPGX --mode snapshots \\")
        print("    --vmin -0.0001 --vmax 0.0001 --colormap RdBu_r")
        print("\n# Only show difference (no individual plots):")
        print("python plot_difference.py file1.nc file2.nc MLD --no-individual")
    else:
        main()
