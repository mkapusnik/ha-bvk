# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# Ensure `/app/scraper` is importable as the `scraper` package when
# running `/app/main.py` from the repo root.
ENV PYTHONPATH=/app

# Install Chromium + driver (as required by the scraper)
RUN apt-get update \
  && apt-get install -y --no-install-recommends chromium chromium-driver tesseract-ocr \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy current scraper sources
COPY . /app/scraper

# Keep compatibility with existing entrypoint expecting /app/main.py
RUN ln -sf /app/scraper/main.py /app/main.py \
  && ln -sf /app/scraper/requirements.txt /app/requirements.txt

CMD ["python", "/app/main.py"]
