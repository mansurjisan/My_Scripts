#!/bin/bash
# Generate enhanced style plots for all regions and cycles
# Features: Custom colormap, 300 DPI, full-length colorbar, no contour lines

source /home/mjisan/miniconda3/bin/activate xesmf_env

DATE=$1
BASE_DIR="/mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/${DATE}"
SCRIPT_DIR="/mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL"

# Check if date directory exists
if [ ! -d "$BASE_DIR" ]; then
    echo "Directory $BASE_DIR does not exist!"
    exit 1
fi

# Region definitions: name:lon_min:lon_max:lat_min:lat_max:label:vmin:vmax
REGIONS=(
    "us_east_coast:-82:-65:25:45:US East Coast:-0.3:0.3"
    "chesapeake_bay:-77.5:-75.5:36.6:39.7:Chesapeake Bay:-0.3:0.3"
    "new_york_harbor:-74.5:-71.5:40.0:41.5:New York Harbor:-0.3:0.3"
    "boston_harbor:-71.5:-69.5:41.5:43.0:Boston Harbor:-0.3:0.3"
    "delaware_bay:-76.0:-74.5:38.5:40.0:Delaware Bay:-0.3:0.3"
    "tampa_bay:-83.0:-81.5:26.0:28.5:Tampa Bay:-0.3:0.3"
    "galveston_bay:-95.5:-94.0:29.0:30.0:Galveston Bay:-0.5:0.5"
    "mobile_bay:-88.5:-87.0:30.0:31.0:Mobile Bay:-0.5:0.5"
    "puget_sound:-123.5:-122.0:47.0:48.5:Puget Sound:-0.3:0.3"
    "puerto_rico:-67.5:-65.0:17.5:18.8:Puerto Rico:-0.3:0.3"
    "conus:-130:-60:20:55:CONUS:-0.3:0.3"
    "global:-180:180:-90:90:Global:-0.3:0.3"
)

CYCLES=("00" "06" "12" "18")

# Extract year, month, day from date
YEAR="${DATE:0:4}"
MONTH="${DATE:4:2}"
DAY="${DATE:6:2}"

for cycle in "${CYCLES[@]}"; do
    echo "=== Processing t${cycle}z ==="

    NOANOMALY="${BASE_DIR}/stofs_2d_glo.t${cycle}z.fields.cwl.maxele.noanomaly.nc"
    ANOMALY="${BASE_DIR}/stofs_2d_glo.t${cycle}z.fields.cwl.maxele.nc"

    if [ ! -f "$NOANOMALY" ] || [ ! -f "$ANOMALY" ]; then
        echo "  Skipping t${cycle}z - files not found"
        continue
    fi

    # Create output directory
    OUTPUT_DIR="${BASE_DIR}/plots/${DATE}_${cycle}z"
    mkdir -p "$OUTPUT_DIR"

    FORECAST_TIME="${YEAR}-${MONTH}-${DAY} ${cycle}:00 UTC"

    for region_def in "${REGIONS[@]}"; do
        IFS=':' read -r name lon_min lon_max lat_min lat_max label vmin vmax <<< "$region_def"

        OUTPUT="${OUTPUT_DIR}/t${cycle}z_${name}_enhanced.png"

        echo "  Generating: ${label} (t${cycle}z)"

        python "${SCRIPT_DIR}/plot_enhanced_style.py" \
            "$NOANOMALY" \
            "$ANOMALY" \
            --output "$OUTPUT" \
            --lon-range $lon_min $lon_max \
            --lat-range $lat_min $lat_max \
            --location-name "$label" \
            --forecast-time "$FORECAST_TIME" \
            --vmin $vmin --vmax $vmax 2>&1 | grep -v "^$"
    done
done

echo "=== Done ==="
