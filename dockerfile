# Use a lightweight Python 3.11 base image
FROM python:3.11-slim

# ------------------------
# Install system dependencies (Tesseract OCR + OpenCV dependencies)
# ------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
        build-essential \
        pkg-config && \
    rm -rf /var/lib/apt/lists/*

# ------------------------
# Set working directory
# ------------------------
WORKDIR /app

# ------------------------
# Copy Python dependencies and install
# ------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------
# Copy the rest of the backend code
# ------------------------
COPY . .

# ------------------------
# Expose port for Railway
# ------------------------
EXPOSE 5000

# ------------------------
# Run the Flask app
# ------------------------
CMD ["python", "app.py"]
