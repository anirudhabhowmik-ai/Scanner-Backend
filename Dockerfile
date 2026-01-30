FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# ---------------- SYSTEM DEPENDENCIES ----------------
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    build-essential \

    # LibreOffice (Office → PDF)
    libreoffice \
    libreoffice-calc \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-core \
    libreoffice-common \
    libreoffice-java-common \
    default-jre \

    # Required for LibreOffice headless
    libxinerama1 \
    libxrender1 \
    libfontconfig1 \
    libcups2 \
    libsm6 \
    libice6 \

    # Fonts
    fonts-dejavu \
    fonts-liberation \
    fonts-noto \
    fonts-noto-cjk \

    # PDF + OCR tools
    ghostscript \
    qpdf \
    poppler-utils \
    unpaper \
    pngquant \
    ocrmypdf \

    # Tesseract OCR + Languages
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
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
    tesseract-ocr-script-latn \
    tesseract-ocr-script-deva \

    # Image libs
    libgl1 \
    libglib2.0-0 \
    libjpeg62-turbo \
    zlib1g \

    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------------- OCR FIXES ----------------

ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/g' /etc/ImageMagick-6/policy.xml || true

RUN if [ -f /etc/ghostscript/cidfmap ]; then \
        echo "Ghostscript found"; \
    fi && \
    sed -i '/pattern="PDF"/d' /etc/ImageMagick-6/policy.xml 2>/dev/null || true && \
    sed -i '/pattern="PS"/d' /etc/ImageMagick-6/policy.xml 2>/dev/null || true && \
    sed -i '/pattern="EPS"/d' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

ENV HOME=/tmp
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ---------------- APP SETUP ----------------
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN tesseract --version && \
    gs --version && \
    ocrmypdf --version && \
    echo "All OCR tools installed successfully"

# 🔥 FIX: Gunicorn configured for long OCR jobs
CMD gunicorn \
  --bind 0.0.0.0:$PORT \
  --workers 1 \
  --threads 2 \
  --timeout 300 \
  --graceful-timeout 300 \
  --max-requests 50 \
  app:app
