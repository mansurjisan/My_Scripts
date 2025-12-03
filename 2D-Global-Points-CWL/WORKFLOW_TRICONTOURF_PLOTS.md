# Workflow: Generating STOFS-2D Maxele Difference Tricontourf Plots

## Overview

This document describes the workflow for generating tricontourf visualization plots that show the difference between bias-corrected and non-bias-corrected STOFS-2D Global maximum water elevation (maxele) data.

---

## Directory Structure

```
/mnt/d/STOFS2D-Analysis/
├── MAXELE_PLOTS/
│   ├── 20251122/                          # Date directory
│   │   ├── stofs_2d_glo.t00z.fields.cwl.maxele.noanomaly.nc   # Non-bias-corrected
│   │   ├── stofs_2d_glo.t00z.fields.cwl.maxele.nc             # Bias-corrected
│   │   ├── stofs_2d_glo.t06z.fields.cwl.maxele.noanomaly.nc
│   │   ├── stofs_2d_glo.t06z.fields.cwl.maxele.nc
│   │   ├── ... (t12z, t18z files)
│   │   └── plots/
│   │       ├── 20251122_00z/              # Cycle subdirectory
│   │       │   ├── t00z_us_east_coast_tricontourf.png
│   │       │   ├── t00z_chesapeake_bay_tricontourf.png
│   │       │   ├── t00z_mobile_bay_tricontourf.png
│   │       │   ├── ... (other regions)
│   │       │   ├── t00z_conus_tricontourf.png
│   │       │   └── t00z_global_tricontourf.png
│   │       ├── 20251122_06z/
│   │       ├── 20251122_12z/
│   │       └── 20251122_18z/
│   ├── 20251123/
│   ├── 20251124/
│   └── PDFs/                              # Combined PDF output
│       ├── 20251122_t00z_tricontourf.pdf
│       ├── 20251122_t06z_tricontourf.pdf
│       └── ... (all date/cycle combinations)
│
└── My_Scripts/2D-Global-Points-CWL/
    ├── plot_difference_maxele_enhanced.py  # Main plotting script
    ├── generate_all_tricontourf.sh         # Batch script for regional plots
    ├── generate_conus_global_tricontourf.sh # Batch script for large domains
    └── GSHHS_shp/                          # Coastline shapefiles
        └── f/GSHHS_f_L1.shp
```

---

## Input Data

### NetCDF Files (from AWS S3)
Each date has 4 forecast cycles (00z, 06z, 12z, 18z), each with 2 files:

| File | Description |
|------|-------------|
| `stofs_2d_glo.t{HH}z.fields.cwl.maxele.noanomaly.nc` | Non-bias-corrected maxele |
| `stofs_2d_glo.t{HH}z.fields.cwl.maxele.nc` | Bias-corrected maxele |

### Key Variables in NetCDF
- `x` - Longitude of mesh nodes
- `y` - Latitude of mesh nodes
- `element` - Triangle connectivity (3 node indices per triangle)
- `zeta_max` - Maximum water elevation (meters)

---

## Step-by-Step Workflow

### Step 1: Download Data from AWS S3

Data is downloaded from NOAA's AWS bucket:
```bash
# S3 bucket structure
s3://noaa-nos-stofs2d-pds/STOFS-2D-Global/forecasts/netcdf/YYYYMMDD/

# Example download
aws s3 cp s3://noaa-nos-stofs2d-pds/STOFS-2D-Global/forecasts/netcdf/20251124/ \
    /mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/20251124/ \
    --recursive --exclude "*" --include "*maxele*"
```

### Step 2: Create Output Directories

```bash
DATE=20251124
BASE_DIR="/mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/${DATE}"

mkdir -p "${BASE_DIR}/plots/${DATE}_00z"
mkdir -p "${BASE_DIR}/plots/${DATE}_06z"
mkdir -p "${BASE_DIR}/plots/${DATE}_12z"
mkdir -p "${BASE_DIR}/plots/${DATE}_18z"
```

### Step 3: Generate Regional Tricontourf Plots

Run the batch script for all 10 regional domains:

```bash
cd /mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL
bash generate_all_tricontourf.sh 20251124
```

**Regions defined in `generate_all_tricontourf.sh`:**

| Region | Lon Range | Lat Range |
|--------|-----------|-----------|
| US East Coast | -82 to -65 | 25 to 45 |
| Chesapeake Bay | -77.5 to -75.5 | 36.6 to 39.7 |
| New York Harbor | -74.5 to -71.5 | 40.0 to 41.5 |
| Boston Harbor | -71.5 to -69.5 | 41.5 to 43.0 |
| Delaware Bay | -76.0 to -74.5 | 38.5 to 40.0 |
| Tampa Bay | -83.0 to -81.5 | 26.0 to 28.5 |
| Galveston Bay | -95.5 to -94.0 | 29.0 to 30.0 |
| Mobile Bay | -88.5 to -87.0 | 30.0 to 31.0 |
| Puget Sound | -123.5 to -122.0 | 47.0 to 48.5 |
| Puerto Rico | -67.5 to -65.0 | 17.5 to 18.8 |

### Step 4: Generate CONUS and Global Domain Plots

Run the batch script for large-scale domains:

```bash
bash generate_conus_global_tricontourf.sh 20251124
```

**Domains defined in `generate_conus_global_tricontourf.sh`:**

| Domain | Lon Range | Lat Range |
|--------|-----------|-----------|
| CONUS | -130 to -60 | 20 to 55 |
| Global | -180 to 180 | -90 to 90 |

### Step 5: Generate PDF Reports

Combine all plots for each cycle into a PDF:

```python
# Python script to create PDFs
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from PIL import Image
from glob import glob

dates = ["20251122", "20251123", "20251124"]
cycles = ["00", "06", "12", "18"]

for date in dates:
    for cycle in cycles:
        plot_dir = f"/mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/{date}/plots/{date}_{cycle}z"
        png_files = sorted(glob(f"{plot_dir}/*_tricontourf.png"))

        pdf_path = f"/mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/PDFs/{date}_t{cycle}z_tricontourf.pdf"
        c = canvas.Canvas(pdf_path, pagesize=landscape(letter))

        for png_file in png_files:
            # Add each image as a page
            c.drawImage(png_file, x, y, width, height)
            c.showPage()

        c.save()
```

---

## Main Plotting Script Usage

### Basic Command
```bash
python plot_difference_maxele_enhanced.py \
    <noanomaly_file> \
    <anomaly_file> \
    zeta_max \
    --use-tricontourf \
    [options]
```

### Key Options

| Option | Description | Example |
|--------|-------------|---------|
| `--use-tricontourf` | Enable tricontourf visualization | |
| `--region custom` | Use custom bounding box | |
| `--lon-range` | Longitude bounds | `--lon-range -88.5 -87.0` |
| `--lat-range` | Latitude bounds | `--lat-range 30.0 31.0` |
| `--vmin --vmax` | Color scale range | `--vmin -0.5 --vmax 0.5` |
| `--location-name` | Title label | `--location-name "Mobile Bay"` |
| `--save` | Output file path | `--save output.png` |
| `--no-individual` | Skip individual file plots | |
| `--max-points 0` | No point limit | |

### Full Example
```bash
python plot_difference_maxele_enhanced.py \
    /mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/20251124/stofs_2d_glo.t12z.fields.cwl.maxele.noanomaly.nc \
    /mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/20251124/stofs_2d_glo.t12z.fields.cwl.maxele.nc \
    zeta_max \
    --region custom \
    --lon-range -88.5 -87.0 \
    --lat-range 30.0 31.0 \
    --vmin -0.5 --vmax 0.5 \
    --no-individual \
    --max-points 0 \
    --use-tricontourf \
    --location-name "Mobile Bay" \
    --save /mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/20251124/plots/20251124_12z/t12z_mobile_bay_tricontourf.png
```

---

## Processing Pipeline Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                     AWS S3 Data Download                        │
│  s3://noaa-nos-stofs2d-pds/STOFS-2D-Global/forecasts/netcdf/   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Input NetCDF Files                           │
│  • stofs_2d_glo.t{HH}z.fields.cwl.maxele.noanomaly.nc          │
│  • stofs_2d_glo.t{HH}z.fields.cwl.maxele.nc                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              plot_difference_maxele_enhanced.py                 │
│                                                                 │
│  1. Load NetCDF data (x, y, element, zeta_max)                 │
│  2. Calculate difference: bias_corrected - non_bias_corrected  │
│  3. Extract regional mesh (filter nodes + remap elements)       │
│  4. Apply outlier filtering (±1.5m threshold)                  │
│  5. Create matplotlib Triangulation                            │
│  6. Generate tricontourf plot                                  │
│  7. Overlay GSHHS coastline                                    │
│  8. Add colorbar, title, labels                                │
│  9. Save PNG                                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Output PNG Files                             │
│  • Regional plots (10 regions × 4 cycles = 40 per date)        │
│  • CONUS/Global plots (2 domains × 4 cycles = 8 per date)      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PDF Generation                               │
│  • Combine all PNGs for each cycle into single PDF             │
│  • 12 pages per PDF (10 regional + 2 large domain)             │
│  • Landscape orientation                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Output Summary

### Per Date
| Output Type | Count | Description |
|-------------|-------|-------------|
| Regional PNGs | 40 | 10 regions × 4 cycles |
| CONUS/Global PNGs | 8 | 2 domains × 4 cycles |
| PDFs | 4 | 1 per cycle |

### Total for 3 Dates (Nov 22-24, 2025)
| Output Type | Count |
|-------------|-------|
| Regional PNGs | 120 |
| CONUS/Global PNGs | 24 |
| PDFs | 12 |

---

## Environment Setup

### Conda Environment
```bash
source /home/mjisan/miniconda3/bin/activate xesmf_env
```

### Required Packages
- `numpy`
- `matplotlib`
- `netCDF4`
- `cartopy`
- `shapely`
- `pillow`
- `reportlab` (for PDF generation)

---

## Troubleshooting

### Issue: Artificial Blue Spots in Coastal Bays
**Cause:** Extreme outlier values in the data
**Solution:** Outlier filtering is applied (±1.5m threshold) to mask triangles with unrealistic values

### Issue: Memory Error for Large Domains
**Cause:** Global mesh has ~3.6M nodes and ~7M triangles
**Solution:** Regional mesh extraction reduces data size before plotting

### Issue: Slow Rendering
**Cause:** Tricontourf is computationally intensive
**Solution:** Run batch scripts in background; plots take ~30-60 seconds each

### Issue: Missing Coastline
**Cause:** GSHHS shapefile not found
**Solution:** Ensure `GSHHS_shp/f/GSHHS_f_L1.shp` exists in script directory

---

## Quick Reference Commands

```bash
# Activate environment
source /home/mjisan/miniconda3/bin/activate xesmf_env

# Navigate to script directory
cd /mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL

# Generate all regional plots for a date
bash generate_all_tricontourf.sh 20251124

# Generate CONUS and Global plots for a date
bash generate_conus_global_tricontourf.sh 20251124

# Generate single plot manually
python plot_difference_maxele_enhanced.py \
    input_noanomaly.nc input_anomaly.nc zeta_max \
    --use-tricontourf --region custom \
    --lon-range -88.5 -87.0 --lat-range 30.0 31.0 \
    --vmin -0.5 --vmax 0.5 \
    --location-name "Mobile Bay" \
    --save output.png
```

---

## Contact

For questions about this workflow, contact the STOFS-2D validation team.
