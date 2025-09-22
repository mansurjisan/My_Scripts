#!/usr/bin/env python3
"""
Enhanced script to plot single NetCDF files or differences between two files
Supports wind speed calculation from U/V components

python single-file-netcdf-plotter.py fort.222.nc WIND_SPEED_10m     --mode snapshots     --region custom --lon-range -85 -65 --lat-range 25 45     --colormap jet     --smooth     --color-levels 50     --dpi 300     --vmin 0 --vmax 30     --coastlines     --output-dir wind_snapshots_UND

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
from mpl_toolkits.axes_grid1 import make_axes_locatable
import warnings
warnings.filterwarnings('ignore', message='.*XRandR.*')

def detect_file_type(nc):
    """Detect if file is regular grid or unstructured"""
    dims = nc.dimensions.keys()
    if 'latitude' in dims and 'longitude' in dims:
        return 'regular'
    elif 'grid_xt' in dims and 'grid_yt' in dims:
        return 'regular'  # Alternative regular grid format
    elif 'node' in dims:
        return 'unstructured'
    else:
        raise ValueError("Unknown file type - neither regular grid nor unstructured")

def load_netcdf_data(filename):
    """Load data from NetCDF file"""
    try:
        nc = Dataset(filename, 'r')
        file_type = detect_file_type(nc)
        print(f"Detected file type: {file_type}")
        return nc, file_type
    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading NetCDF file: {e}")
        sys.exit(1)

def get_available_variables(nc, file_type, include_derived=False):
    """Get list of plottable variables"""
    variables = []
    for var_name in nc.variables:
        var = nc.variables[var_name]
        if hasattr(var, 'dimensions'):
            if file_type == 'regular':
                # Check for different dimension naming conventions
                has_time_lat_lon = ('time' in var.dimensions and 
                                   'latitude' in var.dimensions and 
                                   'longitude' in var.dimensions)
                has_record_grid = ('record' in var.dimensions and 
                                 'grid_yt' in var.dimensions and 
                                 'grid_xt' in var.dimensions)
                if has_time_lat_lon or has_record_grid:
                    variables.append(var_name)
            else:  # unstructured
                if 'time' in var.dimensions and 'node' in var.dimensions:
                    variables.append(var_name)
    
    # Add derived variables if requested
    if include_derived and file_type == 'regular':
        # Check for different wind component naming conventions
        wind_pairs = [
            ('UGRD_10maboveground', 'VGRD_10maboveground', 'WIND_SPEED_10m'),
            ('ugrd10m', 'vgrd10m', 'WIND_SPEED_10m'),
            ('UGRD_surface', 'VGRD_surface', 'WIND_SPEED_surface'),
            ('ugrdsfc', 'vgrdsfc', 'WIND_SPEED_surface')
        ]
        
        for u_var, v_var, wind_var in wind_pairs:
            if u_var in nc.variables and v_var in nc.variables:
                if wind_var not in variables:  # Avoid duplicates
                    variables.append(wind_var)
    
    return variables

def calculate_wind_speed(nc, time_index, level='10maboveground'):
    """Calculate wind speed from U and V components"""
    
    # Define possible U/V variable pairs
    wind_pairs = {
        '10maboveground': [('UGRD_10maboveground', 'VGRD_10maboveground'),
                          ('ugrd10m', 'vgrd10m')],
        '10m': [('UGRD_10maboveground', 'VGRD_10maboveground'),
               ('ugrd10m', 'vgrd10m')],
        'surface': [('UGRD_surface', 'VGRD_surface'),
                   ('ugrdsfc', 'vgrdsfc')]
    }
    
    # Find the correct U/V pair
    u_var = None
    v_var = None
    
    if level in wind_pairs:
        for u_name, v_name in wind_pairs[level]:
            if u_name in nc.variables and v_name in nc.variables:
                u_var = u_name
                v_var = v_name
                break
    
    if u_var is None or v_var is None:
        print(f"Debug: Looking for wind components at level {level}")
        print(f"Debug: Available variables: {list(nc.variables.keys())}")
        return None, f"Wind speed at {level}"
    
    # Detect dimension structure
    var_dims = nc.variables[u_var].dimensions
    if 'record' in var_dims:
        # Alternative format with record dimension
        u_data = nc.variables[u_var][time_index, :, :]
        v_data = nc.variables[v_var][time_index, :, :]
    else:
        # Standard format with time dimension
        u_data = nc.variables[u_var][time_index, :, :]
        v_data = nc.variables[v_var][time_index, :, :]
    
    # Handle fill values
    if hasattr(nc.variables[u_var], '_FillValue'):
        u_data = np.ma.masked_equal(u_data, nc.variables[u_var]._FillValue)
    if hasattr(nc.variables[v_var], '_FillValue'):
        v_data = np.ma.masked_equal(v_data, nc.variables[v_var]._FillValue)
    
    # Calculate wind speed
    wind_speed = np.sqrt(u_data**2 + v_data**2)
    
    return wind_speed, f"Wind Speed at {level.replace('_', ' ')}"

#def plot_single_regular(nc, var_name, time_index, output_file=None,
#                       region='global', lon_range=None, lat_range=None,
#                       colormap='viridis', dpi=150, vmin=None, vmax=None,
#                       color_levels=None, figsize=(12, 8), title_suffix='',
#                       smooth=False, add_coastlines=False, add_vectors=False,
#                       vector_spacing=5):
def plot_single_regular(nc, var_name, time_index, output_file=None,
                       region='global', lon_range=None, lat_range=None,
                       colormap='viridis', dpi=150, vmin=None, vmax=None,
                       color_levels=None, figsize=(12, 8), title_suffix='',
                       smooth=False, add_coastlines=False, add_vectors=False,
                       vector_spacing=5, source_filename=None):

    """Plot single variable from regular grid file"""
    
    # Detect coordinate system
    if 'latitude' in nc.variables and 'longitude' in nc.variables:
        # Standard lat/lon coordinates
        lat = nc.variables['latitude'][:]
        lon = nc.variables['longitude'][:]
    elif 'grid_yt' in nc.variables and 'grid_xt' in nc.variables:
        # Alternative grid coordinates
        lat = nc.variables['grid_yt'][:]
        lon = nc.variables['grid_xt'][:]
    else:
        print("Error: Cannot find latitude/longitude coordinates")
        return None
    
    # Check longitude convention (0-360 or -180-180)
    print(f"Longitude range in file: {lon.min():.2f} to {lon.max():.2f}")
    print(f"Latitude range in file: {lat.min():.2f} to {lat.max():.2f}")
    
    # Get data based on variable type
    if var_name.startswith('WIND_SPEED'):
        # Extract level from variable name and map to actual variable suffix
        if 'WIND_SPEED_10m' in var_name:
            level = '10maboveground'
        elif 'WIND_SPEED_surface' in var_name:
            level = 'surface'
        else:
            # Try to extract level from variable name
            level = var_name.replace('WIND_SPEED_', '')
        
        data, long_name = calculate_wind_speed(nc, time_index, level)
        if data is None:
            print(f"Cannot calculate wind speed: required components not found")
            return None
        units = 'm/s'
        var_info = type('obj', (object,), {'long_name': long_name, 'units': units})()
    else:
        var_data = nc.variables[var_name]
        if time_index >= var_data.shape[0]:
            print(f"Error: Time index {time_index} out of range. Maximum: {var_data.shape[0]-1}")
            return None
        
        data = var_data[time_index, :, :]
        var_info = var_data
        
        # Handle fill values
        if hasattr(var_data, '_FillValue'):
            data = np.ma.masked_equal(data, var_data._FillValue)
        
        long_name = getattr(var_info, 'long_name', var_name)
        units = getattr(var_info, 'units', '')
    
    # Convert longitude to -180 to 180 if needed for plotting
    lon_plot = np.where(lon > 180, lon - 360, lon)
    
    # Create meshgrid
    lon_grid, lat_grid = np.meshgrid(lon_plot, lat)
    
    # If longitude was converted, we need to reorder for proper plotting
    if lon_plot[0] > lon_plot[-1]:  # If not monotonic after conversion
        # Find the split point (where it jumps from ~180 to ~-180)
        split_idx = np.where(np.diff(lon_plot) < 0)[0]
        if len(split_idx) > 0:
            split_idx = split_idx[0] + 1
            # Reorder: put negative values first, then positive
            new_order = np.concatenate([np.arange(split_idx, len(lon_plot)), 
                                       np.arange(0, split_idx)])
            lon_plot = lon_plot[new_order]
            data = data[:, new_order]
            lon_grid, lat_grid = np.meshgrid(lon_plot, lat)
    
    # Get time string
    if 'time' in nc.variables:
        time_var = nc.variables['time']
        if hasattr(time_var, 'shape') and len(time_var.shape) == 0:
            # Scalar time variable - need to calculate actual time from record index
            base_time_val = time_var[:]
            if hasattr(time_var, 'units'):
                from netCDF4 import num2date
                # Parse the base time and add hours based on record index
                # The history shows hourly data, so add time_index hours
                actual_time_val = base_time_val + time_index
                time_obj = num2date(actual_time_val, time_var.units)
                time_str = time_obj.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = f"Record {time_index}"
        else:
            # Array time variable
            time_val = time_var[time_index] if len(time_var.shape) > 0 else time_var[:]
            
            if hasattr(time_var, 'units'):
                from netCDF4 import num2date
                time_obj = num2date(time_val, time_var.units)
                time_str = time_obj.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = f"Index {time_index}"
    elif 'record' in nc.dimensions:
        # For files with record dimension but no time variable
        time_str = f"Record {time_index}"
    else:
        time_str = f"Index {time_index}"
    
    # Define regional bounds
    if region == 'north_atlantic':
        lon_min, lon_max = -80, 20
        lat_min, lat_max = 20, 80
    elif region == 'custom' and lon_range and lat_range:
        lon_min, lon_max = lon_range
        lat_min, lat_max = lat_range
        print(f"Custom region requested: lon [{lon_min}, {lon_max}], lat [{lat_min}, {lat_max}]")
    else:
        lon_min = lon_grid.min()
        lon_max = lon_grid.max()
        lat_min = lat_grid.min()
        lat_max = lat_grid.max()
    
    # Calculate statistics
    data_masked = np.ma.masked_invalid(data)
    data_min, data_max = data_masked.min(), data_masked.max()
    data_mean = data_masked.mean()
    data_std = data_masked.std()
    
    print(f"\nStatistics for {var_name}:")
    print(f"  Min: {data_min:.6f}")
    print(f"  Max: {data_max:.6f}")
    print(f"  Mean: {data_mean:.6f}")
    print(f"  Std: {data_std:.6f}")
    
    # Set color range
    if vmin is not None or vmax is not None:
        plot_vmin = vmin if vmin is not None else data_min
        plot_vmax = vmax if vmax is not None else data_max
    else:
        plot_vmin, plot_vmax = data_min, data_max
    
    # Create figure with or without Cartopy projection
    if add_coastlines:
        try:
            import cartopy.crs as ccrs
            import cartopy.feature as cfeature
            
            # Create figure with PlateCarree projection
            fig = plt.figure(figsize=figsize, dpi=dpi)
            ax = plt.axes(projection=ccrs.PlateCarree())
            
            # Add map features with higher resolution
            # Resolution options: '110m' (low), '50m' (medium), '10m' (high)
            if region != 'global' and (lon_max - lon_min) < 30:
                # Use high resolution for zoomed regions
                resolution = '10m'
            elif region != 'global' and (lon_max - lon_min) < 90:
                # Use medium resolution for regional views
                resolution = '50m'
            else:
                # Use low resolution for global views
                resolution = '110m'
            
            ax.add_feature(cfeature.COASTLINE.with_scale(resolution), linewidth=0.5, color='black')
            ax.add_feature(cfeature.LAND.with_scale(resolution), alpha=0.1, facecolor='gray')
            ax.add_feature(cfeature.OCEAN.with_scale(resolution), alpha=0.1, facecolor='lightblue')
            ax.add_feature(cfeature.BORDERS.with_scale(resolution), linewidth=0.3, alpha=0.5)
            
            # Add lakes and rivers for zoomed views
            if resolution in ['10m', '50m']:
                ax.add_feature(cfeature.LAKES.with_scale(resolution), alpha=0.3, facecolor='lightblue', edgecolor='black', linewidth=0.3)
                if resolution == '10m':
                    ax.add_feature(cfeature.RIVERS.with_scale(resolution), alpha=0.3, edgecolor='blue', linewidth=0.5)
            
            # Add US states for US region
            if region == 'custom' and lon_range and lat_range:
                if -130 < np.mean(lon_range) < -60 and 20 < np.mean(lat_range) < 50:
                    ax.add_feature(cfeature.STATES.with_scale('50m'), linewidth=0.2, edgecolor='gray', alpha=0.5)
            
            # Add gridlines with labels but no lines
            gl = ax.gridlines(draw_labels=True, linewidth=0, color='gray', alpha=0, linestyle='')
            gl.top_labels = False
            gl.right_labels = False
            gl.xlabel_style = {'size': 10}
            gl.ylabel_style = {'size': 10}
            
            use_cartopy = True
            
        except ImportError:
            print("Warning: Cartopy not available. Install with 'pip install cartopy' for coastlines.")
            print("Falling back to standard matplotlib plot.")
            fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
            use_cartopy = False
    else:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        use_cartopy = False
    
    # Color normalization
    norm = None
    if color_levels is not None:
        levels = np.linspace(plot_vmin, plot_vmax, color_levels + 1)
        norm = BoundaryNorm(levels, ncolors=256, clip=True)
    
    # Plot data
    if norm is not None:
        im = ax.pcolormesh(lon_grid, lat_grid, data, 
                          cmap=colormap, shading='auto', norm=norm)
    else:
        im = ax.pcolormesh(lon_grid, lat_grid, data, 
                          cmap=colormap, shading='auto',
                          vmin=plot_vmin, vmax=plot_vmax)
    
    # Colorbar with exact limits
    #cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    # Colorbar with proper positioning for Cartopy
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes
    
    # Create an inset axes for the colorbar
    cbar_ax = inset_axes(ax,
                         width="3%",  # width = 3% of parent_bbox width
                         height="100%",  # height = 100% of parent_bbox height
                         loc='center left',
                         bbox_to_anchor=(1.02, 0., 1, 1),
                         bbox_transform=ax.transAxes,
                         borderpad=0,
                         )
    cbar = plt.colorbar(im, cax=cbar_ax)


    
    # Force colorbar to show exact vmin/vmax values
    if vmin is not None or vmax is not None:
        cbar.mappable.set_clim(plot_vmin, plot_vmax)
        # Set explicit tick locations including endpoints
        if color_levels and color_levels > 10:
            # For many levels, show fewer ticks
            tick_locs = np.linspace(plot_vmin, plot_vmax, 7)
        else:
            tick_locs = np.linspace(plot_vmin, plot_vmax, 6)
        cbar.set_ticks(tick_locs)
        cbar.set_ticklabels([f'{v:.1f}' if v % 1 != 0 else f'{int(v)}' for v in tick_locs])
    
    cbar.ax.tick_params(labelsize=9)
    
    # Format colorbar label based on variable
    if 'WIND' in var_name.upper():
        cbar_label = f'Wind Speed ({units})'
    elif 'PRES' in var_name.upper():
        cbar_label = f'Pressure ({units})'
    else:
        cbar_label = f'{long_name} ({units})' if units else long_name
    
    cbar.set_label(cbar_label, fontsize=10)
    
    # Labels and title
    ax.set_xlabel('Longitude (degrees)', fontsize=10)
    ax.set_ylabel('Latitude (degrees)', fontsize=10)
    
    # Format the time string for display
    if 'T' in time_str:  # ISO format
        from datetime import datetime
        dt = datetime.fromisoformat(time_str.replace(' ', 'T'))
        formatted_time = dt.strftime('%H%M UTC %b %d, %Y')
    elif ':' in time_str:  # Already formatted
        try:
            from datetime import datetime
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            formatted_time = dt.strftime('%H%M UTC %b %d, %Y')
        except:
            formatted_time = time_str
    else:
        formatted_time = time_str
    
    # Create title based on variable name
    #if 'WIND_SPEED' in var_name:
    #    main_title = 'Maximum Surface Wind Speed'
    #elif 'PRES' in var_name:
    #    main_title = f'{long_name}'
    #else:
    #    main_title = f'{long_name}'

    # Create title based on variable name and source file
    if 'WIND_SPEED' in var_name:
        # Detect which model based on filename or variable names
        model_label = ''
        if source_filename:
            if 'fort.222' in source_filename:
                model_label = ' (UND)'
            elif 'stofs' in source_filename.lower():
                model_label = ' (NOAA)'
        elif 'UGRD_10maboveground' in nc.variables:
            model_label = ' (UND)'
        elif 'ugrd10m' in nc.variables:
            model_label = ' (NOAA)'
        
        main_title = f'Maximum Surface Wind Speed{model_label}'
    elif 'PRES' in var_name:
        main_title = f'{long_name}'
    else:
        main_title = f'{long_name}'
        
    # Clear default title
    ax.set_title('', pad=20)
    
    # Add date/time in top left corner - bold
    ax.text(0.02, 1.02, formatted_time, transform=ax.transAxes,
            fontsize=11, fontweight='bold', verticalalignment='bottom', horizontalalignment='left')
    
    # Add main title in center - bold
    ax.text(0.5, 1.02, main_title, transform=ax.transAxes,
            fontsize=11, fontweight='bold', verticalalignment='bottom', horizontalalignment='center')
    
    # Add min/max in top right corner - bold
    min_max_text = f'Min | Max  {data_min:.1f} | {data_max:.1f}'
    ax.text(0.98, 1.02, min_max_text, transform=ax.transAxes,
            fontsize=11, fontweight='bold', verticalalignment='bottom', horizontalalignment='right')
    
    # Add wind vectors if requested and if we have U/V components
    if add_vectors:
        # Determine which wind components to use
        u_var = None
        v_var = None
        
        # Check for different naming conventions
        wind_pairs = [
            ('UGRD_10maboveground', 'VGRD_10maboveground'),
            ('ugrd10m', 'vgrd10m'),
            ('UGRD_surface', 'VGRD_surface'),
            ('ugrdsfc', 'vgrdsfc')
        ]
        
        for u_name, v_name in wind_pairs:
            if u_name in nc.variables and v_name in nc.variables:
                u_var = u_name
                v_var = v_name
                break
        
        # If not found, try to find any U/V pair
        if u_var is None:
            for var in nc.variables:
                if var.startswith('UGRD_') or var.startswith('ugrd'):
                    # Try to find matching V component
                    potential_v = var.replace('UGRD', 'VGRD').replace('ugrd', 'vgrd')
                    if potential_v in nc.variables:
                        u_var = var
                        v_var = potential_v
                        break
        
        if u_var and v_var:
            # Get U and V components based on dimension structure
            var_dims = nc.variables[u_var].dimensions
            if 'record' in var_dims:
                u_data = nc.variables[u_var][time_index, :, :]
                v_data = nc.variables[v_var][time_index, :, :]
            else:
                u_data = nc.variables[u_var][time_index, :, :]
                v_data = nc.variables[v_var][time_index, :, :]
            
            # Handle fill values
            if hasattr(nc.variables[u_var], '_FillValue'):
                u_data = np.ma.masked_equal(u_data, nc.variables[u_var]._FillValue)
            if hasattr(nc.variables[v_var], '_FillValue'):
                v_data = np.ma.masked_equal(v_data, nc.variables[v_var]._FillValue)
            
            # Reorder if longitude was converted
            if lon_plot[0] > lon_plot[-1]:
                split_idx = np.where(np.diff(lon_plot) < 0)[0]
                if len(split_idx) > 0:
                    split_idx = split_idx[0] + 1
                    new_order = np.concatenate([np.arange(split_idx, len(lon_plot)), 
                                               np.arange(0, split_idx)])
                    u_data = u_data[:, new_order]
                    v_data = v_data[:, new_order]
            
            # Subsample for vectors (don't plot every point)
            skip = vector_spacing
            lon_vec = lon_plot[::skip]
            lat_vec = lat[::skip]
            u_vec = u_data[::skip, ::skip]
            v_vec = v_data[::skip, ::skip]
            
            # Create meshgrid for vectors
            lon_vec_grid, lat_vec_grid = np.meshgrid(lon_vec, lat_vec)
            
            # Plot vectors with clean arrow style similar to NCL
            if use_cartopy:
                Q = ax.quiver(lon_vec_grid, lat_vec_grid, u_vec, v_vec,
                            transform=ccrs.PlateCarree(),
                            color='black', pivot='middle',
                            width=0.002, scale=300,  # Increased scale to make arrows smaller
                            headwidth=3, headlength=4, headaxislength=3.5,
                            alpha=0.7)
            else:
                Q = ax.quiver(lon_vec_grid, lat_vec_grid, u_vec, v_vec,
                            color='black', pivot='middle',
                            width=0.002, scale=300,  # Increased scale to make arrows smaller
                            headwidth=3, headlength=4, headaxislength=3.5,
                            alpha=0.7)
            
            # Add white background rectangle for the key (smaller size)
            import matplotlib.patches as mpatches
            rect = mpatches.Rectangle(
                (0.91, 0.03),  # position in axes coordinates
                0.08, 0.06,    # smaller width, height
                facecolor='white',
                edgecolor='black',
                linewidth=0.5,
                transform=ax.transAxes,
                zorder=10
            )
            ax.add_patch(rect)
            
            # Add reference arrow with label (5 m/s is more reasonable)
            qk = ax.quiverkey(Q, 0.95, 0.06, 5, '5 m/s',
                            labelpos='N', coordinates='axes',
                            color='black',
                            fontproperties={'size': 8},
                            labelsep=0.03)
            
            print(f"Added wind vectors from {u_var} and {v_var}")
        else:
            print("Warning: Could not find U/V wind components for vectors")
    
    # Set limits and styling
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('auto')
    # ax.grid(True, alpha=0.2, linewidth=0.5)  # Comment out to disable grid
    
    plt.tight_layout()
    
    # Save or show
    if output_file:
        fig.savefig(output_file, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        print(f"\nPlot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()
    
    return data_mean

def plot_single_unstructured(nc, var_name, time_index, output_file=None,
                            region='north_atlantic', lon_range=None, lat_range=None,
                            max_points=100000, colormap='viridis', point_size=0.5, 
                            dpi=150, use_triangulation=False, vmin=None, vmax=None,
                            color_levels=None, figsize=(12, 8), title_suffix=''):
    """Plot single variable from unstructured grid file"""
    
    # Get coordinates
    x = nc.variables['x'][:]
    y = nc.variables['y'][:]
    
    # Get variable data
    var_data = nc.variables[var_name]
    if time_index >= var_data.shape[0]:
        print(f"Error: Time index {time_index} out of range. Maximum: {var_data.shape[0]-1}")
        return None
    
    data = var_data[time_index, :]
    
    # Handle fill values
    if hasattr(var_data, '_FillValue'):
        data = np.ma.masked_equal(data, var_data._FillValue)
    
    # Get time string
    if 'time' in nc.variables and nc.variables['time'].dtype.char == 'S':
        time_str = nc.variables['time'][time_index].tobytes().decode('utf-8').strip()
    else:
        time_var = nc.variables['time']
        time_val = time_var[time_index]
        if hasattr(time_var, 'units'):
            from netCDF4 import num2date
            time_obj = num2date(time_val, time_var.units)
            time_str = time_obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            time_str = f"Index {time_index}"
    
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
    
    print(f"Using {len(x_region)} points for plotting")
    
    # Calculate statistics
    data_min, data_max = np.nanmin(data_region), np.nanmax(data_region)
    data_mean = np.nanmean(data_region)
    data_std = np.nanstd(data_region)
    
    print(f"\nStatistics for {var_name}:")
    print(f"  Min: {data_min:.6f}")
    print(f"  Max: {data_max:.6f}")
    print(f"  Mean: {data_mean:.6f}")
    print(f"  Std: {data_std:.6f}")
    
    # Set color range
    if vmin is not None or vmax is not None:
        plot_vmin = vmin if vmin is not None else data_min
        plot_vmax = vmax if vmax is not None else data_max
    else:
        plot_vmin, plot_vmax = data_min, data_max
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Color normalization
    norm = None
    if color_levels is not None:
        levels = np.linspace(plot_vmin, plot_vmax, color_levels + 1)
        norm = BoundaryNorm(levels, ncolors=256, clip=True)
    
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
    cbar.ax.tick_params(labelsize=9)
    
    # Labels
    long_name = getattr(var_data, 'long_name', var_name)
    units = getattr(var_data, 'units', '')
    
    cbar.set_label(f'{long_name} ({units})', fontsize=10)
    ax.set_xlabel('Longitude (degrees)', fontsize=10)
    ax.set_ylabel('Latitude (degrees)', fontsize=10)
    
    title = f'{long_name}{title_suffix}\nTime: {time_str}'
    ax.set_title(title, fontsize=12)
    
    # Add statistics
    stats_text = (f'Mean: {data_mean:.3f}, Std: {data_std:.3f}\n'
                 f'Min: {data_min:.3f}, Max: {data_max:.3f}')
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
           fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Set limits and styling
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2, linewidth=0.5)
    
    # Add reference lines for North Atlantic
    if region == 'north_atlantic':
        ax.axhline(y=0, color='gray', linestyle='-', alpha=0.3, linewidth=0.5)
        ax.axvline(x=0, color='gray', linestyle='-', alpha=0.3, linewidth=0.5)
    
    plt.tight_layout()
    
    # Save or show
    if output_file:
        fig.savefig(output_file, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        print(f"\nPlot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()
    
    return data_mean

def generate_single_snapshots(file1, variable=None, output_dir='snapshots',
                             time_start=None, time_end=None, time_step=1,
                             **kwargs):
    """Generate snapshots for a single file"""
    
    # Load file
    nc, file_type = load_netcdf_data(file1)
    
    # Get available variables including derived ones
    variables = get_available_variables(nc, file_type, include_derived=True)
    
    # If no variable specified, use the first available variable
    if variable is None:
        if variables:
            variable = variables[0]
            print(f"No variable specified, using: {variable}")
        else:
            print("No plottable variables found")
            nc.close()
            return
    
    # Check variable exists
    if variable not in variables:
        print(f"Variable {variable} not found or cannot be computed")
        print(f"Available variables: {variables}")
        nc.close()
        return
    
    # Get time dimensions (for actual variables, not derived)
    if variable.startswith('WIND_SPEED'):
        # Find the appropriate U component to get time dimensions
        possible_u_vars = [
            'UGRD_10maboveground', 'ugrd10m',
            'UGRD_surface', 'ugrdsfc'
        ]
        
        ref_var = None
        if 'WIND_SPEED_10m' in variable:
            # Try 10m wind variables first
            for var in ['UGRD_10maboveground', 'ugrd10m']:
                if var in nc.variables:
                    ref_var = var
                    break
        elif 'WIND_SPEED_surface' in variable:
            # Try surface wind variables
            for var in ['UGRD_surface', 'ugrdsfc']:
                if var in nc.variables:
                    ref_var = var
                    break
        
        # If still not found, try any U variable
        if ref_var is None:
            for var in possible_u_vars:
                if var in nc.variables:
                    ref_var = var
                    break
        
        if ref_var is None:
            # Last resort: find any variable starting with U or ugrd
            for var in nc.variables:
                if var.startswith('UGRD') or var.startswith('ugrd'):
                    ref_var = var
                    break
        
        if ref_var and ref_var in nc.variables:
            var_dims = nc.variables[ref_var].dimensions
            if 'record' in var_dims:
                n_times = nc.dimensions['record'].size
            else:
                n_times = nc.variables[ref_var].shape[0]
            print(f"Using {ref_var} to determine time dimensions: {n_times} time steps")
        else:
            print(f"Cannot find reference variable for time dimensions")
            print(f"Available variables: {list(nc.variables.keys())}")
            nc.close()
            return
    else:
        if variable in nc.variables:
            var_dims = nc.variables[variable].dimensions
            if 'record' in var_dims:
                n_times = nc.dimensions['record'].size
            else:
                n_times = nc.variables[variable].shape[0]
        else:
            print(f"Variable {variable} not found")
            nc.close()
            return
    
    print(f"File has {n_times} time steps")
    
    # Set time range
    if time_start is None:
        time_start = 0
    if time_end is None:
        time_end = n_times
    else:
        time_end = min(time_end, n_times)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each time step
    print(f"\nGenerating snapshots for {variable}...")
    print(f"Time range: {time_start} to {time_end-1} (step {time_step})")
    
    for t_idx in range(time_start, time_end, time_step):
        print(f"\nProcessing time step {t_idx}/{n_times-1}...")
        
        # Generate output filename
        output_file = os.path.join(output_dir, f"{variable}_t{t_idx:04d}.png")
        
        # Create plot based on file type
        if file_type == 'regular':
            plot_single_regular(nc, variable, t_idx, 
                              output_file=output_file,
                                source_filename=file1,
                                **kwargs)
        else:
            plot_single_unstructured(nc, variable, t_idx,
                                   output_file=output_file, **kwargs)
    
    print(f"\nSnapshot generation complete!")
    print(f"Generated snapshots in {output_dir}/")
    
    nc.close()

def main():
    parser = argparse.ArgumentParser(
        description='Plot single NetCDF file or differences between two files')
    
    # Main arguments - make file2 fully optional
    parser.add_argument('file1', help='NetCDF file to plot')
    parser.add_argument('variable', nargs='?', default=None,
                       help='Variable name to plot (optional)')
    
    # Mode selection
    parser.add_argument('--mode', choices=['single', 'difference', 'snapshots'],
                       default='single', help='Operation mode')
    parser.add_argument('--file2', type=str, default=None,
                       help='Second file for difference mode')
    
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
    parser.add_argument('--no-individual', action='store_true',
                       help='Only show difference plot (for difference mode)')
    
    # Region options
    parser.add_argument('-r', '--region', default='global',
                       choices=['global', 'north_atlantic', 'custom'],
                       help='Region to plot')
    parser.add_argument('--lon-range', type=float, nargs=2,
                       help='Custom longitude range')
    parser.add_argument('--lat-range', type=float, nargs=2,
                       help='Custom latitude range')
    
    # Plot options
    parser.add_argument('--max-points', type=int, default=100000,
                       help='Maximum points to plot for unstructured grids')
    parser.add_argument('--colormap', default='viridis',
                       help='Matplotlib colormap')
    parser.add_argument('--point-size', type=float, default=0.5,
                       help='Size of scatter points (unstructured grids)')
    parser.add_argument('--dpi', type=int, default=150,
                       help='Plot resolution DPI')
    parser.add_argument('--triangulation', action='store_true',
                       help='Use triangulated surface (unstructured grids)')
    parser.add_argument('--vmin', type=float,
                       help='Minimum value for color scale')
    parser.add_argument('--vmax', type=float,
                       help='Maximum value for color scale')
    parser.add_argument('--color-levels', type=int,
                       help='Number of discrete color levels')
    parser.add_argument('--no-symmetric', action='store_true',
                       help='Do not use symmetric color scale (difference mode)')
    parser.add_argument('--smooth', action='store_true',
                       help='Use smoother rendering (contourf) for regular grids')
    parser.add_argument('--coastlines', action='store_true',
                       help='Add coastlines and map features (requires Cartopy)')
    parser.add_argument('--vectors', action='store_true',
                       help='Add wind vectors (arrows) to the plot')
    parser.add_argument('--vector-spacing', type=int, default=5,
                       help='Spacing between vectors (skip every N points, default=5)')
    
    # Utility options
    parser.add_argument('-l', '--list', action='store_true',
                       help='List available variables')
    
    args = parser.parse_args()
    
    # Determine if this is single file or difference mode
    is_difference_mode = (args.file2 is not None) and (args.mode == 'difference')
    
    # Handle single file mode (default)
    if not is_difference_mode:
        nc, file_type = load_netcdf_data(args.file1)
        
        if args.list:
            variables = get_available_variables(nc, file_type, include_derived=True)
            print(f"\nFile type: {file_type}")
            print(f"Available variables in {os.path.basename(args.file1)}:")
            for var in sorted(variables):
                if var.startswith('WIND_SPEED'):
                    print(f"  {var} (derived from U/V components)")
                else:
                    var_obj = nc.variables[var]
                    long_name = getattr(var_obj, 'long_name', 'No description')
                    units = getattr(var_obj, 'units', 'No units')
                    print(f"  {var}: {long_name} ({units})")
            nc.close()
            return
        
        # Prepare kwargs
        plot_kwargs = {
            'region': args.region,
            'lon_range': args.lon_range,
            'lat_range': args.lat_range,
            'colormap': args.colormap,
            'dpi': args.dpi,
            'vmin': args.vmin,
            'vmax': args.vmax,
            'color_levels': args.color_levels,
            'smooth': args.smooth,
            'add_coastlines': args.coastlines,
            'add_vectors': args.vectors,
            'vector_spacing': args.vector_spacing,
        }
        
        if file_type == 'unstructured':
            plot_kwargs.update({
                'max_points': args.max_points,
                'point_size': args.point_size,
                'use_triangulation': args.triangulation,
            })
        
        if args.mode == 'snapshots':
            nc.close()
            generate_single_snapshots(
                args.file1, args.variable, args.output_dir,
                args.time_start, args.time_end, args.time_step,
                **plot_kwargs
            )
        else:  # Single plot
            # Get variable if not specified
            if args.variable is None:
                variables = get_available_variables(nc, file_type, include_derived=True)
                if variables:
                    args.variable = variables[0]
                    print(f"No variable specified, using: {args.variable}")
                else:
                    print("No plottable variables found")
                    nc.close()
                    return
            
            if file_type == 'regular':
                plot_single_regular(nc, args.variable,
                                  args.time, output_file=args.save,
                                    source_filename=args.file1,
                                    **plot_kwargs)
            else:
                plot_single_unstructured(nc, args.variable,
                                       args.time, output_file=args.save, **plot_kwargs)
            nc.close()
    
    else:
        # Difference mode - requires --file2 to be specified
        if args.file2 is None:
            print("Error: Difference mode requires --file2 to be specified")
            sys.exit(1)
        
        print(f"Difference mode between {args.file1} and {args.file2}")
        print("Difference plotting not implemented in this version")
        print("Use the original difference plotting script for comparing two files")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("NetCDF Single File Plotter with Wind Speed Support")
        print("="*50)
        print("\nUSAGE:")
        print("python plot.py <file> [variable] [options]")
        print("\nSINGLE FILE EXAMPLES:")
        print("\n# List variables (including derived like wind speed):")
        print("python plot.py fort.222.nc --list")
        print("\n# Plot wind speed from fort.222.nc:")
        print("python plot.py fort.222.nc WIND_SPEED_10m --time 0 --save wind_speed.png")
        print("\n# Generate wind speed snapshots:")
        print("python plot.py fort.222.nc WIND_SPEED_10m --mode snapshots --output-dir wind_snapshots")
        print("\n# Plot pressure from fort.221.nc:")
        print("python plot.py fort.221.nc PRES_surface --save pressure.png")
        print("\n# Plot any variable from fort.11.nc:")
        print("python plot.py fort.11.nc MLD --time 5 --save mld_plot.png")
        print("\n# High quality plot with custom range:")
        print("python plot.py fort.222.nc WIND_SPEED_10m --vmin 0 --vmax 30 --color-levels 15 --dpi 300")
        print("\nDIFFERENCE MODE:")
        print("\n# To compare two files, use --file2:")
        print("python plot.py file1.nc VARIABLE --file2 file2.nc --mode difference")
    else:
        main()
