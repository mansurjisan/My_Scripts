# STOFS-2D Timeseries Comparison Plots Workflow

**Author:** Mansur Jisan
**Date:** December 2025

This document describes the workflow for generating side-by-side timeseries comparison plots for STOFS-2D Global barotropic model validation.

## Overview

The workflow generates station-by-station timeseries comparison plots showing:
- **WITH anomaly correction**: Bias-corrected model output (left panel)
- **WITHOUT anomaly correction**: Original model output (right panel)

Each panel shows model predictions vs CO-OPS observations with RMSE and correlation statistics.

## Prerequisites

### Required Python Packages
```bash
pip install numpy pandas matplotlib netCDF4 searvey pillow
```

### Required Local Package
The `stofs2d_obs` package must be installed from the local repository:
```bash
cd stofs2d-obs-main/stofs2d-obs-main
pip install -e .
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
│           └── ... (all 8 files for 4 cycles)
├── comparison_plots_YYYYMMDD_XXz/   # Output directory per cycle
│   ├── station_0000_XXXXXXX_comparison.png
│   ├── station_0001_XXXXXXX_comparison.png
│   └── barotropic_YYYYMMDD_XXz.pdf  # Combined PDF
├── compare_side_by_side.py          # Main script
└── stofs2d-obs-main/                # Required package
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

cd ../../..
```

### Step 2: Generate Timeseries Plots

Run `compare_side_by_side.py` for each forecast cycle:

```bash
DATE=20251122

# Generate plots for all 4 cycles
for CYCLE in 00 06 12 18; do
    python3 compare_side_by_side.py \
        --cwl stofs_data/${DATE}/raw/stofs_2d_glo.t${CYCLE}z.points.cwl.nc \
        --noanomaly stofs_data/${DATE}/raw/stofs_2d_glo.t${CYCLE}z.points.cwl.noanomaly.nc \
        --station-range 0 834 \
        --output-dir comparison_plots_${DATE}_${CYCLE}z
done
```

**Command Options:**
- `--cwl FILE`: Path to the WITH anomaly correction NetCDF file
- `--noanomaly FILE`: Path to the WITHOUT anomaly correction NetCDF file
- `--station-range START END`: Range of stations to process (0 to 834 for all stations)
- `--station-idx IDX`: Process a single station by index
- `--output-dir DIR`: Output directory for plots
- `--datum DATUM`: Vertical datum (default: MSL)
- `--output-pdf FILE`: Custom PDF filename

### Step 3: Output Files

For each cycle, the following files are generated in `comparison_plots_YYYYMMDD_XXz/`:

| File | Description |
|------|-------------|
| `station_NNNN_XXXXXXX_comparison.png` | Individual station comparison plot |
| `barotropic_YYYYMMDD_XXz.pdf` | Combined PDF with all station plots |

## Plot Features

Each comparison plot includes:
- **Side-by-side panels**: WITH anomaly (left) vs WITHOUT anomaly (right)
- **Timeseries data**: Model (blue) vs Observations (red)
- **Statistics box**: RMSE and correlation coefficient for each panel
- **Matched y-axis**: Both panels use the same scale for easy comparison
- **Station info**: Title shows station name from CO-OPS

## Complete Example

Process all cycles for multiple dates:

```bash
# Process November 22, 2025
for CYCLE in 00 06 12 18; do
    python3 compare_side_by_side.py \
        --cwl stofs_data/20251122/raw/stofs_2d_glo.t${CYCLE}z.points.cwl.nc \
        --noanomaly stofs_data/20251122/raw/stofs_2d_glo.t${CYCLE}z.points.cwl.noanomaly.nc \
        --station-range 0 834 \
        --output-dir comparison_plots_20251122_${CYCLE}z
done

# Process November 23, 2025
for CYCLE in 00 06 12 18; do
    python3 compare_side_by_side.py \
        --cwl stofs_data/20251123/raw/stofs_2d_glo.t${CYCLE}z.points.cwl.nc \
        --noanomaly stofs_data/20251123/raw/stofs_2d_glo.t${CYCLE}z.points.cwl.noanomaly.nc \
        --station-range 0 834 \
        --output-dir comparison_plots_20251123_${CYCLE}z
done
```

## Script Details

### compare_side_by_side.py

This script:
1. Reads STOFS-2D NetCDF files (with and without anomaly correction)
2. Uses `Fort61Reader` from `stofs2d_obs` package to read station data
3. Matches model stations to CO-OPS tide gauge stations using `COOPSMatcher`
4. Fetches observed water levels from CO-OPS API using `searvey`
5. Creates `ModelObsComparison` objects to align data and calculate statistics
6. Generates side-by-side plots with matched y-axis scales
7. Combines all PNG plots into a single PDF using `PIL`

### Key Functions

- `create_side_by_side_plot()`: Creates comparison plot for a single station
- `combine_plots_to_pdf()`: Combines all PNG files into a single PDF

### Output Statistics

The script prints summary statistics at the end:
- Number of stations processed
- Mean RMSE for WITH and WITHOUT anomaly correction
- Mean correlation for both cases
- RMSE improvement percentage

## Notes

- The script processes ~834 stations per cycle
- Each cycle takes approximately 1-2 hours to complete (depending on network speed)
- CO-OPS observations are fetched in real-time via the searvey library
- Stations without matching CO-OPS data are skipped
- The PDF combines all successful plots (typically 200+ per cycle)

## Troubleshooting

### Missing stofs2d_obs package
```bash
cd stofs2d-obs-main/stofs2d-obs-main
pip install -e .
```

### No CO-OPS match found
Some model stations may not have corresponding CO-OPS tide gauges. These are skipped automatically.

### Network errors
The script fetches CO-OPS observations in real-time. If network errors occur, the script continues to the next station.
