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

    # 🔥 REQUIRED so LibreOffice works in Docker headless
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

    # Script detection
    tesseract-ocr-script-latn \
    tesseract-ocr-script-deva \

    # Image libs
    libgl1 \
    libglib2.0-0 \
    libjpeg62-turbo \
    zlib1g \

    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 🔥🔥🔥 REAL FIX — Debian Bookworm path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Prevent LibreOffice profile corruption
ENV HOME=/tmp

# ---------------- APP SETUP ----------------
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
