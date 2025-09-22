#!/bin/bash
# comparison_workflow.sh

echo "=== Complete Wind Speed Comparison Workflow ==="

# 1. Generate FORT.222 wind speed snapshots
echo -e "\n[1/4] Generating FORT.222 wind speed snapshots..."
python plot_fort222.py fort.222.nc WIND_SPEED_10m \
    --mode snapshots \
    --region custom --lon-range -85 -65 --lat-range 25 45 \
    --colormap jet \
    --smooth \
    --color-levels 50 \
    --dpi 300 \
    --vmin 0 --vmax 30 \
    --coastlines \
    --output-dir wind_snapshots_FORT

# 2. Generate STOFS wind speed snapshots (every 3 hours to match FORT)
echo -e "\n[2/4] Generating STOFS wind speed snapshots..."
python plot_fort222.py stofs_2d_glo_fcst1.222.nc WIND_SPEED_10m \
    --mode snapshots \
    --time-step 3 \
    --region custom --lon-range -85 -65 --lat-range 25 45 \
    --colormap jet \
    --smooth \
    --color-levels 50 \
    --dpi 300 \
    --vmin 0 --vmax 30 \
    --coastlines \
    --output-dir wind_snapshots_STOFS

# 3. Generate difference plots
echo -e "\n[3/4] Generating difference plots"
mkdir -p difference_plots

# Get number of FORT time steps 
MAX_FORT_STEPS=56  # Adjust based on input data

for fort_idx in $(seq 0 $((MAX_FORT_STEPS - 1))); do
    stofs_idx=$((fort_idx * 3))
    hour=$((fort_idx * 3))
    hour_str=$(printf "%03d" $hour)
    
    echo "  Processing hour ${hour}..."
    
    python plot_fort222_diff.py fort.222.nc WIND_SPEED_10m \
        --mode difference \
        --file2 stofs_2d_glo_fcst1.222.nc \
        --time1 $fort_idx \
        --time2 $stofs_idx \
        --region custom --lon-range -85 -65 --lat-range 25 45 \
        --colormap RdBu_r \
        --smooth \
        --color-levels 50 \
        --dpi 300 \
        --vmin -5 --vmax 5 \
        --coastlines \
        --save "difference_plots/diff_h${hour_str}.png"
done

# 4. Combine into three-panel images
echo -e "\n[4/4] Creating combined three-panel images..."
python combine_panels.py wind_snapshots_FORT wind_snapshots_STOFS difference_plots combined_panels

echo -e "\n=== Workflow Complete ==="
echo "Individual FORT snapshots: wind_snapshots_FORT/"
echo "Individual STOFS snapshots: wind_snapshots_STOFS/"
echo "Difference plots: difference_plots/"
echo "Combined panels: combined_panels/"

# Optional: Create animations
echo -e "\nCreating animations..."
convert -delay 20 -loop 0 combined_panels/combined_h*.png combined_panels/animation_combined.gif
echo "Combined animation: combined_panels/animation_combined.gif"
