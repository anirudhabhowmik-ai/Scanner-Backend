from flask import Blueprint, request, send_file, jsonify
import subprocess
import os
import uuid

excel_to_pdf_bp = Blueprint("excel_to_pdf", __name__)

@excel_to_pdf_bp.route("/excel-to-pdf", methods=["POST"])
def excel_to_pdf():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files")
    output_files = []

    try:
        for file in files:
            temp_id = str(uuid.uuid4())
            input_path = f"/tmp/{temp_id}_{file.filename}"
            file.save(input_path)

            # LibreOffice conversion
            subprocess.run([
                "soffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", "/tmp",
                input_path
            ], check=True)

            pdf_path = input_path.rsplit(".", 1)[0] + ".pdf"
            output_files.append(pdf_path)

        # Return single PDF if only one
        if len(output_files) == 1:
            return send_file(output_files[0], as_attachment=True)

        return jsonify({"message": "Multiple PDFs generated", "files": output_files}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
