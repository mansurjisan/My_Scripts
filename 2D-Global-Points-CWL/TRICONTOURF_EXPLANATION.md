# Scatter vs Tricontourf: Visualization Methods for STOFS-2D Maxele Data

## Overview

This document explains the difference between two visualization methods used for plotting STOFS-2D maximum water elevation (maxele) difference data:
1. **Scatter Plot** - Previous method
2. **Tricontourf** - New method (NCL-style triangular mesh visualization)

---

## Understanding the ADCIRC Unstructured Mesh

STOFS-2D uses ADCIRC, a finite element model with an **unstructured triangular mesh**. The mesh consists of two components:

### 1. Nodes (Points)
- Each node has coordinates (longitude, latitude) and a data value (e.g., `zeta_max`)
- Stored in NetCDF as arrays: `x[node]`, `y[node]`, `zeta_max[node]`
- STOFS-2D Global has ~3.6 million nodes

### 2. Elements (Triangles) - The Connectivity
- Defines how nodes connect to form triangles
- Stored in NetCDF as `element[triangle, 3]` - each row lists 3 node indices
- Example: `element[0] = [45, 102, 78]` means triangle 0 connects nodes 45, 102, and 78

```
Node 45 -------- Node 102
    \            /
     \  tri 0  /
      \      /
       \    /
        \  /
       Node 78
```

The mesh is **unstructured** because triangles vary in size:
- **Fine mesh** (small triangles): Coastal areas, bays, estuaries - high resolution needed
- **Coarse mesh** (large triangles): Deep ocean - less resolution needed

---

## Method 1: Scatter Plot (Previous Approach)

### How It Works
```python
ax.scatter(longitude, latitude, c=data, s=point_size)
```
- Plots each mesh node as an individual colored point
- **Ignores the element (triangle) connectivity entirely**
- Point size is arbitrary (user-defined)

### Visual Representation
```
Scatter (points only):
    •       •
      •   •
        •
      •   •
    •       •
```

### Advantages
| Benefit | Description |
|---------|-------------|
| Fast rendering | Simple point plotting, minimal computation |
| Simple implementation | No mesh connectivity required |
| Memory efficient | Only stores point coordinates |
| Good for QC | Can see individual node values |
| Works without elements | Useful if connectivity unavailable |

### Disadvantages
| Issue | Description |
|-------|-------------|
| **Point density bias** | Dense mesh areas appear darker/more saturated than coarse areas |
| **Gaps in visualization** | Coarse mesh regions (offshore) show gaps between points |
| **Arbitrary point size** | Size choice affects visual perception of values |
| **Overlapping points** | Dense coastal areas have overlapping markers |
| **Not physically meaningful** | Doesn't represent actual model structure |
| **Resolution comparison issues** | Hard to compare across different mesh resolutions |

### Example Issue: Density Bias
In coastal bays (fine mesh), thousands of points cluster together creating dark patches.
In deep ocean (coarse mesh), sparse points create a dotted appearance.
This makes it **difficult to compare values** across regions with different mesh densities.

---

## Method 2: Tricontourf (New Approach)

### How It Works
```python
triangulation = matplotlib.tri.Triangulation(x, y, triangles=elements)
ax.tricontourf(triangulation, data, levels=levels, cmap=colormap)
```
- Uses the **actual ADCIRC element connectivity** to create triangulation
- Interpolates color continuously across each triangle face
- Creates filled contours following the mesh structure

### Visual Representation
```
Tricontourf (uses mesh connectivity):
┌─────────────┐
│\           /│
│ \    ▲    / │
│  \  / \  /  │
│   \/   \/   │
└─────────────┘
```

### Advantages
| Benefit | Description |
|---------|-------------|
| **Physically accurate** | Represents actual model mesh topology |
| **Smooth visualization** | Continuous color gradients across triangles |
| **No density bias** | Color represents only data value, not mesh resolution |
| **NCL-style** | Matches NCAR Command Language visualization standard |
| **Proper interpolation** | Values interpolated across triangle faces (matches model computation) |
| **Publication quality** | Professional appearance for reports/presentations |
| **Matches official products** | Similar to NOAA/NOS operational visualizations |

### Disadvantages
| Issue | Description |
|-------|-------------|
| Slower rendering | More computation required for triangulation |
| Requires connectivity | Element table must be available in NetCDF |
| Can smooth small features | Interpolation may mask point-scale anomalies |
| Memory intensive | Large meshes require more RAM |
| Needs outlier filtering | Extreme values can create artifacts |
| Complex regional subsetting | Requires index remapping for regional plots |

---

## Technical Implementation Details

### Regional Mesh Extraction
For regional plots (e.g., Chesapeake Bay, Mobile Bay), we extract a subset of the mesh:

1. **Filter nodes** within the bounding box (lon_min, lon_max, lat_min, lat_max)
2. **Filter triangles** where all 3 vertices are within the region
3. **Remap indices** - create new sequential node indices for the regional mesh
4. **Create triangulation** with the remapped regional mesh

```python
def extract_regional_mesh(nc_file, x, y, data, lon_min, lon_max, lat_min, lat_max):
    # Find nodes in region
    node_mask = (x >= lon_min) & (x <= lon_max) & (y >= lat_min) & (y <= lat_max)
    regional_indices = np.where(node_mask)[0]

    # Create index mapping (old -> new)
    index_map = {old_idx: new_idx for new_idx, old_idx in enumerate(regional_indices)}

    # Filter and remap triangles
    # ... (remap element indices to new sequential indices)

    return x_regional, y_regional, elements_regional, data_regional
```

### Outlier Filtering
To prevent artificial color artifacts (e.g., dark blue spots in bays), we mask triangles with extreme values:

```python
# Mask NaN values
mask_nan = np.isnan(data)

# Mask outliers beyond ±1.5m (unrealistic for bias correction differences)
outlier_threshold = 1.5
mask_outlier = np.abs(data) > outlier_threshold

# Combined mask
mask_bad = mask_nan | mask_outlier

# Apply mask to triangles where any vertex has bad value
tri_has_bad = mask_bad[triangulation.triangles].any(axis=1)
triangulation.set_mask(tri_has_bad)
```

### GSHHS Coastline Overlay
High-resolution shoreline data (GSHHS) is overlaid to:
- Provide land masking (light gray fill)
- Show accurate coastline boundaries
- Improve visual clarity of coastal features

---

## When to Use Each Method

### Use Scatter When:
- Quick data exploration or quality control
- Mesh connectivity is unavailable
- Need to identify specific node anomalies
- Memory or speed is critical
- Checking raw data values at individual points

### Use Tricontourf When:
- Final publication or presentation plots
- Comparing data across different dates/cycles
- Need physically meaningful visualization
- Presenting to stakeholders or management
- Matching NOAA/NOS official product style
- Validation reports and documentation

---

## Key Takeaway

| Method | What It Shows |
|--------|---------------|
| **Scatter** | Raw data points - what you actually have in the file |
| **Tricontourf** | Interpolated field - what the model physically represents |

For validation work comparing bias-corrected vs non-bias-corrected maxele, **tricontourf is preferred** because:
1. Smooth gradients make differences easier to interpret visually
2. No density bias means fair comparison across all regions
3. Matches how the model actually computes values across the mesh
4. Professional quality suitable for reports to stakeholders

---

## Files Modified

### `plot_difference_maxele_enhanced.py`
- Added `--use-tricontourf` command line option
- Added `extract_regional_mesh()` function for proper mesh subsetting
- Added outlier filtering (±1.5m threshold) to remove artifacts
- Added GSHHS coastline overlay for land masking

### Batch Scripts
- `generate_all_tricontourf.sh` - Regional plots (10 regions)
- `generate_conus_global_tricontourf.sh` - CONUS and Global domain plots

---

## Example Usage

```bash
# Generate tricontourf plot for Mobile Bay
python plot_difference_maxele_enhanced.py \
    stofs_2d_glo.t12z.fields.cwl.maxele.noanomaly.nc \
    stofs_2d_glo.t12z.fields.cwl.maxele.nc \
    zeta_max \
    --region custom \
    --lon-range -88.5 -87.0 \
    --lat-range 30.0 31.0 \
    --vmin -0.5 --vmax 0.5 \
    --use-tricontourf \
    --location-name "Mobile Bay" \
    --save mobile_bay_tricontourf.png
```

---

## Summary

**Before (Scatter):**
- Plotted individual points at each mesh node
- Dense coastal areas appeared darker due to point clustering
- Offshore areas had gaps between points
- Not representative of actual model physics

**After (Tricontourf):**
- Uses actual ADCIRC triangular mesh connectivity
- Smooth continuous color field across triangles
- No density bias - color only represents data value
- Matches NCL-style visualization used in operational oceanography
- Added outlier filtering to remove artificial artifacts
- Added high-resolution GSHHS coastline for land masking

The new method provides **physically meaningful, publication-quality visualizations** that accurately represent the STOFS-2D model output.
