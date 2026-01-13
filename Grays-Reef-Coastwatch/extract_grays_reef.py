#!/usr/bin/env python3
"""
Gray's Reef NMS Data Extraction using erddapy

Extracts environmental data from NOAA CoastWatch ERDDAP servers for
Gray's Reef National Marine Sanctuary (Georgia coast).

Datasets:
- SST & Anomaly (Coral Reef Watch v3.1, 2003-2024)
- Chlorophyll-a (VIIRS Science Quality Monthly, 2012-2024)
- K490 Turbidity (MODIS Aqua Monthly, 2003-2024)

Usage:
    python extract_grays_reef.py --all
    python extract_grays_reef.py --sst
    python extract_grays_reef.py --chlorophyll
    python extract_grays_reef.py --k490
"""

import argparse
import os
import sys
from datetime import datetime

try:
    from erddapy import ERDDAP
    import pandas as pd
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    print("Install dependencies with: pip install erddapy pandas")
    sys.exit(1)


# Gray's Reef NMS bounding box
BOUNDS = {
    'lat_min': 31.36,
    'lat_max': 31.42,
    'lon_min': -80.93,
    'lon_max': -80.82
}

# Dataset configurations
DATASETS = {
    'sst': {
        'name': 'SST & Anomaly (Coral Reef Watch)',
        'server': 'https://coastwatch.pfeg.noaa.gov/erddap',
        'dataset_id': 'NOAA_DHW_monthly',
        'variables': ['sea_surface_temperature', 'sea_surface_temperature_anomaly'],
        'time_start': '2003-01-01',
        'time_end': '2024-12-31',
        'output_file': 'sst_raw.csv'
    },
    'chlorophyll': {
        'name': 'Chlorophyll-a (VIIRS Science Quality)',
        'server': 'https://coastwatch.noaa.gov/erddap',
        'dataset_id': 'noaacwNPPVIIRSSQchlaMonthly',
        'variables': ['chlor_a'],
        'time_start': '2012-01-01',
        'time_end': '2024-12-31',
        'output_file': 'chlorophyll_raw.csv'
    },
    'k490': {
        'name': 'K490 Turbidity (MODIS Aqua)',
        'server': 'https://coastwatch.pfeg.noaa.gov/erddap',
        'dataset_id': 'erdMH1kd490mday_R2022SQ',
        'variables': ['Kd_490'],
        'time_start': '2003-01-01',
        'time_end': '2024-12-31',
        'output_file': 'k490_raw.csv'
    }
}


def extract_erddap_data(
    server_url: str,
    dataset_id: str,
    variables: list,
    time_start: str,
    time_end: str,
    output_file: str = None,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Extract data from ERDDAP server for Gray's Reef bounding box.

    Parameters
    ----------
    server_url : str
        ERDDAP server URL (e.g., 'https://coastwatch.pfeg.noaa.gov/erddap')
    dataset_id : str
        Dataset identifier (e.g., 'NOAA_DHW_monthly')
    variables : list
        List of variable names to extract
    time_start : str
        Start date in 'YYYY-MM-DD' format
    time_end : str
        End date in 'YYYY-MM-DD' format
    output_file : str, optional
        Path to save CSV output
    verbose : bool
        Print progress messages

    Returns
    -------
    pandas.DataFrame
        Extracted data with time, latitude, longitude, and requested variables
    """
    if verbose:
        print(f"  Server: {server_url}")
        print(f"  Dataset: {dataset_id}")
        print(f"  Variables: {variables}")
        print(f"  Time range: {time_start} to {time_end}")
        print(f"  Bounding box: {BOUNDS['lat_min']}-{BOUNDS['lat_max']}N, "
              f"{BOUNDS['lon_min']}-{BOUNDS['lon_max']}W")

    # Initialize ERDDAP connection
    e = ERDDAP(server=server_url, protocol='griddap')
    e.dataset_id = dataset_id

    # Initialize griddap (required for erddapy >= 2.0)
    e.griddap_initialize()

    # Set constraints
    e.constraints = {
        'time>=': f"{time_start}T00:00:00Z",
        'time<=': f"{time_end}T00:00:00Z",
        'latitude>=': BOUNDS['lat_min'],
        'latitude<=': BOUNDS['lat_max'],
        'longitude>=': BOUNDS['lon_min'],
        'longitude<=': BOUNDS['lon_max'],
    }

    # Set variables (always include coordinates)
    e.variables = ['time', 'latitude', 'longitude'] + variables

    # Download data
    if verbose:
        print("  Downloading...")

    try:
        df = e.to_pandas()
    except Exception as err:
        print(f"  ERROR: Failed to download data - {err}")
        return None

    if verbose:
        print(f"  Retrieved {len(df):,} records")
        if len(df) > 0:
            time_col = [c for c in df.columns if 'time' in c.lower()][0]
            print(f"  Date range: {df[time_col].min()} to {df[time_col].max()}")

    # Save to file if specified
    if output_file and df is not None and len(df) > 0:
        df.to_csv(output_file, index=False)
        if verbose:
            print(f"  Saved to: {output_file}")

    return df


def extract_dataset(dataset_key: str, output_dir: str = '.', verbose: bool = True) -> pd.DataFrame:
    """Extract a specific dataset by key."""
    if dataset_key not in DATASETS:
        print(f"Unknown dataset: {dataset_key}")
        print(f"Available: {list(DATASETS.keys())}")
        return None

    config = DATASETS[dataset_key]
    output_path = os.path.join(output_dir, config['output_file'])

    if verbose:
        print(f"\n{'='*60}")
        print(f"Extracting: {config['name']}")
        print('='*60)

    return extract_erddap_data(
        server_url=config['server'],
        dataset_id=config['dataset_id'],
        variables=config['variables'],
        time_start=config['time_start'],
        time_end=config['time_end'],
        output_file=output_path,
        verbose=verbose
    )


def extract_all(output_dir: str = './grays_reef_data', verbose: bool = True) -> dict:
    """Extract all configured datasets."""
    os.makedirs(output_dir, exist_ok=True)

    if verbose:
        print("Gray's Reef NMS Data Extraction")
        print(f"Output directory: {output_dir}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}
    success_count = 0

    for key in DATASETS:
        df = extract_dataset(key, output_dir=output_dir, verbose=verbose)
        results[key] = df
        if df is not None and len(df) > 0:
            success_count += 1

    if verbose:
        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print('='*60)
        print(f"Successfully extracted: {success_count}/{len(DATASETS)} datasets")
        print(f"Files saved to: {output_dir}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Extract Gray\'s Reef NMS environmental data from NOAA CoastWatch ERDDAP'
    )

    parser.add_argument(
        '-o', '--output-dir',
        default='./grays_reef_data',
        help='Output directory for CSV files (default: ./grays_reef_data)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress messages'
    )

    # Dataset selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--all',
        action='store_true',
        help='Extract all datasets (default)'
    )
    group.add_argument(
        '--sst',
        action='store_true',
        help='Extract SST & Anomaly only (2003-2024)'
    )
    group.add_argument(
        '--chlorophyll',
        action='store_true',
        help='Extract Chlorophyll-a only (2012-2024)'
    )
    group.add_argument(
        '--k490',
        action='store_true',
        help='Extract K490 Turbidity only (2003-2024)'
    )

    args = parser.parse_args()
    verbose = not args.quiet

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Determine which datasets to extract
    if args.sst:
        extract_dataset('sst', output_dir=args.output_dir, verbose=verbose)
    elif args.chlorophyll:
        extract_dataset('chlorophyll', output_dir=args.output_dir, verbose=verbose)
    elif args.k490:
        extract_dataset('k490', output_dir=args.output_dir, verbose=verbose)
    else:
        # Default: extract all
        extract_all(output_dir=args.output_dir, verbose=verbose)


if __name__ == "__main__":
    main()
