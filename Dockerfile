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

# 🔥🔥🔥 CRITICAL FIXES FOR SELECTABLE TEXT 🔥🔥🔥

# 1. Debian Bookworm tesseract path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# 2. FIX GHOSTSCRIPT PERMISSIONS (CRITICAL for OCR text layer)
# By default, Ghostscript has security restrictions that prevent
# reading/writing certain file types. We need to relax these for OCR.
RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/g' /etc/ImageMagick-6/policy.xml || true

# Alternative fix if the above doesn't work:
RUN if [ -f /etc/ghostscript/cidfmap ]; then \
        echo "Ghostscript found"; \
    fi && \
    # Remove PDF security restrictions
    sed -i '/pattern="PDF"/d' /etc/ImageMagick-6/policy.xml 2>/dev/null || true && \
    sed -i '/pattern="PS"/d' /etc/ImageMagick-6/policy.xml 2>/dev/null || true && \
    sed -i '/pattern="EPS"/d' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

# 3. Prevent LibreOffice profile corruption
ENV HOME=/tmp

# 4. Ensure proper locale for text encoding
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ---------------- APP SETUP ----------------
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Verify installations
RUN tesseract --version && \
    gs --version && \
    ocrmypdf --version && \
    echo "All OCR tools installed successfully"

CMD gunicorn --bind 0.0.0.0:$PORT app:app