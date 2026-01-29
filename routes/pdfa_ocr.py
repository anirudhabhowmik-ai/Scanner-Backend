from flask import Blueprint, request, send_file, jsonify
import tempfile
import os
import subprocess

pdfa_ocr_bp = Blueprint("pdfa_ocr", __name__)


@pdfa_ocr_bp.route("/pdfa-ocr", methods=["POST"])
def pdfa_ocr():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.pdf")
            output_path = os.path.join(tmpdir, "output_pdfa.pdf")

            file.save(input_path)

            # 🔥 OCR + PDF/A conversion
            # --force-ocr → OCR even if text exists
            # --output-type pdfa → produce PDF/A
            # --optimize 3 → best compression
            # --deskew, --clean → better scan quality
            cmd = [
                "ocrmypdf",
                "--force-ocr",
                "--output-type", "pdfa",
                "--optimize", "3",
                "--deskew",
                "--clean",
                input_path,
                output_path
            ]

            subprocess.run(cmd, check=True)

            return send_file(
                output_path,
                as_attachment=True,
                download_name="pdfa_ocr.pdf",
                mimetype="application/pdf"
            )

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "OCR conversion failed", "details": str(e)}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
