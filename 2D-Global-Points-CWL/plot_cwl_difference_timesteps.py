#!/usr/bin/env python3
"""
Script to plot water level (zeta) differences between two NetCDF files for each timestep.
Computes: cwl.nc - noanomaly.nc (bias-corrected minus non-bias-corrected)
Focused on Chesapeake Bay region.

Usage:
    python plot_cwl_difference_timesteps.py

    # Or with custom options:
    python plot_cwl_difference_timesteps.py --time-start 0 --time-end 10 --time-step 2
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from netCDF4 import Dataset, num2date
import argparse
import sys
import os
from datetime import datetime
from matplotlib.colors import BoundaryNorm, TwoSlopeNorm
import warnings
warnings.filterwarnings('ignore')

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    print("Warning: geopandas not available. Coastlines will not be drawn.")

try:
    import imageio.v2 as imageio
    IMAGEIO_AVAILABLE = True
except ImportError:
    try:
        import imageio
        IMAGEIO_AVAILABLE = True
    except ImportError:
        IMAGEIO_AVAILABLE = False
        print("Warning: imageio not available. Animation will not be created.")


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


def get_time_string(nc, time_index):
    """Get formatted time string for a given time index"""
    time_var = nc.variables['time']
    if hasattr(time_var, 'units'):
        time_val = time_var[time_index]
        try:
            time_obj = num2date(time_val, time_var.units)
            return time_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            return f"Time step {time_index}"
    return f"Time step {time_index}"


def compute_difference(nc1, nc2, time_index, x_mask, y_mask, region_mask):
    """Compute difference between two datasets for a specific time step"""

    # Get variable data for specific time
    data1 = nc1.variables['zeta'][time_index, :][region_mask]
    data2 = nc2.variables['zeta'][time_index, :][region_mask]

    # Handle fill values
    var_data1 = nc1.variables['zeta']
    var_data2 = nc2.variables['zeta']

    if hasattr(var_data1, '_FillValue'):
        data1 = np.ma.masked_equal(data1, var_data1._FillValue)
    if hasattr(var_data2, '_FillValue'):
        data2 = np.ma.masked_equal(data2, var_data2._FillValue)

    # Mask very large/small values (dry nodes)
    data1 = np.ma.masked_outside(data1, -100, 100)
    data2 = np.ma.masked_outside(data2, -100, 100)

    # Calculate difference: cwl - noanomaly (bias-corrected - non-bias-corrected)
    diff_data = data2 - data1

    return diff_data, data1, data2


def plot_difference(x_region, y_region, diff_data, time_str, output_file,
                   lon_min, lon_max, lat_min, lat_max,
                   vmin=-0.3, vmax=0.3, colormap='RdBu_r',
                   point_size=1.0, color_levels=20, location_name='Chesapeake Bay'):
    """Create difference plot for a single timestep"""

    # Calculate statistics
    valid_data = diff_data.compressed() if hasattr(diff_data, 'compressed') else diff_data[~np.isnan(diff_data)]
    if len(valid_data) == 0:
        print(f"  Warning: No valid data for this timestep")
        return None, None, None

    diff_min = np.min(valid_data)
    diff_max = np.max(valid_data)
    diff_mean = np.mean(valid_data)
    diff_std = np.std(valid_data)
    diff_rms = np.sqrt(np.mean(valid_data**2))

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10), dpi=150)

    # Create color normalization
    levels = np.linspace(vmin, vmax, color_levels + 1)
    norm = BoundaryNorm(levels, ncolors=256, clip=True)

    # Plot data as scatter
    im = ax.scatter(x_region, y_region, c=diff_data,
                   cmap=colormap, s=point_size, alpha=0.8,
                   edgecolors='none', rasterized=True, norm=norm)

    # Colorbar with nice tick values divisible by 0.05
    cbar = plt.colorbar(im, ax=ax, shrink=0.9, pad=0.02, extend='both')
    cbar.ax.tick_params(labelsize=11)
    cbar.set_label('Water Level Difference (m)', fontsize=12)

    # Set colorbar ticks to nice values divisible by 0.05
    tick_interval = 0.05
    # Round vmin down and vmax up to nearest 0.05
    tick_min = np.floor(vmin / tick_interval) * tick_interval
    tick_max = np.ceil(vmax / tick_interval) * tick_interval
    cbar_ticks = np.arange(tick_min, tick_max + tick_interval/2, tick_interval)
    # Ensure vmin and vmax are included
    cbar_ticks = cbar_ticks[(cbar_ticks >= vmin) & (cbar_ticks <= vmax)]
    # Always include the exact vmin and vmax at ends
    cbar_ticks = np.unique(np.concatenate([[vmin], cbar_ticks, [vmax]]))
    cbar.set_ticks(cbar_ticks)
    cbar.set_ticklabels([f'{t:.2f}' for t in cbar_ticks])

    # Labels
    ax.set_xlabel('Longitude (degrees)', fontsize=12)
    ax.set_ylabel('Latitude (degrees)', fontsize=12)

    # Title
    title = f'Water Level Difference ({location_name})\n'
    title += f'Bias-Corrected minus Non-Bias-Corrected\n'
    title += f'Time: {time_str}'
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)

    # Statistics text box (min and max only)
    stats_text = f'Min: {diff_min:.4f} m\nMax: {diff_max:.4f} m'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
           fontsize=10, verticalalignment='top',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                    edgecolor='gray', linewidth=1, alpha=0.9))

    # Set limits
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linewidth=0.5)

    # Add coastline if available
    if GEOPANDAS_AVAILABLE:
        try:
            from shapely.geometry import box

            # Determine appropriate GSHHS resolution
            lon_range = lon_max - lon_min
            lat_range = lat_max - lat_min
            region_size = max(lon_range, lat_range)

            if region_size < 5:
                gshhs_file = 'GSHHS_shp/f/GSHHS_f_L1.shp'
                linewidth = 0.6
            elif region_size < 20:
                gshhs_file = 'GSHHS_shp/h/GSHHS_h_L1.shp'
                linewidth = 0.7
            else:
                gshhs_file = 'GSHHS_shp/i/GSHHS_i_L1.shp'
                linewidth = 0.8

            if os.path.exists(gshhs_file):
                coastline = gpd.read_file(gshhs_file)
                bbox = box(lon_min, lat_min, lon_max, lat_max)
                try:
                    coastline['geometry'] = coastline.buffer(0)
                    coastline_clipped = coastline.clip(bbox)
                    coastline_clipped.boundary.plot(ax=ax, edgecolor='black',
                                                    linewidth=linewidth, zorder=10)
                except Exception as e:
                    coastline.boundary.plot(ax=ax, edgecolor='black',
                                            linewidth=linewidth, zorder=10)
            elif os.path.exists('ne_10m_land.shp'):
                land = gpd.read_file('ne_10m_land.shp')
                bbox = box(lon_min, lat_min, lon_max, lat_max)
                land_clipped = land.clip(bbox)
                land_clipped.boundary.plot(ax=ax, edgecolor='black',
                                           linewidth=1.0, zorder=10)
        except Exception as e:
            pass  # Skip coastline if error

    plt.tight_layout()

    # Save
    fig.savefig(output_file, dpi=200, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    plt.close(fig)

    return diff_mean, diff_std, diff_rms


def main():
    parser = argparse.ArgumentParser(
        description='Plot water level differences between cwl.nc and noanomaly.nc for each timestep')

    # Input files (with defaults)
    parser.add_argument('--file1', default='stofs_2d_glo.t00z.fields.cwl.noanomaly.nc',
                       help='First NetCDF file (non-bias-corrected)')
    parser.add_argument('--file2', default='stofs_2d_glo.t00z.fields.cwl.nc',
                       help='Second NetCDF file (bias-corrected)')

    # Time selection
    parser.add_argument('--time-start', type=int, default=0,
                       help='Starting time index (default: 0)')
    parser.add_argument('--time-end', type=int, default=None,
                       help='Ending time index (default: all)')
    parser.add_argument('--time-step', type=int, default=1,
                       help='Time step interval (default: 1)')

    # Region options - Chesapeake Bay defaults
    parser.add_argument('--lon-min', type=float, default=-77.5,
                       help='Minimum longitude (default: -77.5 for Chesapeake Bay)')
    parser.add_argument('--lon-max', type=float, default=-75.5,
                       help='Maximum longitude (default: -75.5 for Chesapeake Bay)')
    parser.add_argument('--lat-min', type=float, default=36.5,
                       help='Minimum latitude (default: 36.5 for Chesapeake Bay)')
    parser.add_argument('--lat-max', type=float, default=39.5,
                       help='Maximum latitude (default: 39.5 for Chesapeake Bay)')
    parser.add_argument('--location-name', type=str, default='Chesapeake Bay',
                       help='Location name for plot title')

    # Plot options
    parser.add_argument('--vmin', type=float, default=-0.3,
                       help='Minimum value for color scale (default: -0.3)')
    parser.add_argument('--vmax', type=float, default=0.3,
                       help='Maximum value for color scale (default: 0.3)')
    parser.add_argument('--colormap', default='RdBu_r',
                       help='Matplotlib colormap (default: RdBu_r)')
    parser.add_argument('--point-size', type=float, default=1.0,
                       help='Size of scatter points (default: 1.0)')
    parser.add_argument('--color-levels', type=int, default=20,
                       help='Number of discrete color levels (default: 20)')

    # Output options
    parser.add_argument('--output-dir', default='cwl_difference_plots',
                       help='Output directory for plots (default: cwl_difference_plots)')
    parser.add_argument('--output-prefix', default='cwl_diff',
                       help='Output filename prefix (default: cwl_diff)')

    args = parser.parse_args()

    print("=" * 60)
    print("Water Level Difference Plot Generator")
    print("Comparing: Bias-Corrected vs Non-Bias-Corrected")
    print("=" * 60)

    # Load files
    print(f"\nLoading files...")
    print(f"  File 1 (noanomaly): {args.file1}")
    print(f"  File 2 (cwl): {args.file2}")

    nc1 = load_netcdf_data(args.file1)
    nc2 = load_netcdf_data(args.file2)

    # Get coordinates
    x = nc1.variables['x'][:]
    y = nc1.variables['y'][:]

    # Get time dimension
    n_times = nc1.variables['zeta'].shape[0]
    print(f"\nTotal timesteps: {n_times}")

    # Set time range
    time_start = args.time_start
    time_end = args.time_end if args.time_end is not None else n_times
    time_end = min(time_end, n_times)
    time_step = args.time_step

    print(f"Processing timesteps: {time_start} to {time_end-1} (step {time_step})")

    # Region bounds
    lon_min, lon_max = args.lon_min, args.lon_max
    lat_min, lat_max = args.lat_min, args.lat_max

    print(f"\nRegion: {args.location_name}")
    print(f"  Longitude: {lon_min} to {lon_max}")
    print(f"  Latitude: {lat_min} to {lat_max}")

    # Create region mask (once, since grid is the same for all timesteps)
    print("\nCreating region mask...")
    region_mask = ((x >= lon_min) & (x <= lon_max) &
                  (y >= lat_min) & (y <= lat_max))

    x_region = x[region_mask]
    y_region = y[region_mask]
    n_points = len(x_region)
    print(f"  Points in region: {n_points:,}")

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"\nOutput directory: {args.output_dir}")


    # Process each timestep
    n_processed = 0
    total_steps = len(range(time_start, time_end, time_step))

    print(f"\nGenerating {total_steps} plots...")
    print("-" * 60)

    for t_idx in range(time_start, time_end, time_step):
        n_processed += 1
        time_str = get_time_string(nc1, t_idx)

        print(f"[{n_processed}/{total_steps}] Time step {t_idx}: {time_str}")

        # Compute difference
        diff_data, data1, data2 = compute_difference(
            nc1, nc2, t_idx, x_region, y_region, region_mask
        )

        # Generate output filename
        output_file = os.path.join(args.output_dir, f"{args.output_prefix}_t{t_idx:04d}.png")

        # Create plot
        diff_mean, diff_std, diff_rms = plot_difference(
            x_region, y_region, diff_data, time_str, output_file,
            lon_min, lon_max, lat_min, lat_max,
            vmin=args.vmin, vmax=args.vmax, colormap=args.colormap,
            point_size=args.point_size, color_levels=args.color_levels,
            location_name=args.location_name
        )

        if diff_mean is not None:
            print(f"  Saved: {output_file}")

    # Create animation from all generated plots
    if IMAGEIO_AVAILABLE:
        print("\n" + "-" * 60)
        print("Creating animation...")

        # Get list of all generated PNG files in order
        png_files = sorted([f for f in os.listdir(args.output_dir)
                           if f.startswith(args.output_prefix) and f.endswith('.png')])

        if len(png_files) > 1:
            # Read all images
            images = []
            for png_file in png_files:
                img_path = os.path.join(args.output_dir, png_file)
                images.append(imageio.imread(img_path))

            # Save as MP4
            mp4_file = os.path.join(args.output_dir, f'{args.output_prefix}_animation.mp4')
            fps = 2  # 2 frames per second
            imageio.mimsave(mp4_file, images, fps=fps)
            print(f"  Animation saved: {mp4_file}")
            print(f"  Frames: {len(images)}, FPS: {fps}, Duration: {len(images) / fps:.1f}s")
        else:
            print("  Not enough frames for animation (need at least 2)")

    # Summary
    print("\n" + "=" * 60)
    print(f"Done! All plots saved to: {args.output_dir}/")
    print("=" * 60)

    nc1.close()
    nc2.close()


if __name__ == "__main__":
    main()
