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

    img_bytes = file.read()

    # Convert image bytes → OpenCV
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({"error": "Invalid image"}), 400

    # ---- Image enhancement (scanner effect)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    pil_img = Image.fromarray(enhanced)
    output = io.BytesIO()

    # =========================
    # OUTPUT FORMAT
    # =========================
    if output_format in ["jpg", "jpeg"]:
        pil_img.save(output, format="JPEG", quality=95)
        mimetype = "image/jpeg"
        filename = "scanned.jpg"

    elif output_format == "pdf":
        pil_img = pil_img.convert("RGB")
        pil_img.save(output, format="PDF", resolution=300.0)
        mimetype = "application/pdf"
        filename = "scanned.pdf"

    else:
        return jsonify({"error": "Unsupported format"}), 400

    output.seek(0)

    return send_file(
        output,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )


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
        "endpoints": ["/scan", "/merge-pdf"]
    })


# =========================
# START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
