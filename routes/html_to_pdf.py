from flask import Blueprint, request, send_file, jsonify
from weasyprint import HTML
import uuid, os

html_to_pdf_bp = Blueprint("html_to_pdf", __name__)

@html_to_pdf_bp.route("/html-to-pdf", methods=["POST"])
def html_to_pdf():
    try:
        if "files" not in request.files:
            return jsonify({"error": "No HTML file uploaded"}), 400

        files = request.files.getlist("files")

        if len(files) > 1:
            return jsonify({"error": "Upload only one HTML file"}), 400

        file = files[0]
        html_content = file.read().decode("utf-8")

        temp_id = str(uuid.uuid4())
        pdf_path = f"/tmp/{temp_id}.pdf"

        HTML(string=html_content, base_url="/").write_pdf(pdf_path)

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name="converted.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
