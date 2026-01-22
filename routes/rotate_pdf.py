from flask import Blueprint, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import json

rotate_pdf_bp = Blueprint(
    "rotate_pdf",
    __name__,
    url_prefix="/rotate-pdf"
)

@rotate_pdf_bp.route("", methods=["POST"])
def rotate_pdf():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "PDF files required"}), 400

    rotations_raw = request.form.get("rotations")
    if not rotations_raw:
        return jsonify({"error": "Rotation data missing"}), 400

    try:
        rotations = json.loads(rotations_raw)
    except Exception:
        return jsonify({"error": "Invalid rotation data"}), 400

    writer = PdfWriter()
    page_index = 0  # 🔑 GLOBAL PAGE INDEX

    for pdf_file in files:
        reader = PdfReader(pdf_file)

        for page in reader.pages:
            rotate = rotations[page_index] if page_index < len(rotations) else 0
            if rotate:
                page.rotate(rotate)
            writer.add_page(page)
            page_index += 1

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp)
    tmp.close()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name="rotated.pdf",
        mimetype="application/pdf"
    )
