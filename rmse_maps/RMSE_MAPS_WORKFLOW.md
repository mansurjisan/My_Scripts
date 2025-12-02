# STOFS-2D RMSE Maps Generation Workflow

**Author:** Mansur Jisan
**Date:** December 2025

This document describes the workflow for generating RMSE (Root Mean Square Error) maps comparing STOFS-2D Global model forecasts against CO-OPS tide gauge observations.

## Overview

The workflow generates geographic RMSE maps for the STOFS-2D Global barotropic model validation, comparing:
- **WITHOUT anomaly correction**: Original model output
- **WITH anomaly correction**: Bias-corrected model output

## Prerequisites

### Required Python Packages
```bash
pip install numpy pandas matplotlib netCDF4 cartopy searvey pillow
```

### Required Data
- STOFS-2D NetCDF files from NOAA AWS S3:
  - `stofs_2d_glo.tXXz.points.cwl.nc` (with anomaly correction)
  - `stofs_2d_glo.tXXz.points.cwl.noanomaly.nc` (without anomaly correction)
- Where `XX` is the forecast cycle: 00, 06, 12, or 18

## Directory Structure

```
STOFS2D-Analysis/
├── stofs_data/
│   └── YYYYMMDD/
│       └── raw/
│           ├── stofs_2d_glo.t00z.points.cwl.nc
│           ├── stofs_2d_glo.t00z.points.cwl.noanomaly.nc
│           ├── stofs_2d_glo.t06z.points.cwl.nc
│           ├── stofs_2d_glo.t06z.points.cwl.noanomaly.nc
│           ├── stofs_2d_glo.t12z.points.cwl.nc
│           ├── stofs_2d_glo.t12z.points.cwl.noanomaly.nc
│           ├── stofs_2d_glo.t18z.points.cwl.nc
│           └── stofs_2d_glo.t18z.points.cwl.noanomaly.nc
├── rmse_maps_YYYYMMDD/           # Intermediate CSV files
├── rmse_maps_YYYYMMDD_uniform/   # Final output maps
├── generate_rmse_maps_v2.py      # Step 1: Calculate RMSE stats
└── generate_rmse_maps_uniform.py # Step 2: Generate uniform maps
```

## Workflow Steps

### Step 1: Download STOFS-2D Data

Download the NetCDF files from NOAA AWS S3:

```bash
# Set the date
DATE=20251122

# Create directory
mkdir -p stofs_data/${DATE}/raw
cd stofs_data/${DATE}/raw

# Download all 4 cycles (00z, 06z, 12z, 18z)
for CYCLE in 00 06 12 18; do
    # With anomaly correction
    curl -O "https://noaa-gestofs-pds.s3.amazonaws.com/_para4/stofs_2d_glo.${DATE}/stofs_2d_glo.t${CYCLE}z.points.cwl.nc"

    # Without anomaly correction
    curl -O "https://noaa-gestofs-pds.s3.amazonaws.com/_para4/stofs_2d_glo.${DATE}/stofs_2d_glo.t${CYCLE}z.points.cwl.noanomaly.nc"
done
```

### Step 2: Calculate RMSE Statistics

Run `generate_rmse_maps_v2.py` to calculate RMSE for each station by comparing model output against CO-OPS observations:

```bash
# Generate RMSE statistics for all 4 cycles
python3 generate_rmse_maps_v2.py --date 20251122
```

**Command Options:**
- `--date YYYYMMDD` (required): Date to process
- `--cycles 00 06 12 18` (optional): Specific cycles to process (default: all 4)

**Output:**
- Creates directory `rmse_maps_YYYYMMDD/`
- Generates CSV files: `rmse_stats_YYYYMMDD_XXz.csv` for each cycle
- Each CSV contains: station info, lat, lon, RMSE with/without correction, correlation

### Step 3: Generate Uniform RMSE Maps

Run `generate_rmse_maps_uniform.py` to create the final maps with consistent station count across all cycles:

```bash
# Generate uniform maps with full-height colorbar
python3 generate_rmse_maps_uniform.py --date 20251122
```

**Command Options:**
- `--date YYYYMMDD` (required): Date to process
- `--cycles 00 06 12 18` (optional): Specific cycles to process
- `--input-dir PATH` (optional): Input directory with CSV files
- `--output-dir PATH` (optional): Output directory for maps

**Output:**
- Creates directory `rmse_maps_YYYYMMDD_uniform/`
- Generates PNG maps for each cycle (8 total: 4 with, 4 without correction)
- Generates combined PDF with all maps

## Output Files

For each date, the following files are generated in `rmse_maps_YYYYMMDD_uniform/`:

| File | Description |
|------|-------------|
| `rmse_map_YYYYMMDD_00z_without.png` | 00Z cycle, without anomaly correction |
| `rmse_map_YYYYMMDD_00z_with.png` | 00Z cycle, with anomaly correction |
| `rmse_map_YYYYMMDD_06z_without.png` | 06Z cycle, without anomaly correction |
| `rmse_map_YYYYMMDD_06z_with.png` | 06Z cycle, with anomaly correction |
| `rmse_map_YYYYMMDD_12z_without.png` | 12Z cycle, without anomaly correction |
| `rmse_map_YYYYMMDD_12z_with.png` | 12Z cycle, with anomaly correction |
| `rmse_map_YYYYMMDD_18z_without.png` | 18Z cycle, without anomaly correction |
| `rmse_map_YYYYMMDD_18z_with.png` | 18Z cycle, with anomaly correction |
| `rmse_maps_YYYYMMDD.pdf` | Combined PDF with all 8 maps |
| `rmse_stats_YYYYMMDD_XXz.csv` | RMSE statistics CSV for each cycle |

## Map Features

The generated maps include:
- **GSHHS high-resolution coastlines**: Detailed shoreline rendering
- **Uniform station count**: ~215 stations consistent across all cycles
- **Full-height colorbar**: Colorbar matches the plot height
- **Forecast Cycle label**: Shows the forecast initialization time
- **RMSE color scale**: 0.0 to 0.5 meters (yellow to red)
- **Gray markers**: Stations without data for that cycle

## Complete Example

Process multiple dates:

```bash
# Process November 22, 2025
python3 generate_rmse_maps_v2.py --date 20251122
python3 generate_rmse_maps_uniform.py --date 20251122

# Process November 23, 2025
python3 generate_rmse_maps_v2.py --date 20251123
python3 generate_rmse_maps_uniform.py --date 20251123

# Process November 24, 2025
python3 generate_rmse_maps_v2.py --date 20251124
python3 generate_rmse_maps_uniform.py --date 20251124
```

## Script Details

### generate_rmse_maps_v2.py

This script:
1. Reads STOFS-2D NetCDF files (with and without anomaly correction)
2. Matches model stations to CO-OPS tide gauge stations using `searvey` library
3. Fetches observed water levels from CO-OPS API
4. Calculates RMSE and correlation for each station
5. Saves statistics to CSV files

### generate_rmse_maps_uniform.py

This script:
1. Reads CSV files from all cycles
2. Builds a master station list (union of all cycles)
3. Creates geographic maps using Cartopy with PlateCarree projection
4. Uses GSHHS high-resolution coastlines
5. Plots stations colored by RMSE value
6. Shows stations without data as gray markers
7. Combines all maps into a single PDF

## Notes

- The RMSE calculation uses the full forecast period (~7.7 days)
- CO-OPS observations are fetched in real-time via the searvey library
- Stations are identified by lat/lon coordinates (rounded to 5 decimal places)
- The color scale is fixed at 0-0.5m for consistent comparison across cycles
