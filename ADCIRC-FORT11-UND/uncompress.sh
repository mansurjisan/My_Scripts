#!/bin/bash

#
# This script finds all files with a .a extension in a target directory and
# processes them in parallel. It assumes each .a file is a gzipped tar archive
# containing a single data file. The script will extract the data file and
# use it to replace the original .a archive.
#
# Usage:
#   ./this_script.sh [TARGET_DIRECTORY]
#
# If TARGET_DIRECTORY is not provided, it will process files in the
# current directory.
#

# --- Configuration ---

# Set the directory to search. Use the first command-line argument if provided,
# otherwise default to the current directory (".").
TARGET_DIR="bcdownloads"

# Determine the number of parallel jobs. This will use the number of CPU cores
# available on the system. If the 'nproc' command isn't available, it defaults to 4.
NCORES=4


# --- Sanity Checks ---

# Check if the target directory actually exists.
if [[ ! -d "$TARGET_DIR" ]]; then
    echo "Error: Directory '$TARGET_DIR' not found." >&2
    exit 1
fi


# --- Main Logic ---

# This function defines how to process a single file.
process_file() {
    # The file to process is the first argument to the function.
    local file="$1"
    
    # Create a secure temporary file to store the extracted content.
    # This temp file is created in the same directory as the source file.
    local tmpfile
    tmpfile=$(mktemp "$(dirname "$file")/$(basename "$file").XXXXXX")
    
    # Exit if the temporary file could not be created.
    if [[ ! -f "$tmpfile" ]]; then
        echo "Error: Could not create temp file for '$file'" >&2
        return 1
    fi

    echo "Processing: '$file'"
    
    # Use 'tar' to extract the archive.
    # -x: extract
    # -O: extract files to standard output instead of disk
    # -z: filter the archive through gzip (for .tgz/.tar.gz)
    # -f: specify the file to use
    # We redirect the standard output (the file contents) to our temp file.
    if tar -xOzf "$file" > "$tmpfile"; then
        # If the extraction was successful, replace the original file with the temp file.
        # This is an atomic operation if on the same filesystem.
        mv "$tmpfile" "$file"
        echo "Success: '$file' has been uncompressed."
    else
        # If tar returns an error, print a message and clean up the temp file.
        echo "Error: Failed to extract '$file'. The original file is unchanged." >&2
        rm "$tmpfile"
        return 1
    fi
}

# Export the function so it's available to the sub-processes that xargs will create.
export -f process_file

# --- Execution ---

echo "Starting parallel processing in '$TARGET_DIR' using up to $NCORES cores..."

# Use 'find' to locate the files and pipe the list to 'xargs' for parallel execution.
# find:
#   "$TARGET_DIR": The directory to search.
#   -maxdepth 1: Do not search in subdirectories.
#   -type f: Only find files.
#   -name "*.a": Find files with the .a extension.
#   -print0: Print the full filename, followed by a null character (for safety).
# xargs:
#   -0: Read null-terminated input (to work with find's -print0).
#   -r: Do not run if the input is empty.
#   -P "$NCORES": The maximum number of processes to run in parallel.
#   -I {}: The placeholder for the input filename.
#   bash -c '...': The command to run for each file.
find "$TARGET_DIR" -maxdepth 1 -type f -name "*.a" -print0 | xargs -0 -r -P "$NCORES" -I {} bash -c 'process_file "{}"'

echo "All tasks complete."
