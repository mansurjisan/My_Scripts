Workflow for generating ADCIRC fort.11.nc files from RTOFS (Real-Time Ocean Forecast System) data. This is a oceanographic data processing pipeline that converts HYCOM archive files to NetCDF format suitable for ADCIRC boundary conditions.

## Overview
This pipeline downloads RTOFS global ocean model data, processes it through spatial interpolation and format conversion, and ultimately creates boundary condition files for ADCIRC coastal ocean modeling.

## Detailed Script Analysis

### 1. **rtofs_download.sh**
**Purpose:** Downloads RTOFS archive files (.a and .b format) from NOAA servers

**Key Functionality:**
- Downloads 8 forecast files (nowcast through 7-day forecast) for the current date
- Uses parallel downloading (4 processes) for efficiency
- Downloads both .a (data) and .b (header) files for each forecast hour
- Creates two important configuration files:
  - `test.inp`: Control file for OGCM_DL.a program
  - `ogcm_data.txt`: Lists 10 days of data files to process

**How to Run:**
```bash
./rtofs_download.sh
```

### 2. **rtofs_rename.sh**
**Purpose:** Renames forecast files from time-step format to date-based format

**Key Functionality:**
- Converts files from forecast notation (n00, f24, f48, etc.) to date notation
- Creates an additional day+8 file by copying day+7 (extending the forecast)
- Example: `rtofs_glo.t00z.f24.archv.a` → `rtofs_glo.t00z.n00.archv.20250831.a`

**How to Run:**
```bash
./rtofs_rename.sh
```

### 3. **uncompress.sh**
**Purpose:** Decompresses the downloaded .a files (which are gzipped tar archives)

**Key Functionality:**
- Processes all .a files in the bcdownloads directory
- Uses parallel processing (4 cores) for efficiency
- Extracts the actual data file from each compressed archive
- Replaces the compressed file with the extracted data

**How to Run:**
```bash
./uncompress.sh
```

### 4. **download_extra_nowcasts.sh**
**Purpose:** Manages nowcast archive files for specific dates

**Key Functionality:**
- Copies next day's files to an archive directory
- Retrieves specific date's files from archive to main directory
- Used for backfilling or recovering specific dates

**How to Run:**
```bash
./download_extra_nowcasts.sh YYYYMMDD YYYYMMDD
# Example:
./download_extra_nowcasts.sh 20250730 20250730
```

### 5. **dlv3_array.sh**
**Purpose:** Main processing script that converts HYCOM archive files to NetCDF

**Key Functionality:**
- Runs as an SGE job array (10 parallel tasks)
- Each task processes one day of data
- Executes two critical sub-scripts for each date:
  - `isubaregion_nd_m.csh`: Interpolates from GLBb0.08 to GLBy0.08 grid
  - `archv2ncdf3z_nd_m.csh`: Converts to NetCDF with vertical interpolation

**How to Run:**
```bash
qsub dlv3_array.sh
```

### 6. **sim.sub**
**Purpose:** Final step to generate fort.11.nc using OGCM_DL.a program

**Key Functionality:**
- Loads required modules (mvapich2, netcdf)
- Runs OGCM_DL.a with test.inp configuration
- Produces the final bcforcing_ver6p2.nc file

**How to Run:**
```bash
qsub sim.sub
# or directly:
./sim.sub
```

## Supporting Scripts Explained

### **isubaregion_nd_m.csh**
- Performs spatial interpolation from global grid (GLBb0.08) to regional grid (GLBy0.08)
- Uses HYCOM tools to subset and interpolate the data
- Target grid: 4500 x 4263 points

### **archv2ncdf3z_nd_m.csh**
- Converts HYCOM archive format to NetCDF
- Performs vertical interpolation to 33 standard depth levels (0m to 5500m)
- Extracts temperature and salinity fields

## Complete Workflow Sequence

```bash
# Day 1: Download and prepare data
./rtofs_download.sh          # Downloads files, creates test.inp and ogcm_data.txt
./rtofs_rename.sh            # Renames files to date format
./uncompress.sh              # Decompresses .a files

# Optional: For specific date recovery
./download_extra_nowcasts.sh 20250829 20250829

# Day 2: Process data (on HPC with SGE)
qsub dlv3_array.sh           # Processes 10 days of data in parallel

# Day 3: Generate fort.11.nc
qsub sim.sub                 # Creates bcforcing_ver6p2.nc
```

## Important Notes for HPC Usage

1. **Module Requirements:**
   - intel compiler
   - netcdf library
   - mvapich2 MPI implementation

2. **Directory Structure:**
   ```
   /asclepius/acerrone/baroclinic_shadow/preprocessing/
   ├── bcdownloads/           # Downloaded RTOFS files
   │   ├── GLBb0.08/         # Original grid
   │   └── GLBy0.08/         # Target grid
   └── HYCOM-tools/          # Processing executables
   ```

3. **File Formats:**
   - `.a` files: HYCOM binary data files
   - `.b` files: ASCII header files with metadata
   - `.nc` files: NetCDF output files

4. **Time Considerations:**
   - Download: ~30-60 minutes depending on connection
   - Processing (dlv3_array.sh): Several hours for 10 days
   - Final generation: ~30 minutes

The final output `bcforcing_ver6p2.nc` can be renamed to `fort.11.nc` for use as ADCIRC boundary conditions. This file contains time-varying temperature and salinity fields that ADCIRC uses to force the coastal ocean model at its open boundaries.