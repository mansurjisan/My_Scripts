#! /bin/csh

set echo
set time=1
#
date
# --- from interpolated subregion archive files, GLBb0.08 to GLBy0.08.
#
# --- H is the home directory
# --- R is the original region
# --- U is the target   region
# --- D is the location of the original  archive files.
# --- N is the location of the subregion archive files.
# --- E,y,d,h select the archive files.
#
#
#setenv DATA /home2/dwirasae/CGADICRC-Dev/HYCOM/rtofs/Data
setenv FIXestofs /home2/dwirasae/CGADICRC-Dev/HYCOM/rtofs/fix
setenv SubregionEXECestofs /asclepius/acerrone/HYCOM-tools/subregion/src


setenv H $DATA
setenv R GLBb0.08
setenv U GLBy0.08
setenv E $1
setenv D ${H}/${R}
setenv N ${H}/${U}
#
if ( ! -d ${D} ) then
   mkdir -p $D $N
   ln -s $FIXestofs/rtofs_glo.navy_0.08.regional.grid.a       $D/regional.grid.a
   ln -s $FIXestofs/rtofs_glo.navy_0.08.regional.grid.b       $D/regional.grid.b
   ln -s $FIXestofs/rtofs_glo.navy_0.08.regional.depth.a      $D/regional.depth.a
   ln -s $FIXestofs/rtofs_glo.navy_0.08.regional.depth.b      $D/regional.depth.b
   ln -s $FIXestofs/gofs_regional.gmapi.${R}.a                $N/regional.gmap.a
   ln -s $FIXestofs/gofs_regional.gmapi.${R}.b                $N/regional.gmap.b
   ln -s $FIXestofs/gofs_regional.grid.${U}.a                 $N/regional.grid.a
   ln -s $FIXestofs/gofs_regional.grid.${U}.b                 $N/regional.grid.b
   ln -s $FIXestofs/gofs_regional.depth.${R}.a                $N/regional.depth.a
   ln -s $FIXestofs/gofs_regional.depth.${R}.b                $N/regional.depth.b
endif
cd $D
#

#cp -u ${H}/${E}.a                     $D/${E}.a
#cp -u ${H}/${E}.b                     $D/${E}.b
/bin/rm  ${N}/${E}.[ab] 
ln -sf ${H}/${E}.a                     $D/${E}.a
ln -sf ${H}/${E}.b                     $D/${E}.b
touch  ${N}/${E}.b
/bin/rm ${N}/${E}.[ab]
$SubregionEXECestofs/isubaregion << E-o-D
${N}/regional.grid.a
${N}/regional.gmap.a
${N}/regional.depth.a
${D}/regional.depth.a
${D}/${E}.a
${N}/${E}.a
${R} interpolate to ${U}
 4500     'idm   ' = target longitudinal array size
 4263     'jdm   ' = target latitudinal  array size 
   0      'iceflg' = ice in output archive flag (0=none,1=energy loan model)
   0      'smooth' = smooth interface depths    (0=F,1=T)
E-o-D
date

echo "Delete $D/${E}.[ab]" 
/bin/rm $D/${E}.[ab]
