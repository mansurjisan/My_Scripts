# Gray's Reef National Marine Sanctuary - Environmental Data

This repository contains oceanographic environmental data for **Gray's Reef National Marine Sanctuary** (NMS), located off the coast of Georgia, USA.

## Study Area

- **Location**: Southeast US Atlantic Coast, offshore Georgia
- **Coordinates**: 31.36°N - 31.42°N, 80.82°W - 80.93°W
- **Sanctuary**: [Gray's Reef NMS](https://graysreef.noaa.gov/)

## Data Sources

All data are downloaded from NOAA CoastWatch ERDDAP servers:

| Variable | Source | Dataset ID | Resolution | Time Range |
|----------|--------|------------|------------|------------|
| Sea Surface Temperature (SST) | Coral Reef Watch v3.1 | `NOAA_DHW_monthly` | 5 km | 2003-2024 |
| SST Anomaly | Coral Reef Watch v3.1 | `NOAA_DHW_monthly` | 5 km | 2003-2024 |
| K490 Turbidity | MODIS Aqua | `erdMH1kd490mday_R2022SQ` | 4 km | 2003-2024 |
| Chlorophyll-a | VIIRS Science Quality | `noaacwNPPVIIRSSQchlaMonthly` | 750 m | 2012-2024 |

## Data Files

### Time Series (Recommended for Analysis)

These files contain **spatially-averaged monthly values** - one row per month:

| File | Variables | Period | Rows |
|------|-----------|--------|------|
| `sst_timeseries.csv` | time, sea_surface_temperature, sea_surface_temperature_anomaly | 2003-2024 | 264 |
| `chlorophyll_timeseries.csv` | time, chlor_a | 2012-2024 | 154 |
| `k490_modis_timeseries.csv` | time, kd_490 | 2003-2024 | 249 |

### Raw Gridded Data

These files contain the **original gridded data** - multiple lat/lon points per timestep:

| File | Description |
|------|-------------|
| `sst_raw.csv` | SST & anomaly, all grid points (2003-2024) |
| `chlorophyll_viirs_raw.csv` | Chlorophyll-a, all grid points (2012-2024) |
| `k490_modis_raw.csv` | K490 turbidity, all grid points (2003-2024) |

## Variable Descriptions

| Variable | Units | Description |
|----------|-------|-------------|
| `sea_surface_temperature` | °C | Sea surface temperature |
| `sea_surface_temperature_anomaly` | °C | Deviation from climatological mean |
| `chlor_a` | mg/m³ | Chlorophyll-a concentration (proxy for phytoplankton) |
| `kd_490` | m⁻¹ | Diffuse attenuation coefficient at 490nm (water clarity/turbidity) |


## Files in This Repository

```
Grays-Reef-Coastwatch/
├── README.md                    # This file
├── grays_reef_analysis.ipynb    # Jupyter notebook with analysis
├── extract_grays_reef.py        # Python script for data extraction
├── download_data.sh             # Bash script for data download
└── data/                        # CSV data files
    ├── sst_timeseries.csv
    ├── chlorophyll_timeseries.csv
    ├── k490_modis_timeseries.csv
    └── ... (raw data files)
```

## References

- NOAA CoastWatch: https://coastwatch.noaa.gov/
- ERDDAP: https://coastwatch.pfeg.noaa.gov/erddap/
- Gray's Reef NMS: https://graysreef.noaa.gov/
- Coral Reef Watch: https://coralreefwatch.noaa.gov/
