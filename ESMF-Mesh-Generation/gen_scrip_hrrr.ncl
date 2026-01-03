;----------------------------------------------------------------------
; gen_scrip_hrrr.ncl
; Generate SCRIP grid file from HRRR NetCDF for ESMF mesh creation
;
; HRRR uses a Lambert Conformal grid with 2D lat/lon arrays
;
; Usage:
;   ncl 'input_file="hrrr_for_esmf.nc"' 'output_file="hrrr_scrip.nc"' gen_scrip_hrrr.ncl
;
; Author: Adapted for SECOFS UFS-Coastal transition
; Date: January 2026
;----------------------------------------------------------------------

begin

; Default file names
if (.not. isvar("input_file")) then
    input_file = "hrrr_for_esmf.nc"
end if

if (.not. isvar("output_file")) then
    output_file = "hrrr_scrip.nc"
end if

print("============================================")
print("Generating SCRIP file for HRRR grid")
print("Input:  " + input_file)
print("Output: " + output_file)
print("============================================")

; Open input file
fin = addfile(input_file, "r")

; Read 2D coordinates
lat2d = fin->lat
lon2d = fin->lon

dims = dimsizes(lat2d)
ny = dims(0)
nx = dims(1)

print("Grid dimensions: " + nx + " x " + ny)
print("Lon range: " + min(lon2d) + " to " + max(lon2d))
print("Lat range: " + min(lat2d) + " to " + max(lat2d))

; Check if coordinates are 1D or 2D
ndims_lat = dimsizes(dimsizes(lat2d))

if (ndims_lat .eq. 1) then
    ; 1D coordinates - use rectilinear
    print("Using rectilinear_to_SCRIP (1D coordinates)")

    opt = True
    opt@ForceOverwrite = True
    opt@PrintTimings = True
    opt@Title = "HRRR 3km grid for SECOFS DATM"

    rectilinear_to_SCRIP(output_file, lat2d, lon2d, opt)
else
    ; 2D coordinates - use curvilinear (let NCL compute corners)
    print("Using curvilinear_to_SCRIP (2D coordinates)")

    opt = True
    opt@ForceOverwrite = True
    opt@PrintTimings = True
    opt@Title = "HRRR 3km Lambert Conformal grid for SECOFS DATM"

    ; Let NCL compute corners automatically
    curvilinear_to_SCRIP(output_file, lat2d, lon2d, opt)
end if

print("============================================")
print("SCRIP file created: " + output_file)
print("============================================")
print("")
print("Next step: Convert SCRIP to ESMF mesh:")
print("  ESMF_Scrip2Unstruct " + output_file + " hrrr_esmf_mesh.nc 0")
print("")

end
