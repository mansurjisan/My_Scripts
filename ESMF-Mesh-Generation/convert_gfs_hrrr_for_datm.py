#!/usr/bin/env python3
"""
Convert GFS/HRRR GRIB2 to CF-compliant NetCDF for DATM
=====================================================

This script converts operational GFS and HRRR GRIB2 files to the NetCDF format
required by UFS-Coastal DATM. It uses wgrib2 for GRIB2 processing and Python
for NetCDF attribute modification.

This is an alternative to the full NCL-based workflow when you just need
the data files (not the ESMF mesh, which still requires NCL/ESMF tools).

Usage:
    python convert_gfs_hrrr_for_datm.py --gfs /path/to/gfs.grib2 --output ./datm_input
    python convert_gfs_hrrr_for_datm.py --hrrr /path/to/hrrr.grib2 --output ./datm_input

Author: Adapted for SECOFS UFS-Coastal transition
Date: January 2026
"""

import argparse
import subprocess
import os
import sys
from pathlib import Path

try:
    from netCDF4 import Dataset
    import numpy as np
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False
    print("Warning: netCDF4 not available, will use wgrib2 only")


# Variables required by DATM for atmospheric forcing
DATM_VARIABLES = {
    'TMP:2 m above ground': {'wgrib2_name': 'TMP_2maboveground', 'datm_name': 'Sa_tbot', 'units': 'K'},
    'SPFH:2 m above ground': {'wgrib2_name': 'SPFH_2maboveground', 'datm_name': 'Sa_shum', 'units': 'kg/kg'},
    'PRES:surface': {'wgrib2_name': 'PRES_surface', 'datm_name': 'Sa_pslv', 'units': 'Pa'},
    'UGRD:10 m above ground': {'wgrib2_name': 'UGRD_10maboveground', 'datm_name': 'Sa_u', 'units': 'm/s'},
    'VGRD:10 m above ground': {'wgrib2_name': 'VGRD_10maboveground', 'datm_name': 'Sa_v', 'units': 'm/s'},
    'DSWRF:surface': {'wgrib2_name': 'DSWRF_surface', 'datm_name': 'Faxa_swdn', 'units': 'W/m2'},
    'DLWRF:surface': {'wgrib2_name': 'DLWRF_surface', 'datm_name': 'Faxa_lwdn', 'units': 'W/m2'},
    'PRATE:surface': {'wgrib2_name': 'PRATE_surface', 'datm_name': 'Faxa_rain', 'units': 'kg/m2/s'},
}

# SECOFS domain bounds
SECOFS_DOMAIN = {
    'lonmin': -88.0,
    'lonmax': -63.0,
    'latmin': 17.0,
    'latmax': 40.0
}


def check_wgrib2():
    """Check if wgrib2 is available."""
    try:
        result = subprocess.run(['wgrib2', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def extract_grib2_to_netcdf(grib2_file, output_nc, domain=None, variables=None):
    """
    Convert GRIB2 file to NetCDF using wgrib2.

    Parameters
    ----------
    grib2_file : str
        Path to input GRIB2 file
    output_nc : str
        Path to output NetCDF file
    domain : dict, optional
        Domain bounds {'lonmin', 'lonmax', 'latmin', 'latmax'}
    variables : list, optional
        List of variable patterns to extract (wgrib2 -match format)
    """
    if not os.path.exists(grib2_file):
        raise FileNotFoundError(f"GRIB2 file not found: {grib2_file}")

    # Build wgrib2 command
    cmd = ['wgrib2', grib2_file]

    # Variable selection
    if variables:
        var_pattern = '|'.join(variables)
        cmd.extend(['-match', var_pattern])

    # Domain subsetting
    if domain:
        subset_grib = output_nc.replace('.nc', '_subset.grib2')
        cmd.extend(['-small_grib',
                    f"{domain['lonmin']}:{domain['lonmax']}",
                    f"{domain['latmin']}:{domain['latmax']}",
                    subset_grib])

        print(f"Extracting and subsetting: {grib2_file}")
        subprocess.run(cmd, check=True)

        # Convert subset to NetCDF
        print(f"Converting to NetCDF: {output_nc}")
        subprocess.run(['wgrib2', subset_grib, '-netcdf', output_nc], check=True)

        # Cleanup
        os.remove(subset_grib)
    else:
        # Direct conversion
        cmd.extend(['-netcdf', output_nc])
        print(f"Converting to NetCDF: {output_nc}")
        subprocess.run(cmd, check=True)

    return output_nc


def add_cf_attributes(nc_file):
    """
    Add CF-compliant attributes required by ESMF/DATM.

    Parameters
    ----------
    nc_file : str
        Path to NetCDF file to modify
    """
    if not HAS_NETCDF:
        print("Warning: Cannot add CF attributes without netCDF4")
        return

    ds = Dataset(nc_file, 'r+')

    # Global attributes
    ds.Conventions = 'CF-1.6'
    ds.title = 'Atmospheric forcing for DATM'
    ds.history = f'Converted by convert_gfs_hrrr_for_datm.py'

    # Fix coordinate attributes
    for var_name in ['latitude', 'lat']:
        if var_name in ds.variables:
            var = ds.variables[var_name]
            var.units = 'degrees_north'
            var.axis = 'Y'
            var.standard_name = 'latitude'

    for var_name in ['longitude', 'lon']:
        if var_name in ds.variables:
            var = ds.variables[var_name]
            var.units = 'degrees_east'
            var.axis = 'X'
            var.standard_name = 'longitude'

    if 'time' in ds.variables:
        ds.variables['time'].axis = 'T'

    # Add coordinates attribute to data variables
    coord_vars = ['time', 'lat', 'latitude', 'lon', 'longitude']
    for var_name in ds.variables:
        if var_name not in coord_vars:
            try:
                ds.variables[var_name].coordinates = 'longitude latitude'
            except:
                pass

    ds.close()
    print(f"Added CF attributes: {nc_file}")


def process_gfs(grib2_files, output_dir, domain=SECOFS_DOMAIN):
    """
    Process GFS GRIB2 files for DATM.

    Parameters
    ----------
    grib2_files : list
        List of GFS GRIB2 file paths
    output_dir : str
        Output directory for NetCDF files
    domain : dict
        Domain bounds
    """
    os.makedirs(output_dir, exist_ok=True)

    variables = list(DATM_VARIABLES.keys())

    for grib2_file in grib2_files:
        basename = os.path.basename(grib2_file)
        # Generate output filename
        # e.g., gfs.t06z.pgrb2.0p25.f000 -> gfs.t06z.f000.nc
        nc_name = basename.replace('.pgrb2.0p25', '').replace('.grib2', '.nc').replace('.grb2', '.nc')
        if not nc_name.endswith('.nc'):
            nc_name += '.nc'

        output_nc = os.path.join(output_dir, nc_name)

        try:
            extract_grib2_to_netcdf(grib2_file, output_nc, domain=domain, variables=variables)
            add_cf_attributes(output_nc)
            print(f"Created: {output_nc}")
        except Exception as e:
            print(f"Error processing {grib2_file}: {e}")


def process_hrrr(grib2_files, output_dir, domain=SECOFS_DOMAIN):
    """
    Process HRRR GRIB2 files for DATM.

    Parameters
    ----------
    grib2_files : list
        List of HRRR GRIB2 file paths
    output_dir : str
        Output directory for NetCDF files
    domain : dict
        Domain bounds (note: HRRR may not cover full domain)
    """
    os.makedirs(output_dir, exist_ok=True)

    variables = list(DATM_VARIABLES.keys())

    for grib2_file in grib2_files:
        basename = os.path.basename(grib2_file)
        nc_name = basename.replace('.grib2', '.nc').replace('.grb2', '.nc')
        if not nc_name.endswith('.nc'):
            nc_name += '.nc'

        output_nc = os.path.join(output_dir, nc_name)

        try:
            # HRRR domain may not fully cover SECOFS, so we might skip subsetting
            # or use intersection
            extract_grib2_to_netcdf(grib2_file, output_nc, domain=domain, variables=variables)
            add_cf_attributes(output_nc)
            print(f"Created: {output_nc}")
        except Exception as e:
            print(f"Error processing {grib2_file}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert GFS/HRRR GRIB2 to CF-compliant NetCDF for DATM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert single GFS file
    python convert_gfs_hrrr_for_datm.py --gfs /path/to/gfs.t06z.pgrb2.0p25.f000 --output ./datm_input

    # Convert multiple GFS files (glob pattern)
    python convert_gfs_hrrr_for_datm.py --gfs "/path/to/gfs.t06z.pgrb2.0p25.f*" --output ./datm_input

    # Convert HRRR file
    python convert_gfs_hrrr_for_datm.py --hrrr /path/to/hrrr.t06z.wrfsfcf00.grib2 --output ./datm_input
        """
    )

    parser.add_argument('--gfs', nargs='+', help='GFS GRIB2 file(s)')
    parser.add_argument('--hrrr', nargs='+', help='HRRR GRIB2 file(s)')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--domain', choices=['secofs', 'full'], default='secofs',
                        help='Domain subsetting (default: secofs)')
    parser.add_argument('--lonmin', type=float, help='Override minimum longitude')
    parser.add_argument('--lonmax', type=float, help='Override maximum longitude')
    parser.add_argument('--latmin', type=float, help='Override minimum latitude')
    parser.add_argument('--latmax', type=float, help='Override maximum latitude')

    args = parser.parse_args()

    if not args.gfs and not args.hrrr:
        parser.error("Must specify --gfs or --hrrr files")

    if not check_wgrib2():
        print("ERROR: wgrib2 is required but not found")
        sys.exit(1)

    # Set domain
    if args.domain == 'full':
        domain = None
    else:
        domain = SECOFS_DOMAIN.copy()
        if args.lonmin:
            domain['lonmin'] = args.lonmin
        if args.lonmax:
            domain['lonmax'] = args.lonmax
        if args.latmin:
            domain['latmin'] = args.latmin
        if args.latmax:
            domain['latmax'] = args.latmax

    # Process files
    if args.gfs:
        print("=" * 60)
        print("Processing GFS files")
        print("=" * 60)
        process_gfs(args.gfs, args.output, domain)

    if args.hrrr:
        print("=" * 60)
        print("Processing HRRR files")
        print("=" * 60)
        process_hrrr(args.hrrr, args.output, domain)

    print("=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == '__main__':
    main()
