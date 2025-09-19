#!/bin/bash
# copy script for RTOFS data with test.inp and ogcm_data.txt generation
# Usage: ./copy_nco_data.sh YYYYMMDD
# Example: ./copy_nco_data.sh 20250905
#
# For forecast cycle 20250905 00 UTC:
# - n00 file from 20250904 directory (previous day's nowcast)
# - n00 file from 20250905 directory (current day's nowcast)
# - f24-f192 files from 20250905 directory (current day's forecast)
# modified script from UND Fort11 by mansur.jisan@noaa.gov

set -e

# Check arguments
if [[ $# -ne 1 ]]; then
    echo "Error: Please provide a date in YYYYMMDD format"
    echo "Usage: $0 YYYYMMDD"
    echo "Example: $0 20250905"
    exit 1
fi

TARGET_DATE="$1"

# Calculate previous day for n00 file
PREV_DATE=$(date -d "${TARGET_DATE:0:4}-${TARGET_DATE:4:2}-${TARGET_DATE:6:2} - 1 day" +%Y%m%d)

# NCO paths
NCO_PATH_PREV="/lfs/h1/ops/prod/com/rtofs/v2.5/rtofs.${PREV_DATE}"
NCO_PATH_CURR="/lfs/h1/ops/prod/com/rtofs/v2.5/rtofs.${TARGET_DATE}"
DEST_DIR="bcdownloads"
SIM_DIR="bcdownloads/GLBy0.08"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

print_source() {
    echo -e "${CYAN}[SOURCE: $1]${NC}"
}

print_debug() {
    echo -e "${BLUE}[DEBUG] $1${NC}"
}

echo "========================================="
echo "WCOSS2 RTOFS Data Copy Script"
echo "========================================="
echo "Forecast cycle date: $TARGET_DATE"
echo "Previous day (for first n00): $PREV_DATE"
echo ""
echo "Source directories:"
echo "  n00 (day -1) from: $NCO_PATH_PREV"
echo "  n00 (day 0) and forecasts from: $NCO_PATH_CURR"
echo "Destination: $DEST_DIR"

# Check if source directories exist
if [[ ! -d "$NCO_PATH_PREV" ]]; then
    print_error "Error: Previous day directory not found: $NCO_PATH_PREV"
    echo "Available directories:"
    ls /lfs/h1/ops/prod/com/rtofs/v2.5/ | grep rtofs | tail -10
    exit 1
fi

if [[ ! -d "$NCO_PATH_CURR" ]]; then
    print_error "Error: Current day directory not found: $NCO_PATH_CURR"
    echo "Available directories:"
    ls /lfs/h1/ops/prod/com/rtofs/v2.5/ | grep rtofs | tail -10
    exit 1
fi

# Create destination directories
mkdir -p "$DEST_DIR"
mkdir -p "$SIM_DIR"

# Clean up existing files in GLBy0.08
if [[ -d "$SIM_DIR" ]]; then
    echo "Cleaning up existing files in $SIM_DIR..."
    rm -f "$SIM_DIR/bcforcing_ver6p2.nc" 2>/dev/null || true
    rm -f "$SIM_DIR"/rtofs_glo.t00z.n00.archv.* 2>/dev/null || true
fi

# Clean up existing .a and .b files in bcdownloads
if [[ -d "$DEST_DIR" ]]; then
    print_info "Cleaning up existing .a and .b files in $DEST_DIR..."
    rm -f "$DEST_DIR"/*.a "$DEST_DIR"/*.b 2>/dev/null || true
fi

# Step 1: Copy n00 file from previous day (this will be the "n00" in the final set)
echo ""
print_info "==== STEP 1: Copying n00 from PREVIOUS day ===="
print_source "$NCO_PATH_PREV"
for ext in a b; do
    SOURCE_FILE="${NCO_PATH_PREV}/rtofs_glo.t00z.n00.archv.${ext}"
    DEST_FILE="${DEST_DIR}/rtofs_glo.t00z.n00.archv.${ext}"
    if [[ -f "$SOURCE_FILE" ]]; then
        print_debug "Source: $SOURCE_FILE"
        print_debug "Dest:   $DEST_FILE"
        echo "  Copying: rtofs_glo.t00z.n00.archv.${ext} (from $PREV_DATE)"
        cp "$SOURCE_FILE" "$DEST_FILE"
    else
        print_error "  Error: n00 file not found: $SOURCE_FILE"
        exit 1
    fi
done

# Step 2: Copy n00 file from current day as f00
echo ""
print_info "==== STEP 2: Copying n00 from CURRENT day as f00 ===="
print_source "$NCO_PATH_CURR"
for ext in a b; do
    SOURCE_FILE="${NCO_PATH_CURR}/rtofs_glo.t00z.n00.archv.${ext}"
    DEST_FILE="${DEST_DIR}/rtofs_glo.t00z.f00.archv.${ext}"
    if [[ -f "$SOURCE_FILE" ]]; then
        print_debug "Source: $SOURCE_FILE"
        print_debug "Dest:   $DEST_FILE"
        echo "  Copying: rtofs_glo.t00z.n00.archv.${ext} -> f00.archv.${ext}"
        cp "$SOURCE_FILE" "$DEST_FILE"
    else
        print_error "  Error: n00 file not found: $SOURCE_FILE"
        exit 1
    fi
done

# Step 3: Copy forecast files from current day (including real f156, f168, f192)
echo ""
print_info "==== STEP 3: Copying forecast files from CURRENT day ===="
print_source "$NCO_PATH_CURR"
FORECAST_HOURS="f24 f48 f72 f96 f120 f144 f168 f192"
for hour in $FORECAST_HOURS; do
    for ext in a b; do
        SOURCE_FILE="${NCO_PATH_CURR}/rtofs_glo.t00z.${hour}.archv.${ext}"
        DEST_FILE="${DEST_DIR}/rtofs_glo.t00z.${hour}.archv.${ext}"
        if [[ -f "$SOURCE_FILE" ]]; then
            echo "  Copying: rtofs_glo.t00z.${hour}.archv.${ext}"
            if [[ "$hour" == "f24" && "$ext" == "a" ]]; then
                # Show debug info for first forecast file
                print_debug "Source: $SOURCE_FILE"
                print_debug "Dest:   $DEST_FILE"
            fi
            cp "$SOURCE_FILE" "$DEST_FILE"
        else
            print_warning "  Warning: File not found: $SOURCE_FILE"
        fi
    done
done

# --- Generate test.inp file ---
echo ""
print_info "Creating test.inp file..."

# Calculate dates based on the PREVIOUS day (since first n00 is from previous day)
YEAR=${PREV_DATE:0:4}
MONTH=${PREV_DATE:4:2}
DAY=${PREV_DATE:6:2}
START_DATE_FORMATTED="${YEAR}-${MONTH}-${DAY}"

# Calculate start and end dates for test.inp
# Start from previous day, end 10 days later (9 days after start)
START_DATETIME_TEST_INP="${START_DATE_FORMATTED} 00:00"
END_DATETIME_TEST_INP=$(date -d "${START_DATE_FORMATTED} + 9 days" +"%Y-%m-%d 00:00")

# Create test.inp file
cat > "$SIM_DIR/test.inp" <<EOF
# 1st Line is Comment: Control File Template
$START_DATETIME_TEST_INP ! Start datetime (YYYY-MM-DD HH:mm)
$END_DATETIME_TEST_INP ! End datetime (YYYY-MM-DD HH:mm)
8 ! DT multiplier: DT is 3 hrs for GOFS 3.1 so 8 indicates 24 hr output
ftp ! The server to download from (ftp -or- ncs -or- opd)
3 ! Output type, = 1 for T & S attributes only, = 2 for T,S,U,V attributes, = 3 for all
bathyfixed.14
bcforcing_ver6p2.nc
EOF

print_info "test.inp created at: $SIM_DIR/test.inp"

# --- Generate ogcm_data.txt file ---
echo ""
print_info "Creating ogcm_data.txt file..."

# Number of entries (10 days starting from PREV_DATE)
NUM_OGCM_ENTRIES=10
echo "$NUM_OGCM_ENTRIES" > "$SIM_DIR/ogcm_data.txt"

for i in $(seq 0 9); do
    CURRENT_OGCM_DATE_YYYYMMDD=$(date -d "${START_DATE_FORMATTED} + $i days" +"%Y%m%d")
    CURRENT_OGCM_DATE_FORMATTED=$(date -d "${START_DATE_FORMATTED} + $i days" +"%Y-%m-%d 00:00")
    echo "'$CURRENT_OGCM_DATE_FORMATTED' rtofs_glo.t00z.n00.archv.$CURRENT_OGCM_DATE_YYYYMMDD.nc dmy dmy" >> "$SIM_DIR/ogcm_data.txt"
done

print_info "ogcm_data.txt created at: $SIM_DIR/ogcm_data.txt"

# --- Summary ---
echo ""
echo "========================================="
print_info "Copy and file generation complete!"
echo "========================================="
echo "Files copied to: $DEST_DIR"
echo "Configuration files created in: $SIM_DIR"
echo ""
echo "Data coverage summary:"
echo "  - n00: from $NCO_PATH_PREV"
echo "  - f00: from $NCO_PATH_CURR (n00 renamed)"
echo "  - f24-f192: from $NCO_PATH_CURR"
echo ""
echo "File mapping (source -> destination):"
echo "  ${PREV_DATE}/n00 -> n00"
echo "  ${TARGET_DATE}/n00 -> f00"
echo "  ${TARGET_DATE}/f24 -> f24"
echo "  ${TARGET_DATE}/f48 -> f48"
echo "  ${TARGET_DATE}/f72 -> f72"
echo "  ${TARGET_DATE}/f96 -> f96"
echo "  ${TARGET_DATE}/f120 -> f120"
echo "  ${TARGET_DATE}/f144 -> f144"
echo "  ${TARGET_DATE}/f168 -> f168"
echo "  ${TARGET_DATE}/f192 -> f192"
echo ""
echo "Final time coverage after rtofs_rename.sh will be:"
echo "  - Day 0: $PREV_DATE (n00 from previous day)"
echo "  - Day 1: $TARGET_DATE (n00 from current day as f00)"
echo "  - Day 2-8: Forecasts from $TARGET_DATE"
echo ""

# Check if files were created
if [[ -f "$SIM_DIR/test.inp" ]]; then
    echo "test.inp contents:"
    echo "-------------------"
    cat "$SIM_DIR/test.inp"
    echo ""
else
    print_error "ERROR: test.inp was not created!"
fi

if [[ -f "$SIM_DIR/ogcm_data.txt" ]]; then
    echo "ogcm_data.txt contents:"
    echo "-------------------"
    cat "$SIM_DIR/ogcm_data.txt"
    echo ""
else
    print_error "ERROR: ogcm_data.txt was not created!"
fi

# List files with count
echo "Files in $DEST_DIR:"
echo "-------------------"
TOTAL_FILES=$(ls "$DEST_DIR/"*.a "$DEST_DIR/"*.b 2>/dev/null | wc -l || echo "0")
echo "Total .a and .b files: $TOTAL_FILES"

# Verify all expected files
echo ""
echo "File verification:"
EXPECTED_HOURS="n00 f00 f24 f48 f72 f96 f120 f144 f168 f192"
for hour in $EXPECTED_HOURS; do
    for ext in a b; do
        FILE="${DEST_DIR}/rtofs_glo.t00z.${hour}.archv.${ext}"
        if [[ -f "$FILE" ]]; then
            echo "  OK: ${hour}.${ext}"
        else
            echo "  MISSING: ${hour}.${ext}"
        fi
    done
done

echo ""
echo "========================================="
print_info "Ready for next steps in the pipeline"
echo "Next steps:"
echo "  2) Run: ./rtofs_rename.sh"
echo "  3) Run: ./dlv3_array.sh"
echo "  4) Run: ./OGCM_DL.a < test.inp"
echo "========================================="
EOF
