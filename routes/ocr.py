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

def deskew_image(image):
    """Automatically deskew/rotate the image for better OCR"""
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Threshold
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    
    # Find all coordinates of rotated text
    coords = np.column_stack(np.where(thresh > 0))
    
    # Calculate rotation angle
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        
        # Correct angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Only deskew if angle is significant (more than 0.5 degrees)
        if abs(angle) > 0.5:
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h),
                                    flags=cv2.INTER_CUBIC,
                                    borderMode=cv2.BORDER_REPLICATE)
            print(f"  Deskewed by {angle:.2f} degrees")
            return rotated
    
    return image

def remove_noise(image):
    """Remove noise while preserving text quality"""
    # Use Non-local Means Denoising - gentle settings
    if len(image.shape) == 3:
        denoised = cv2.fastNlMeansDenoisingColored(image, None, 6, 6, 7, 21)
    else:
        denoised = cv2.fastNlMeansDenoising(image, None, 6, 7, 21)
    return denoised

def enhance_contrast(gray):
    """Enhance contrast using multiple techniques"""
    # Apply CLAHE for local contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced

def get_optimal_threshold(gray):
    """Apply optimal thresholding technique based on image characteristics"""
    # Calculate image statistics
    mean_val = np.mean(gray)
    std_val = np.std(gray)
    
    print(f"  Image stats - Mean: {mean_val:.1f}, Std: {std_val:.1f}")
    
    # For low contrast images
    if std_val < 30:
        print("  Using adaptive thresholding (low contrast)")
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 21, 10
        )
    # For normal images
    else:
        print("  Using Otsu thresholding")
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return thresh

def preprocess_for_ocr(img, method='auto'):
    """Advanced preprocessing for better OCR accuracy with multiple methods"""
    # Remove noise first
    denoised = remove_noise(img)
    
    # Deskew the image
    deskewed = deskew_image(denoised)
    
    # Convert to grayscale
    if len(deskewed.shape) == 3:
        gray = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
    else:
        gray = deskewed
    
    # Resize if too small (OCR works better with 300+ DPI equivalent)
    h, w = gray.shape
    target_height = 1200  # Increased from 800
    if h < target_height:
        scale = target_height / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        print(f"  Upscaled by {scale:.2f}x to {gray.shape[1]}x{gray.shape[0]}")
    
    # Enhance contrast
    enhanced = enhance_contrast(gray)
    
    # Apply optimal thresholding
    thresh = get_optimal_threshold(enhanced)
    
    # Light morphological cleanup - ONLY if needed
    # Remove small noise
    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    return cleaned

def preprocess_simple(img):
    """Simple preprocessing - just grayscale and minor enhancement"""
    # This works better for already clean, high-quality scans
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    
    # Resize if needed
    h, w = gray.shape
    if h < 1000:
        scale = 1000 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Slight sharpening
    kernel = np.array([[-1,-1,-1],
                      [-1, 9,-1],
                      [-1,-1,-1]]) / 9
    sharpened = cv2.filter2D(gray, -1, kernel)
    
    return sharpened

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
        
        # Get preprocessing method from request (optional)
        preprocess_method = request.form.get("method", "auto")
        
        # Try multiple preprocessing methods and PSM modes for best results
        results = []
        
        # Method 1: Advanced preprocessing with PSM 3 (auto page segmentation)
        try:
            print("\n--- Method 1: Advanced + PSM 3 ---")
            processed1 = preprocess_for_ocr(img, method='auto')
            pil_img1 = Image.fromarray(processed1)
            
            # PSM 3: Fully automatic page segmentation (best for mixed layouts)
            config1 = r'--oem 3 --psm 3'
            text1 = pytesseract.image_to_string(pil_img1, config=config1, lang='eng').strip()
            results.append(('Advanced+PSM3', text1, len(text1)))
            print(f"  Result: {len(text1)} chars")
        except Exception as e:
            print(f"  Method 1 failed: {e}")
        
        # Method 2: Simple preprocessing with PSM 1 (auto with OSD)
        try:
            print("\n--- Method 2: Simple + PSM 1 ---")
            processed2 = preprocess_simple(img)
            pil_img2 = Image.fromarray(processed2)
            
            # PSM 1: Auto with orientation and script detection
            config2 = r'--oem 3 --psm 1'
            text2 = pytesseract.image_to_string(pil_img2, config=config2, lang='eng').strip()
            results.append(('Simple+PSM1', text2, len(text2)))
            print(f"  Result: {len(text2)} chars")
        except Exception as e:
            print(f"  Method 2 failed: {e}")
        
        # Method 3: Advanced preprocessing with PSM 6 (uniform block)
        try:
            print("\n--- Method 3: Advanced + PSM 6 ---")
            processed3 = preprocess_for_ocr(img, method='auto')
            pil_img3 = Image.fromarray(processed3)
            
            # PSM 6: Uniform block of text
            config3 = r'--oem 3 --psm 6'
            text3 = pytesseract.image_to_string(pil_img3, config=config3, lang='eng').strip()
            results.append(('Advanced+PSM6', text3, len(text3)))
            print(f"  Result: {len(text3)} chars")
        except Exception as e:
            print(f"  Method 3 failed: {e}")
        
        # Method 4: No preprocessing - direct OCR (for already clean images)
        try:
            print("\n--- Method 4: Direct + PSM 3 ---")
            if len(img.shape) == 3:
                gray_direct = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray_direct = img
            
            # Resize if too small
            h_d, w_d = gray_direct.shape
            if h_d < 1000:
                scale = 1000 / h_d
                gray_direct = cv2.resize(gray_direct, None, fx=scale, fy=scale, 
                                        interpolation=cv2.INTER_CUBIC)
            
            pil_img4 = Image.fromarray(gray_direct)
            config4 = r'--oem 3 --psm 3'
            text4 = pytesseract.image_to_string(pil_img4, config=config4, lang='eng').strip()
            results.append(('Direct+PSM3', text4, len(text4)))
            print(f"  Result: {len(text4)} chars")
        except Exception as e:
            print(f"  Method 4 failed: {e}")
        
        # Choose the best result (longest text with reasonable content)
        if not results:
            return jsonify({
                "error": "All OCR methods failed",
                "text": "",
                "length": 0
            }), 500
        
        # Sort by length and pick the longest
        results.sort(key=lambda x: x[2], reverse=True)
        best_method, best_text, best_length = results[0]
        
        print(f"\n✓ Best result from: {best_method}")
        print(f"✓ Extracted {best_length} characters")
        if best_length > 0:
            print(f"Preview: {best_text[:200]}...")
        
        # Return all results for debugging
        all_results = [{"method": r[0], "length": r[2]} for r in results]
        
        return jsonify({
            "success": True,
            "text": best_text,
            "length": best_length,
            "method_used": best_method,
            "all_methods": all_results
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