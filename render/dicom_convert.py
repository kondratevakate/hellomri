# utils_mri.py
import os, sys, argparse
import SimpleITK as sitk  # SimpleITK's series reader sorts DICOM slices correctly. See docs. 

def dicom_series_to_nifti(dicom_dir: str, out_path: str) -> str:
    """Convert a DICOM series folder to a single NIfTI file (keeps spacing & orientation)."""
    reader = sitk.ImageSeriesReader()
    series = reader.GetGDCMSeriesFileNames(dicom_dir)
    if not series:
        raise FileNotFoundError(f"No DICOM files found in: {dicom_dir}")
    reader.SetFileNames(series)
    img = reader.Execute()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    sitk.WriteImage(img, out_path)
    return out_path

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="DICOM series -> NIfTI (.nii or .nii.gz)")
    ap.add_argument("--in", dest="inp", required=True, help="Path to a DICOM series folder")
    ap.add_argument("--out", dest="out", required=True, help="Output NIfTI path (.nii or .nii.gz)")
    args = ap.parse_args()

    try:
        outp = dicom_series_to_nifti(args.inp, args.out)
        print(f"[OK] Wrote {outp}")
    except Exception as e:
        print(f"[ERR] {e}", file=sys.stderr)
        sys.exit(2)

