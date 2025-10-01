# ADCIRC Fort.63 Transect Analysis Tools

These scripts analyze ADCIRC model output (fort.63.nc files) along transects between observation stations, providing insights into model behavior in areas without direct observations. This addresses the need to understand how model predictions change spatially between known observation points.

## Scripts

### 1. `transect_timeseries_fort63.py`
Extracts and visualizes water elevation timeseries at multiple points along a transect between two locations.

### 2. `plot_transect_map.py`
Creates maps showing the transect path and sampling points.



## transect_timeseries_fort63.py

### Purpose

Generates individual timeseries plots for evenly-spaced points along a transect, showing how water elevation behavior changes spatially between observation stations.

### Features
- Extracts timeseries at N points along a user-defined transect
- Creates individual timeseries plots for each point

### Usage

```bash
python transect_timeseries_fort63.py <nc_file> <lon1> <lat1> <lon2> <lat2> [options]

```

### Required Arguments
- `nc_file`: Path to fort.63.nc file
- `lon1`: Starting longitude (decimal degrees)
- `lat1`: Starting latitude (decimal degrees)
- `lon2`: Ending longitude (decimal degrees)
- `lat2`: Ending latitude (decimal degrees)

### Optional Arguments
- `--points N`: Number of sampling points along transect (default: 20)
- `--stations "NAME1" "NAME2"`: Names for start/end stations
- `--output-dir DIR`: Output directory for plots (default: transect_timeseries)
- `--start-time YYYY-MM-DD`: Start time for analysis
- `--end-time YYYY-MM-DD`: End time for analysis
- `--save-csv`: Save statistics to CSV file (optional)

### Examples

#### Basic transect analysis (20 points)
```bash
python transect_timeseries_fort63.py fort.63_UND.nc \
    -75.705 35.208 -76.670 34.717 \
    --points 20 \
    --output-dir hatteras_beaufort
```

#### With station names and more points
```bash
python transect_timeseries_fort63.py fort.63_UND.nc \
    -75.705 35.208 -76.670 34.717 \
    --points 30 \
    --stations "USCG_Hatteras" "Duke_Marine_Lab" \
    --output-dir hatteras_beaufort_analysis
```

#### Time-filtered analysis with CSV output
```bash
python transect_timeseries_fort63.py fort.63_UND.nc \
    -75.705 35.208 -76.670 34.717 \
    --points 25 \
    --stations "Hatteras" "Beaufort" \
    --start-time "2025-09-16" \
    --end-time "2025-09-20" \
    --output-dir filtered_analysis \
    --save-csv
```

### Output Files

The script creates the following in the output directory:

1. **Individual timeseries plots**: `timeseries_XXX_kmYY.png`
   - One for each sampling point
   - Shows water elevation over time

## plot_transect_map.py

### Purpose
Visualizes the transect path and sampling points on a map, showing the map of the transect and optionally the underlying model mesh.

### Features
- Shows transect line and sampling points
- Optional mesh node visualization
- Automatic mesh density handling for large datasets
- Creates both detailed and simplified maps

### Usage

```bash
python plot_transect_map.py <lon1> <lat1> <lon2> <lat2> [options]
```

### Required Arguments
- `lon1`: Starting longitude
- `lat1`: Starting latitude
- `lon2`: Ending longitude
- `lat2`: Ending latitude

### Optional Arguments
- `--points N`: Number of points along transect (default: 20)
- `--stations "NAME1" "NAME2"`: Names for start/end stations
- `--nc-file FILE`: NetCDF file for mesh coordinates (optional)
- `--show-mesh`: Display mesh nodes in background
- `--output FILE`: Output filename (default: transect_map.png)
- `--buffer DEGREES`: Map extent buffer (default: 0.5)

### Examples

#### Simple transect map
```bash
python plot_transect_map.py \
    -75.705 35.208 -76.670 34.717 \
    --points 30 \
    --stations "Hatteras_NC" "Beaufort_NC" \
    --output transect_map.png
```

#### Map with mesh visualization
```bash
python plot_transect_map.py \
    -75.705 35.208 -76.670 34.717 \
    --points 30 \
    --stations "USCG_Hatteras" "Duke_Marine_Lab" \
    --nc-file fort.63_UND.nc \
    --show-mesh \
    --output hatteras_beaufort_mesh.png
```

### Output Files

1. **Main map**: `<output_name>.png`
   - Left panel: Overview with optional mesh
   - Right panel: Detailed view with point numbers
   - Shows transect path, sampling points, and distance

2. **Simple map**: `<output_name>_simple.png`
   - Clean visualization without mesh
   - Color gradient showing distance progression
   - Distance labels at key points

### Mesh Visualization Notes

For large meshes (>100,000 nodes in region):
- Automatically switches to density heatmap
- Prevents plot overload with too many points
- Blue gradient shows node density

For moderate meshes (<100,000 nodes):
- Shows subsampled points
- Adaptive point sizing based on count
- Light blue color for visibility

## Common Use Cases

### 1. Analyze Model Behavior Between Tide Gauges
```bash
# Generate timeseries
python transect_timeseries_fort63.py fort.63.nc \
    -75.750 36.183 -75.978 36.843 \
    --points 30 \
    --stations "Duck_NC" "Virginia_Beach_VA" \
    --output-dir duck_vb_analysis

# Create map
python plot_transect_map.py \
    -75.750 36.183 -75.978 36.843 \
    --points 30 \
    --stations "Duck_NC" "Virginia_Beach_VA" \
    --output duck_vb_map.png
```

### 2. Compare Two Model Runs
```bash
# Run 1
python transect_timeseries_fort63.py fort.63_run1.nc \
    -75.705 35.208 -76.670 34.717 \
    --points 25 --output-dir run1_transect

# Run 2  
python transect_timeseries_fort63.py fort.63_run2.nc \
    -75.705 35.208 -76.670 34.717 \
    --points 25 --output-dir run2_transect

```

### 3. Storm Event Analysis
```bash
# Focus on storm period
python transect_timeseries_fort63.py fort.63.nc \
    -90.0 29.0 -94.0 29.5 \
    --points 20 \
    --stations "New_Orleans" "Galveston" \
    --start-time "2025-09-15" \
    --end-time "2025-09-20" \
    --output-dir storm_transect \
    --save-csv
```

## Output Interpretation

### Timeseries Plots
- **Consistent patterns**: Good model continuity
- **Phase shifts**: Expected due to wave propagation
- **Amplitude changes**: May indicate bathymetry effects
- **Discontinuities**: Potential model issues

### Comparison Plot
- **Top panel**: Shows if tidal patterns are coherent
- **Middle panel**: Reveals spatial gradients
- **Bottom panel**: Identifies regions of rapid change

### Statistics
- **Range variations**: Indicate changing tidal dynamics
- **Standard deviation**: Shows variability changes
- **Mean offsets**: May indicate setup/setdown effects

---

## Requirements

- Python 3.6+
- numpy
- matplotlib
- netCDF4
- datetime
