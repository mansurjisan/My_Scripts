#!/bin/bash

# RTOFS Data Download Script
# Downloads .a and .b archive files from NOAA RTOFS model using parallel processing

# Delete bcforcing_ver6p2.nc if it exists
rm -f /asclepius/acerrone/baroclinic_shadow/preprocessing/bcdownloads/GLBy0.08/bcforcing_ver6p2.nc

rm -f /asclepius/acerrone/baroclinic_shadow/preprocessing/bcdownloads/GLBy0.08/rtofs_glo.t00z.n00.archv.*

set -e  # Exit on any error

# --- Calculate common dates for file generation ---
# Get yesterday's date in YYYY-MM-DD HH:mm format
START_DATETIME_TEST_INP=$(date -d "yesterday" +"%Y-%m-%d 00:00")
# Get end date for test.inp (start_datetime + 9 days)
END_DATETIME_TEST_INP=$(date -d "$(date -d "yesterday" +"%Y-%m-%d") + 9 days" +"%Y-%m-%d 00:00")

# Get yesterday's date in YYYY-MM-DD format for ogcm_data.txt lines
OGCM_START_DATE_YYYYMMDD=$(date -d "yesterday" +"%Y%m%d")

# --- Working directories ---
PREPROCESSING_DIR="/asclepius/acerrone/baroclinic_shadow/preprocessing"
SIM_DIR="/asclepius/acerrone/baroclinic_shadow/preprocessing/bcdownloads/GLBy0.08"

# --- Create test.inp file ---
echo "Creating test.inp in $SIM_DIR..."
cat <<EOT_TEST_INP > "$SIM_DIR/test.inp"
# 1st Line is Comment: Control File Template
$START_DATETIME_TEST_INP ! Start datetime (YYYY-MM-DD HH:mm)
$END_DATETIME_TEST_INP ! End datetime (YYYY-MM-DD HH:mm)
8 ! DT multiplier: DT is 3 hrs for GOFS 3.1 so 8 indicates 24 hr output
ftp ! The server to ownload from (ftp -or- ncs -or- opd)
3 ! Output type, = 1 for T & S attributes only, = 2 for T,S,U,V attributes
bathyfixed.14
bcforcing_ver6p2.nc
EOT_TEST_INP
echo "test.inp created."
echo ""

# --- Create ogcm_data.txt file ---
echo "Creating ogcm_data.txt in $SIM_DIR..."
# Number of entries should match the dlv3_array.sh tasks (10 tasks)
NUM_OGCM_ENTRIES=10
echo "$NUM_OGCM_ENTRIES" > "$SIM_DIR/ogcm_data.txt"

for i in $(seq 0 $((NUM_OGCM_ENTRIES - 1))); do
  CURRENT_OGCM_DATE_YYYYMMDD=$(date -d "$OGCM_START_DATE_YYYYMMDD + $i days" +"%Y%m%d")
  CURRENT_OGCM_DATE_FORMATTED=$(date -d "$OGCM_START_DATE_YYYYMMDD + $i days" +"%Y-%m-%d 00:00")
  echo "'$CURRENT_OGCM_DATE_FORMATTED' rtofs_glo.t00z.n00.archv.$CURRENT_OGCM_DATE_YYYYMMDD.nc dmy dmy" >> "$SIM_DIR/ogcm_data.txt"
done
echo "ogcm_data.txt created."
echo ""

# Configuration
NUM_PROCESSORS=4
OUTPUT_DIR="bcdownloads"
BASE_URL="https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

# Function to cleanup existing files
cleanup_existing_files() {
    local output_dir="$1"
    
    if [[ ! -d "$output_dir" ]]; then
        return 0
    fi
    
    # Find all .a and .b files (only in the immediate directory, not subdirectories)
    local files=$(find "$output_dir" -maxdepth 1 -name "*.a" -o -name "*.b" 2>/dev/null)
    
    if [[ -n "$files" ]]; then
        local count=$(echo "$files" | wc -l)
        print_info "Cleaning up $count existing .a and .b files..."
        
        echo "$files" | while read -r file; do
            if [[ -f "$file" ]]; then
                rm -f "$file"
                echo "  Deleted: $(basename "$file")"
            fi
        done
    else
        print_info "No existing .a or .b files found to clean up."
    fi
}

# Function to download a single file
download_file() {
    local url="$1"
    local filename=$(basename "$url")
    local local_path="$OUTPUT_DIR/$filename"
    
    # Skip if file already exists
    if [[ -f "$local_path" ]]; then
        print_warning "File already exists, skipping: $filename"
        return 0
    fi
    
    echo "Downloading: $filename"
    
    # Download with curl, showing progress
    if curl -L --fail --connect-timeout 60 --max-time 2000 \
            --user-agent "RTOFS-Download-Script/1.0" \
            --progress-bar \
            --output "$local_path" \
            "$url"; then
        print_info "? Successfully downloaded: $filename"
        return 0
    else
        print_error "? Error downloading $filename"
        rm -f "$local_path"  # Remove partial file
        return 1
    fi
}

# Function to generate URLs for given date
generate_urls() {
    local date_str="$1"
    local forecast_hours=("n00" "f24" "f48" "f72" "f96" "f120" "f144" "f156")
    
    for hour in "${forecast_hours[@]}"; do
        for ext in "a" "b"; do
            echo "$BASE_URL/rtofs.$date_str/rtofs_glo.t00z.$hour.archv.$ext"
        done
    done
}

# Export function for parallel execution
export -f download_file print_info print_warning print_error
export OUTPUT_DIR RED GREEN YELLOW NC

# Main function
main() {
    # Get current date in YYYYMMDD format
    local current_date=$(date +%Y%m%d)
    print_info "Downloading RTOFS data for date: $current_date"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    print_info "Output directory: $(realpath "$OUTPUT_DIR")"
    
    # Clean up existing .a and .b files
    echo
    print_info "Cleaning up existing files..."
    cleanup_existing_files "$OUTPUT_DIR"
    
    # Generate URLs
    echo
    local urls=($(generate_urls "$current_date"))
    
    print_info "Generated ${#urls[@]} URLs to download"
    echo "Files to download:"
    for url in "${urls[@]}"; do
        echo "  - $(basename "$url")"
    done
    
    # Download files using parallel processing
    echo
    print_info "Starting downloads with $NUM_PROCESSORS parallel processes..."
    
    # Create a temporary file with URLs
    local temp_file=$(mktemp)
    printf '%s\n' "${urls[@]}" > "$temp_file"
    
    # Download in parallel using xargs
    local failed=0
    if ! cat "$temp_file" | xargs -P "$NUM_PROCESSORS" -I {} bash -c 'download_file "$@"' _ {}; then
        failed=1
    fi
    
    # Cleanup temp file
    rm -f "$temp_file"
    
    # Summary
    echo
    echo "=================================================="
    echo "Download Summary:"
    
    local total=${#urls[@]}
    local successful=0
    local failed_count=0
    
    # Count successful downloads
    for url in "${urls[@]}"; do
        local filename=$(basename "$url")
        local local_path="$OUTPUT_DIR/$filename"
        if [[ -f "$local_path" ]]; then
            ((successful++))
        else
            ((failed_count++))
        fi
    done
    
    echo "  Total files: $total"
    echo "  Successful: $successful"
    echo "  Failed: $failed_count"
    echo "=================================================="
    
    if [[ $failed_count -gt 0 ]]; then
        print_warning "? $failed_count files failed to download. Check the output above for details."
        exit 1
    else
        print_info "? All files downloaded successfully!"
    fi
}

# Handle interruption
trap 'echo -e "\n\nDownload interrupted by user."; exit 1' INT

# Run main function
main "$@" 
