#!/bin/bash

# RTOFS File Renaming and Copying Script
# Renames forecast files to date-based naming and creates additional day copies

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

# Function to get date with offset
get_date_with_offset() {
    local days_offset=$1
    date -d "+${days_offset} days" +%Y%m%d
}

# Function to rename file
rename_file() {
    local old_name="$1"
    local new_name="$2"
    
    if [[ -f "$INPUT_DIR/$old_name" ]]; then
        mv "$INPUT_DIR/$old_name" "$INPUT_DIR/$new_name"
        print_info "✓ Renamed: $old_name → $new_name"
        return 0
    else
        print_warning "⚠ File not found: $old_name"
        return 1
    fi
}

# Function to copy file
copy_file() {
    local source="$1"
    local target="$2"
    
    if [[ -f "$INPUT_DIR/$source" ]]; then
        cp "$INPUT_DIR/$source" "$INPUT_DIR/$target"
        print_info "✓ Copied: $source → $target"
        return 0
    else
        print_warning "⚠ Source file not found: $source"
        return 1
    fi
}

# Main function
main() {
    print_info "Starting RTOFS file renaming and copying process..."
    
    # Check if input directory exists
    if [[ ! -d "$INPUT_DIR" ]]; then
        print_error "Error: Directory $INPUT_DIR does not exist!"
        exit 1
    fi
    
    # Get current date and calculate dates for each day
    local current_date=$(date +%Y%m%d)
    local date_plus_1=$(get_date_with_offset 1)
    local date_plus_2=$(get_date_with_offset 2)
    local date_plus_3=$(get_date_with_offset 3)
    local date_plus_4=$(get_date_with_offset 4)
    local date_plus_5=$(get_date_with_offset 5)
    local date_plus_6=$(get_date_with_offset 6)
    local date_plus_7=$(get_date_with_offset 7)
    local date_plus_8=$(get_date_with_offset 8)
    
    print_info "Current date: $current_date"
    print_info "Date mappings:"
    echo "  Current date: $current_date"
    echo "  Current date + 1 day: $date_plus_1"
    echo "  Current date + 2 days: $date_plus_2"
    echo "  Current date + 3 days: $date_plus_3"
    echo "  Current date + 4 days: $date_plus_4"
    echo "  Current date + 5 days: $date_plus_5"
    echo "  Current date + 6 days: $date_plus_6"
    echo "  Current date + 7 days: $date_plus_7"
    echo "  Current date + 8 days: $date_plus_8"
    
    echo
    print_info "Renaming files..."
    
    # Rename n00 files (current date)
    rename_file "rtofs_glo.t00z.n00.archv.a" "rtofs_glo.t00z.n00.archv.${current_date}.a"
    rename_file "rtofs_glo.t00z.n00.archv.b" "rtofs_glo.t00z.n00.archv.${current_date}.b"
    
    # Rename f24 files (current date + 1 day)
    rename_file "rtofs_glo.t00z.f24.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_1}.a"
    rename_file "rtofs_glo.t00z.f24.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_1}.b"
    
    # Rename f48 files (current date + 2 days)
    rename_file "rtofs_glo.t00z.f48.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_2}.a"
    rename_file "rtofs_glo.t00z.f48.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_2}.b"
    
    # Rename f72 files (current date + 3 days)
    rename_file "rtofs_glo.t00z.f72.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_3}.a"
    rename_file "rtofs_glo.t00z.f72.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_3}.b"
    
    # Rename f96 files (current date + 4 days)
    rename_file "rtofs_glo.t00z.f96.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_4}.a"
    rename_file "rtofs_glo.t00z.f96.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_4}.b"
    
    # Rename f120 files (current date + 5 days)
    rename_file "rtofs_glo.t00z.f120.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_5}.a"
    rename_file "rtofs_glo.t00z.f120.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_5}.b"
    
    # Rename f144 files (current date + 6 days)
    rename_file "rtofs_glo.t00z.f144.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_6}.a"
    rename_file "rtofs_glo.t00z.f144.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_6}.b"
    
    # Rename f156 files (current date + 7 days)
    rename_file "rtofs_glo.t00z.f156.archv.a" "rtofs_glo.t00z.n00.archv.${date_plus_7}.a"
    rename_file "rtofs_glo.t00z.f156.archv.b" "rtofs_glo.t00z.n00.archv.${date_plus_7}.b"
    
    echo
    print_info "Copying files for day +8..."
    
    # Copy day +7 files to create day +8 files
    copy_file "rtofs_glo.t00z.n00.archv.${date_plus_7}.a" "rtofs_glo.t00z.n00.archv.${date_plus_8}.a"
    copy_file "rtofs_glo.t00z.n00.archv.${date_plus_7}.b" "rtofs_glo.t00z.n00.archv.${date_plus_8}.b"
    
    echo
    print_info "File processing complete!"
    
    # Summary
    echo
    echo "=================================================="
    echo "Processing Summary:"
    echo "  Directory: $INPUT_DIR"
    echo "  Files renamed from forecast format to date format"
    echo "  Additional day +8 files created from day +7 files"
    echo "=================================================="
    
    print_info "✓ All file operations completed successfully!"
}

# Handle interruption
trap 'echo -e "\n\nFile processing interrupted by user."; exit 1' INT

# Run main function
main "$@" 
