from flask import Blueprint, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import os

extract_pages_bp = Blueprint("extract_pages", __name__, url_prefix="/extract-pages")

def parse_pages(pages_str, total_pages):
    pages = set()
    for part in pages_str.split(","):
        if "-" in part:
            start, end = part.split("-")
            for i in range(int(start)-1, int(end)):
                if 0 <= i < total_pages:
                    pages.add(i)
        else:
            i = int(part) - 1
            if 0 <= i < total_pages:
                pages.add(i)
    return sorted(pages)

@extract_pages_bp.route("", methods=["POST"])
def extract_pages():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    pages_str = request.form.get("pages", "").strip()
    if not pages_str:
        return jsonify({"error": "No pages provided"}), 400

    file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_in:
        file.save(temp_in.name)
        reader = PdfReader(temp_in.name)
        writer = PdfWriter()

        pages = parse_pages(pages_str, len(reader.pages))
        if not pages:
            return jsonify({"error": "Invalid page range"}), 400

        for i in pages:
            writer.add_page(reader.pages[i])

        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(temp_out.name, "wb") as f:
            writer.write(f)

    return send_file(
        temp_out.name,
        as_attachment=True,
        download_name="extracted_pages.pdf"
    )
