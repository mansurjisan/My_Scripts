#!/usr/bin/env python3
"""
Fixed script to plot fort.11.nc with proper color-levels support
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from netCDF4 import Dataset
import argparse
import sys
import os
from datetime import datetime

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

def plot_snapshot(nc, var_name, time_index, x, y, output_file,
                 region='north_atlantic', lon_range=None, lat_range=None,
                 max_points=100000, colormap='viridis', point_size=0.5,
                 dpi=150, use_triangulation=False, vmin=None, vmax=None,
                 color_levels=None, symmetric=False, figsize=(15, 10)):
    """Create and save a single snapshot"""
    
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
    
    # Get variable data
    var_data = nc.variables[var_name]
    
    if time_index >= var_data.shape[0]:
        print(f"Error: Time index {time_index} out of range.")
        return False
    
    data = var_data[time_index, :]
    time_str = nc.variables['time'][time_index].tobytes().decode('utf-8').strip()
    
    # Handle fill values
    if hasattr(var_data, '_FillValue'):
        data = np.ma.masked_equal(data, var_data._FillValue)
    
    # Filter for region
    if region != 'global':
        region_mask = ((x >= lon_min) & (x <= lon_max) & 
                      (y >= lat_min) & (y <= lat_max))
        x_region = x[region_mask]
        y_region = y[region_mask]
        data_region = data[region_mask]
    else:
        x_region = x
        y_region = y
        data_region = data
    
    # Subsample if needed
    if max_points > 0 and len(x_region) > max_points:
        step = max(1, len(x_region) // max_points)
        indices = np.arange(0, len(x_region), step)
        x_region = x_region[indices]
        y_region = y_region[indices]
        data_region = data_region[indices]
    
    print(f"  Using {len(x_region)} points")
    
    # Calculate color range
    data_min, data_max = np.nanmin(data_region), np.nanmax(data_region)
    
    if vmin is not None or vmax is not None:
        plot_vmin = vmin if vmin is not None else data_min
        plot_vmax = vmax if vmax is not None else data_max
    elif symmetric:
        abs_max = max(abs(data_min), abs(data_max))
        plot_vmin, plot_vmax = -abs_max, abs_max
    else:
        plot_vmin, plot_vmax = data_min, data_max
    
    print(f"  Data range: {data_min:.6f} to {data_max:.6f}")
    print(f"  Color range: {plot_vmin:.6f} to {plot_vmax:.6f}")
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Handle discrete color levels
    if color_levels is not None:
        from matplotlib.colors import BoundaryNorm
        levels = np.linspace(plot_vmin, plot_vmax, color_levels + 1)
        norm = BoundaryNorm(levels, ncolors=256, clip=True)
        print(f"  Using {color_levels} discrete color levels")
    else:
        norm = None
    
    # Plot data
    if use_triangulation and len(x_region) < 50000:
        triang = tri.Triangulation(x_region, y_region)
        if norm is not None:
            im = ax.tripcolor(triang, data_region, shading='gouraud', 
                             cmap=colormap, alpha=0.9, norm=norm)
        else:
            im = ax.tripcolor(triang, data_region, shading='gouraud', 
                             cmap=colormap, alpha=0.9, vmin=plot_vmin, vmax=plot_vmax)
    else:
        if norm is not None:
            im = ax.scatter(x_region, y_region, c=data_region, 
                           cmap=colormap, s=point_size, alpha=0.8,
                           edgecolors='none', rasterized=True, norm=norm)
        else:
            im = ax.scatter(x_region, y_region, c=data_region, 
                           cmap=colormap, s=point_size, alpha=0.8,
                           edgecolors='none', rasterized=True,
                           vmin=plot_vmin, vmax=plot_vmax)
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.ax.tick_params(labelsize=10)
    
    # Labels
    long_name = getattr(var_data, 'long_name', var_name)
    units = getattr(var_data, 'units', '')
    
    ax.set_xlabel('Longitude (degrees)', fontsize=12)
    ax.set_ylabel('Latitude (degrees)', fontsize=12)
    region_title = f" - {region.replace('_', ' ').title()}" if region != 'global' else ""
    ax.set_title(f'{long_name}{region_title}\nTime: {time_str}', fontsize=14, pad=20)
    cbar.set_label(f'{long_name} ({units})', fontsize=11)
    
    # Set limits and styling
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2, linewidth=0.5)
    
    # Add reference lines for North Atlantic
    if region == 'north_atlantic':
        ax.axhline(y=0, color='white', linestyle='-', alpha=0.6, linewidth=1)
        ax.axvline(x=0, color='white', linestyle='-', alpha=0.6, linewidth=1)
    
    plt.tight_layout()
    fig.patch.set_facecolor('white')
    
    # Save plot
    fig.savefig(output_file, dpi=300, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    plt.close(fig)
    
    print(f"  Saved: {output_file}")
    return True

def generate_snapshots(filename, variable=None, output_dir='snapshots',
                      time_start=None, time_end=None, time_step=1, **kwargs):
    """Generate snapshots for multiple time steps"""
    
    # Load data
    nc = load_netcdf_data(filename)
    
    # Get variable
    if variable is None:
        available_vars = get_available_variables(nc)
        if not available_vars:
            print("No time-varying variables found!")
            nc.close()
            return
        variable = available_vars[0]
        print(f"Using first available variable: {variable}")
    
    # Check variable exists
    if variable not in nc.variables:
        print(f"Variable {variable} not found!")
        available_vars = get_available_variables(nc)
        print(f"Available variables: {available_vars}")
        nc.close()
        return
    
    # Get coordinates once
    print("Loading coordinates...")
    x = nc.variables['x'][:]
    y = nc.variables['y'][:]
    
    # Get time info
    var_data = nc.variables[variable]
    n_times = var_data.shape[0]
    
    # Set time range
    if time_start is None:
        time_start = 0
    if time_end is None:
        time_end = n_times
    else:
        time_end = min(time_end, n_times)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate info file
    info_file = os.path.join(output_dir, 'snapshot_info.txt')
    with open(info_file, 'w') as f:
        f.write(f"Snapshot Generation Information\n")
        f.write(f"="*50 + "\n")
        f.write(f"Source file: {filename}\n")
        f.write(f"Variable: {variable}\n")
        f.write(f"Time range: {time_start} to {time_end-1} (step {time_step})\n")
        f.write(f"Total snapshots: {len(range(time_start, time_end, time_step))}\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"="*50 + "\n\n")
    
    # Process each time step
    snapshots_generated = 0
    print(f"\nGenerating snapshots for {variable}...")
    print(f"Time range: {time_start} to {time_end-1} (step {time_step})")
    
    for t_idx in range(time_start, time_end, time_step):
        print(f"\nProcessing time step {t_idx}/{n_times-1}...")
        
        output_file = os.path.join(output_dir, f"{variable}_t{t_idx:04d}.png")
        
        if plot_snapshot(nc, variable, t_idx, x, y, output_file, **kwargs):
            snapshots_generated += 1
            
            # Update info file
            time_str = nc.variables['time'][t_idx].tobytes().decode('utf-8').strip()
            with open(info_file, 'a') as f:
                f.write(f"Time {t_idx}: {time_str} -> {os.path.basename(output_file)}\n")
    
    print(f"\n{'='*50}")
    print(f"Snapshot generation complete!")
    print(f"Generated {snapshots_generated} snapshots in {output_dir}/")
    print(f"Info file: {info_file}")
    
    nc.close()

def main():
    parser = argparse.ArgumentParser(
        description='Fort.11/bcforcing NetCDF plotter with snapshot generation')
    
    # Main arguments
    parser.add_argument('filename', help='NetCDF filename')
    parser.add_argument('variable', nargs='?', help='Variable name to plot')
    
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
    parser.add_argument('--output-dir', default='snapshots',
                       help='Directory for snapshot output')
    parser.add_argument('--save', type=str, help='Save single plot to file')
    
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
    parser.add_argument('--colormap', default='viridis',
                       help='Matplotlib colormap')
    parser.add_argument('--point-size', type=float, default=0.5,
                       help='Size of scatter points')
    parser.add_argument('--dpi', type=int, default=150,
                       help='Plot resolution DPI')
    parser.add_argument('--triangulation', action='store_true',
                       help='Use triangulated surface')
    parser.add_argument('--vmin', type=float,
                       help='Minimum value for color scale')
    parser.add_argument('--vmax', type=float,
                       help='Maximum value for color scale')
    parser.add_argument('--color-levels', type=int,
                       help='Number of discrete color levels')
    parser.add_argument('--symmetric', action='store_true',
                       help='Make color scale symmetric around zero')
    
    # Utility options
    parser.add_argument('-l', '--list', action='store_true',
                       help='List available variables')
    
    args = parser.parse_args()
    
    # Load NetCDF file
    nc = load_netcdf_data(args.filename)
    
    # List variables if requested
    if args.list:
        available_vars = get_available_variables(nc)
        print("\nAvailable time-varying variables:")
        print("="*50)
        for var in available_vars:
            var_obj = nc.variables[var]
            long_name = getattr(var_obj, 'long_name', 'No description')
            units = getattr(var_obj, 'units', 'No units')
            shape = var_obj.shape
            print(f"\n{var}:")
            print(f"  Description: {long_name}")
            print(f"  Units: {units}")
            print(f"  Shape: {shape} (time_steps={shape[0]}, nodes={shape[1]})")
        nc.close()
        return
    
    # Check if variable provided
    if not args.variable:
        available_vars = get_available_variables(nc)
        print("Please specify a variable to plot.")
        print(f"Available variables: {available_vars}")
        nc.close()
        return
    
    nc.close()
    
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
        'symmetric': args.symmetric
    }
    
    # Execute based on mode
    if args.mode == 'snapshots':
        print(f"\n{'='*50}")
        print("SNAPSHOT GENERATION MODE")
        print(f"{'='*50}")
        generate_snapshots(
            args.filename, args.variable, args.output_dir,
            args.time_start, args.time_end, args.time_step,
            **plot_kwargs
        )
    else:  # Single plot mode
        print(f"\n{'='*50}")
        print("SINGLE PLOT MODE")
        print(f"{'='*50}")
        
        nc = load_netcdf_data(args.filename)
        x = nc.variables['x'][:]
        y = nc.variables['y'][:]
        
        output_file = args.save if args.save else 'temp_plot.png'
        plot_snapshot(nc, args.variable, args.time, x, y, output_file, **plot_kwargs)
        
        if not args.save:
            # Display the plot if not saving
            from PIL import Image
            img = Image.open(output_file)
            plt.figure(figsize=(15, 10))
            plt.imshow(img)
            plt.axis('off')
            plt.show()
            os.remove(output_file)
        else:
            print(f"Plot saved to {args.save}")
        
        nc.close()

if __name__ == "__main__":
    main()
