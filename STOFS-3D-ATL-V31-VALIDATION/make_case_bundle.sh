#!/bin/bash
# Freeze the STOFS-3D-ATL PDY 20261001 12z validation case ("case bundle") on WCOSS2.
# Plain cp (no -p) so copies get fresh mtimes and are not aged by purge rules.
# Preferred input list: the inputs.<stage>.json manifests in COMOUT (exact file lists).
# Fallback: explicit path patterns (reproduce the same file chain the nos-workflow code walks).
# MJ (10/03/26)
#
# Usage:  make_case_bundle.sh [-n] [-d DEST] [options]
#   -n                dry run: build the plan, print per-group counts/sizes/missing, copy nothing
#   -d DEST           bundle root (default $NOSCRUB/case_bundles/stofs_3d_atl_$PDY)
#   --skip LIST       comma list of groups to skip:
#                     gfs,hrrr,nwm,rtofs,adt,wl,law,seeds,opsref,comout,provenance,other
#   --skip-public     skip groups that are on public buckets: gfs,hrrr,nwm,rtofs
#   --skip-restart    skip the 26 GB ops rerun restart.nc (on S3)
#   --skip-init       skip the converted *.init.nowcast.nc in COMOUT (~26 GB)
#   --skip-rst        skip rst.nowcast.nc / hotstart_it* nowcast output (~26 GB)
#   --skip-fields     skip out2d/field *.nc under restart_outputs (staout_* etc. are kept)
#   --skip-big        = --skip-restart --skip-init --skip-rst --skip-fields
#   --no-md5          skip md5sums in MANIFEST.txt (sizes only)
# Env overrides: PDY CYC LOGNAME NOSCRUB DEST COMOUT_DIRS DYN_SEED OPS_KEEP OPS_RERUN
#                PACKAGEROOT JOBS (md5 parallelism, default 4)

set -u

PDY=${PDY:-20261001}
CYC=${CYC:-12}
LOGNAME=${LOGNAME:-$(id -un)}
RUN=stofs_3d_atl_ufs
NOSCRUB=${NOSCRUB:-/lfs/h1/nos/estofs/noscrub/$LOGNAME}
PTMP=${PTMP:-/lfs/h1/nos/ptmp/$LOGNAME}
DEST=${DEST:-$NOSCRUB/case_bundles/stofs_3d_atl_$PDY}
COMOUT_DIRS=${COMOUT_DIRS:-$PTMP/com/nos_opsexe/$RUN.$PDY $PTMP/com/nos_dyn4/$RUN.$PDY}
DYN_SEED=${DYN_SEED:-$NOSCRUB/dyn_seed_20260930}
OPS_KEEP=${OPS_KEEP:-$NOSCRUB/ops_keep/stofs_3d_atl.$PDY}
OPS_RERUN=${OPS_RERUN:-/lfs/h1/ops/prod/com/stofs/v3.1/stofs_3d_atl.$PDY/rerun}
PACKAGEROOT=${PACKAGEROOT:-$NOSCRUB/packages}
COMGFS=${COMGFS:-/lfs/h1/ops/prod/com/gfs/v16.3}
COMHRRR=${COMHRRR:-/lfs/h1/ops/prod/com/hrrr/v4.1}
COMNWM=${COMNWM:-/lfs/h1/ops/prod/com/nwm/v3.1}
COMRTOFS=${COMRTOFS:-/lfs/h1/ops/prod/com/rtofs/v2.5}
DCOM=${DCOM:-/lfs/h1/ops/prod/dcom}
JOBS=${JOBS:-4}

DRY=0; SKIP=","; SKIP_RESTART=0; SKIP_INIT=0; SKIP_RST=0; SKIP_FIELDS=0; MD5=1
while [ $# -gt 0 ]; do
  case "$1" in
    -n) DRY=1 ;;
    -d) DEST=$2; shift ;;
    --skip) SKIP="$SKIP$2,"; shift ;;
    --skip-public) SKIP="${SKIP}gfs,hrrr,nwm,rtofs," ;;
    --skip-restart) SKIP_RESTART=1 ;;
    --skip-init) SKIP_INIT=1 ;;
    --skip-rst) SKIP_RST=1 ;;
    --skip-fields) SKIP_FIELDS=1 ;;
    --skip-big) SKIP_RESTART=1; SKIP_INIT=1; SKIP_RST=1; SKIP_FIELDS=1 ;;
    --no-md5) MD5=0 ;;
    -h|--help) sed -n 2,26p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

PDYm1=$(date -u -d "${PDY} -1 day" +%Y%m%d)
ANCHOR=$(date -u -d "${PDY} ${CYC}:00:00" +%s)
HR=3600
PFX=$RUN.t${CYC}z.$PDY

skipped() { case "$SKIP" in *",$1,"*) return 0;; esac; return 1; }

WORK=$DEST/.work
mkdir -p "$WORK" || { echo "cannot create $DEST" >&2; exit 1; }
PLAN=$WORK/plan.tsv       # group <TAB> src <TAB> rel
: > "$PLAN"
MISSING=$WORK/missing.txt
: > "$MISSING"

add() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$PLAN"; }

# ---- classify an absolute source path into (group, rel) ---------------------
classify() {
  local p=$1
  case "$p" in
    */com/gfs/*/gfs.*)   G=gfs;   R=gfs/gfs.${p#*/gfs.} ;;
    */com/hrrr/*/hrrr.*) G=hrrr;  R=hrrr/hrrr.${p#*/hrrr.} ;;
    */com/nwm/*/nwm.*)   G=nwm;   R=nwm/nwm.${p#*/nwm.} ;;
    */com/rtofs/*/rtofs.*) G=rtofs; R=rtofs/rtofs.${p#*/rtofs.} ;;
    */dcom/*/coops_waterlvlobs/*) G=wl;  R=dcom/${p#*/dcom/} ;;
    */dcom/*/can_streamgauge/*|*/dcom/*/canadian_water/*) G=law; R=dcom/${p#*/dcom/} ;;
    */dcom/*/cmems/*)    G=adt;   R=dcom/${p#*/dcom/} ;;
    */dcom/*)            G=other; R=dcom/${p#*/dcom/} ;;
    */dyn_seed_*/*)      G=seeds; R=seeds/dyn_seed_${p#*/dyn_seed_} ;;
    */ptmp/*/work/*)     G=ephemeral; R= ;;
    *)                   G=other; R=other/${p#/} ;;
  esac
}

# ---- 1. manifest-driven inputs ----------------------------------------------
MANLIST=$WORK/manifest_paths.txt
: > "$MANLIST"
MANFOUND=0
for c in $COMOUT_DIRS; do
  for st in prep nowcast forecast; do
    m=$c/$PFX.inputs.$st.json
    [ -s "$m" ] || continue
    MANFOUND=$((MANFOUND+1))
    echo "manifest: $m"
    python3 - "$m" >> "$MANLIST" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
for g in d.get("inputs", []):
    if g.get("category") == "static":      # fix files: reproducible via tools/fetch_stofs_3d_atl_fix.sh
        continue
    for f in g.get("files", []):
        print(f)
EOF
  done
done
sort -u "$MANLIST" -o "$MANLIST"

declare -A HAVE_GROUP
while IFS= read -r p; do
  [ -n "$p" ] || continue
  case "$p" in /*) ;; *) continue ;; esac     # bare names = staged copies in $DATA, covered by COMOUT
  classify "$p"
  [ "$G" = ephemeral ] && continue
  skipped "$G" && { HAVE_GROUP[$G]=1; continue; }
  HAVE_GROUP[$G]=1
  if [ -f "$p" ]; then add "$G" "$p" "$R"; else echo "$G	$p" >> "$MISSING"; fi
done < "$MANLIST"

# ---- 2. fallback patterns for groups the manifests did not cover ------------
fb() {   # fb group src rel  (only when manifests gave nothing for that group)
  [ -n "${HAVE_GROUP[$1]:-}" ] && return
  skipped "$1" && return
  if [ -f "$2" ]; then add "$1" "$2" "$3"; else echo "$1	$2" >> "$MISSING"; fi
}

# GFS 0.25: hourly valid times anchor-27h .. anchor+99h; each hour from newest cycle at lead 1-6 h, then anchor f001-f099
v=$((ANCHOR - 27*HR))
while [ "$v" -le $((ANCHOR + 99*HR)) ]; do
  if [ "$v" -gt "$ANCHOR" ]; then cyc=$ANCHOR
  else b=$((v - HR)); cyc=$(( b - b % (6*HR) )); fi
  f=$(( (v - cyc) / HR ))
  d=$(date -u -d @"$cyc" +%Y%m%d); h=$(date -u -d @"$cyc" +%H)
  n=$(printf 'gfs.t%sz.pgrb2.0p25.f%03d' "$h" "$f")
  fb gfs "$COMGFS/gfs.$d/$h/atmos/$n" "gfs/gfs.$d/$h/atmos/$n"
  v=$((v + HR))
done

# HRRR: f01 of the previous hour's cycle for valid anchor-24h..anchor, then anchor-cycle f01..f48
v=$((ANCHOR - 24*HR))
while [ "$v" -le "$ANCHOR" ]; do
  cyc=$((v - HR)); d=$(date -u -d @"$cyc" +%Y%m%d); h=$(date -u -d @"$cyc" +%H)
  n=hrrr.t${h}z.wrfsfcf01.grib2
  fb hrrr "$COMHRRR/hrrr.$d/conus/$n" "hrrr/hrrr.$d/conus/$n"
  v=$((v + HR))
done
for f in $(seq 1 48); do
  n=$(printf 'hrrr.t%sz.wrfsfcf%02d.grib2' "$CYC" "$f")
  fb hrrr "$COMHRRR/hrrr.$PDY/conus/$n" "hrrr/hrrr.$PDY/conus/$n"
done

# NWM medium_range_mem1 (139 files): yday t06z f006; yday t12z f001-6; yday t18z f001-6; today t00z f001-6; today t06z f001-120
nwmf() { local d=$1 c=$2 f=$3
  local n; n=$(printf 'nwm.t%02dz.medium_range.channel_rt_1.f%03d.conus.nc' "$c" "$f")
  fb nwm "$COMNWM/nwm.$d/medium_range_mem1/$n" "nwm/nwm.$d/medium_range_mem1/$n"; }
nwmf "$PDYm1" 6 6
for f in $(seq 1 6); do nwmf "$PDYm1" 12 "$f"; nwmf "$PDYm1" 18 "$f"; nwmf "$PDY" 0 "$f"; done
for f in $(seq 1 120); do nwmf "$PDY" 6 "$f"; done

# RTOFS (same-day cycle, 6-hourly slots; US_east 3dz tile; previous-day fills are only in the manifest path)
rt() { fb rtofs "$COMRTOFS/rtofs.$PDY/$1" "rtofs/rtofs.$PDY/$1"; }
for s in n012 n018; do rt rtofs_glo_2ds_${s}_diag.nc; done
for s in n012 n018 n024; do rt rtofs_glo_3dz_${s}_6hrly_hvr_US_east.nc; done
for f in $(seq 0 6 120); do
  rt "$(printf 'rtofs_glo_2ds_f%03d_diag.nc' "$f")"
  [ "$f" -ge 6 ] && rt "$(printf 'rtofs_glo_3dz_f%03d_6hrly_hvr_US_east.nc' "$f")"
done

# ADT (CMEMS NRT L4), CO-OPS WL xml (11 stations, PDY and PDY-1), St. Lawrence CSV
for d in "$PDY" "$PDYm1"; do
  if [ -z "${HAVE_GROUP[adt]:-}" ] && ! skipped adt; then
    fb adt "$DCOM/$d/validation_data/marine/cmems/ssh/nrt_global_allsat_phy_l4_${d}_${d}.nc" \
       "dcom/$d/validation_data/marine/cmems/ssh/nrt_global_allsat_phy_l4_${d}_${d}.nc"
  fi
  if [ -z "${HAVE_GROUP[wl]:-}" ] && ! skipped wl; then
    for x in "$DCOM/$d"/coops_waterlvlobs/*.xml; do
      [ -f "$x" ] && add wl "$x" "dcom/$d/coops_waterlvlobs/$(basename "$x")"
    done
  fi
  if [ -z "${HAVE_GROUP[law]:-}" ] && ! skipped law; then
    for sub in can_streamgauge canadian_water; do
      x=$DCOM/$d/$sub/02OA016_hydrometric.csv
      [ -f "$x" ] && add law "$x" "dcom/$d/$sub/02OA016_hydrometric.csv"
    done
  fi
done

# ---- 3. always-copied groups -------------------------------------------------
addtree() {   # addtree group dir relprefix  (all regular files, honoring size flags)
  local g=$1 dir=$2 pre=$3 f rel
  skipped "$g" && return
  if [ ! -d "$dir" ]; then echo "$g	$dir/ (directory)" >> "$MISSING"; return; fi
  while IFS= read -r -d '' f; do
    rel=${f#$dir/}
    case "$rel" in
      *.init.nowcast.nc|*init.nowcast*.nc) [ $SKIP_INIT -eq 1 ] && continue ;;
      *rst.nowcast.nc|*/hotstart_it=*.nc|hotstart_it=*.nc) [ $SKIP_RST -eq 1 ] && continue ;;
      *.restart.nc) [ $SKIP_RESTART -eq 1 ] && continue ;;
      *restart_outputs/*.nc)
        case "$(basename "$f")" in staout_*|mirror*) ;; *) [ $SKIP_FIELDS -eq 1 ] && continue ;; esac ;;
    esac
    add "$g" "$f" "$pre/$rel"
  done < <(find "$dir" -type f -print0)
}

for c in $COMOUT_DIRS; do addtree comout "$c" "comout/$(basename "$(dirname "$c")")"; done
addtree seeds  "$DYN_SEED" seeds/$(basename "$DYN_SEED")
addtree opsref "$OPS_KEEP" ops_keep/$(basename "$OPS_KEEP")
addtree opsref "$OPS_RERUN" ops_rerun/stofs_3d_atl.$PDY/rerun

# provenance: code revisions, config, PBS cards, fix-file listing (fix itself is NOT copied)
if ! skipped provenance; then
  PROV=$WORK/provenance; rm -rf "$PROV"; mkdir -p "$PROV"
  for r in nos-workflow nos-workflow/ush/python/nos-utils; do
    d=$PACKAGEROOT/$r
    if [ -d "$d/.git" ] || [ -f "$d/.git" ]; then
      { echo "$r"; git -C "$d" rev-parse HEAD; git -C "$d" status --short | head -50; } > "$PROV/git_$(basename "$r").txt" 2>&1
    fi
  done
  cp "$PACKAGEROOT"/nos-workflow/parm/systems/stofs_3d_atl_ufs_standalone.yaml "$PROV"/ 2>/dev/null
  cp "$PACKAGEROOT"/nos-workflow/pbs/stofs_3d_atl_ufs_standalone/*.pbs "$PROV"/ 2>/dev/null
  ls -lR "$PACKAGEROOT"/nos-workflow/fix/stofs_3d_atl_ufs > "$PROV/fix_listing.txt" 2>&1
  ls -l "$PACKAGEROOT"/nos-workflow/exec > "$PROV/exec_listing.txt" 2>&1
  find "$PROV" -type f -print0 | while IFS= read -r -d '' f; do add provenance "$f" "provenance/${f#$PROV/}"; done
fi

# dedupe on destination
sort -u -t "$(printf '\t')" -k3,3 "$PLAN" -o "$PLAN"

# ---- 4. summary --------------------------------------------------------------
declare -A GCNT GSZ
TOTAL=0; N=0
while IFS=$'\t' read -r g src rel; do
  s=$(stat -c %s "$src" 2>/dev/null || echo 0)
  GCNT[$g]=$(( ${GCNT[$g]:-0} + 1 )); GSZ[$g]=$(( ${GSZ[$g]:-0} + s ))
  TOTAL=$((TOTAL + s)); N=$((N+1))
done < "$PLAN"

hum() { numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "$1 B"; }
declare -A PUB=( [gfs]="S3 noaa-gfs-bdp-pds" [hrrr]="S3 noaa-hrrr-bdp-pds" [nwm]="S3 noaa-nwm-pds"
  [rtofs]="S3 noaa-nws-rtofs-pds" [adt]="Copernicus Marine (login)" [wl]="CO-OPS API (not byte-identical)"
  [law]="ECCC datamart (rolling)" [opsref]="S3 noaa-nos-stofs3d-pds (partly)" [seeds]="NO" [comout]="NO" [provenance]="NO" [other]="?" )
echo
echo "case bundle: $RUN PDY=$PDY cyc=$CYC -> $DEST"
echo "manifests read: $MANFOUND (0 means pattern fallback for everything)"
printf '%-11s %7s %10s   %s\n' group files size public
for g in "${!GCNT[@]}"; do printf '%-11s %7s %10s   %s\n' "$g" "${GCNT[$g]}" "$(hum "${GSZ[$g]}")" "${PUB[$g]:-?}"; done | sort
printf '%-11s %7s %10s\n' TOTAL "$N" "$(hum "$TOTAL")"
AVAIL=$(df -Pk "$DEST" | awk 'NR==2{print $4*1024}')
echo "free space at dest: $(hum "$AVAIL")"
[ "$TOTAL" -gt "$AVAIL" ] && echo "WARNING: bundle does not fit in free space; use --skip-public / --skip-big"
NM=$(wc -l < "$MISSING")
echo "missing: $NM (listed in $DEST/MISSING.txt)"
cp "$MISSING" "$DEST/MISSING.txt"
[ "$NM" -gt 0 ] && head -40 "$MISSING" | sed 's/^/   /'
cp "$PLAN" "$DEST/PLAN.tsv"

if [ $DRY -eq 1 ]; then echo "dry run: nothing copied"; exit 0; fi

# ---- 5. copy -----------------------------------------------------------------
i=0; COPIED=0; SKIPPED=0; FAIL=0
while IFS=$'\t' read -r g src rel; do
  i=$((i+1))
  out=$DEST/$rel
  s=$(stat -c %s "$src")
  if [ -f "$out" ] && [ "$(stat -c %s "$out")" = "$s" ]; then SKIPPED=$((SKIPPED+1)); continue; fi
  mkdir -p "$(dirname "$out")"
  echo "[$i/$N] $g $rel ($(hum "$s"))"
  if cp "$src" "$out.part" && mv "$out.part" "$out"; then COPIED=$((COPIED+1))
  else FAIL=$((FAIL+1)); echo "FAILED: $src" >&2; rm -f "$out.part"; fi
done < "$PLAN"
echo "copied=$COPIED already-present=$SKIPPED failed=$FAIL"

# ---- 6. MANIFEST.txt (md5  size  relpath) ------------------------------------
MAN=$DEST/MANIFEST.txt
declare -A OLD
[ -f "$MAN" ] && while read -r m s r; do OLD[$r]="$m $s"; done < "$MAN"
NEW=$WORK/manifest.new; : > "$NEW"; TOHASH=$WORK/tohash.txt; : > "$TOHASH"
while IFS= read -r -d '' f; do
  r=${f#$DEST/}; s=$(stat -c %s "$f")
  if [ $MD5 -eq 0 ]; then echo "- $s $r" >> "$NEW"
  elif [ "${OLD[$r]:-x}" != "x" ] && [ "${OLD[$r]##* }" = "$s" ]; then echo "${OLD[$r]} $r" >> "$NEW"
  else printf '%s\0' "$f" >> "$TOHASH"; fi
done < <(find "$DEST" -type f ! -path "$WORK/*" ! -name MANIFEST.txt ! -name '*.part' -print0)
if [ -s "$TOHASH" ]; then
  export DEST
  xargs -0 -n1 -P "$JOBS" sh -c 'f=$1; printf "%s %s %s\n" "$(md5sum "$f" | cut -d" " -f1)" "$(stat -c %s "$f")" "${f#$DEST/}"' _ < "$TOHASH" >> "$NEW"
fi
sort -k3 "$NEW" > "$MAN"
echo "MANIFEST.txt: $(wc -l < "$MAN") files, total $(hum "$(awk '{t+=$2} END{print t+0}' "$MAN")")"
rm -f "$NEW" "$TOHASH"
echo "done. Re-point a prep at the bundle: see case_bundle_20261001_inventory.txt"
