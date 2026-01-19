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
import platform

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =====================
# Configure Tesseract
# =====================
# Use Windows path only if on Windows
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# =====================
# Utility functions
# =====================
def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left
    rect[2] = pts[np.argmax(s)]      # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]   # top-right
    rect[3] = pts[np.argmax(diff)]   # bottom-left
    return rect

def detect_document_contour(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    morph_gradient = cv2.morphologyEx(blur, cv2.MORPH_GRADIENT, kernel)
    edges1 = cv2.Canny(blur, 30, 100)
    edges2 = cv2.Canny(blur, 50, 150)
    edges3 = cv2.Canny(blur, 75, 200)
    edges4 = cv2.Canny(morph_gradient, 30, 100)
    edges_combined = cv2.bitwise_or(edges1, edges2)
    edges_combined = cv2.bitwise_or(edges_combined, edges3)
    edges_combined = cv2.bitwise_or(edges_combined, edges4)
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges_combined, kernel_dilate, iterations=2)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel_close)
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:25]
    min_area = (w * h) * 0.05
    max_area = (w * h) * 0.98
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        peri = cv2.arcLength(contour, True)
        for epsilon_mult in [0.015, 0.02, 0.03, 0.04, 0.05]:
            epsilon = epsilon_mult * peri
            approx = cv2.approxPolyDP(contour, epsilon, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2)
                ordered = order_points(pts)
                widthA = np.linalg.norm(ordered[0] - ordered[1])
                widthB = np.linalg.norm(ordered[2] - ordered[3])
                heightA = np.linalg.norm(ordered[0] - ordered[3])
                heightB = np.linalg.norm(ordered[1] - ordered[2])
                avg_width = (widthA + widthB) / 2
                avg_height = (heightA + heightB) / 2
                if avg_width > 0 and avg_height > 0:
                    aspect_ratio = max(avg_width, avg_height) / min(avg_width, avg_height)
                    if aspect_ratio < 10:
                        score = area / (aspect_ratio * 0.1)
                        candidates.append((approx, area, score))
                        break
    if candidates:
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[0][0]
    return None

# =====================
# Routes
# =====================

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
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Invalid image"}), 400
        h, w = img.shape[:2]
        max_dim = 1500
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img_resized = cv2.resize(img, (int(w*scale), int(h*scale)))
            scale_back = max(h, w) / max_dim
        else:
            img_resized = img
            scale_back = 1.0
        doc_contour = detect_document_contour(img_resized)
        if doc_contour is not None:
            pts = doc_contour.reshape(4, 2) * scale_back
            corners = order_points(pts).tolist()
            return jsonify({"detected": True, "corners": corners, "width": w, "height": h})
        else:
            margin_w = int(w*0.02)
            margin_h = int(h*0.02)
            return jsonify({
                "detected": False,
                "corners": [[margin_w, margin_h],[w-margin_w, margin_h],[w-margin_w, h-margin_h],[margin_w, h-margin_h]],
                "width": w, "height": h
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
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Invalid image format"}), 400
        if enhance:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
            l = clahe.apply(l)
            img = cv2.cvtColor(cv2.merge((l,a,b)), cv2.COLOR_LAB2BGR)
            kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
            img = cv2.filter2D(img, -1, kernel)
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        output = io.BytesIO()
        if output_format in ["jpg","jpeg"]:
            pil_img.save(output, format="JPEG", quality=95)
            mimetype = "image/jpeg"; filename="scanned.jpg"
        elif output_format=="pdf":
            if pil_img.mode!='RGB': pil_img=pil_img.convert('RGB')
            pil_img.save(output, format="PDF", resolution=300.0)
            mimetype="application/pdf"; filename="scanned.pdf"
        else:
            return jsonify({"error":"Unsupported format"}),400
        output.seek(0)
        return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"ERROR in /scan: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}),500

@app.route("/merge-pdf", methods=["POST", "OPTIONS"])
def merge_pdfs():
    if request.method=="OPTIONS": return "",204
    try:
        if "files" not in request.files: return jsonify({"error":"No PDF files uploaded"}),400
        pdf_files = request.files.getlist("files")
        if len(pdf_files)<2: return jsonify({"error":"Upload at least two PDFs"}),400
        writer = PdfWriter()
        for pdf in pdf_files:
            if not pdf.filename.lower().endswith(".pdf"): return jsonify({"error":"Only PDF files allowed"}),400
            writer.append(pdf)
        output = io.BytesIO()
        writer.write(output)
        writer.close()
        output.seek(0)
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name="merged.pdf")
    except Exception as e:
        print(f"ERROR in /merge-pdf: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}),500

@app.route("/ocr", methods=["POST","OPTIONS"])
def ocr_extract():
    if request.method=="OPTIONS": return "",204
    try:
        print("\n=== OCR REQUEST ===")
        if "image" not in request.files:
            return jsonify({"error":"No image uploaded"}),400
        file = request.files["image"]
        np_img = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if img is None: return jsonify({"error":"Invalid image format"}),400

        # Preprocessing
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,11,2)
        denoised = cv2.fastNlMeansDenoising(thresh,None,10,7,21)
        pil_img = Image.fromarray(denoised)

        # OCR
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng').strip()
        return jsonify({"success":True,"text":text,"length":len(text)})
    except Exception as e:
        print(f"ERROR in /ocr: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}),500

@app.route("/tesseract-check")
def tesseract_check():
    try:
        version = pytesseract.get_tesseract_version()
        return {"installed": True, "version": str(version)}
    except Exception as e:
        return {"installed": False, "error": str(e)}

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status":"PDFMaster backend running",
        "version":"2.0",
        "endpoints":["/scan","/detect-corners","/merge-pdf","/ocr","/tesseract-check"]
    })

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    print(f"\n{'='*50}")
    print(f"PDFMaster Backend v2.0 - Enhanced Edge Detection")
    print(f"Running on http://127.0.0.1:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
