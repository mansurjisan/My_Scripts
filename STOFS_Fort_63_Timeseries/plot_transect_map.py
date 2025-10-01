#!/usr/bin/env python3
"""
Plot transect points on a map to visualize the sampling points
Shows the transect line and all sampling points between two stations

python plot_transect_map.py     -75.705 35.208 -76.670 34.717     --points 30     --stations "USCG_Hatteras" "Duke_Marine_Lab"     --nc-file fort.63_UND.nc     --show-mesh     --output hatteras_beaufort_map_with_mesh.png

"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import netCDF4 as nc
import argparse

def plot_transect_map(nc_file, start_point, end_point, n_points=20,
                     station_names=None, save_plot='transect_map.png',
                     show_mesh=False, region_buffer=0.5):
    """
    Create a map showing the transect line and sampling points
    
    Parameters:
    -----------
    nc_file : str
        Path to fort.63.nc file (for mesh coordinates)
    start_point : tuple
        (lon, lat) of transect start
    end_point : tuple
        (lon, lat) of transect end
    n_points : int
        Number of sampling points
    station_names : tuple
        Names of start and end stations
    save_plot : str
        Output filename
    show_mesh : bool
        Whether to show mesh nodes in background
    region_buffer : float
        Buffer around transect for map extent (degrees)
    """
    
    # Create transect points
    lon1, lat1 = start_point
    lon2, lat2 = end_point
    
    transect_lons = np.linspace(lon1, lon2, n_points)
    transect_lats = np.linspace(lat1, lat2, n_points)
    
    # Calculate transect distance
    total_distance = np.sqrt((lon2 - lon1)**2 + (lat2 - lat1)**2) * 111.0  # km
    
    # Create figure with two subplots
    fig = plt.figure(figsize=(16, 8))
    
    # Main map
    ax1 = plt.subplot(121)
    
    # If requested, show mesh nodes in background
    if show_mesh and nc_file:
        try:
            ds = nc.Dataset(nc_file, 'r')
            x = ds.variables['x'][:]
            y = ds.variables['y'][:]
            
            # Define region to show
            lon_min = min(lon1, lon2) - region_buffer
            lon_max = max(lon1, lon2) + region_buffer
            lat_min = min(lat1, lat2) - region_buffer
            lat_max = max(lat1, lat2) + region_buffer
            
            # Filter mesh nodes to region
            mask = ((x >= lon_min) & (x <= lon_max) & 
                   (y >= lat_min) & (y <= lat_max))
            
            # Get nodes in region
            indices = np.where(mask)[0]
            print(f"Found {len(indices):,} nodes in region")
            
            # Adaptive subsampling based on node count
            if len(indices) > 100000:
                # For very dense meshes, use density plot instead
                x_region = x[indices]
                y_region = y[indices]
                
                # Create 2D histogram for density
                bins_lon = np.linspace(lon_min, lon_max, 100)
                bins_lat = np.linspace(lat_min, lat_max, 100)
                H, xedges, yedges = np.histogram2d(x_region, y_region, 
                                                   bins=[bins_lon, bins_lat])
                
                # Plot as density map
                im = ax1.imshow(H.T, origin='lower', aspect='equal',
                               extent=[lon_min, lon_max, lat_min, lat_max],
                               cmap='Blues', alpha=0.6, interpolation='gaussian')
                print(f"Showing mesh density (too many points for scatter plot)")
            else:
                # For moderate meshes, subsample and show points
                target_points = 30000
                if len(indices) > target_points:
                    step = len(indices) // target_points
                    indices = indices[::step]
                    print(f"Subsampled to {len(indices):,} nodes for plotting")
                
                # Plot mesh nodes with adaptive size
                if len(indices) > 10000:
                    point_size = 0.3
                elif len(indices) > 5000:
                    point_size = 0.5
                else:
                    point_size = 1.0
                
                ax1.scatter(x[indices], y[indices], c='lightblue', s=point_size, 
                           alpha=0.4, rasterized=True, label=f'Mesh nodes ({len(indices):,} shown)')
            
            ds.close()
        except Exception as e:
            print(f"Could not load mesh nodes: {e}")
    
    # Plot transect line
    ax1.plot([lon1, lon2], [lat1, lat2], 'b-', linewidth=2, 
            label='Transect line', zorder=3)
    
    # Plot sampling points along transect
    for i in range(n_points):
        if i == 0:  # Start point
            ax1.scatter(transect_lons[i], transect_lats[i], c='green', s=200, 
                       marker='^', edgecolor='black', linewidth=2, zorder=5,
                       label='Start station')
        elif i == n_points - 1:  # End point
            ax1.scatter(transect_lons[i], transect_lats[i], c='red', s=200, 
                       marker='v', edgecolor='black', linewidth=2, zorder=5,
                       label='End station')
        else:  # Middle points
            color = plt.cm.viridis(i / n_points)
            ax1.scatter(transect_lons[i], transect_lats[i], c=[color], s=50, 
                       marker='o', edgecolor='black', linewidth=0.5, zorder=4)
    
    # Add station labels
    if station_names:
        ax1.text(lon1, lat1 + 0.05, station_names[0], fontsize=10, 
                ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        ax1.text(lon2, lat2 - 0.05, station_names[1], fontsize=10, 
                ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    # Add distance annotation
    mid_lon = (lon1 + lon2) / 2
    mid_lat = (lat1 + lat2) / 2
    ax1.text(mid_lon, mid_lat + 0.1, f'{total_distance:.1f} km', 
            fontsize=11, ha='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    
    # Set map extent
    if not show_mesh:
        lon_min = min(lon1, lon2) - region_buffer
        lon_max = max(lon1, lon2) + region_buffer
        lat_min = min(lat1, lat2) - region_buffer
        lat_max = max(lat1, lat2) + region_buffer
    
    ax1.set_xlim(lon_min, lon_max)
    ax1.set_ylim(lat_min, lat_max)
    ax1.set_xlabel('Longitude (degrees)', fontsize=11)
    ax1.set_ylabel('Latitude (degrees)', fontsize=11)
    ax1.set_title(f'Transect Map - {n_points} Sampling Points', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_aspect('equal')
    ax1.legend(loc='best', fontsize=9)
    
    
    # Zoomed detail view
    ax2 = plt.subplot(122)
    
    # Show numbered points
    for i in range(n_points):
        color = 'green' if i == 0 else 'red' if i == n_points-1 else 'blue'
        marker = '^' if i == 0 else 'v' if i == n_points-1 else 'o'
        size = 150 if i == 0 or i == n_points-1 else 80
        
        ax2.scatter(transect_lons[i], transect_lats[i], c=color, s=size, 
                   marker=marker, edgecolor='black', linewidth=1, zorder=4)
        
        # Add point numbers
        if i % 3 == 0 or i == 0 or i == n_points-1:  # Label every 3rd point
            offset_x = 0.02 if i % 2 == 0 else -0.02
            offset_y = 0.02 if i % 2 == 0 else -0.02
            ax2.text(transect_lons[i] + offset_x, transect_lats[i] + offset_y, 
                    str(i+1), fontsize=8, ha='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
    
    # Connect points with line
    ax2.plot(transect_lons, transect_lats, 'b-', linewidth=1, alpha=0.5)
    
    # Calculate and show distances between points
    point_spacing = total_distance / (n_points - 1)
    ax2.text(0.5, -0.12, f'Point spacing: {point_spacing:.1f} km', 
            transform=ax2.transAxes, ha='center', fontsize=10)
    
    # Set extent for detail view
    detail_buffer = 0.1
    ax2.set_xlim(min(transect_lons) - detail_buffer, max(transect_lons) + detail_buffer)
    ax2.set_ylim(min(transect_lats) - detail_buffer, max(transect_lats) + detail_buffer)
    ax2.set_xlabel('Longitude (degrees)', fontsize=11)
    ax2.set_ylabel('Latitude (degrees)', fontsize=11)
    ax2.set_title('Transect Point Details', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_aspect('equal')
    
    # Add summary text
    fig.text(0.5, 0.02, 
            f'Transect: ({lon1:.3f}, {lat1:.3f}) to ({lon2:.3f}, {lat2:.3f}) | '
            f'Points: {n_points} | Total Distance: {total_distance:.1f} km | '
            f'Spacing: {point_spacing:.1f} km',
            ha='center', fontsize=10, style='italic')
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.08)
    plt.savefig(save_plot, dpi=150, bbox_inches='tight')
    print(f"Map saved to: {save_plot}")
    
    # Also create a simple version without mesh
    create_simple_map(transect_lons, transect_lats, station_names, 
                     save_plot.replace('.png', '_simple.png'))

def create_simple_map(lons, lats, station_names, save_plot):
    """Create a simplified map showing just the transect"""
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Calculate distances for coloring
    distances_km = []
    for i in range(len(lons)):
        if i == 0:
            distances_km.append(0)
        else:
            dx = lons[i] - lons[0]
            dy = lats[i] - lats[0]
            distances_km.append(np.sqrt(dx**2 + dy**2) * 111.0)
    
    # Create color map based on distance
    colors = plt.cm.plasma(np.array(distances_km) / max(distances_km))
    
    # Plot the transect line first
    ax.plot(lons, lats, 'gray', linewidth=2, alpha=0.5, zorder=1)
    
    # Plot points with color gradient
    scatter = ax.scatter(lons, lats, c=distances_km, s=100, 
                        cmap='plasma', edgecolor='black', linewidth=1,
                        zorder=5, vmin=0, vmax=max(distances_km))
    
    # Highlight start and end with larger markers
    ax.scatter(lons[0], lats[0], s=300, marker='^', 
              facecolor='green', edgecolor='black', linewidth=2, zorder=6)
    ax.scatter(lons[-1], lats[-1], s=300, marker='v', 
              facecolor='red', edgecolor='black', linewidth=2, zorder=6)
    
    # Add labels
    if station_names:
        ax.text(lons[0], lats[0] + 0.05, station_names[0], 
               fontsize=12, ha='center', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        ax.text(lons[-1], lats[-1] - 0.05, station_names[1], 
               fontsize=12, ha='center', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.8))
    
    # Add some intermediate distance labels
    n_labels = min(5, len(lons))
    label_indices = np.linspace(0, len(lons)-1, n_labels, dtype=int)
    for idx in label_indices[1:-1]:  # Skip start and end
        ax.annotate(f'{distances_km[idx]:.0f} km', 
                   xy=(lons[idx], lats[idx]),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=8, alpha=0.7,
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.6))
    
    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax, label='Distance along transect (km)')
    
    # Labels and title
    ax.set_xlabel('Longitude (degrees)', fontsize=12)
    ax.set_ylabel('Latitude (degrees)', fontsize=12)
    ax.set_title(f'Transect Sampling Points ({len(lons)} points)', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')
    
    # Add north arrow (simple)
    ax.annotate('N', xy=(0.95, 0.95), xycoords='axes fraction',
               fontsize=16, fontweight='bold', ha='center',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax.annotate('', xy=(0.95, 0.92), xytext=(0.95, 0.87),
               xycoords='axes fraction', 
               arrowprops=dict(arrowstyle='->', lw=2, color='black'))
    
    plt.tight_layout()
    plt.savefig(save_plot, dpi=150, bbox_inches='tight')
    print(f"map saved to: {save_plot}")

def main():
    parser = argparse.ArgumentParser(
        description='Visualize transect on a map',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic transect map
  python plot_transect_map.py \\
      -75.705 35.208 -76.670 34.717 \\
      --points 30 --output transect_map.png
  
  # With station names and mesh background
  python plot_transect_map.py \\
      -75.705 35.208 -76.670 34.717 \\
      --points 30 --stations "Hatteras" "Beaufort" \\
      --nc-file fort.63.nc --show-mesh \\
      --output hatteras_beaufort_map.png
        """)
    
    parser.add_argument('lon1', type=float, help='Starting longitude')
    parser.add_argument('lat1', type=float, help='Starting latitude')
    parser.add_argument('lon2', type=float, help='Ending longitude')
    parser.add_argument('lat2', type=float, help='Ending latitude')
    
    parser.add_argument('--points', type=int, default=20,
                       help='Number of points along transect')
    parser.add_argument('--stations', type=str, nargs=2,
                       help='Names of start and end stations')
    parser.add_argument('--nc-file', type=str,
                       help='NetCDF file for mesh coordinates (optional)')
    parser.add_argument('--show-mesh', action='store_true',
                       help='Show mesh nodes in background')
    parser.add_argument('--output', type=str, default='transect_map.png',
                       help='Output filename')
    parser.add_argument('--buffer', type=float, default=0.5,
                       help='Map extent buffer in degrees')
    
    args = parser.parse_args()
    
    # Create map
    plot_transect_map(
        nc_file=args.nc_file,
        start_point=(args.lon1, args.lat1),
        end_point=(args.lon2, args.lat2),
        n_points=args.points,
        station_names=tuple(args.stations) if args.stations else None,
        save_plot=args.output,
        show_mesh=args.show_mesh,
        region_buffer=args.buffer
    )

if __name__ == '__main__':
    main()
