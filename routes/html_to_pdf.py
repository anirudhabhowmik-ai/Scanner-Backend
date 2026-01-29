from flask import Blueprint, request, send_file, jsonify
from weasyprint import HTML
from PyPDF2 import PdfMerger
import uuid, os

html_to_pdf_bp = Blueprint("html_to_pdf", __name__)

@html_to_pdf_bp.route("/html-to-pdf", methods=["POST"])
def html_to_pdf():
    try:
        if "files" not in request.files:
            return jsonify({"error": "No HTML file uploaded"}), 400

        files = request.files.getlist("files")
        temp_pdf_paths = []

        for file in files:
            html_content = file.read().decode("utf-8")

            temp_id = str(uuid.uuid4())
            pdf_path = f"/tmp/{temp_id}.pdf"

            HTML(string=html_content, base_url="/").write_pdf(pdf_path)
            temp_pdf_paths.append(pdf_path)

        # If multiple HTML files → merge
        if len(temp_pdf_paths) > 1:
            merged_path = f"/tmp/{uuid.uuid4()}_merged.pdf"
            merger = PdfMerger()

            for pdf in temp_pdf_paths:
                merger.append(pdf)

            merger.write(merged_path)
            merger.close()

            return send_file(
                merged_path,
                as_attachment=True,
                download_name="converted.pdf",
                mimetype="application/pdf"
            )

        # Single file
        return send_file(
            temp_pdf_paths[0],
            as_attachment=True,
            download_name="converted.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
