FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cache optimization)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the code
COPY . .

# Run with gunicorn (production-grade)
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]
