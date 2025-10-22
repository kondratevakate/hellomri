# preprocess_ants.py
from pathlib import Path
import argparse

from brainles_preprocessing.modality import Modality, CenterModality
from brainles_preprocessing.preprocessor import (
    AtlasCentricPreprocessor,
    NativeSpacePreprocessor,
)
from brainles_preprocessing.normalization.percentile_normalizer import PercentileNormalizer
from brainles_preprocessing.registration.ANTs.ANTs import ANTsRegistrator
from brainles_preprocessing.n4_bias_correction.sitk.sitk_n4_bias_corrector import SitkN4BiasCorrector
# Brain extraction (optional): HD-BET or SynthStrip; comment out if not installed.
# from brainles_preprocessing.brain_extraction.hd_bet_extractor import HDBetExtractor
# from brainles_preprocessing.brain_extraction.synthstrip_extractor import SynthStripExtractor

def build_args():
    ap = argparse.ArgumentParser(description="ANTs preprocessing (N4 + optional ANTs registration)")
    ap.add_argument("--mode", choices=["atlas", "native"], default="atlas",
                    help="atlas: register to atlas + N4; native: N4 only")
    ap.add_argument("--t1", required=True, help="Path to T1w NIfTI (.nii.gz)")
    ap.add_argument("--flair", help="Optional FLAIR NIfTI")
    ap.add_argument("--t2", help="Optional T2 NIfTI")
    ap.add_argument("--atlas", default="", help="Atlas T1 (e.g., SRI24_T1.nii.gz). If empty, package defaults are used.")
    ap.add_argument("--outdir", required=True, help="Output folder")
    # toggles
    ap.add_argument("--no-n4", action="store_true", help="Disable N4 bias correction")
    ap.add_argument("--extract-brain", action="store_true", help="Enable brain extraction (requires extractor installed)")
    return ap.parse_args()

def main():
    a = build_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    # Normalizer (only needed if you request normalized_* outputs)
    normalizer = PercentileNormalizer(0.1, 99.9, 0, 1)

    # Choose brain extractor if you installed one (commented by default)
    brain_extractor = None
    # brain_extractor = HDBetExtractor()  # requires hd-bet installed
    # brain_extractor = SynthStripExtractor()  # requires synthstrip extra

    n4 = None if a.no_n4 else SitkN4BiasCorrector()
    ants = ANTsRegistrator()  # uses antspyx under the hood

    t1 = Path(a.t1)
    center = CenterModality(
        modality_name="t1",
        input_path=t1,
        normalizer=normalizer,  # only needed for normalized_* outputs
        # request raw outputs (brain-extracted & skull) so you have something to consume downstream
        raw_bet_output_path=out / "raw_bet" / f"{t1.stem}_bet_raw.nii.gz",
        raw_skull_output_path=out / "raw_skull" / f"{t1.stem}_skull_raw.nii.gz",
        # masks if you want them
        bet_mask_output_path=out / "masks" / f"{t1.stem}_bet_mask.nii.gz",
        # toggles
        n4_bias_correction=not a.no_n4,
        atlas_correction=True if a.mode == "atlas" else False,
    )

    movings = []
    for name, p in (("flair", a.flair), ("t2", a.t2)):
        if p:
            p = Path(p)
            movings.append(
                Modality(
                    modality_name=name, input_path=p, normalizer=normalizer,
                    raw_bet_output_path=out / "raw_bet" / f"{p.stem}_bet_raw.nii.gz",
                    raw_skull_output_path=out / "raw_skull" / f"{p.stem}_skull_raw.nii.gz",
                    n4_bias_correction=not a.no_n4,
                    atlas_correction=(a.mode == "atlas"),
                )
            )

    if a.mode == "atlas":
        # Atlas-centric pipeline: ANTs registration to atlas + N4 + (optional) extraction
        pre = AtlasCentricPreprocessor(
            center_modality=center,
            moving_modalities=movings,
            registrator=ants,
            n4_bias_corrector=n4,
            brain_extractor=brain_extractor,
        )
        # Optional: save intermediate folders (handy for debugging)
        pre.run(
            save_dir_coregistration=out / "coregistration",
            save_dir_atlas_registration=out / "atlas_registration",
            save_dir_n4_bias_correction=out / "n4_bias_correction",
            save_dir_brain_extraction=out / "brain_extraction",
        )
    else:
        # Native space: N4 (+ extraction) only, no atlas registration
        pre = NativeSpacePreprocessor(
            center_modality=center,
            moving_modalities=movings,
            n4_bias_corrector=n4,
            brain_extractor=brain_extractor,
        )
        pre.run(
            save_dir_n4_bias_correction=out / "n4_bias_correction",
            save_dir_brain_extraction=out / "brain_extraction",
        )

if __name__ == "__main__":
    main()

