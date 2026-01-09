# SECOFS-UFS Diagnostic Scripts

Comparison and visualization tools for SECOFS (Southeast Coastal Ocean Forecast System) sensitivity testing between:
- **Standalone SCHISM** (Operational SECOFS)
- **UFS-SECOFS** (UFS-Coastal with CDEPS/DATM coupling)

## Requirements

```bash
# Python 3.8+
pip install numpy matplotlib

# Or with conda:
conda install numpy matplotlib
```

## Scripts Overview

### Station Timeseries Comparison

| Script | Description |
|--------|-------------|
| `compare_no_wind.py` | Compare SECOFS vs UFS-SECOFS without wind forcing (sensitivity test) |
| `plot_no_wind_individual.py` | Generate individual station plots for no-wind comparison |
| `compare_station_timeseries.py` | Multi-panel comparison with statistics (RMSE, bias, correlation) |
| `plot_station_comparison.py` | User-friendly single station comparison plots |
| `plot_station_timeseries.py` | Basic station timeseries visualization |

### Field Comparison (2D Maps)

| Script | Description |
|--------|-------------|
| `compare_ufs_schism.py` | 3-panel comparison maps (Op SECOFS \| UFS-SECOFS \| Difference) |
| `plot_wind_us_pr.py` | Wind speed maps with US East Coast + Puerto Rico inset |
| `plot_zeta_us_pr.py` | Water level maps with US East Coast + Puerto Rico inset |

## Quick Start

### 1. Edit Configuration

Each script has a `USER CONFIGURATION` section at the top. Update these paths:

```python
# Example from compare_no_wind.py
SECOFS_DIR = '/path/to/station_out_secofs_no_wind'
UFS_DIR = '/path/to/station_out_ufs_no_wind'
STATION_FILE = '/path/to/station.in'
OUTPUT_DIR = '/path/to/output/plots'
```

### 2. Run Scripts

```bash
# Station comparison
python3 compare_no_wind.py
python3 plot_no_wind_individual.py

# Field comparison (requires netCDF4)
python3 compare_ufs_schism.py
```

## Input File Formats

### Station Files (staout_*)
- SCHISM station output format
- Column 1: Time (seconds from start)
- Columns 2-N: Station values

### Station.in
- SCHISM station definition file
- Contains station coordinates and names

### NetCDF Files (for field comparison)
- SCHISM native output format (schout_*.nc)
- Variables: `elev`, `wind_speed`, `SCHISM_hgrid_node_x/y`, `SCHISM_hgrid_face_nodes`

## WCOSS2 Usage

```bash
# Load modules
module load python/3.10.4
# Or: module load miniconda3/4.12.0

# Run
cd /path/to/secofs-ufs-diag
python3 compare_no_wind.py
```

### PBS Job Example

```bash
#!/bin/bash
#PBS -N secofs_diag
#PBS -A NOSOFS-DEV
#PBS -q dev
#PBS -l select=1:ncpus=1:mem=4GB
#PBS -l walltime=00:30:00

module load python/3.10.4
cd $PBS_O_WORKDIR
python3 compare_no_wind.py
```

## Output

Scripts generate PNG plots in the specified OUTPUT_DIR:
- `*_timeseries.png` - Multi-panel timeseries
- `*_difference.png` - Difference plots
- `*_scatter.png` - Scatter comparison
- Individual station plots in subdirectories

## Author

Mansur Jisan - January 2026
