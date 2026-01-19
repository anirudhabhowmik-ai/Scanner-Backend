# routes/compress.py
from flask import Blueprint, request, send_file, jsonify
import tempfile
import os
import pikepdf

compress_bp = Blueprint("compress", __name__, url_prefix="/compress-pdf")

@compress_bp.route("/", methods=["POST"])
def compress_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    input_path = None
    output_path = None

    try:
        # Save uploaded PDF to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_input:
            file.save(tmp_input.name)
            input_path = tmp_input.name

        # Temporary output file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_output:
            output_path = tmp_output.name

        # Open PDF and compress
        with pikepdf.open(input_path) as pdf:
            pdf.save(output_path)  # <- just save without extra arguments

        # Return compressed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"compressed_{file.filename}"
        )

    except Exception as e:
        print("ERROR in compress_pdf:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up temporary files
        for path in [input_path, output_path]:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception as cleanup_error:
                print("Cleanup error:", cleanup_error)
