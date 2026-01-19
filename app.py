from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
import os
from pypdf import PdfWriter
import traceback
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure Tesseract path (update if needed for your system)
# For Windows: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# For Linux/Mac: usually auto-detected if installed via package manager


def order_points(pts):
    """Order points in clockwise order: top-left, top-right, bottom-right, bottom-left"""
    rect = np.zeros((4, 2), dtype="float32")
    
    # Sum and diff for ordering
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left (smallest sum)
    rect[2] = pts[np.argmax(s)]      # bottom-right (largest sum)
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]   # top-right (smallest diff)
    rect[3] = pts[np.argmax(diff)]   # bottom-left (largest diff)
    
    return rect


def detect_document_contour(img):
    """
    Advanced document detection using multiple edge detection techniques
    Returns: 4-point contour or None
    """
    h, w = img.shape[:2]
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Create multiple processed versions
    # 1. Bilateral filter - reduces noise while keeping edges
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # 2. Morphological gradient - highlights edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    morph_gradient = cv2.morphologyEx(blur, cv2.MORPH_GRADIENT, kernel)
    
    # 3. Multiple Canny edge detection with different thresholds
    edges1 = cv2.Canny(blur, 30, 100)
    edges2 = cv2.Canny(blur, 50, 150)
    edges3 = cv2.Canny(blur, 75, 200)
    edges4 = cv2.Canny(morph_gradient, 30, 100)
    
    # Combine all edge maps
    edges_combined = cv2.bitwise_or(edges1, edges2)
    edges_combined = cv2.bitwise_or(edges_combined, edges3)
    edges_combined = cv2.bitwise_or(edges_combined, edges4)
    
    # Dilate to close gaps in edges
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges_combined, kernel_dilate, iterations=2)
    
    # Close small gaps
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel_close)
    
    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort by area (largest first)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:25]
    
    min_area = (w * h) * 0.05  # Minimum 5% of image area
    max_area = (w * h) * 0.98  # Maximum 98% of image area
    
    candidates = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        
        # Skip if too small or too large
        if area < min_area or area > max_area:
            continue
        
        # Approximate contour to polygon
        peri = cv2.arcLength(contour, True)
        
        # Try different epsilon values for approximation
        for epsilon_mult in [0.015, 0.02, 0.03, 0.04, 0.05]:
            epsilon = epsilon_mult * peri
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) == 4:
                # Check if it's reasonably rectangular
                # Calculate aspect ratio and angles
                pts = approx.reshape(4, 2)
                ordered = order_points(pts)
                
                # Calculate width and height of the detected rectangle
                widthA = np.linalg.norm(ordered[0] - ordered[1])
                widthB = np.linalg.norm(ordered[2] - ordered[3])
                heightA = np.linalg.norm(ordered[0] - ordered[3])
                heightB = np.linalg.norm(ordered[1] - ordered[2])
                
                # Check aspect ratio is reasonable (not too thin)
                avg_width = (widthA + widthB) / 2
                avg_height = (heightA + heightB) / 2
                
                if avg_width > 0 and avg_height > 0:
                    aspect_ratio = max(avg_width, avg_height) / min(avg_width, avg_height)
                    
                    # Accept if aspect ratio is reasonable (less than 10:1)
                    if aspect_ratio < 10:
                        # Score based on area and aspect ratio
                        score = area / (aspect_ratio * 0.1)
                        candidates.append((approx, area, score))
                        break
    
    # Return best candidate if found
    if candidates:
        # Sort by score
        candidates.sort(key=lambda x: x[2], reverse=True)
        best_contour = candidates[0][0]
        return best_contour
    
    return None


@app.route("/detect-corners", methods=["POST", "OPTIONS"])
def detect_corners():
    if request.method == "OPTIONS":
        return "", 204
    
    try:
        print("\n=== DETECT CORNERS REQUEST ===")
        
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files["image"]
        img_bytes = file.read()
        
        # Decode image
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Invalid image"}), 400
        
        h, w = img.shape[:2]
        print(f"Image size: {w}x{h}")
        
        # Resize if too large (for faster processing)
        max_dim = 1500
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img_resized = cv2.resize(img, (new_w, new_h))
            scale_back = max(h, w) / max_dim
        else:
            img_resized = img
            scale_back = 1.0
        
        # Detect document
        doc_contour = detect_document_contour(img_resized)
        
        if doc_contour is not None:
            # Scale back to original size
            pts = doc_contour.reshape(4, 2) * scale_back
            ordered_pts = order_points(pts)
            corners = ordered_pts.tolist()
            
            print(f"✓ Document detected with corners: {corners}")
            
            return jsonify({
                "detected": True,
                "corners": corners,
                "width": w,
                "height": h
            })
        else:
            # Use full image with small margin
            margin_percent = 0.02  # 2% margin
            margin_w = int(w * margin_percent)
            margin_h = int(h * margin_percent)
            
            print("No document detected, using full image with margins")
            
            return jsonify({
                "detected": False,
                "corners": [
                    [margin_w, margin_h],
                    [w - margin_w, margin_h],
                    [w - margin_w, h - margin_h],
                    [margin_w, h - margin_h]
                ],
                "width": w,
                "height": h
            })
    
    except Exception as e:
        print(f"ERROR in /detect-corners: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/scan", methods=["POST", "OPTIONS"])
def scan_and_convert():
    if request.method == "OPTIONS":
        return "", 204
    
    try:
        print("\n=== SCAN REQUEST ===")
        
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files["image"]
        output_format = request.form.get("format", "jpg").lower()
        enhance = request.form.get("enhance", "true").lower() == "true"
        
        img_bytes = file.read()
        
        # Decode image
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Invalid image format"}), 400
        
        print(f"Image decoded: shape={img.shape}")
        
        # Apply enhancement if requested
        if enhance:
            print("Applying enhancement...")
            # Convert to LAB color space
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            
            # Merge back
            enhanced_lab = cv2.merge((l_enhanced, a, b))
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # Slight sharpening
            kernel = np.array([[-1, -1, -1],
                              [-1,  9, -1],
                              [-1, -1, -1]]) / 1.0
            enhanced = cv2.filter2D(enhanced, -1, kernel)
        else:
            enhanced = img
        
        # Convert BGR to RGB
        rgb_img = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        
        output = io.BytesIO()
        
        # Save in requested format
        if output_format in ["jpg", "jpeg"]:
            pil_img.save(output, format="JPEG", quality=95)
            mimetype = "image/jpeg"
            filename = "scanned.jpg"
        elif output_format == "pdf":
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            pil_img.save(output, format="PDF", resolution=300.0)
            mimetype = "application/pdf"
            filename = "scanned.pdf"
        else:
            return jsonify({"error": "Unsupported format"}), 400
        
        output.seek(0)
        print(f"Sending {filename}: {output.getbuffer().nbytes} bytes")
        
        return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)
    
    except Exception as e:
        print(f"ERROR in /scan: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/merge-pdf", methods=["POST", "OPTIONS"])
def merge_pdfs():
    if request.method == "OPTIONS":
        return "", 204
    
    try:
        print("\n=== MERGE PDF REQUEST ===")
        
        if "files" not in request.files:
            return jsonify({"error": "No PDF files uploaded"}), 400
        
        pdf_files = request.files.getlist("files")
        if len(pdf_files) < 2:
            return jsonify({"error": "Upload at least two PDFs"}), 400
        
        writer = PdfWriter()
        for pdf in pdf_files:
            if not pdf.filename.lower().endswith(".pdf"):
                return jsonify({"error": "Only PDF files allowed"}), 400
            writer.append(pdf)
        
        output = io.BytesIO()
        writer.write(output)
        writer.close()
        output.seek(0)
        
        print(f"Merged {len(pdf_files)} PDFs")
        
        return send_file(
            output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="merged.pdf"
        )
    except Exception as e:
        print(f"ERROR in /merge-pdf: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/ocr", methods=["POST", "OPTIONS"])
def ocr_extract():
    """Extract text from image using Tesseract OCR"""
    if request.method == "OPTIONS":
        return "", 204
    
    try:
        print("\n=== OCR REQUEST ===")
        
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files["image"]
        img_bytes = file.read()
        
        # Decode image
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Invalid image format"}), 400
        
        print(f"Processing image for OCR: shape={img.shape}")
        
        # Preprocessing for better OCR accuracy
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        # Convert to PIL Image for Tesseract
        pil_img = Image.fromarray(denoised)
        
        # Perform OCR with custom configuration for better accuracy
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng')
        
        # Clean up text
        text = text.strip()
        
        print(f"Extracted {len(text)} characters")
        print(f"Text preview: {text[:100]}...")
        
        return jsonify({
            "success": True,
            "text": text,
            "length": len(text)
        })
        
    except Exception as e:
        print(f"ERROR in /ocr: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "PDFMaster backend running",
        "version": "2.0",
        "endpoints": ["/scan", "/detect-corners", "/merge-pdf", "/ocr"]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n{'='*50}")
    print(f"PDFMaster Backend v2.0 - Enhanced Edge Detection")
    print(f"Running on http://127.0.0.1:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=True)