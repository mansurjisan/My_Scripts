# RTOFS to ADCIRC Fort.11 Boundary Conditions Pipeline

## Overview
This pipeline processes RTOFS (Real-Time Ocean Forecast System) data to generate boundary condition files (fort.11.nc) for ADCIRC model simulations. 

## System Requirements
- **Platform**: WCOSS2 (Weather and Climate Operational Supercomputing System 2)
- **Resources**: Tested with interactive session using 10 nodes, 384GB memory
- **Interactive Session Command**: `submit_interactive 10 384GB 08:00:00`

## Directory Structure

### Script Repository
Location: `/u/mansur.jisan/My_Scripts/ADCIRC-FORT11-MJISAN` \
GitHub Repo: `https://github.com/mansurjisan/My_Scripts/new/main/ADCIRC-FORT11-MJISAN`
- `copy_nco_data.sh` - Copies RTOFS data from NCO data tank
- `rtofs_rename.sh` - Renames forecast files to date-based format
- `dlv3_array_pbs.sh` - Processes files in parallel using HYCOM tools

### Working Directory
Location: `/lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11`

### Required Tools
- **HYCOM-tools**: `/lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/HYCOM-tools`
- **OGCM_DL.a**: `/lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/bcdownloads/GLBy0.08/OGCM_DL.a`

## Installation

### Step 1: Copy Required Executables
```bash
# Copy HYCOM tools
cp -r /path/to/HYCOM-tools /lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/

# Copy OGCM_DL.a executable
cp /path/to/OGCM_DL.a /lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/bcdownloads/GLBy0.08/
```

### Step 2: Copy Scripts
```bash
# Copy processing scripts to working directory
cp /u/mansur.jisan/My_Scripts/ADCIRC-FORT11-MJISAN/*.sh /lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/
chmod +x *.sh
```

## Usage

### Complete Workflow Example
For a forecast cycle starting September 16, 2025:

#### Step 1: Copy RTOFS Data from NCO Data Tank
```bash
./copy_nco_data.sh 20250916  # Forecast date (current day)
```
This copies:
- Nowcast (n00) from previous day (Sep 15)
- Nowcast (n00) and forecasts (f24-f192) from current day (Sep 16)

#### Step 2: Rename Files to Date Format
```bash
./rtofs_rename.sh 20250915  # Nowcast date (previous day)
```
Converts forecast-hour naming (n00, f24, f48...) to date-based naming (20250915, 20250916...)

#### Step 3: Process Files Using HYCOM Tools
```bash
./dlv3_array_pbs.sh 20250915  # Start date (nowcast date)
```
- Processes 10 days of data in parallel
- Runs in batches of 6 tasks to optimize memory usage
- Takes approximately 30-35 minutes to complete
- Interpolates from GLBb0.08 to GLBy0.08 grid
- Converts to NetCDF format with 33 depth levels


#### Step 4: Generate Boundary Conditions File
```bash
cd bcdownloads/GLBy0.08
./OGCM_DL.a < test.inp
```
Produces `bcforcing_ver6p2.nc` - the final fort.11.nc file for ADCIRC

## Output Files

### Intermediate Files
- `bcdownloads/*.a` and `*.b` - RTOFS archive files in HYCOM format
- `bcdownloads/GLBy0.08/rtofs_glo.t00z.n00.archv.YYYYMMDD.nc` - Daily NetCDF files

### Final Output
- `bcdownloads/GLBy0.08/bcforcing_ver6p2.nc` - ADCIRC boundary conditions file (fort.11.nc)

## Data Coverage
- **Nowcast**: 1 day (previous day's n00)
- **Forecast**: 7.5+ days (current day's n00 plus f24-f192)
- **Total Coverage**: 10 days of boundary conditions

## Configuration Files
The pipeline automatically generates:
- `test.inp` - Control file for OGCM_DL.a
- `ogcm_data.txt` - List of NetCDF files to process

## Performance Notes
- Batch size of 6 parallel tasks optimizes memory usage on WCOSS2
- Processing time: ~30-35 minutes for 10 days of data
- Memory requirement: 384GB recommended for parallel processing

## Troubleshooting

### Common Issues
1. **Missing files**: Ensure NCO data tank has complete RTOFS data for requested dates
2. **Memory errors**: Reduce batch size in dlv3_array_pbs.sh if needed

### Verification Commands
```bash
# Check if RTOFS files exist
ls /lfs/h1/ops/prod/com/rtofs/v2.5/rtofs.YYYYMMDD/

# Verify intermediate NetCDF files
ls -la bcdownloads/GLBy0.08/*.nc

# Check final output
ncdump -h bcdownloads/GLBy0.08/bcforcing_ver6p2.nc | head -20
```

## Contact
mansur.jisan@noaa.gov
