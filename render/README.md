# HelloMRI – CPU Segmentation & Slicer Render

Minimal CPU-only segmentation pipeline that: (1) converts **DICOM → NIfTI** (2) runs atlas segmentation (default: `DKatlas`) (3) (Optional) Renders a cover PNG via **3D Slicer**.

---

## Inputs

Place data in `INPUT_DIR` (default: `/mnt/input`):

- **NIfTI**: `*.nii` / `*.nii.gz`  
- **DICOM**: pass the series folder **or** a parent; the converter recurses to find a valid series.

Example:
/mnt/input/
├─ CaseA.nii.gz
└─ ST000000/
├─ SE000001/ # DICOM series
└─ SE000002/


## Outputs

For each case `<stem>` a subfolder is created in `OUTPUT_DIR` (default: `/mnt/output`):

/mnt/output/<stem>/
├─ <stem>.nii.gz # written if input was DICOM (converted NIfTI)
├─ <stem>_seg.nii.gz # segmentation
└─ <stem>_cover.png # Slicer-rendered image (if enabled)


---

## Build & Run (Docker)

```
# Build
docker build -t hellomri-segmentator .

# Run
docker run --rm \
  -v /ABS/PATH/input:/mnt/input:ro \
  -v /ABS/PATH/output:/mnt/output \
  -e INPUT_DIR=/mnt/input \
  -e OUTPUT_DIR=/mnt/output \
  hellomri-segmentator
```
