from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
import os
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import traceback

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =========================
# DEBUG: Show edge detection (optional)
# =========================
@app.route("/debug-edges", methods=["POST", "OPTIONS"])
def debug_edges():
    """Returns the edge-detected image for debugging"""
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        file = request.files["image"]
        img_bytes = file.read()

        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Invalid image"}), 400

        h, w = img.shape[:2]
        
        # Same edge detection as detect-corners
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        edged1 = cv2.Canny(blur, 50, 150)
        edged2 = cv2.Canny(blur, 75, 200)
        edged = cv2.bitwise_or(edged1, edged2)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edged, kernel, iterations=1)
        
        # Find and draw contours
        contours, _ = cv2.findContours(dilated.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        # Draw on original image
        debug_img = img.copy()
        cv2.drawContours(debug_img, contours, -1, (0, 255, 0), 3)
        
        # Find best 4-sided contour
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                cv2.drawContours(debug_img, [approx], -1, (0, 0, 255), 5)
                break
        
        # Convert to JPEG
        rgb_img = cv2.cvtColor(debug_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        output = io.BytesIO()
        pil_img.save(output, format="JPEG", quality=95)
        output.seek(0)
        
        return send_file(output, mimetype="image/jpeg")
        
    except Exception as e:
        print(f"ERROR in /debug-edges: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =========================
# DETECT CORNERS (for frontend)
# =========================
@app.route("/detect-corners", methods=["POST", "OPTIONS"])
def detect_corners():
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        print("\n=== DETECT CORNERS REQUEST ===")
        
        if "image" not in request.files:
            print("ERROR: No image in request")
            return jsonify({"error": "No image uploaded"}), 400

        file = request.files["image"]
        img_bytes = file.read()
        print(f"Received {len(img_bytes)} bytes")

        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            print("ERROR: Could not decode image")
            return jsonify({"error": "Invalid image"}), 400

        h, w = img.shape[:2]
        print(f"Image size: {w}x{h}")

        # Document detection - improved algorithm
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges sharp
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Try adaptive thresholding for better edge detection
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY, 11, 2)
        
        # Multiple edge detection attempts
        edged1 = cv2.Canny(blur, 50, 150)
        edged2 = cv2.Canny(blur, 75, 200)
        edged = cv2.bitwise_or(edged1, edged2)
        
        # Dilate to close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edged, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(dilated.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]
        
        print(f"Found {len(contours)} contours")

        doc_contour = None
        min_area_ratio = 0.05  # Reduced from 0.1 to be more sensitive
        
        for i, c in enumerate(contours):
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            area = cv2.contourArea(approx)
            area_ratio = area / (w * h)
            
            print(f"Contour {i}: {len(approx)} points, area ratio: {area_ratio:.3f}")
            
            if len(approx) == 4 and area_ratio > min_area_ratio:
                doc_contour = approx
                print(f"✓ Found document contour with area: {area} ({area_ratio*100:.1f}% of image)")
                break
            elif len(approx) >= 4 and len(approx) <= 6 and area_ratio > min_area_ratio * 1.5:
                # Accept 5-6 sided shapes if they're large enough (may be imperfect rectangles)
                peri = cv2.arcLength(approx, True)
                approx = cv2.approxPolyDP(c, 0.04 * peri, True)  # More aggressive approximation
                if len(approx) == 4:
                    doc_contour = approx
                    print(f"✓ Found document (simplified contour) with area: {area}")
                    break

        if doc_contour is not None:
            pts = doc_contour.reshape(4, 2)
            
            # Order points: top-left, top-right, bottom-right, bottom-left
            rect = np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]  # top-left
            rect[2] = pts[np.argmax(s)]  # bottom-right
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]  # top-right
            rect[3] = pts[np.argmax(diff)]  # bottom-left

            corners = rect.tolist()
            print(f"Detected corners: {corners}")
            
            return jsonify({
                "detected": True,
                "corners": corners,
                "width": w,
                "height": h
            })
        else:
            print("No document detected, using full image")
            margin = 20
            return jsonify({
                "detected": False,
                "corners": [
                    [margin, margin],
                    [w - margin, margin],
                    [w - margin, h - margin],
                    [margin, h - margin]
                ],
                "width": w,
                "height": h
            })
            
    except Exception as e:
        print(f"ERROR in /detect-corners: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =========================
# SCAN + CONVERT
# =========================
@app.route("/scan", methods=["POST", "OPTIONS"])
def scan_and_convert():
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        print("\n=== SCAN REQUEST ===")
        
        if "image" not in request.files:
            print("ERROR: No image in request")
            return jsonify({"error": "No image uploaded"}), 400

        file = request.files["image"]
        output_format = request.form.get("format", "jpg").lower()
        enhance = request.form.get("enhance", "true").lower() == "true"

        img_bytes = file.read()
        
        print(f"Received: {len(img_bytes)} bytes, format: {output_format}, enhance: {enhance}")

        # Convert image bytes → OpenCV (keep color!)
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)  # IMREAD_COLOR is crucial!
        
        if img is None:
            print("ERROR: Could not decode image")
            return jsonify({"error": "Invalid image format"}), 400

        print(f"Image decoded: shape={img.shape}, dtype={img.dtype}")

        # Apply subtle enhancement while preserving color
        if enhance:
            print("Applying enhancement...")
            # Convert to LAB color space
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel only
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            
            # Merge back
            enhanced_lab = cv2.merge((l_enhanced, a, b))
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # Slight sharpening
            kernel = np.array([[0, -1, 0],
                              [-1, 5, -1],
                              [0, -1, 0]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)
            print(f"Enhanced image: shape={enhanced.shape}, dtype={enhanced.dtype}")
        else:
            enhanced = img
            print("No enhancement applied")

        # CRITICAL: Convert BGR (OpenCV) to RGB (PIL) to preserve colors!
        print("Converting BGR to RGB...")
        rgb_img = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
        print(f"RGB image: shape={rgb_img.shape}, dtype={rgb_img.dtype}")
        
        pil_img = Image.fromarray(rgb_img)
        print(f"PIL image: mode={pil_img.mode}, size={pil_img.size}")
        
        output = io.BytesIO()

        # Save in requested format
        if output_format in ["jpg", "jpeg"]:
            print("Saving as JPEG...")
            pil_img.save(output, format="JPEG", quality=95)
            mimetype = "image/jpeg"
            filename = "scanned.jpg"
        elif output_format == "pdf":
            print("Saving as PDF...")
            # Make sure we're saving RGB PDF, not grayscale!
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            pil_img.save(output, format="PDF", resolution=300.0)
            mimetype = "application/pdf"
            filename = "scanned.pdf"
        else:
            print(f"ERROR: Unsupported format {output_format}")
            return jsonify({"error": "Unsupported format"}), 400

        output.seek(0)
        size = output.getbuffer().nbytes
        print(f"Sending {filename}: {size} bytes")
        
        return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)
        
    except Exception as e:
        print(f"ERROR in /scan: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =========================
# MERGE PDFs
# =========================
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


# =========================
# HEALTH CHECK
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "PDFMaster backend running",
        "endpoints": ["/scan", "/detect-corners", "/merge-pdf", "/debug-edges"]
    })


# =========================
# START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n{'='*50}")
    print(f"PDFMaster Backend Starting on http://127.0.0.1:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=True)