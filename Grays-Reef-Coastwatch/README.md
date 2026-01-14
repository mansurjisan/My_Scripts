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
| Sea Surface Temperature (SST) | Coral Reef Watch v3.1 | `NOAA_DHW_monthly` | 5 km | **1989-2025** |
| SST Anomaly | Coral Reef Watch v3.1 | `NOAA_DHW_monthly` | 5 km | **1989-2025** |
| K490 Turbidity | MODIS Aqua | `erdMH1kd490mday_R2022SQ` | 4 km | 2003-2024 |
| Chlorophyll-a (VIIRS) | VIIRS Science Quality | `noaacwNPPVIIRSSQchlaMonthly` | 750 m | 2012-2024 |
| Chlorophyll-a (MODIS) | MODIS Aqua | `erdMH1chlamday_R2022SQ` | 4 km | **2003-2019** |

## Data Files

### Time Series (Recommended for Analysis)

These files contain **spatially-averaged monthly values** - one row per month:

| File | Variables | Period | Rows |
|------|-----------|--------|------|
| `sst_timeseries.csv` | time, sea_surface_temperature, sea_surface_temperature_anomaly | **1989-2025** | **444** |
| `chlorophyll_timeseries.csv` | time, chlor_a | 2012-2024 | 154 |
| `chlorophyll_modis_timeseries.csv` | time, chlor_a | **2003-2019** | **204** |
| `k490_modis_timeseries.csv` | time, kd_490 | 2003-2024 | 249 |

### Raw Gridded Data

These files contain the **original gridded data** - multiple lat/lon points per timestep:

| File | Description |
|------|-------------|
| `sst_raw.csv` | SST & anomaly, all grid points (1989-2025) |
| `chlorophyll_viirs_raw.csv` | Chlorophyll-a VIIRS, all grid points (2012-2024) |
| `chlorophyll_modis_raw.csv` | Chlorophyll-a MODIS, all grid points (2003-2019) |
| `k490_modis_raw.csv` | K490 turbidity, all grid points (2003-2024) |

## Variable Descriptions

| Variable | Units | Description |
|----------|-------|-------------|
| `sea_surface_temperature` | °C | Sea surface temperature |
| `sea_surface_temperature_anomaly` | °C | Deviation from climatological mean |
| `chlor_a` | mg/m³ | Chlorophyll-a concentration (proxy for phytoplankton) |
| `kd_490` | m⁻¹ | Diffuse attenuation coefficient at 490nm (water clarity/turbidity) |

## Quick Start (R)

```r
# Load time series data
sst <- read.csv("data/sst_timeseries.csv")
chlor_viirs <- read.csv("data/chlorophyll_timeseries.csv")
chlor_modis <- read.csv("data/chlorophyll_modis_timeseries.csv")
k490 <- read.csv("data/k490_modis_timeseries.csv")

# Convert time column to Date
sst$time <- as.Date(sst$time)
chlor_viirs$time <- as.Date(chlor_viirs$time)
chlor_modis$time <- as.Date(chlor_modis$time)
k490$time <- as.Date(k490$time)

# Plot SST (37 years: 1989-2025)
plot(sst$time, sst$sea_surface_temperature, type="l",
     xlab="Date", ylab="SST (°C)",
     main="Gray's Reef NMS - Sea Surface Temperature (1989-2025)")

# Plot Chlorophyll (MODIS: 2003-2019)
plot(chlor_modis$time, chlor_modis$chlor_a, type="l", col="green",
     xlab="Date", ylab="Chlorophyll-a (mg/m³)",
     main="Gray's Reef NMS - Chlorophyll-a (MODIS, 2003-2019)")
```

## Files in This Repository

```
Grays-Reef-Coastwatch/
├── README.md                    # This file
├── grays_reef_analysis.ipynb    # Jupyter notebook with analysis
├── extract_grays_reef.py        # Python script for data extraction
├── download_data.sh             # Bash script for data download
└── data/                        # CSV data files
    ├── sst_timeseries.csv              (444 months, 1989-2025)
    ├── sst_raw.csv
    ├── chlorophyll_timeseries.csv      (VIIRS, 154 months, 2012-2024)
    ├── chlorophyll_modis_timeseries.csv (MODIS, 204 months, 2003-2019)
    ├── k490_modis_timeseries.csv       (249 months, 2003-2024)
    └── ... (raw data files)
```

## Data Summary

### SST (1989-2025) - 37 years
- **444 monthly records**
- Temperature range: 12.3 - 29.8°C
- Anomaly range: -6.2 to +2.8°C

### Chlorophyll-a
- **MODIS (2003-2019)**: 204 months, range 0.6 - 6.9 mg/m³
- **VIIRS (2012-2024)**: 154 months, range 0.5 - 8.9 mg/m³

### K490 Turbidity (2003-2024)
- 249 monthly records
- Range: 0.075 - 0.59 m⁻¹

## References

- NOAA CoastWatch: https://coastwatch.noaa.gov/
- ERDDAP: https://coastwatch.pfeg.noaa.gov/erddap/
- Gray's Reef NMS: https://graysreef.noaa.gov/
- Coral Reef Watch: https://coralreefwatch.noaa.gov/
