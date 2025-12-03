#!/bin/bash
# Generate tricontourf plots for all regions and cycles

source /home/mjisan/miniconda3/bin/activate xesmf_env

DATE=$1
BASE_DIR="/mnt/d/STOFS2D-Analysis/MAXELE_PLOTS/${DATE}"
SCRIPT_DIR="/mnt/d/STOFS2D-Analysis/My_Scripts/2D-Global-Points-CWL"

# Check if date directory exists
if [ ! -d "$BASE_DIR" ]; then
    echo "Directory $BASE_DIR does not exist!"
    exit 1
fi

mkdir -p "${BASE_DIR}/plots"

# Region definitions: name:lon_min:lon_max:lat_min:lat_max:label
REGIONS=(
    "us_east_coast:-82:-65:25:45:US East Coast"
    "chesapeake_bay:-77.5:-75.5:36.6:39.7:Chesapeake Bay"
    "new_york_harbor:-74.5:-71.5:40.0:41.5:New York Harbor"
    "boston_harbor:-71.5:-69.5:41.5:43.0:Boston Harbor"
    "delaware_bay:-76.0:-74.5:38.5:40.0:Delaware Bay"
    "tampa_bay:-83.0:-81.5:26.0:28.5:Tampa Bay"
    "galveston_bay:-95.5:-94.0:29.0:30.0:Galveston Bay"
    "mobile_bay:-88.5:-87.0:30.0:31.0:Mobile Bay"
    "puget_sound:-123.5:-122.0:47.0:48.5:Puget Sound"
    "puerto_rico:-67.5:-65.0:17.5:18.8:Puerto Rico"
)

CYCLES=("00" "06" "12" "18")

for cycle in "${CYCLES[@]}"; do
    echo "=== Processing t${cycle}z ==="

    NOANOMALY="${BASE_DIR}/stofs_2d_glo.t${cycle}z.fields.cwl.maxele.noanomaly.nc"
    ANOMALY="${BASE_DIR}/stofs_2d_glo.t${cycle}z.fields.cwl.maxele.nc"

    if [ ! -f "$NOANOMALY" ] || [ ! -f "$ANOMALY" ]; then
        echo "  Skipping t${cycle}z - files not found"
        continue
    fi

    for region_def in "${REGIONS[@]}"; do
        IFS=':' read -r name lon_min lon_max lat_min lat_max label <<< "$region_def"

        OUTPUT="${BASE_DIR}/plots/t${cycle}z_${name}_tricontourf.png"

        echo "  Generating: ${label} (t${cycle}z)"

        python "${SCRIPT_DIR}/plot_difference_maxele_enhanced.py" \
            "$NOANOMALY" \
            "$ANOMALY" \
            zeta_max \
            --region custom \
            --lon-range $lon_min $lon_max \
            --lat-range $lat_min $lat_max \
            --vmin -0.5 --vmax 0.5 \
            --no-individual \
            --max-points 0 \
            --use-tricontourf \
            --location-name "$label" \
            --save "$OUTPUT" 2>&1 | grep -E "(Plot saved|Error|Warning)"
    done
done

echo "=== Done ==="
