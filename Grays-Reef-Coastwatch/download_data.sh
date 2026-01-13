#!/bin/bash
#
# Gray's Reef NMS Data Download Script
# Downloads environmental data from NOAA CoastWatch ERDDAP servers using curl
#
# Usage:
#   ./download_data.sh           # Download all datasets
#   ./download_data.sh --sst     # Download SST only
#   ./download_data.sh --help    # Show help
#

set -e

OUTPUT_DIR="./grays_reef_data"

# Gray's Reef bounding box
LAT_MIN="31.36"
LAT_MAX="31.42"
LON_MIN="-80.93"
LON_MAX="-80.82"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

print_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_info() {
    echo -e "${YELLOW}INFO:${NC} $1"
}

download_sst() {
    print_header "Downloading SST Anomaly (Coral Reef Watch, 2003-2024)"
    local output_file="$OUTPUT_DIR/sst_raw.csv"
    # Note: Latitude is in descending order in this dataset, so we use LAT_MAX:LAT_MIN
    local url="https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW_monthly.csv?sea_surface_temperature[(2003-01-16T00:00:00Z):1:(2024-12-16T00:00:00Z)][($LAT_MAX):1:($LAT_MIN)][($LON_MIN):1:($LON_MAX)],sea_surface_temperature_anomaly[(2003-01-16T00:00:00Z):1:(2024-12-16T00:00:00Z)][($LAT_MAX):1:($LAT_MIN)][($LON_MIN):1:($LON_MAX)]"

    echo "  Output: $output_file"
    print_info "Downloading 22 years of monthly data..."
    if curl -g -f -o "$output_file" "$url" 2>/dev/null; then
        local size=$(du -h "$output_file" | cut -f1)
        print_success "Downloaded $size"
    else
        print_error "Download failed"
        return 1
    fi
}

download_chlorophyll() {
    print_header "Downloading Chlorophyll-a (VIIRS Monthly, 2012-2024)"
    local output_file="$OUTPUT_DIR/chlorophyll_raw.csv"
    # VIIRS has altitude dimension, using Monthly Science Quality dataset
    local url="https://coastwatch.noaa.gov/erddap/griddap/noaacwNPPVIIRSSQchlaMonthly.csv?chlor_a[(2012-01-01T12:00:00Z):1:(2024-12-31T12:00:00Z)][(0.0)][($LAT_MIN):1:($LAT_MAX)][($LON_MIN):1:($LON_MAX)]"

    echo "  Output: $output_file"
    print_info "Downloading 13 years of monthly data..."
    if curl -g -f -o "$output_file" "$url" 2>/dev/null; then
        local size=$(du -h "$output_file" | cut -f1)
        print_success "Downloaded $size"
    else
        print_error "Download failed"
        return 1
    fi
}

download_k490_modis() {
    print_header "Downloading K490 Turbidity (MODIS Monthly, 2003-2024)"
    local output_file="$OUTPUT_DIR/k490_raw.csv"
    # MODIS K490 Science Quality - latitude is ascending
    local url="https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdMH1kd490mday_R2022SQ.csv?Kd_490[(2003-01-16T00:00:00Z):1:(2024-12-16T00:00:00Z)][($LAT_MIN):1:($LAT_MAX)][($LON_MIN):1:($LON_MAX)]"

    echo "  Output: $output_file"
    print_info "Downloading 22 years of monthly data..."
    if curl -g -f -o "$output_file" "$url" 2>/dev/null; then
        local size=$(du -h "$output_file" | cut -f1)
        print_success "Downloaded $size"
    else
        print_error "Download failed"
        return 1
    fi
}

download_all() {
    echo ""
    echo "Gray's Reef NMS Data Download"
    echo "Bounding box: ${LAT_MIN}-${LAT_MAX}°N, ${LON_MIN}-${LON_MAX}°W"
    echo "Output directory: $OUTPUT_DIR"
    echo ""
    echo "Datasets:"
    echo "  - SST (Coral Reef Watch): 2003-2024"
    echo "  - Chlorophyll-a (VIIRS): 2012-2024"
    echo "  - K490 Turbidity (MODIS): 2003-2024"
    echo ""

    mkdir -p "$OUTPUT_DIR"

    local success=0
    local failed=0

    if download_sst; then ((success++)); else ((failed++)); fi
    if download_chlorophyll; then ((success++)); else ((failed++)); fi
    if download_k490_modis; then ((success++)); else ((failed++)); fi

    print_header "DOWNLOAD COMPLETE"
    echo "Successful: $success"
    echo "Failed: $failed"
    echo ""
    echo "Files in $OUTPUT_DIR:"
    ls -lh "$OUTPUT_DIR"/*.csv 2>/dev/null || echo "No CSV files found"
}

show_help() {
    echo "Gray's Reef NMS Data Download Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all           Download all datasets (default)"
    echo "  --sst           Download SST Anomaly only (2003-2024)"
    echo "  --chlorophyll   Download Chlorophyll-a only (2012-2024)"
    echo "  --k490          Download K490 MODIS only (2003-2024)"
    echo "  --output DIR    Set output directory (default: ./grays_reef_data)"
    echo "  --help          Show this help message"
    echo ""
    echo "Datasets:"
    echo "  SST & Anomaly  - Coral Reef Watch v3.1 (Monthly, 2003-2024)"
    echo "  Chlorophyll-a  - VIIRS Science Quality (Monthly, 2012-2024)"
    echo "  K490 Turbidity - MODIS Aqua (Monthly, 2003-2024)"
}

# Parse arguments
DATASET="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            DATASET="all"
            shift
            ;;
        --sst)
            DATASET="sst"
            shift
            ;;
        --chlorophyll)
            DATASET="chlorophyll"
            shift
            ;;
        --k490)
            DATASET="k490"
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run appropriate download
case $DATASET in
    all)
        download_all
        ;;
    sst)
        download_sst
        ;;
    chlorophyll)
        download_chlorophyll
        ;;
    k490)
        download_k490_modis
        ;;
esac
