FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# ---------- SYSTEM DEPENDENCIES ----------
RUN apt-get update && apt-get install -y \
    # Core utilities
    curl \
    ca-certificates \
    build-essential \

    # LibreOffice (Office → PDF)
    libreoffice \
    libreoffice-calc \
    libreoffice-writer \
    libreoffice-core \
    libreoffice-common \
    libreoffice-java-common \
    default-jre \

    # Fonts (important for PDF rendering)
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

    # Script detection support
    tesseract-ocr-script-latn \
    tesseract-ocr-script-deva \

    # Image libs
    libgl1 \
    libglib2.0-0 \
    libjpeg62-turbo \
    zlib1g \

    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------- APP SETUP ----------
WORKDIR /app

COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway uses PORT env variable
ENV PORT=10000

EXPOSE 10000

CMD ["python", "app.py"]
