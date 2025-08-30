#! /bin/csh
#
set echo
set time=1
#
date
#
# --- interpolate to 3-d z-levels from a HYCOM mean archive file.
#

# --- Set environment variables and arguments
setenv ArchvEXECestofs /asclepius/acerrone/HYCOM-tools/archive/src
setenv E $1
set date_arg = $2 #<-- CAPTURE the second argument (the date)

setenv H $DATA
setenv R GLBb0.08
setenv U GLBy0.08
setenv D ${H}/${U}
#
if ( ! -d ${D} ) then
    mkdir -p $D
endif
cd $D

# --- Construct the unique input filename using the date
set inp_file = "archv2ncdf3z_${date_arg}.inp"

## --- optional title and institution.
#
setenv CDF_TITLE       "RTOFS ${R} to ${U}"
setenv CDF_INST        "NOAA/NOS/OCS/CMMB"
setenv CDF030 ${D}/${E}.nc
setenv CDF031 ${D}/${E}.nc
setenv CDF032 ${D}/${E}.nc
setenv CDF033 ${D}/${E}.nc
setenv CDF034 ${D}/${E}.nc
#
touch $CDF030
touch $CDF031 $CDF032
touch $CDF033 $CDF034
/bin/rm $CDF030
/bin/rm $CDF031 $CDF032
/bin/rm $CDF033 $CDF034

# --- Create the input file with the new dynamic name
cat <<E-o-D >! $inp_file
${E}.a
netCDF
 000   'iexpt ' = experiment number x10 (000=from archive file)
   0   'yrflag' = days in year flag (0=360J16,1=366J16,2=366J01,3-actual)
4500   'idm   ' = longitudinal array size
4263   'jdm   ' = latitudinal  array size
  41   'kdm   ' = number of layers
  34.0 'thbase' = reference density (sigma units)
   0   'smooth' = smooth the layered fields (0=F,1=T)
   0   'baclin' = extract baroclinic velocity (0=total,1=baroclinic)
   1   'iorign' = i-origin of plotted subregion
   1   'jorign' = j-origin of plotted subregion
   0   'idmp  ' = i-extent of plotted subregion (<=idm; 0 implies idm)
   0   'jdmp  ' = j-extent of plotted subregion (<=jdm; 0 implies jdm)
   2   'inbot ' = 
 1.0   'zbot  ' = 
   1   'itype ' =  
  33   'kz    ' = number of depths to sample
   0.0 'z     ' = sample depth  1
  10.0 'z     ' = sample depth  2
  20.0 'z     ' = sample depth  3
  30.0 'z     ' = sample depth  4
  50.0 'z     ' = sample depth  5
  75.0 'z     ' = sample depth  6
 100.0 'z     ' = sample depth  7
 125.0 'z     ' = sample depth  8
 150.0 'z     ' = sample depth  9
 200.0 'z     ' = sample depth 10
 250.0 'z     ' = sample depth 11
 300.0 'z     ' = sample depth 12
 400.0 'z     ' = sample depth 13
 500.0 'z     ' = sample depth 14
 600.0 'z     ' = sample depth 15
 700.0 'z     ' = sample depth 16
 800.0 'z     ' = sample depth 17
 900.0 'z     ' = sample depth 18
1000.0 'z     ' = sample depth 19
1100.0 'z     ' = sample depth 20
1200.0 'z     ' = sample depth 21
1300.0 'z     ' = sample depth 22
1400.0 'z     ' = sample depth 23
1500.0 'z     ' = sample depth 24
1750.0 'z     ' = sample depth 25
2000.0 'z     ' = sample depth 26
2500.0 'z     ' = sample depth 27
3000.0 'z     ' = sample depth 28
3500.0 'z     ' = sample depth 29
4000.0 'z     ' = sample depth 30
4500.0 'z     ' = sample depth 31
5000.0 'z     ' = sample depth 32
5500.0 'z     ' = sample depth 33
   0   'botio ' = bathymetry  I/O unit (0 no I/O)
   0   'mltio ' = mix.l.thk.  I/O unit (0 no I/O)
   0   'tempml' = temperature jump across mixed-layer (degC,  0 no I/O)
   0   'densml' =      density jump across mixed-layer (kg/m3, 0 no I/O)
   0   'infio ' = intf. depth I/O unit (0 no I/O, <0 label with layer #)
   0   'wvlio ' = w-velocity  I/O unit (0 no I/O)
   0   'uvlio ' = u-velocity  I/O unit (0 no I/O)
   0   'vvlio ' = v-velocity  I/O unit (0 no I/O)
   0   'splio ' = speed       I/O unit (0 no I/O)
  30   'istio ' = in-situ temp I/O unit (0 no I/O)
   0   'temio ' = temperature I/O unit (0 no I/O) 
  30   'salio ' = salinity    I/O unit (0 no I/O)
   0   'tthio ' = density     I/O unit (0 no I/O) 0   'keio  ' = kinetic energy
E-o-D

# --- Execute the program using the new input file
cat $inp_file
$ArchvEXECestofs/archv2ncdf3z < $inp_file

# Clean up the input file after use (optional but good practice)
# /bin/rm $inp_file