#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR=${INPUT_DIR:-/mnt/input}
OUTPUT_DIR=${OUTPUT_DIR:-/mnt/output}

PREPROC_MODE=${PREPROC_MODE:-native}          # native | atlas
ATLAS_T1=${ATLAS_T1:-}                        # set path if PREPROC_MODE=atlas

# SLICER=/opt/Slicer/Slicer
SLICER_BIN=${SLICER_BIN:-/Applications/Slicer.app/Contents/MacOS/Slicer}
SCRIPT=/app/render_brain_cover.py

echo "[INFO] Input:  $INPUT_DIR"
echo "[INFO] Output: $OUTPUT_DIR"

shopt -s nullglob

# --- helper: convert a DICOM dir to NIfTI using utils_mri.py
convert_dicom() {
  local dicom_dir="$1"
  local out_nii="$2"
  echo "[INFO] Converting DICOM -> NIfTI: $dicom_dir -> $out_nii"
  python /app/dicom_convert.py --in "$dicom_dir" --out "$out_nii"
}

# Find all NIfTI files and DICOM directories (heuristic: contains at least one .dcm)
find_cases() {
  # NIfTI files
  for f in "$INPUT_DIR"/*.nii "$INPUT_DIR"/*.nii.gz; do
    [ -f "$f" ] && echo "$f"
  done
  # DICOM dirs
  for d in "$INPUT_DIR"/*; do
    echo "$d"
  done
}

process_case() {
  local in="$1"
  local stem
  stem="$(basename "$in")"
  stem="${stem%%.*}"

  mkdir -p "$OUTPUT_DIR/$stem"

  # 1) Load NIfTI or DICOM
  local nii="$in"
  echo "$in"
  if [ -d "$in" ]; then
    nii="$OUTPUT_DIR/$stem/${stem}.nii.gz"
    convert_dicom "$in" "$nii"
  fi

  local preproc_dir="$OUTPUT_DIR/$stem/preproc"
  echo "[INFO] ANTs preprocessing ($PREPROC_MODE): $nii"
  if [ "$PREPROC_MODE" = "atlas" ] && [ -n "${ATLAS_T1:-}" ]; then
    python /app/preprocess.py --mode atlas --t1 "$nii" --atlas "$ATLAS_T1" --outdir "$preproc_dir"
  else
    python /app/preprocess.py --mode native --t1 "$nii" --outdir "$preproc_dir"
  fi
  # pick best preprocessed file (written by the helper)
  PREPICK=$(cat "$preproc_dir/_picked.txt" 2>/dev/null || true)
  local seg_input="${PREPICK:-$nii}"
  echo "[INFO] Using for segmentation: $seg_input"

  # 2) Segment with Brainchop CLI (CPU)
#   echo "[INFO] Brainchop: $nii"
#   brainchop "$nii" -m DKatlas -o "$OUTPUT_DIR/$stem/${stem}_seg.nii.gz"
  echo "[INFO] Brainchop: $seg_input"
  printf 'n\n' | brainchop "$seg_input" -m DKatlas -o "$OUTPUT_DIR/$stem/${stem}_seg.nii.gz"


  # (Optional) 3) render with Slicer later if needed using $SLICER and $SCRIPT
  # 3) Render still (Slicer headless on macOS)
#   echo "[INFO] Slicer render: $stem"
#   "$SLICER_BIN" --no-splash \
#     --python-script "$SCRIPT" \
#         --volume "$nii" \
#         --labels "$OUTPUT_DIR/$stem/${stem}_seg.nii.gz" \
#         --out "$OUTPUT_DIR/$stem/${stem}_cover.png" \
#         --preset "DTI-FA-Brain" \
#         --opacity 0.35
}

any=false
for c in $(find_cases); do
  any=true
  process_case "$c"
done

if ! $any; then
  echo "[WARN] No inputs found in $INPUT_DIR (.nii/.nii.gz or DICOM folders with .dcm)."
fi

