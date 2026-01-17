from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
import os
from PyPDF2 import PdfMerger

app = Flask(__name__)
CORS(app)

# =========================
# SCAN + CONVERT
# =========================
@app.route("/scan", methods=["POST"])
def scan_and_convert():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    output_format = request.form.get("format", "jpg").lower()
    enhance = request.form.get("enhance", "true").lower() == "true"

    img_bytes = file.read()

    # Convert image bytes → OpenCV
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400

    # ---- Document detection (find corners)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 200)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    doc_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            doc_contour = approx
            break

    # Apply perspective transform if document detected
    if doc_contour is not None:
        pts = doc_contour.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        (tl, tr, br, bl) = rect
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxHeight = max(int(heightA), int(heightB))

        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    else:
        # No document detected → use original
        warped = img.copy()

    # ---- Enhancement (optional, more subtle)
    if enhance:
        # Convert to LAB color space for better color preservation
        lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE only to L channel (less aggressive)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        
        # Merge back
        lab_clahe = cv2.merge((l_clahe, a, b))
        enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
        
        # Slight sharpening
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]]) / 9
        enhanced = cv2.filter2D(enhanced, -1, kernel)
    else:
        enhanced = warped

    # Convert to PIL Image
    pil_img = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
    output = io.BytesIO()

    # =========================
    # OUTPUT FORMAT
    # =========================
    if output_format in ["jpg", "jpeg"]:
        pil_img.save(output, format="JPEG", quality=95)
        mimetype = "image/jpeg"
        filename = "scanned.jpg"
    elif output_format == "pdf":
        # Save as RGB PDF to preserve colors
        pil_img.save(output, format="PDF", resolution=300.0)
        mimetype = "application/pdf"
        filename = "scanned.pdf"
    else:
        return jsonify({"error": "Unsupported format"}), 400

    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)


# =========================
# DETECT CORNERS (for frontend)
# =========================
@app.route("/detect-corners", methods=["POST"])
def detect_corners():
    """Return detected document corners for frontend cropper"""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    img_bytes = file.read()

    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400

    h, w = img.shape[:2]

    # Document detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 200)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    doc_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            doc_contour = approx
            break

    if doc_contour is not None:
        pts = doc_contour.reshape(4, 2).tolist()
        return jsonify({"corners": pts, "width": w, "height": h})
    else:
        # Return default corners (full image)
        return jsonify({
            "corners": [[0, 0], [w, 0], [w, h], [0, h]],
            "width": w,
            "height": h
        })


# =========================
# MERGE PDFs
# =========================
@app.route("/merge-pdf", methods=["POST"])
def merge_pdfs():
    if "files" not in request.files:
        return jsonify({"error": "No PDF files uploaded"}), 400

    pdf_files = request.files.getlist("files")
    if len(pdf_files) < 2:
        return jsonify({"error": "Upload at least two PDFs"}), 400

    merger = PdfMerger()
    try:
        for pdf in pdf_files:
            if not pdf.filename.lower().endswith(".pdf"):
                return jsonify({"error": "Only PDF files allowed"}), 400
            merger.append(pdf)

        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)

        return send_file(
            output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="merged.pdf"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# HEALTH CHECK
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "PDFMaster backend running",
        "endpoints": ["/scan", "/detect-corners", "/merge-pdf"]
    })


# =========================
# START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)