FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for PDF parsing and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure LF line endings for startup scripts across OS checkouts
RUN sed -i 's/\r$//' startup.sh && chmod +x startup.sh

EXPOSE 8000

CMD ["sh", "startup.sh"]