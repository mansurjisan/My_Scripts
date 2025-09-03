#!/bin/bash
# Interactive parallel processing script for PBS
# Run this on your allocated interactive node

echo "=== INTERACTIVE PARALLEL PROCESSING STARTED ==="
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "Available cores: $(nproc)"

# Load necessary modules for PBS
#module purge
#module load intel
#module load netcdf
#module load mvapich2
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
    # Use your target start date (August 29th)
    local start_date="20250828"
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
export DATA ArchvEXECestofs

echo "=== Starting parallel processing of 10 tasks ==="
echo "Processing dates from August 29th to September 7th, 2025"

# Launch tasks in parallel using all available cores
# With 10 CPUs and 32GB RAM, we can run all 10 tasks simultaneously
batch_size=3

echo "Processing all $batch_size tasks in parallel..."

# Launch all tasks at once
for task_id in {1..10}; do
    process_date $task_id &
    echo "Started task $task_id in background (PID: $!)"
done

# Wait for all background jobs to complete
echo "=== Waiting for all tasks to complete ==="
wait

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
