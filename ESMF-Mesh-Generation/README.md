# SECOFS ESMF Mesh Generation for UFS-Coastal DATM

This directory contains scripts for creating ESMF mesh files from GFS and HRRR
atmospheric data, adapted for the SECOFS transition to UFS-Coastal framework.

## Overview

The workflow converts operational GFS (0.25°) and HRRR (3km) GRIB2 data into
ESMF mesh format required by UFS-Coastal DATM component.

```
┌─────────────────────────────────────────────────────────────────────┐
│ GFS/HRRR GRIB2 → NetCDF → SCRIP → ESMF Mesh                        │
│                                                                     │
│ Step 1: wgrib2 -netcdf           (GRIB2 → NetCDF)                  │
│ Step 2: modify_*_4_esmfmesh.py   (Add CF attributes)               │
│ Step 3: gen_scrip_*.ncl          (NetCDF → SCRIP)                  │
│ Step 4: ESMF_Scrip2Unstruct      (SCRIP → ESMF Mesh)               │
└─────────────────────────────────────────────────────────────────────┘
```

## Scripts

### Python Scripts

| Script | Description |
|--------|-------------|
| `modify_gfs_4_esmfmesh.py` | Prepare GFS NetCDF for ESMF mesh generation |
| `modify_hrrr_4_esmfmesh.py` | Prepare HRRR NetCDF for ESMF mesh generation |
| `convert_gfs_hrrr_for_datm.py` | Convert GRIB2 to CF-compliant NetCDF (simplified workflow) |

### NCL Scripts

| Script | Description |
|--------|-------------|
| `gen_scrip_gfs.ncl` | Generate SCRIP grid file from GFS (rectilinear grid) |
| `gen_scrip_hrrr.ncl` | Generate SCRIP grid file from HRRR (curvilinear grid) |

### Shell Scripts

| Script | Description |
|--------|-------------|
| `create_esmf_mesh_secofs.sh` | Master script running complete workflow |

### Configuration Files

| File | Description |
|------|-------------|
| `datm_in_secofs` | DATM namelist template for SECOFS |
| `datm_streams_secofs.xml` | DATM stream configuration for GFS+HRRR |

## Prerequisites

```bash
# Required tools
module load wgrib2          # GRIB2 processing
module load ncl             # NCL for SCRIP generation
module load esmf            # ESMF_Scrip2Unstruct
module load python/3.9      # Python with netCDF4

# Python packages
pip install netCDF4 numpy
```

## Quick Start

### Option 1: Full Workflow (creates ESMF meshes)

```bash
# Run master script
./create_esmf_mesh_secofs.sh \
    /path/to/gfs.t06z.pgrb2.0p25.f000 \
    /path/to/hrrr.t06z.wrfsfcf00.grib2 \
    ./esmf_output

# Output:
#   esmf_output/gfs_esmf_mesh.nc
#   esmf_output/hrrr_esmf_mesh.nc
```

### Option 2: Simplified Workflow (NetCDF only, for existing meshes)

```bash
# Convert GFS/HRRR to NetCDF only (use existing ESMF meshes)
python convert_gfs_hrrr_for_datm.py \
    --gfs /path/to/gfs.t06z.pgrb2.0p25.f* \
    --output ./datm_input
```

### Option 3: Step-by-Step

```bash
# Step 1: Convert GRIB2 to NetCDF
wgrib2 gfs.t06z.pgrb2.0p25.f000 \
    -match "TMP:2 m|SPFH:2 m|PRES:surface|UGRD:10 m|VGRD:10 m|DSWRF|DLWRF|PRATE" \
    -small_grib -88:-63 17:40 gfs_subset.grib2
wgrib2 gfs_subset.grib2 -netcdf gfs_raw.nc

# Step 2: Add ESMF attributes
python modify_gfs_4_esmfmesh.py gfs_raw.nc gfs_for_esmf.nc

# Step 3: Generate SCRIP file
ncl 'input_file="gfs_for_esmf.nc"' 'output_file="gfs_scrip.nc"' gen_scrip_gfs.ncl

# Step 4: Create ESMF mesh
ESMF_Scrip2Unstruct gfs_scrip.nc gfs_esmf_mesh.nc 0
```

## DATM Configuration

After generating ESMF meshes, configure DATM:

1. Copy `datm_in_secofs` to your run directory as `datm_in`
2. Copy `datm_streams_secofs.xml` as `datm.streams.xml`
3. Update file paths in both files

### Key DATM Settings

```fortran
! datm_in
datamode       = 'GFS'                              ! Use GFS-style forcing
model_meshfile = 'INPUT/secofs_esmf_mesh.nc'        ! SCHISM mesh
nx_global      = 1684786                            ! SECOFS node count
```

### Stream Configuration

The dual-forcing approach uses:
- **GFS stream**: Global 0.25° coverage for full domain
- **HRRR stream**: High-res 3km for CONUS portion

## Validation Against Current Workflow

Compare DATM output against current nosofs sflux files:

| DATM Field | sflux Variable | File |
|------------|---------------|------|
| Sa_u, Sa_v | uwind, vwind | sflux_air_*.nc |
| Sa_tbot | stmp | sflux_air_*.nc |
| Faxa_swdn | dswrf | sflux_rad_*.nc |
| Faxa_rain | prate | sflux_prc_*.nc |

## References

- [UFS-Coastal Documentation](https://ufs-coastal-application.readthedocs.io/)
- [CDEPS DATM Guide](https://escomp.github.io/CDEPS/versions/master/html/datm.html)
- [ESMF User Guide](https://earthsystemmodeling.org/docs/)

## Workflow Origin

Adapted from ERA5 ESMF mesh workflow validated for Duck, NC case study.
Original scripts: `/work/noaa/nosofs/mjisan/pyschism-main/PySCHISM_tutorial/Scripts/Sflux/Duck_NC`

---
*Created: January 2026 for SECOFS UFS-Coastal transition*
