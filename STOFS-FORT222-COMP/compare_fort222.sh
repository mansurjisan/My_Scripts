#!/bin/bash
# compare_all_timesteps.sh

# File paths
FORT_FILE="fort.222.nc"
STOFS_FILE="stofs_2d_glo_fcst1.222.nc"
PLOT_SCRIPT="fort222_comparisons.py"

# Output directory
OUTPUT_DIR="difference_plots"
mkdir -p $OUTPUT_DIR

# Fort.222 has 3-hourly data, STOFS has hourly data
# Assuming both start at the same time (t=0)

# Number of time steps in fort.222 (3-hourly)
# We need to adjust this based on actual file
MAX_FORT_STEPS=56  # Example: 56 steps = 168 hours = 7 days

# Loop through fort.222 time indices
for fort_idx in $(seq 0 $((MAX_FORT_STEPS - 1))); do
    # Calculate corresponding STOFS index (hourly data)
    # fort_idx * 3 = hours from start = stofs_idx
    stofs_idx=$((fort_idx * 3))
    
    # Calculate the hour for the filename
    hour=$((fort_idx * 3))
    
    # Format hour with leading zeros (3 digits)
    hour_str=$(printf "%03d" $hour)
    
    echo "Processing: Fort.222 index $fort_idx (hour $hour) vs STOFS index $stofs_idx"
    
    # Run the plotting command
    python $PLOT_SCRIPT $FORT_FILE WIND_SPEED_10m \
        --mode difference \
        --file2 $STOFS_FILE \
        --time1 $fort_idx \
        --time2 $stofs_idx \
        --region custom --lon-range -85 -65 --lat-range 25 45 \
        --colormap RdBu_r \
        --smooth \
        --color-levels 50 \
        --dpi 300 \
        --vmin -5 --vmax 5 \
        --coastlines \
        --save "${OUTPUT_DIR}/diff_h${hour_str}.png"
    
    # Check if the command was successful
    if [ $? -ne 0 ]; then
        echo "Error processing hour $hour"
        # Optionally break or continue
        # break
    fi
done

echo "All difference plots generated in $OUTPUT_DIR/"
