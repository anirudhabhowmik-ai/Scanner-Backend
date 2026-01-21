from flask import Blueprint, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
import tempfile

delete_pages_bp = Blueprint(
    "delete_pages",
    __name__,
    url_prefix="/delete-pages"
)

def parse_pages(page_str):
    pages = set()
    for part in page_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            pages.update(range(int(start) - 1, int(end)))
        else:
            pages.add(int(part) - 1)
    return pages

@delete_pages_bp.route("", methods=["POST"])
def delete_pages():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    pages_input = request.form.get("pages", "").strip()
    if not pages_input:
        return jsonify({"error": "No pages specified"}), 400

    try:
        pages_to_delete = parse_pages(pages_input)
    except Exception:
        return jsonify({"error": "Invalid page format"}), 400

    reader = PdfReader(request.files["file"])
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i not in pages_to_delete:
            writer.add_page(page)

    if len(writer.pages) == 0:
        return jsonify({"error": "All pages removed"}), 400

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(temp.name, "wb") as f:
        writer.write(f)

    return send_file(
        temp.name,
        as_attachment=True,
        download_name="pages_deleted.pdf",
        mimetype="application/pdf"
    )
