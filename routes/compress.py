import os
import subprocess
import platform
import tempfile
from flask import Blueprint, request, send_file, jsonify, after_this_request

compress_bp = Blueprint("compress", __name__, url_prefix="/compress-pdf")

# =======================
# Detect Ghostscript path
# =======================
if platform.system() == "Windows":
    # Windows: point directly to gswin64c.exe
    GS_PATH = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
else:
    # Linux/Mac: use gs in PATH
    import shutil
    GS_PATH = shutil.which("gs")
    if not GS_PATH:
        raise RuntimeError("Ghostscript not found. Please install Ghostscript.")

# =======================
# Compress PDF Endpoint
# =======================
@compress_bp.route("/", methods=["POST"])
def compress_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    input_path = None
    output_path = None

    try:
        # Save uploaded PDF to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_input:
            file.save(tmp_input.name)
            input_path = tmp_input.name

        # Temp output file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_output:
            output_path = tmp_output.name

        subprocess.run(
            [
                GS_PATH,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dDownsampleColorImages=true",
                "-dDownsampleGrayImages=true",
                "-dDownsampleMonoImages=true",
                "-dColorImageResolution=100",
                "-dGrayImageResolution=100",
                "-dMonoImageResolution=300",
                "-dColorImageDownsampleType=/Bicubic",
                "-dGrayImageDownsampleType=/Bicubic",
                "-dMonoImageDownsampleType=/Subsample",
                "-dJPEGQ=60",
                "-dDetectDuplicateImages=true",
                "-dCompressFonts=true",
                "-dSubsetFonts=true",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={output_path}",
                input_path,
            ],
            check=True,
        )

        # =======================
        # Cleanup temp files safely (Windows-friendly)
        # =======================
        @after_this_request
        def cleanup(response):
            try:
                for path in [input_path, output_path]:
                    if path and os.path.exists(path):
                        os.remove(path)
            except Exception as e:
                print("Cleanup error:", e)
            return response

        # Send compressed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"compressed_{file.filename}",
        )

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Compression failed: {str(e)}"}), 500
