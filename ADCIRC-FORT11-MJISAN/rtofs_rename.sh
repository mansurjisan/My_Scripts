#!/bin/bash

# RTOFS File Renaming and Copying Script
# Modified to accept a specific date parameter and handle f00 files
# Usage: ./rtofs_rename.sh [YYYYMMDD]

set -e  # Exit on any error

# Configuration
INPUT_DIR="bcdownloads"

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

# Function to get date with offset from a base date
get_date_with_offset() {
    local base_date=$1
    local days_offset=$2
    date -d "${base_date:0:4}-${base_date:4:2}-${base_date:6:2} + ${days_offset} days" +%Y%m%d
}

# Function to rename file
rename_file() {
    local old_name="$1"
    local new_name="$2"

    if [[ -f "$INPUT_DIR/$old_name" ]]; then
        mv "$INPUT_DIR/$old_name" "$INPUT_DIR/$new_name"
        print_info "[OK] Renamed: $old_name -> $new_name"
        return 0
    else
        print_warning "[WARN] File not found: $old_name"
        return 1
    fi
}

# Function to copy file
copy_file() {
    local source="$1"
    local target="$2"

    if [[ -f "$INPUT_DIR/$source" ]]; then
        cp "$INPUT_DIR/$source" "$INPUT_DIR/$target"
        print_info "[OK] Copied: $source -> $target"
        return 0
    else
        print_warning "[WARN] Source file not found: $source"
        return 1
    fi
}

# Main function
main() {
    # Check if date parameter is provided
    if [[ $# -eq 1 ]]; then
        local base_date="$1"
        # Validate date format
        if ! [[ "$base_date" =~ ^[0-9]{8}$ ]]; then
            print_error "Error: Date must be in YYYYMMDD format."
            print_error "Usage: $0 [YYYYMMDD]"
            exit 1
        fi
        print_info "Using provided date: $base_date"
    else
        # Use yesterday's date as default (since n00 comes from previous day)
        local base_date=$(date -d "yesterday" +%Y%m%d)
        print_info "No date provided, using yesterday's date: $base_date"
    fi

    print_info "Starting RTOFS file renaming process..."
    echo "Note: This script expects n00 (from previous day), f00 (from current day), and f24-f192 files"

    # Check if input directory exists
    if [[ ! -d "$INPUT_DIR" ]]; then
        print_error "Error: Directory $INPUT_DIR does not exist!"
        exit 1
    fi

    # Calculate dates for each file based on the base date
    # base_date is for n00 (previous day's nowcast)
    local current_date=$base_date
    local date_plus_1=$(get_date_with_offset $base_date 1)  # f00 (current day's nowcast)
    local date_plus_2=$(get_date_with_offset $base_date 2)  # f24
    local date_plus_3=$(get_date_with_offset $base_date 3)  # f48
    local date_plus_4=$(get_date_with_offset $base_date 4)  # f72
    local date_plus_5=$(get_date_with_offset $base_date 5)  # f96
    local date_plus_6=$(get_date_with_offset $base_date 6)  # f120
    local date_plus_7=$(get_date_with_offset $base_date 7)  # f144
    local date_plus_8=$(get_date_with_offset $base_date 8)  # f168
    local date_plus_9=$(get_date_with_offset $base_date 9)  # f192

    echo ""
    print_info "Date mappings:"
    echo "  n00  -> $current_date (previous day nowcast)"
    echo "  f00  -> $date_plus_1 (current day nowcast)"
    echo "  f24  -> $date_plus_2"
    echo "  f48  -> $date_plus_3"
    echo "  f72  -> $date_plus_4"
    echo "  f96  -> $date_plus_5"
    echo "  f120 -> $date_plus_6"
    echo "  f144 -> $date_plus_7"
    echo "  f168 -> $date_plus_8"
    echo "  f192 -> $date_plus_9"

    echo ""
    print_info "Checking for required files..."

    # Check which files exist
    local has_n00=false
    local has_f00=false

    if [[ -f "$INPUT_DIR/rtofs_glo.t00z.n00.archv.a" ]]; then
        has_n00=true
        echo "  [OK] Found n00 files"
    fi

    if [[ -f "$INPUT_DIR/rtofs_glo.t00z.f00.archv.a" ]]; then
        has_f00=true
        echo "  [OK] Found f00 files"
    fi

    if [[ "$has_n00" == false ]]; then
        print_error "  [ERROR] Missing n00 files!"
    fi

    if [[ "$has_f00" == false ]]; then
        print_warning "  [WARN] Missing f00 files - will skip"
    fi

    echo ""
    print_info "Renaming files..."

    # Rename n00 files (base date - previous day's nowcast)
    if [[ "$has_n00" == true ]]; then
        rename_file "rtofs_glo.t00z.n00.archv.a" "rtofs_glo.t00z.n00.archv.${current_date}.a"
        rename_file "rtofs_glo.t00z.n00.archv.b" "rtofs_glo.t00z.n00.archv.${current_date}.b"
    fi

    # Rename f00 files (base date + 1 day - current day's nowcast)
    if [[ "$has_f00" == true ]]; then
        rename_file "rtofs_glo.t00z.f00.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_1}.a"
        rename_file "rtofs_glo.t00z.f00.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_1}.b"
    fi

    # Rename f24 files (base date + 2 days)
    rename_file "rtofs_glo.t00z.f24.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_2}.a"
    rename_file "rtofs_glo.t00z.f24.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_2}.b"

    # Rename f48 files (base date + 3 days)
    rename_file "rtofs_glo.t00z.f48.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_3}.a"
    rename_file "rtofs_glo.t00z.f48.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_3}.b"

    # Rename f72 files (base date + 4 days)
    rename_file "rtofs_glo.t00z.f72.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_4}.a"
    rename_file "rtofs_glo.t00z.f72.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_4}.b"

    # Rename f96 files (base date + 5 days)
    rename_file "rtofs_glo.t00z.f96.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_5}.a"
    rename_file "rtofs_glo.t00z.f96.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_5}.b"

    # Rename f120 files (base date + 6 days)
    rename_file "rtofs_glo.t00z.f120.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_6}.a"
    rename_file "rtofs_glo.t00z.f120.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_6}.b"

    # Rename f144 files (base date + 7 days)
    rename_file "rtofs_glo.t00z.f144.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_7}.a"
    rename_file "rtofs_glo.t00z.f144.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_7}.b"

    # Rename f168 files (base date + 8 days)
    rename_file "rtofs_glo.t00z.f168.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_8}.a"
    rename_file "rtofs_glo.t00z.f168.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_8}.b"

    # Rename f192 files (base date + 9 days)
    rename_file "rtofs_glo.t00z.f192.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_9}.a"
    rename_file "rtofs_glo.t00z.f192.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_9}.b"

    echo ""
    print_info "File processing complete!"

    # Verify final files
    echo ""
    print_info "Verification of renamed files:"
    local expected_dates=("$current_date" "$date_plus_1" "$date_plus_2" "$date_plus_3" "$date_plus_4" "$date_plus_5" "$date_plus_6" "$date_plus_7" "$date_plus_8" "$date_plus_9")
    local all_good=true

    for date in "${expected_dates[@]}"; do
        if [[ -f "$INPUT_DIR/rtofs_glo.t00z.n00.archv.${date}.a" ]] && [[ -f "$INPUT_DIR/rtofs_glo.t00z.n00.archv.${date}.b" ]]; then
            echo "  [OK] ${date}: Found both .a and .b files"
        else
            echo "  [MISSING] ${date}: Missing files"
            all_good=false
        fi
    done

    # Summary
    echo ""
    echo "=================================================="
    echo "Processing Summary:"
    echo "  Directory: $INPUT_DIR"
    echo "  Base date: $base_date"
    echo "  Date range: $current_date to $date_plus_9"
    if [[ "$has_f00" == false ]]; then
        echo "  WARNING: f00 files were not found/processed"
    fi
    echo "=================================================="

    if [[ "$all_good" == true ]]; then
        print_info "[SUCCESS] All file operations completed successfully!"
    else
        print_warning "[WARNING] Some files may be missing - check the verification above"
    fi
}

# Handle interruption
trap 'echo -e "\n\nFile processing interrupted by user."; exit 1' INT

# Run main function with all arguments
main "$@"
