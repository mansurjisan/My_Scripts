#!/bin/bash
# Interactive parallel processing script for PBS
# Usage: ./dlv3_array_pbs.sh [YYYYMMDD]
# Example: ./dlv3_array_pbs.sh 20250915

echo "=== INTERACTIVE PARALLEL PROCESSING STARTED ==="
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "Available cores: $(nproc)"

# Check for date parameter
if [[ $# -eq 1 ]]; then
    START_DATE="$1"
    # Validate date format
    if ! [[ "$START_DATE" =~ ^[0-9]{8}$ ]]; then
        echo "Error: Date must be in YYYYMMDD format."
        echo "Usage: $0 [YYYYMMDD]"
        exit 1
    fi
    echo "Using provided start date: $START_DATE"
else
    # Default to yesterday if no date provided
    START_DATE=$(date -d "yesterday" +%Y%m%d)
    echo "No date provided, using yesterday: $START_DATE"
fi

# Calculate end date (9 days after start date for 10 total days)
END_DATE=$(date -d "${START_DATE:0:4}-${START_DATE:4:2}-${START_DATE:6:2} + 9 days" +%Y%m%d)
echo "Processing range: $START_DATE to $END_DATE (10 days)"

# Load necessary modules for PBS - use the ones that were working
module purge
module purge
module load PrgEnv-intel
module load hdf5/1.10.6
module load netcdf/4.7.4

echo "=== Modules loaded ==="

# Set environment variables - Updated for your PBS system
export DATA=/lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/bcdownloads
export ArchvEXECestofs=/lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11/HYCOM-tools/archive/src

echo "=== Environment Variables ==="
echo "DATA: $DATA"
echo "ArchvEXECestofs: $ArchvEXECestofs"

# Change to working directory
cd /lfs/h1/nos/estofs/noscrub/mansur.jisan/Fort11

# Create output directory for logs
mkdir -p parallel_logs

# Function to process a single date
process_date() {
    local task_id=$1
    local start_date=$2
    local offset=$(($task_id - 1))
    local current_date=$(date -d "${start_date:0:4}-${start_date:4:2}-${start_date:6:2} + $offset days" +%Y%m%d)
    local outfileb="rtofs_glo.t00z.n00.archv.$current_date"

    echo "=== TASK $task_id: Processing $current_date ===" > parallel_logs/task_${task_id}.log
    echo "Started at: $(date)" >> parallel_logs/task_${task_id}.log

    # Check if input files exist
    if [[ ! -f "$DATA/${outfileb}.a" || ! -f "$DATA/${outfileb}.b" ]]; then
        echo "ERROR: Missing input files for $current_date" >> parallel_logs/task_${task_id}.log
        echo "Expected: $DATA/${outfileb}.a and $DATA/${outfileb}.b" >> parallel_logs/task_${task_id}.log
        return 1
    fi

    echo "Processing: $outfileb" >> parallel_logs/task_${task_id}.log

    # Run first command
    echo "Running isubaregion_nd_m.csh..." >> parallel_logs/task_${task_id}.log
    if csh isubaregion_nd_m.csh $outfileb >> parallel_logs/task_${task_id}.log 2>&1; then
        echo "SUCCESS: isubaregion completed successfully" >> parallel_logs/task_${task_id}.log
    else
        echo "ERROR: isubaregion failed" >> parallel_logs/task_${task_id}.log
        return 1
    fi

    # Run second command
    echo "Running archv2ncdf3z_nd_m.csh..." >> parallel_logs/task_${task_id}.log
    if csh archv2ncdf3z_nd_m.csh $outfileb $current_date >> parallel_logs/task_${task_id}.log 2>&1; then
        echo "SUCCESS: archv2ncdf3z completed successfully" >> parallel_logs/task_${task_id}.log

        # Check if NetCDF output was created
        expected_nc="${DATA}/GLBy0.08/${outfileb}.nc"
        if [[ -f "$expected_nc" ]]; then
            echo "OUTPUT: NetCDF file created: $expected_nc" >> parallel_logs/task_${task_id}.log
            ls -lh "$expected_nc" >> parallel_logs/task_${task_id}.log
        else
            echo "WARNING: Expected NetCDF file not found: $expected_nc" >> parallel_logs/task_${task_id}.log
        fi
    else
        echo "ERROR: archv2ncdf3z failed" >> parallel_logs/task_${task_id}.log
        return 1
    fi

    echo "Task $task_id completed successfully at: $(date)" >> parallel_logs/task_${task_id}.log
    echo "SUCCESS: Task $task_id (date: $current_date) completed successfully"
    return 0
}

# Export the function so background processes can use it
export -f process_date
export DATA ArchvEXECestofs START_DATE

echo "=== Starting parallel processing of 10 tasks ==="
echo "Processing dates from $START_DATE to $END_DATE"

# Process in batches of 6 to avoid memory issues
batch_size=6

echo "Processing in batches of $batch_size tasks..."

for ((batch_start=1; batch_start<=10; batch_start+=batch_size)); do
    batch_end=$((batch_start + batch_size - 1))
    if [ $batch_end -gt 10 ]; then
        batch_end=10
    fi

    echo "Processing batch: tasks $batch_start to $batch_end"

    # Launch current batch
    for task_id in $(seq $batch_start $batch_end); do
        process_date $task_id $START_DATE &
        echo "Started task $task_id in background (PID: $!)"
    done

    # Wait for current batch to complete before starting next
    wait
    echo "Batch $batch_start-$batch_end completed"
done

echo "=== All tasks finished ==="

# Summary
echo "=== PROCESSING SUMMARY ==="
successful=0
failed=0

for task_id in {1..10}; do
    if grep -q "completed successfully" parallel_logs/task_${task_id}.log 2>/dev/null; then
        ((successful++))
        echo "SUCCESS: Task $task_id"
    else
        ((failed++))
        echo "FAILED: Task $task_id"
    fi
done

echo ""
echo "Results:"
echo "  Successful tasks: $successful"
echo "  Failed tasks: $failed"
echo "  Total tasks: 10"
echo "  Date range: $START_DATE - $END_DATE"

if [[ $failed -eq 0 ]]; then
    echo "All tasks completed successfully!"
    echo ""
    echo "NetCDF files should be available in:"
    echo "$DATA/GLBy0.08/"
    ls -la "$DATA/GLBy0.08/"*.nc 2>/dev/null || echo "No NetCDF files found yet"
else
    echo "Some tasks failed. Check parallel_logs/task_*.log for details"
    echo ""
    echo "Failed task logs:"
    for task_id in {1..10}; do
        if ! grep -q "completed successfully" parallel_logs/task_${task_id}.log 2>/dev/null; then
            echo "--- Task $task_id log ---"
            tail -10 parallel_logs/task_${task_id}.log 2>/dev/null || echo "Log file not found"
        fi
    done
fi

echo "=== INTERACTIVE PARALLEL PROCESSING COMPLETED ==="
