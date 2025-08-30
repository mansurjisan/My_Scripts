#!/bin/bash

# Simple script to copy RTOFS files between directories
# Usage: ./download_extra_nowcasts.sh DATE DATE
# Example: ./download_extra_nowcasts.sh 20250715 20250715

set -e

# Check arguments
if [[ $# -ne 2 ]]; then
    echo "Error: Incorrect number of arguments."
    echo "Usage: $0 DATE DATE"
    echo "Example: $0 20250715 20250715"
    exit 1
fi

date1="$1"
date2="$2"

# Validate date format
if ! [[ "$date1" =~ ^[0-9]{8}$ && "$date2" =~ ^[0-9]{8}$ ]]; then
    echo "Error: Dates must be in YYYYMMDD format."
    exit 1
fi

# Check if dates are the same
if [[ "$date1" != "$date2" ]]; then
    echo "Error: Both dates must be the same."
    exit 1
fi

# Calculate date + 1 day
next_day=$(date -d "$date1 + 1 day" +%Y%m%d)

# Define directories
source_dir="/asclepius/acerrone/baroclinic_shadow/preprocessing/bcdownloads"
archive_dir="/asclepius/acerrone/baroclinic_shadow/preprocessing/bcdownloads/nowcast_archive"

# Create archive directory if it doesn't exist
mkdir -p "$archive_dir"

echo "Processing date: $date1"
echo "Next day: $next_day"

# Step 1: Copy files with date+1 to archive directory
echo "Copying files with date+1 to archive directory..."
cp "$source_dir/rtofs_glo.t00z.n00.archv.${next_day}.a" "$archive_dir/" 2>/dev/null || echo "Warning: Could not copy ${next_day}.a file"
cp "$source_dir/rtofs_glo.t00z.n00.archv.${next_day}.b" "$archive_dir/" 2>/dev/null || echo "Warning: Could not copy ${next_day}.b file"

# Step 2: Copy files with input date from archive to main directory
echo "Copying files with input date from archive to main directory..."
cp "$archive_dir/rtofs_glo.t00z.n00.archv.${date1}.a" "$source_dir/" 2>/dev/null || echo "Warning: Could not copy ${date1}.a file from archive"
cp "$archive_dir/rtofs_glo.t00z.n00.archv.${date1}.b" "$source_dir/" 2>/dev/null || echo "Warning: Could not copy ${date1}.b file from archive"

echo "File operations completed."
