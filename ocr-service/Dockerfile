FROM python:3.11-slim

# OpenCV / ONNX Runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV HF_HOME=/opt/hf PYTHONUNBUFFERED=1 MALLOC_ARENA_MAX=2
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bake the models into the image (no download on cold start), then make a
# Latin-only folder: the CJK / RTL / Indic recognizers and their language models
# load only when their files are present, and they cost memory English books don't need.
RUN python -c "import indra_ocr; indra_ocr.load(threads=1)" && python - <<'PY'
import shutil, indra_ocr
from pathlib import Path
src = Path(indra_ocr.model_dir())
dst = Path("/opt/indra-latin"); dst.mkdir(parents=True)
skip = ("rec_cjk", "rec_rtl", "rec_world", "rec_other", "script", "lm_cjk", "lm_world", "lm_rtl", "lm_other")
for f in src.iterdir():
    if not f.name.startswith(skip):
        shutil.copy(f.resolve(), dst / f.name)
print("latin models:", sorted(p.name for p in dst.iterdir()))
PY
ENV HF_HUB_OFFLINE=1 INDRA_OCR_MODEL_DIR=/opt/indra-latin

COPY app.py .
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
