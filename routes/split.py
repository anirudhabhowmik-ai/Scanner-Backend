from flask import Blueprint, request, send_file
from pypdf import PdfReader, PdfWriter
import zipfile
import io

split_pdf_bp = Blueprint("split_pdf", __name__)

@split_pdf_bp.route("/split-pdf", methods=["POST"])
def split_pdf():
    if "file" not in request.files:
        return {"error": "No file uploaded"}, 400

    file = request.files["file"]
    reader = PdfReader(file)

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)

            pdf_bytes = io.BytesIO()
            writer.write(pdf_bytes)

            z.writestr(f"page-{i+1}.pdf", pdf_bytes.getvalue())

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name="split-pdf.zip",
        mimetype="application/zip"
    )
