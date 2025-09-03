#h

# Simple copy script for RTOFS data
# Usage: ./copy_nco_data.sh YYYYMMDD

set -e

if [[ $# -ne 1 ]]; then
    echo "Error: Please provide a date in YYYYMMDD format"
    echo "Usage: $0 YYYYMMDD"
    echo "Example: $0 20250829"
    exit 1
fi

TARGET_DATE="$1"
NCO_PATH="/lfs/h1/ops/prod/com/rtofs/v2.5/rtofs.${TARGET_DATE}"
DEST_DIR="bcdownloads"

echo "Copying RTOFS data for date: $TARGET_DATE"
echo "Source: $NCO_PATH"
echo "Destination: $DEST_DIR"

# Check if source exists
if [[ ! -d "$NCO_PATH" ]]; then
    echo "Error: Source directory not found: $NCO_PATH"
    echo "Available directories:"
    ls /lfs/h1/ops/prod/com/rtofs/v2.5/ | grep rtofs | tail -5
    exit 1
fi

# Create destination
mkdir -p "$DEST_DIR"

# Copy files
FORECAST_HOURS="n00 f24 f48 f72 f96 f120 f144 f156"

for hour in $FORECAST_HOURS; do
    for ext in a b; do
        SOURCE_FILE="${NCO_PATH}/rtofs_glo.t00z.${hour}.archv.${ext}"
        DEST_FILE="${DEST_DIR}/rtofs_glo.t00z.${hour}.archv.${ext}"

        if [[ -f "$SOURCE_FILE" ]]; then
            echo "Copying: rtofs_glo.t00z.${hour}.archv.${ext}"
            cp "$SOURCE_FILE" "$DEST_FILE"
        else
            echo "Warning: File not found: $SOURCE_FILE"
        fi
    done
done

echo "Copy complete. Files in $DEST_DIR:"
ls -la "$DEST_DIR/"
