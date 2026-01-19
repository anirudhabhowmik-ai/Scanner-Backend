from flask import Blueprint, request, jsonify
from PIL import Image
import cv2
import numpy as np
import pytesseract
import platform
import os
import subprocess

ocr_bp = Blueprint("ocr", __name__)

# Tesseract configuration for different environments
def setup_tesseract():
    """Configure Tesseract for different environments"""
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
    
    # Linux/Production
    else:
        # Check if tesseract is in PATH
        try:
            result = subprocess.run(['which', 'tesseract'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                tess_path = result.stdout.strip()
                print(f"✓ Tesseract found at: {tess_path}")
                return True
        except Exception as e:
            print(f"⚠ Error checking tesseract: {e}")
        
        # Try common Linux paths
        possible_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",  # macOS Homebrew
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"✓ Tesseract found at: {path}")
                return True
        
        print("⚠ Tesseract not found in common locations")
        return False

# Setup on module load
TESSERACT_AVAILABLE = setup_tesseract()

def preprocess_for_ocr(img):
    """Advanced preprocessing for better OCR accuracy"""
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Resize if too small (OCR works better with larger text)
    h, w = gray.shape
    if h < 800:
        scale = 800 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Apply bilateral filter to reduce noise while keeping edges
    blur = cv2.bilateralFilter(gray, 5, 50, 50)
    
    # Adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
    
    # Optional: Morphological operations to clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
    
    return cleaned

@ocr_bp.route("/ocr", methods=["POST", "OPTIONS"])
def ocr_extract():
    """Extract text from image using Tesseract OCR"""
    if request.method == "OPTIONS":
        return "", 204
    
    try:
        print("\n=== OCR REQUEST ===")
        
        # Check if Tesseract is available
        if not TESSERACT_AVAILABLE:
            print("ERROR: Tesseract not available")
            return jsonify({
                "error": "Tesseract OCR is not installed on the server",
                "details": "Please install tesseract-ocr package"
            }), 503
        
        if "image" not in request.files:
            print("ERROR: No image in request")
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files["image"]
        img_bytes = file.read()
        print(f"Received image: {len(img_bytes)} bytes")
        
        # Decode image
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            print("ERROR: Could not decode image")
            return jsonify({"error": "Invalid image format"}), 400
        
        h, w = img.shape[:2]
        print(f"Image size: {w}x{h}")
        
        # Preprocess for OCR
        processed = preprocess_for_ocr(img)
        print(f"Preprocessed: {processed.shape}")
        
        # Convert to PIL Image
        pil_img = Image.fromarray(processed)
        
        # Perform OCR with custom config
        # --oem 3: Use default OCR Engine Mode
        # --psm 6: Assume uniform block of text
        custom_config = r'--oem 3 --psm 6'
        
        print("Running Tesseract...")
        text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng')
        
        # Clean up text
        text = text.strip()
        
        print(f"✓ Extracted {len(text)} characters")
        if len(text) > 0:
            print(f"Preview: {text[:100]}...")
        
        return jsonify({
            "success": True,
            "text": text,
            "length": len(text)
        })
    
    except pytesseract.TesseractNotFoundError as e:
        print(f"ERROR: Tesseract not found - {e}")
        return jsonify({
            "error": "Tesseract OCR engine not found",
            "details": str(e),
            "help": "Install: apt-get install tesseract-ocr (Linux) or brew install tesseract (Mac)"
        }), 503
    
    except Exception as e:
        print(f"ERROR in OCR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "OCR processing failed",
            "details": str(e)
        }), 500

@ocr_bp.route("/tesseract-check", methods=["GET"])
def tesseract_check():
    """Check if Tesseract is properly installed"""
    try:
        version = pytesseract.get_tesseract_version()
        
        # Get available languages
        langs = pytesseract.get_languages(config='')
        
        return jsonify({
            "installed": True,
            "available": TESSERACT_AVAILABLE,
            "version": str(version),
            "languages": langs,
            "path": pytesseract.pytesseract.tesseract_cmd if hasattr(pytesseract.pytesseract, 'tesseract_cmd') else "default"
        })
    except Exception as e:
        return jsonify({
            "installed": False,
            "available": False,
            "error": str(e),
            "help": "Install tesseract-ocr: apt-get install tesseract-ocr (Linux)"
        }), 503