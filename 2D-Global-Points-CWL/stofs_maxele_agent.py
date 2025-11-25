#!/usr/bin/env python3
"""
STOFS-2D Global Maxele Download and Plotting Agent

Downloads maxele files from NOAA S3 bucket and generates regional difference plots
comparing bias-corrected vs non-bias-corrected maximum water elevation.

Usage:
    python stofs_maxele_agent.py --start-date 2025-11-22 --end-date 2025-11-24
    python stofs_maxele_agent.py --date 2025-11-23 --cycles 00 06
    python stofs_maxele_agent.py --download-only --date 2025-11-23
    python stofs_maxele_agent.py --plot-only --date 2025-11-23

Author: Mansur Jisan
"""

import os
import sys
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

# S3 bucket base URL
S3_BASE_URL = "https://noaa-gestofs-pds.s3.amazonaws.com/_para4"

# Forecast cycles
CYCLES = ["00", "06", "12", "18"]

# File patterns
MAXELE_BIAS_CORRECTED = "stofs_2d_glo.t{cycle}z.fields.cwl.maxele.nc"
MAXELE_NO_ANOMALY = "stofs_2d_glo.t{cycle}z.fields.cwl.maxele.noanomaly.nc"

# Regional plot configurations
REGIONS = {
    "new_york_harbor": {
        "name": "New York Harbor",
        "lon_range": [-74.5, -71.5],
        "lat_range": [40.0, 41.5]
    },
    "boston_harbor": {
        "name": "Boston Harbor",
        "lon_range": [-71.5, -69.5],
        "lat_range": [41.5, 43.0]
    },
    "delaware_bay": {
        "name": "Delaware Bay",
        "lon_range": [-76.0, -74.5],
        "lat_range": [38.5, 40.0]
    },
    "tampa_bay": {
        "name": "Tampa Bay",
        "lon_range": [-83.0, -81.5],
        "lat_range": [26.0, 28.5]
    },
    "galveston_bay": {
        "name": "Galveston Bay",
        "lon_range": [-95.5, -94.0],
        "lat_range": [29.0, 30.0]
    },
    "mobile_bay": {
        "name": "Mobile Bay",
        "lon_range": [-88.5, -87.0],
        "lat_range": [30.0, 31.0]
    },
    "puget_sound": {
        "name": "Puget Sound",
        "lon_range": [-123.5, -122.0],
        "lat_range": [47.0, 48.5]
    },
    "puerto_rico": {
        "name": "Puerto Rico",
        "lon_range": [-67.5, -65.0],
        "lat_range": [17.5, 18.8]
    }
}

# Plot parameters
PLOT_PARAMS = {
    "vmin": -0.5,
    "vmax": 0.5,
    "color_levels": 20,
    "max_points": 0  # 0 means use all points
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def log(message, level="INFO"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def get_date_range(start_date, end_date):
    """Generate list of dates between start and end (inclusive)"""
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def build_s3_url(date_str, filename):
    """Build full S3 URL for a file"""
    return f"{S3_BASE_URL}/stofs_2d_glo.{date_str}/{filename}"


def download_file(url, local_path, retries=3):
    """Download file from URL with retry logic"""
    for attempt in range(retries):
        try:
            log(f"Downloading: {os.path.basename(local_path)}")
            log(f"  URL: {url}")

            # Create directory if needed
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download with progress
            urllib.request.urlretrieve(url, local_path, reporthook=download_progress)
            print()  # New line after progress

            # Verify file exists and has size
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                size_mb = os.path.getsize(local_path) / (1024 * 1024)
                log(f"  Downloaded: {size_mb:.1f} MB")
                return True
            else:
                log(f"  Download failed: empty file", "ERROR")

        except urllib.error.HTTPError as e:
            log(f"  HTTP Error {e.code}: {e.reason}", "ERROR")
            if e.code == 404:
                log(f"  File not found on server", "WARNING")
                return False
        except Exception as e:
            log(f"  Error: {e}", "ERROR")

        if attempt < retries - 1:
            log(f"  Retrying in 5 seconds... (attempt {attempt + 2}/{retries})")
            time.sleep(5)

    return False


def download_progress(block_num, block_size, total_size):
    """Show download progress"""
    if total_size > 0:
        downloaded = block_num * block_size
        percent = min(100, downloaded * 100 / total_size)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total_size / (1024 * 1024)
        sys.stdout.write(f"\r  Progress: {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
        sys.stdout.flush()


def check_file_exists(local_path):
    """Check if file already exists and has reasonable size"""
    if os.path.exists(local_path):
        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        if size_mb > 100:  # Maxele files should be > 100 MB
            return True
    return False


# =============================================================================
# DOWNLOAD FUNCTIONS
# =============================================================================

def download_maxele_files(date, cycle, output_dir):
    """Download both maxele files (bias-corrected and non-bias-corrected) for a date/cycle"""
    date_str = date.strftime("%Y%m%d")
    cycle_dir = os.path.join(output_dir, date_str, f"t{cycle}z")

    files_to_download = [
        (MAXELE_BIAS_CORRECTED.format(cycle=cycle), "bias-corrected"),
        (MAXELE_NO_ANOMALY.format(cycle=cycle), "non-bias-corrected")
    ]

    downloaded_files = {}

    for filename, file_type in files_to_download:
        local_path = os.path.join(cycle_dir, filename)

        # Check if already downloaded
        if check_file_exists(local_path):
            log(f"File already exists: {filename}")
            downloaded_files[file_type] = local_path
            continue

        # Build URL and download
        url = build_s3_url(date_str, filename)

        if download_file(url, local_path):
            downloaded_files[file_type] = local_path
        else:
            log(f"Failed to download {filename}", "WARNING")

    return downloaded_files


def download_all(dates, cycles, output_dir):
    """Download all maxele files for given dates and cycles"""
    log("=" * 60)
    log("STARTING DOWNLOAD")
    log("=" * 60)
    log(f"Dates: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
    log(f"Cycles: {', '.join(cycles)}")
    log(f"Output directory: {output_dir}")
    log("")

    all_downloads = {}

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        log(f"\n{'='*40}")
        log(f"Processing date: {date_str}")
        log(f"{'='*40}")

        all_downloads[date_str] = {}

        for cycle in cycles:
            log(f"\n--- Cycle: {cycle}Z ---")
            files = download_maxele_files(date, cycle, output_dir)
            all_downloads[date_str][cycle] = files

    return all_downloads


# =============================================================================
# PLOTTING FUNCTIONS
# =============================================================================

def generate_regional_plots(bias_corrected_file, no_anomaly_file, cycle, date_str, output_dir, script_path):
    """Generate all regional difference plots for a date/cycle"""

    if not os.path.exists(bias_corrected_file) or not os.path.exists(no_anomaly_file):
        log(f"Missing input files for {date_str} {cycle}Z", "ERROR")
        return False

    plots_dir = os.path.join(output_dir, date_str, f"t{cycle}z", "plots")
    os.makedirs(plots_dir, exist_ok=True)

    log(f"\nGenerating {len(REGIONS)} regional plots for {date_str} {cycle}Z...")

    success_count = 0

    for region_key, region_config in REGIONS.items():
        output_file = os.path.join(plots_dir, f"zeta_max_diff_{region_key}.png")

        log(f"  Plotting: {region_config['name']}")

        cmd = [
            "python3", script_path,
            no_anomaly_file,  # File 1 (non-bias-corrected)
            bias_corrected_file,  # File 2 (bias-corrected)
            "zeta_max",
            "--region", "custom",
            "--lon-range", str(region_config["lon_range"][0]), str(region_config["lon_range"][1]),
            "--lat-range", str(region_config["lat_range"][0]), str(region_config["lat_range"][1]),
            "--vmin", str(PLOT_PARAMS["vmin"]),
            "--vmax", str(PLOT_PARAMS["vmax"]),
            "--color-levels", str(PLOT_PARAMS["color_levels"]),
            "--no-individual",
            "--max-points", str(PLOT_PARAMS["max_points"]),
            "--location-name", region_config["name"],
            "--save", output_file
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per plot
            )

            if result.returncode == 0 and os.path.exists(output_file):
                log(f"    Saved: {os.path.basename(output_file)}")
                success_count += 1
            else:
                log(f"    Failed: {region_config['name']}", "ERROR")
                if result.stderr:
                    log(f"    Error: {result.stderr[:200]}", "ERROR")

        except subprocess.TimeoutExpired:
            log(f"    Timeout: {region_config['name']}", "ERROR")
        except Exception as e:
            log(f"    Exception: {e}", "ERROR")

    log(f"  Completed: {success_count}/{len(REGIONS)} plots")
    return success_count == len(REGIONS)


def plot_all(dates, cycles, output_dir, script_path):
    """Generate all regional plots for given dates and cycles"""
    log("=" * 60)
    log("STARTING PLOT GENERATION")
    log("=" * 60)
    log(f"Dates: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
    log(f"Cycles: {', '.join(cycles)}")
    log(f"Regions: {len(REGIONS)}")
    log("")

    total_plots = 0
    successful_plots = 0

    for date in dates:
        date_str = date.strftime("%Y%m%d")

        for cycle in cycles:
            cycle_dir = os.path.join(output_dir, date_str, f"t{cycle}z")

            bias_corrected = os.path.join(cycle_dir, MAXELE_BIAS_CORRECTED.format(cycle=cycle))
            no_anomaly = os.path.join(cycle_dir, MAXELE_NO_ANOMALY.format(cycle=cycle))

            if os.path.exists(bias_corrected) and os.path.exists(no_anomaly):
                log(f"\n{'='*40}")
                log(f"Plotting: {date_str} {cycle}Z")
                log(f"{'='*40}")

                if generate_regional_plots(bias_corrected, no_anomaly, cycle, date_str, output_dir, script_path):
                    successful_plots += 1
                total_plots += 1
            else:
                log(f"Skipping {date_str} {cycle}Z - missing files", "WARNING")

    log(f"\n{'='*60}")
    log(f"PLOT GENERATION COMPLETE")
    log(f"{'='*60}")
    log(f"Total date/cycles processed: {total_plots}")
    log(f"Successful: {successful_plots}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="STOFS-2D Global Maxele Download and Plotting Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download and plot for date range
  python stofs_maxele_agent.py --start-date 2025-11-22 --end-date 2025-11-24

  # Single date, specific cycles
  python stofs_maxele_agent.py --date 2025-11-23 --cycles 00 06

  # Download only (no plotting)
  python stofs_maxele_agent.py --download-only --date 2025-11-23

  # Plot only (files already downloaded)
  python stofs_maxele_agent.py --plot-only --date 2025-11-23
        """
    )

    # Date arguments
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--date", type=str, help="Single date (YYYY-MM-DD)")

    # Cycle arguments
    parser.add_argument("--cycles", nargs="+", default=CYCLES,
                        help=f"Forecast cycles (default: {' '.join(CYCLES)})")

    # Mode arguments
    parser.add_argument("--download-only", action="store_true",
                        help="Only download files, skip plotting")
    parser.add_argument("--plot-only", action="store_true",
                        help="Only generate plots, skip downloading")

    # Output arguments
    parser.add_argument("--output-dir", type=str, default="./stofs_data",
                        help="Output directory (default: ./stofs_data)")
    parser.add_argument("--plot-script", type=str, default="plot_difference_maxele_enhanced.py",
                        help="Path to plotting script")

    # List regions
    parser.add_argument("--list-regions", action="store_true",
                        help="List available regions and exit")

    args = parser.parse_args()

    # List regions
    if args.list_regions:
        print("\nAvailable regions:")
        print("-" * 50)
        for key, config in REGIONS.items():
            print(f"  {key}:")
            print(f"    Name: {config['name']}")
            print(f"    Lon:  {config['lon_range']}")
            print(f"    Lat:  {config['lat_range']}")
        return

    # Parse dates
    if args.date:
        start_date = datetime.strptime(args.date, "%Y-%m-%d")
        end_date = start_date
    elif args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        parser.error("Must specify either --date or both --start-date and --end-date")

    dates = get_date_range(start_date, end_date)
    cycles = args.cycles
    output_dir = os.path.abspath(args.output_dir)
    script_path = os.path.abspath(args.plot_script)

    # Validate plot script exists
    if not args.download_only and not os.path.exists(script_path):
        log(f"Plotting script not found: {script_path}", "ERROR")
        log("Use --plot-script to specify the correct path")
        sys.exit(1)

    # Print summary
    log("=" * 60)
    log("STOFS-2D MAXELE AGENT")
    log("=" * 60)
    log(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    log(f"Cycles: {', '.join(cycles)}")
    log(f"Output directory: {output_dir}")
    log(f"Mode: {'Download only' if args.download_only else 'Plot only' if args.plot_only else 'Download + Plot'}")
    log("")

    # Execute
    if not args.plot_only:
        download_all(dates, cycles, output_dir)

    if not args.download_only:
        plot_all(dates, cycles, output_dir, script_path)

    log("\n" + "=" * 60)
    log("AGENT COMPLETE")
    log("=" * 60)


if __name__ == "__main__":
    main()
