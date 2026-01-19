from flask import Blueprint, request, jsonify
from PIL import Image
import cv2
import numpy as np
import pytesseract
import platform
import os

ocr_bp = Blueprint("ocr", __name__)

# =========================
# Tesseract configuration
# =========================
def setup_tesseract():
    """Configure Tesseract for Windows and Linux (Railway)"""
    system = platform.system()

    # Windows
    if system == "Windows":
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"✓ Tesseract found at: {path}")
                return True
        print("⚠ Tesseract not found in default Windows locations")
        return False

    # Linux / Railway server
    else:
        possible_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"✓ Tesseract found at: {path}")
                return True

        # If not found, warn
        print("⚠ Tesseract not found on Linux server")
        return False

# Setup on module load
TESSERACT_AVAILABLE = setup_tesseract()

# =========================
# OCR preprocessing
# =========================
def preprocess_for_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Resize if too small
    h, w = gray.shape
    if h < 800:
        scale = 800 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    blur = cv2.bilateralFilter(gray, 5, 50, 50)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
    return cleaned

# =========================
# OCR endpoint
# =========================
@ocr_bp.route("/ocr", methods=["POST", "OPTIONS"])
def ocr_extract():
    if request.method == "OPTIONS":
        return "", 204
    
    if not TESSERACT_AVAILABLE:
        return jsonify({
            "error": "Tesseract OCR is not installed on the server",
            "details": "Install tesseract-ocr system package"
        }), 503
    
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    np_img = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400

    processed = preprocess_for_ocr(img)
    pil_img = Image.fromarray(processed)

    # OCR config
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng').strip()

    return jsonify({
        "success": True,
        "text": text,
        "length": len(text)
    })

# =========================
# Tesseract check endpoint
# =========================
@ocr_bp.route("/tesseract-check", methods=["GET"])
def tesseract_check():
    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages(config='') if TESSERACT_AVAILABLE else []
        return jsonify({
            "installed": True,
            "available": TESSERACT_AVAILABLE,
            "version": str(version) if TESSERACT_AVAILABLE else None,
            "languages": langs,
            "path": pytesseract.pytesseract.tesseract_cmd if TESSERACT_AVAILABLE else None
        })
    except Exception as e:
        return jsonify({
            "installed": False,
            "available": False,
            "error": str(e),
            "help": "Install tesseract-ocr system package"
        }), 503
