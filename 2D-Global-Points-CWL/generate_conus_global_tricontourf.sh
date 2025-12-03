#!/bin/bash
# Generate tricontourf plots for CONUS and Global domains

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

# Large domain definitions: name:lon_min:lon_max:lat_min:lat_max:label
DOMAINS=(
    "conus:-130:-60:20:55:CONUS"
    "global:-180:180:-90:90:Global"
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

    for domain_def in "${DOMAINS[@]}"; do
        IFS=':' read -r name lon_min lon_max lat_min lat_max label <<< "$domain_def"

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
