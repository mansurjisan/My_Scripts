#!/usr/bin/env python3
"""
Enhanced STOFS-2D Maxele Difference Plotting Script
Creates publication-quality tricontourf visualizations with:
- Custom Blue→White→Yellow/Orange/Red colormap
- 300 DPI output
- Full-length colorbar
- No contour lines
- GSHHS coastline overlay
- Light blue ocean background
"""

import matplotlib
matplotlib.use('Agg')

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from netCDF4 import Dataset
import warnings
import argparse
import sys
import os

warnings.filterwarnings('ignore')

# Try to import geopandas for coastlines
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    print("Warning: geopandas not available. Coastlines will not be drawn.")


def extract_regional_mesh(x, y, data, elements, lon_min, lon_max, lat_min, lat_max, buffer=0.1):
    """
    Extract mesh subset for a specific region with remapped indices.
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
    data_reg = data[regional_indices]

    return x_reg, y_reg, elements_reg, data_reg


def create_enhanced_plot(noanomaly_file, anomaly_file, output_file,
                         lon_min, lon_max, lat_min, lat_max,
                         location_name, forecast_time,
                         vmin=-0.3, vmax=0.3):
    """
    Create an enhanced tricontourf plot with the approved styling.
    """
    # Load data
    nc1 = Dataset(noanomaly_file, 'r')
    nc2 = Dataset(anomaly_file, 'r')

    x = nc1.variables['x'][:]
    y = nc1.variables['y'][:]
    data1 = nc1.variables['zeta_max'][:]
    data2 = nc2.variables['zeta_max'][:]
    elements = nc1.variables['element'][:] - 1  # 0-based

    # Handle masked arrays
    if hasattr(data1, 'mask'):
        data1 = np.where(data1.mask, np.nan, data1.data)
    if hasattr(data2, 'mask'):
        data2 = np.where(data2.mask, np.nan, data2.data)

    # Calculate difference
    diff = data2 - data1

    nc1.close()
    nc2.close()

    # Extract regional mesh
    x_reg, y_reg, elements_reg, data_reg = extract_regional_mesh(
        x, y, diff, elements, lon_min, lon_max, lat_min, lat_max
    )

    if x_reg is None:
        print(f"  Warning: No triangles in region for {location_name}!")
        return False

    print(f"  Regional mesh: {len(x_reg)} nodes, {len(elements_reg)} triangles")

    # Create triangulation
    triang = tri.Triangulation(x_reg, y_reg, triangles=elements_reg)

    # Mask bad values
    mask_nan = np.isnan(data_reg)
    outlier_threshold = 1.5
    mask_outlier = np.abs(data_reg) > outlier_threshold
    mask_bad = mask_nan | mask_outlier
    tri_has_bad = mask_bad[triang.triangles].any(axis=1)

    # For global/large domains, also mask triangles that are too large
    # This prevents banding artifacts from sparse deep ocean mesh
    region_width = lon_max - lon_min
    region_height = lat_max - lat_min

    if region_width > 50 or region_height > 50:  # Large domain threshold
        # Calculate triangle edge lengths
        triangles = triang.triangles
        x_tri = x_reg[triangles]
        y_tri = y_reg[triangles]

        # Calculate max edge length for each triangle
        edge1 = np.sqrt((x_tri[:, 1] - x_tri[:, 0])**2 + (y_tri[:, 1] - y_tri[:, 0])**2)
        edge2 = np.sqrt((x_tri[:, 2] - x_tri[:, 1])**2 + (y_tri[:, 2] - y_tri[:, 1])**2)
        edge3 = np.sqrt((x_tri[:, 0] - x_tri[:, 2])**2 + (y_tri[:, 0] - y_tri[:, 2])**2)
        max_edge = np.maximum(np.maximum(edge1, edge2), edge3)

        # Mask triangles with edges longer than threshold (degrees)
        # Use adaptive threshold based on region size
        edge_threshold = min(5.0, region_width / 30)  # Max 5 degrees or 1/30th of domain
        tri_too_large = max_edge > edge_threshold

        # Also check for triangles crossing or near the date line (large longitude span)
        lon_span = np.max(x_tri, axis=1) - np.min(x_tri, axis=1)
        tri_crosses_dateline = lon_span > 180  # Triangle spans more than half the globe

        # Additional check: mask triangles near the date line that might cause artifacts
        # If any vertex is near ±180° and the triangle has significant longitude span
        tri_min_lon = np.min(x_tri, axis=1)
        tri_max_lon = np.max(x_tri, axis=1)
        near_east_dateline = tri_max_lon > 170  # Near +180
        near_west_dateline = tri_min_lon < -170  # Near -180
        has_dateline_vertices = near_east_dateline | near_west_dateline
        significant_span = lon_span > 20  # More than 20 degrees span
        tri_dateline_artifact = has_dateline_vertices & significant_span

        tri_has_bad = tri_has_bad | tri_too_large | tri_crosses_dateline | tri_dateline_artifact
        print(f"  Masked {np.sum(tri_too_large)} large triangles, {np.sum(tri_crosses_dateline)} date-line crossings, {np.sum(tri_dateline_artifact)} dateline artifacts")

    triang.set_mask(tri_has_bad)
    data_clean = np.where(mask_bad, 0, data_reg)

    # ============ ENHANCED VISUALIZATION ============

    fig, ax = plt.subplots(figsize=(12, 14), dpi=300)

    # Set ocean background color
    ax.set_facecolor('#E6F3F7')

    # Custom colormap: Blue (negative) -> White (zero) -> Yellow/Orange/Red (positive)
    colors_neg = plt.cm.Blues_r(np.linspace(0.2, 0.9, 128))
    colors_pos = plt.cm.YlOrRd(np.linspace(0.1, 0.9, 128))
    colors = np.vstack([colors_neg, colors_pos])
    cmap = LinearSegmentedColormap.from_list('custom_diverging', colors)

    # Use TwoSlopeNorm for zero-centered normalization
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

    # 61 contour levels for smooth appearance
    levels = np.linspace(vmin, vmax, 61)

    # Plot tricontourf (no contour lines)
    im = ax.tricontourf(triang, data_clean, levels=levels, cmap=cmap, norm=norm, extend='both')

    # Add GSHHS coastline
    if GEOPANDAS_AVAILABLE:
        try:
            gshhs_path = "/mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL/GSHHS_shp/f/GSHHS_f_L1.shp"
            coastline = gpd.read_file(gshhs_path, bbox=(lon_min-0.5, lat_min-0.5, lon_max+0.5, lat_max+0.5))
            coastline.plot(ax=ax, facecolor='#D4D4D4', edgecolor='#404040', linewidth=0.8, zorder=5)
        except Exception as e:
            print(f"  Coastline warning: {e}")

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    # Colorbar - 50% of figure height for better fit across different aspect ratios
    cbar = fig.colorbar(im, ax=ax, orientation='vertical', shrink=0.5, pad=0.02, aspect=20)
    cbar.set_label('Difference (m)', fontsize=12, fontweight='bold')
    cbar.ax.tick_params(labelsize=10)
    # Use clean tick values based on the scale
    if abs(vmax) == 0.5:
        cbar.set_ticks([-0.5, -0.4, -0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5])
    else:
        cbar.set_ticks([vmin, -0.2, -0.1, 0, 0.1, 0.2, vmax])

    # Title - original style
    ax.set_title(f'Difference in Maximum Water Elevation ({location_name}):\nBias-Corrected vs Non-Bias-Corrected',
                 fontsize=14, fontweight='bold', pad=10)
    ax.set_xlabel('Longitude (degrees)', fontsize=12)
    ax.set_ylabel('Latitude (degrees)', fontsize=12)
    ax.tick_params(axis='both', labelsize=10)

    # Forecast time label
    ax.text(0.02, 0.98, f'Forecast: {forecast_time}',
            transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.9),
            zorder=20)

    ax.set_aspect('equal')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    return True


def main():
    parser = argparse.ArgumentParser(description='Generate enhanced STOFS-2D maxele difference plots')
    parser.add_argument('noanomaly_file', help='Path to non-bias-corrected NetCDF file')
    parser.add_argument('anomaly_file', help='Path to bias-corrected NetCDF file')
    parser.add_argument('--output', '-o', required=True, help='Output PNG file path')
    parser.add_argument('--lon-range', nargs=2, type=float, required=True, help='Longitude range (min max)')
    parser.add_argument('--lat-range', nargs=2, type=float, required=True, help='Latitude range (min max)')
    parser.add_argument('--location-name', required=True, help='Location name for title')
    parser.add_argument('--forecast-time', required=True, help='Forecast time string')
    parser.add_argument('--vmin', type=float, default=-0.3, help='Color scale minimum')
    parser.add_argument('--vmax', type=float, default=0.3, help='Color scale maximum')

    args = parser.parse_args()

    # Check input files exist
    if not os.path.exists(args.noanomaly_file):
        print(f"Error: File not found: {args.noanomaly_file}")
        sys.exit(1)
    if not os.path.exists(args.anomaly_file):
        print(f"Error: File not found: {args.anomaly_file}")
        sys.exit(1)

    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Generating: {args.location_name}")

    success = create_enhanced_plot(
        args.noanomaly_file,
        args.anomaly_file,
        args.output,
        args.lon_range[0], args.lon_range[1],
        args.lat_range[0], args.lat_range[1],
        args.location_name,
        args.forecast_time,
        args.vmin,
        args.vmax
    )

    if success:
        print(f"  Plot saved: {args.output}")
    else:
        print(f"  Failed to generate plot")
        sys.exit(1)


if __name__ == '__main__':
    main()
