# Dockerfile
FROM python:3.11-slim

# 1) System deps
# - clang + build-essential: tinygrad's CPU backend JIT-compiles kernels and needs a C compiler
# - xvfb et al. only if you later add headless Slicer rendering; harmless to include
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang build-essential \
    xvfb xauth x11-apps libglib2.0-0 libxrender1 libsm6 libxext6 libxkbcommon0 libxcb1 \
  && rm -rf /var/lib/apt/lists/*

# 2) Python deps
# - brainchop provides the CLI `brainchop`
# - SimpleITK handles DICOM series -> NIfTI
# - nibabel/numpy are common MRI helpers
RUN pip install --no-cache-dir \
    brainchop \
    SimpleITK \
    nibabel \
    numpy

# 3) Runtime env: keep CPU-only small boxes happy
# - tinygrad reads these env vars; clamp threads to your 4-core server
ENV CC=clang \
    CPU=1 \
    OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

# 4) App files
WORKDIR /app
# Your converter file is named dicom_convert.py in the entrypoint; copy it as-is.
# (If your file is actually utils_mri.py, either rename it or adjust the entrypoint.)
COPY dicom_convert.py /app/dicom_convert.py
COPY entrypoint.sh     /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 5) Helpful directories (you will bind-mount real paths at runtime)
RUN mkdir -p /mnt/input /mnt/output

# 6) Quick self-check so builds fail fast if the CLI isn't present
RUN brainchop --help >/dev/null

# 7) Default command
ENTRYPOINT ["/app/entrypoint.sh"]

