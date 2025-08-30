#!/bin/bash

# Submit a job array with 11 tasks
#$ -t 1-10

# Load necessary modules
module load intel
module load netcdf
module load mvapich2

# Set environment variables
export DATA=/asclepius/acerrone/baroclinic_shadow/preprocessing/bcdownloads
export ArchvEXECestofs=/asclepius/acerrone/baroclinic_shadow/preprocessing/HYCOM-tools/subregion/src

# --- Date Calculation ---
# Set the overall start date for the job series to the previous day's date
start_date=$(date -d "yesterday" +%Y%m%d)

# Calculate the specific date for this array task
offset=$(($SGE_TASK_ID - 1))
current_date=$(date -d "$start_date + $offset days" +%Y%m%d)

echo "Running task $SGE_TASK_ID for date: $current_date"

# --- Main Commands ---
# Define the output file based on the calculated date
outfileb="rtofs_glo.t00z.n00.archv.$current_date"

# Execute the commands for this single date
csh isubaregion_nd_m.csh $outfileb
# Pass both the outfile and the date to the second script
csh archv2ncdf3z_nd_m.csh $outfileb $current_date

echo "Finished task for date: $current_date"
