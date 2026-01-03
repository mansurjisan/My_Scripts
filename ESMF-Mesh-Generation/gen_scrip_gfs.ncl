;----------------------------------------------------------------------
; gen_scrip_gfs.ncl
; Generate SCRIP grid file from GFS NetCDF for ESMF mesh creation
;
; Adapted from ERA5 workflow for SECOFS UFS-Coastal transition
;
; Usage:
;   ncl 'input_file="gfs_for_esmf.nc"' 'output_file="gfs_scrip.nc"' gen_scrip_gfs.ncl
;
; Or set defaults below and run:
;   ncl gen_scrip_gfs.ncl
;
; Author: Adapted for SECOFS UFS-Coastal transition
; Date: January 2026
;----------------------------------------------------------------------

begin

; Default file names (can be overridden from command line)
if (.not. isvar("input_file")) then
    input_file = "gfs_for_esmf.nc"
end if

if (.not. isvar("output_file")) then
    output_file = "gfs_scrip.nc"
end if

print("============================================")
print("Generating SCRIP file for GFS grid")
print("Input:  " + input_file)
print("Output: " + output_file)
print("============================================")

; Open input file
fin = addfile(input_file, "r")

; Read coordinates
lon = fin->lon
lat = fin->lat

nlon = dimsizes(lon)
nlat = dimsizes(lat)

print("Grid dimensions: " + nlon + " x " + nlat)
print("Lon range: " + min(lon) + " to " + max(lon))
print("Lat range: " + min(lat) + " to " + max(lat))

; GFS is regular lat-lon grid
; Generate SCRIP file using rectilinear_to_SCRIP

opt = True
opt@ForceOverwrite = True
opt@PrintTimings = True
opt@Title = "GFS 0.25-degree grid for SECOFS DATM"

; Create SCRIP file
rectilinear_to_SCRIP(output_file, lat, lon, opt)

print("============================================")
print("SCRIP file created: " + output_file)
print("============================================")
print("")
print("Next step: Convert SCRIP to ESMF mesh:")
print("  ESMF_Scrip2Unstruct " + output_file + " gfs_esmf_mesh.nc 0")
print("")

end
