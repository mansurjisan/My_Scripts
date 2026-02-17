#!/usr/bin/env python3
"""
STOFS-2D Water Elevation Difference Animation Script (Parallel Version)
Creates animated visualization of water elevation differences over time.
Uses enhanced plotting style with:
- Custom Blue→White→Yellow/Orange/Red colormap
- 300 DPI output
- GSHHS coastline overlay
- Light blue ocean background
- Parallel frame generation for faster processing
"""

import matplotlib
matplotlib.use('Agg')

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from netCDF4 import Dataset, num2date
import warnings
import argparse
import sys
import os
from datetime import datetime
from multiprocessing import Pool, cpu_count
from functools import partial

warnings.filterwarnings('ignore')

# Try to import geopandas for coastlines
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    print("Warning: geopandas not available. Coastlines will not be drawn.")


def extract_regional_mesh(x, y, elements, lon_min, lon_max, lat_min, lat_max, buffer=0.1):
    """
    Extract mesh subset for a specific region with remapped indices.
    Returns the mask and mapping for reuse across time steps.
    """
    node_mask = ((x >= lon_min - buffer) & (x <= lon_max + buffer) &
                 (y >= lat_min - buffer) & (y <= lat_max + buffer))
    regional_indices = np.where(node_mask)[0]
    index_set = set(regional_indices)

    # Create index mapping
    index_map = {old_idx: new_idx for new_idx, old_idx in enumerate(regional_indices)}

    # Filter elements
    valid_triangles = []
    for elem in elements:
        if elem[0] in index_set and elem[1] in index_set and elem[2] in index_set:
            new_tri = [index_map[elem[0]], index_map[elem[1]], index_map[elem[2]]]
            valid_triangles.append(new_tri)

    if len(valid_triangles) == 0:
        return None, None, None, None

    elements_reg = np.array(valid_triangles)
    x_reg = x[regional_indices]
    y_reg = y[regional_indices]

    return x_reg, y_reg, elements_reg, regional_indices


def generate_single_frame(args):
    """
    Generate a single frame - designed to be called in parallel.
    """
    (frame_idx, t_idx, diff_reg, x_reg, y_reg, elements_reg,
     time_str, n_times, vmin, vmax, lon_min, lon_max, lat_min, lat_max,
     location_name, frames_dir, coastline_path) = args

    # Create triangulation for this process
    triang = tri.Triangulation(x_reg, y_reg, triangles=elements_reg)

    # Setup colormap
    colors_neg = plt.cm.Blues_r(np.linspace(0.2, 0.9, 128))
    colors_pos = plt.cm.YlOrRd(np.linspace(0.1, 0.9, 128))
    colors = np.vstack([colors_neg, colors_pos])
    cmap = LinearSegmentedColormap.from_list('custom_diverging', colors)
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

    # Load coastline for this process
    coastline_gdf = None
    if GEOPANDAS_AVAILABLE and coastline_path:
        try:
            coastline_gdf = gpd.read_file(coastline_path, bbox=(lon_min-0.5, lat_min-0.5, lon_max+0.5, lat_max+0.5))
        except:
            pass

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 14), dpi=300)
    ax.set_facecolor('#E6F3F7')

    # Mask bad values
    mask_nan = np.isnan(diff_reg)
    mask_outlier = np.abs(diff_reg) > 1.5
    mask_bad = mask_nan | mask_outlier
    tri_has_bad = mask_bad[triang.triangles].any(axis=1)
    triang.set_mask(tri_has_bad)
    data_clean = np.where(mask_bad, 0, diff_reg)

    # Plot
    levels = np.linspace(vmin, vmax, 61)
    im = ax.tricontourf(triang, data_clean, levels=levels, cmap=cmap, norm=norm, extend='both')

    # Add coastline
    if coastline_gdf is not None:
        coastline_gdf.plot(ax=ax, facecolor='#D4D4D4', edgecolor='#404040', linewidth=0.8, zorder=5)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('equal')

    # Determine if nowcast or forecast (first 6 hours = nowcast)
    nowcast_hours = 6
    if t_idx < nowcast_hours:
        period_label = "NOWCAST"
        period_color = "#1E90FF"  # Dodger blue
        hour_in_period = t_idx + 1
        period_text = f"{period_label} (Hour {hour_in_period}/6)"
    else:
        period_label = "FORECAST"
        period_color = "#FF6347"  # Tomato red
        hour_in_period = t_idx - nowcast_hours + 1
        total_forecast_hours = n_times - nowcast_hours
        period_text = f"{period_label} (Hour {hour_in_period}/{total_forecast_hours})"

    ax.set_title(f'Difference in Water Elevation ({location_name}):\nBias-Corrected vs Non-Bias-Corrected\n{time_str}',
                 fontsize=14, fontweight='bold', pad=10)
    ax.set_xlabel('Longitude (degrees)', fontsize=12)
    ax.set_ylabel('Latitude (degrees)', fontsize=12)
    ax.tick_params(axis='both', labelsize=10)

    # Add nowcast/forecast label in top-left corner
    ax.text(0.02, 0.98, period_text,
            transform=ax.transAxes, fontsize=11, fontweight='bold',
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=period_color, edgecolor='black', alpha=0.9),
            color='white', zorder=20)

    # Add colorbar - 35% height, thinner
    cbar = fig.colorbar(im, ax=ax, orientation='vertical', shrink=0.35, pad=0.02, aspect=35)
    cbar.set_label('Difference (m)', fontsize=12, fontweight='bold')
    cbar.ax.tick_params(labelsize=10)
    cbar.set_ticks([vmin, -0.2, -0.1, 0, 0.1, 0.2, vmax])

    # Save frame
    frame_file = os.path.join(frames_dir, f'frame_{frame_idx:04d}.png')
    plt.savefig(frame_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return frame_file


def generate_animation(noanomaly_file, anomaly_file, output_dir,
                       lon_min, lon_max, lat_min, lat_max,
                       location_name, forecast_date,
                       vmin=-0.3, vmax=0.3, fps=4, skip_frames=1, n_workers=None):
    """
    Generate animation frames in parallel and create GIF/MP4.
    """
    print(f"Loading data files...")

    # Load data
    nc1 = Dataset(noanomaly_file, 'r')
    nc2 = Dataset(anomaly_file, 'r')

    x = nc1.variables['x'][:]
    y = nc1.variables['y'][:]
    elements = nc1.variables['element'][:] - 1  # 0-based

    # Get time info
    time_var = nc1.variables['time']
    times = time_var[:]
    try:
        time_units = time_var.units
        time_dates = num2date(times, time_units)
    except:
        # Fallback if time conversion fails
        time_dates = [f"Step {i}" for i in range(len(times))]

    n_times = len(times)
    print(f"Found {n_times} time steps")

    # Extract regional mesh once (coordinates don't change)
    print(f"Extracting regional mesh for {location_name}...")
    x_reg, y_reg, elements_reg, regional_indices = extract_regional_mesh(
        x, y, elements, lon_min, lon_max, lat_min, lat_max
    )

    if x_reg is None:
        print(f"Error: No triangles in region for {location_name}!")
        nc1.close()
        nc2.close()
        return False

    print(f"Regional mesh: {len(x_reg)} nodes, {len(elements_reg)} triangles")

    # Create frames directory
    frames_dir = os.path.join(output_dir, 'frames')
    os.makedirs(frames_dir, exist_ok=True)

    # Coastline path
    coastline_path = None
    if GEOPANDAS_AVAILABLE:
        coastline_path = "/mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL/GSHHS_shp/f/GSHHS_f_L1.shp"
        if os.path.exists(coastline_path):
            print("Coastline file found")
        else:
            coastline_path = None

    # Prepare all frame data
    print(f"Pre-loading all time step data...")
    frame_args = []
    frame_idx = 0

    time_indices = list(range(0, n_times, skip_frames))
    total_frames = len(time_indices)

    for t_idx in time_indices:
        # Read zeta for this time step
        zeta1 = nc1.variables['zeta'][t_idx, :]
        zeta2 = nc2.variables['zeta'][t_idx, :]

        # Handle masked arrays
        if hasattr(zeta1, 'mask'):
            zeta1 = np.where(zeta1.mask, np.nan, zeta1.data)
        if hasattr(zeta2, 'mask'):
            zeta2 = np.where(zeta2.mask, np.nan, zeta2.data)

        # Calculate difference (bias-corrected - non-bias-corrected)
        diff = zeta2 - zeta1

        # Extract regional data
        diff_reg = diff[regional_indices]

        # Get time string
        try:
            time_str = time_dates[t_idx].strftime('%Y-%m-%d %H:%M UTC')
        except:
            time_str = str(time_dates[t_idx])

        frame_args.append((
            frame_idx, t_idx, diff_reg, x_reg, y_reg, elements_reg,
            time_str, n_times, vmin, vmax, lon_min, lon_max, lat_min, lat_max,
            location_name, frames_dir, coastline_path
        ))
        frame_idx += 1

    nc1.close()
    nc2.close()

    print(f"Data loaded for {total_frames} frames")

    # Determine number of workers
    if n_workers is None:
        n_workers = min(cpu_count(), 8)  # Cap at 8 workers
    print(f"Generating frames using {n_workers} parallel workers...")

    # Generate frames in parallel
    frame_files = []
    with Pool(processes=n_workers) as pool:
        # Use imap for progress tracking
        for i, frame_file in enumerate(pool.imap(generate_single_frame, frame_args)):
            frame_files.append(frame_file)
            if (i + 1) % 10 == 0 or (i + 1) == total_frames:
                print(f"  Generated frame {i + 1}/{total_frames}")

    # Sort frame files to ensure correct order
    frame_files.sort()

    print(f"Generated {len(frame_files)} frames")

    # Create animation using imageio
    try:
        import imageio

        # Create GIF
        gif_file = os.path.join(output_dir, f'{location_name.lower().replace(" ", "_")}_cwl_diff_animation.gif')
        print(f"Creating GIF: {gif_file}")

        images = []
        for frame_file in frame_files:
            images.append(imageio.imread(frame_file))

        imageio.mimsave(gif_file, images, fps=fps, loop=0)
        print(f"GIF saved: {gif_file}")

        # Also try to create MP4 if ffmpeg is available
        try:
            mp4_file = os.path.join(output_dir, f'{location_name.lower().replace(" ", "_")}_cwl_diff_animation.mp4')
            imageio.mimsave(mp4_file, images, fps=fps)
            print(f"MP4 saved: {mp4_file}")
        except Exception as e:
            print(f"Could not create MP4: {e}")

    except ImportError:
        print("imageio not available, trying ffmpeg directly...")

        # Try ffmpeg
        import subprocess
        gif_file = os.path.join(output_dir, f'{location_name.lower().replace(" ", "_")}_cwl_diff_animation.gif')
        mp4_file = os.path.join(output_dir, f'{location_name.lower().replace(" ", "_")}_cwl_diff_animation.mp4')

        try:
            # Create MP4
            subprocess.run([
                'ffmpeg', '-y', '-framerate', str(fps),
                '-i', os.path.join(frames_dir, 'frame_%04d.png'),
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                mp4_file
            ], check=True)
            print(f"MP4 saved: {mp4_file}")
        except Exception as e:
            print(f"ffmpeg not available or failed: {e}")

    return True


def main():
    parser = argparse.ArgumentParser(description='Generate STOFS-2D water elevation difference animation (parallel)')
    parser.add_argument('noanomaly_file', help='Path to non-bias-corrected NetCDF file')
    parser.add_argument('anomaly_file', help='Path to bias-corrected NetCDF file')
    parser.add_argument('--output-dir', '-o', required=True, help='Output directory for frames and animation')
    parser.add_argument('--lon-range', nargs=2, type=float, default=[-77.5, -75.5], help='Longitude range (min max)')
    parser.add_argument('--lat-range', nargs=2, type=float, default=[36.6, 39.7], help='Latitude range (min max)')
    parser.add_argument('--location-name', default='Chesapeake Bay', help='Location name for title')
    parser.add_argument('--forecast-date', default='2025-11-22', help='Forecast date string')
    parser.add_argument('--vmin', type=float, default=-0.3, help='Color scale minimum')
    parser.add_argument('--vmax', type=float, default=0.3, help='Color scale maximum')
    parser.add_argument('--fps', type=int, default=4, help='Frames per second for animation')
    parser.add_argument('--skip', type=int, default=1, help='Process every Nth time step (1=all, 2=every other, etc.)')
    parser.add_argument('--workers', '-w', type=int, default=None, help='Number of parallel workers (default: auto)')

    args = parser.parse_args()

    # Check input files exist
    if not os.path.exists(args.noanomaly_file):
        print(f"Error: File not found: {args.noanomaly_file}")
        sys.exit(1)
    if not os.path.exists(args.anomaly_file):
        print(f"Error: File not found: {args.anomaly_file}")
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Generating animation for: {args.location_name}")
    print(f"  Region: [{args.lon_range[0]}, {args.lon_range[1]}] x [{args.lat_range[0]}, {args.lat_range[1]}]")

    success = generate_animation(
        args.noanomaly_file,
        args.anomaly_file,
        args.output_dir,
        args.lon_range[0], args.lon_range[1],
        args.lat_range[0], args.lat_range[1],
        args.location_name,
        args.forecast_date,
        args.vmin,
        args.vmax,
        args.fps,
        args.skip,
        args.workers
    )

    if success:
        print("Animation generation complete!")
    else:
        print("Animation generation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
