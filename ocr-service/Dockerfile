FROM python:3.11-slim

# OpenCV / ONNX Runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV HF_HOME=/opt/hf PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bake the models (~76 MB) into the image so cold starts need no download
RUN python -c "import indra_ocr; indra_ocr.load(threads=1)"
ENV HF_HUB_OFFLINE=1

COPY app.py .
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
