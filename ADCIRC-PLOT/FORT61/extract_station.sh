#!/bin/bash
# Extract station names from the file first
python -c "
import netCDF4 as nc
import sys

ds = nc.Dataset('fort.61.nc', 'r')
stations = ds.variables['station_name']

for i in range(min(100, len(stations))):  # Process first 100 as example
    name = ''.join(c.decode('utf-8') if isinstance(c, bytes) else c 
                  for c in stations[i]).strip()
    # Clean name for filename
    clean_name = name.replace(' ', '_').replace(',', '').replace('.', '')[:30]
    print(f'{i}:{clean_name}')
ds.close()
" > station_list.txt

# Process each station
while IFS=: read -r idx name; do
    echo "Processing Station $idx: $name"
    python extract_fort61.py --overlay fort.61.nc fort.61_mjisan.nc \
        --station-idx $idx \
        --labels "UND" "Mansur" \
        --save-plot "${name}_UND_vs_Mansur.png"
done < station_list.txt
