# Use lightweight Python image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # ---------------- LibreOffice (Office → PDF) ----------------
    libreoffice \
    libreoffice-calc \
    libreoffice-writer \
    libreoffice-core \
    libreoffice-common \
    libreoffice-java-common \
    default-jre \

    # ---------------- Fonts ----------------
    fonts-dejavu \
    fonts-liberation \
    fonts-noto \
    fonts-noto-cjk \

    # ---------------- WeasyPrint (HTML → PDF) ----------------
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \

    # ---------------- PDF & Image tools ----------------
    ghostscript \
    poppler-utils \
    pngquant \

    # ---------------- OCR ----------------
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ben \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-por \
    tesseract-ocr-rus \
    tesseract-ocr-jpn \
    tesseract-ocr-kor \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-ara \
    tesseract-ocr-hin \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Railway expects port 10000
EXPOSE 10000

# Run with production server (important)
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
