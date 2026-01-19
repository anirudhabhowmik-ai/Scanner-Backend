from flask import Blueprint, request, send_file, jsonify
from pypdf import PdfWriter
import io

merge_pdf_bp = Blueprint("merge_pdf", __name__)

@merge_pdf_bp.route("/merge-pdf", methods=["POST"])
def merge_pdfs():
    if "files" not in request.files:
        return jsonify({"error":"No PDF files uploaded"}),400
    pdf_files = request.files.getlist("files")
    if len(pdf_files)<2: return jsonify({"error":"Upload at least two PDFs"}),400
    writer = PdfWriter()
    for pdf in pdf_files:
        if not pdf.filename.lower().endswith(".pdf"):
            return jsonify({"error":"Only PDF files allowed"}),400
        writer.append(pdf)
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    output.seek(0)
    return send_file(output,mimetype="application/pdf",as_attachment=True,download_name="merged.pdf")
