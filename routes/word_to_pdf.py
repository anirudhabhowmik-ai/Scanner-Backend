from flask import Blueprint, request, send_file, jsonify
import subprocess
import os
import uuid
from PyPDF2 import PdfMerger

word_to_pdf_bp = Blueprint("word_to_pdf", __name__)

@word_to_pdf_bp.route("/word-to-pdf", methods=["POST"])
def word_to_pdf():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files")
    temp_pdf_paths = []

    try:
        for file in files:
            temp_id = str(uuid.uuid4())
            input_path = f"/tmp/{temp_id}_{file.filename}"
            file.save(input_path)

            # LibreOffice conversion: Word → PDF
            subprocess.run([
                "soffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", "/tmp",
                input_path
            ], check=True)

            pdf_path = input_path.rsplit(".", 1)[0] + ".pdf"
            temp_pdf_paths.append(pdf_path)

        # Merge PDFs if multiple Word files uploaded
        if len(temp_pdf_paths) > 1:
            merged_pdf_path = f"/tmp/{uuid.uuid4()}_merged.pdf"
            merger = PdfMerger()
            for pdf in temp_pdf_paths:
                merger.append(pdf)
            merger.write(merged_pdf_path)
            merger.close()

            # Cleanup individual PDFs
            for pdf in temp_pdf_paths:
                os.remove(pdf)

            return send_file(
                merged_pdf_path,
                as_attachment=True,
                download_name="converted.pdf"
            )

        # Single PDF
        return send_file(
            temp_pdf_paths[0],
            as_attachment=True,
            download_name="converted.pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
