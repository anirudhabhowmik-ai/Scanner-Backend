from flask import Blueprint, request, send_file, jsonify
from werkzeug.utils import secure_filename
import tempfile
import os
import uuid
import threading
import ocrmypdf

# Import background task dictionary and function
from tasks import ocr_task, tasks

ocr_pdf_bp = Blueprint("ocr_pdf", __name__, url_prefix="/ocr-pdf")

ALLOWED_EXTENSIONS = {"pdf"}

# Frontend → Tesseract language mapping
LANGUAGE_MAP = {
    "eng": "eng", "ben": "ben", "spa": "spa", "fra": "fra", "deu": "deu",
    "ita": "ita", "por": "por", "rus": "rus", "jpn": "jpn", "kor": "kor",
    "chi_sim": "chi_sim", "chi_tra": "chi_tra", "ara": "ara", "hin": "hin"
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ------------------------------
# Start OCR (async)
# ------------------------------
@ocr_pdf_bp.route("/", methods=["POST"])
def ocr_pdf_async():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    # Parse selected languages
    languages_input = request.form.get("languages", "eng")
    language_string = "+".join([LANGUAGE_MAP.get(l.strip(), l.strip()) for l in languages_input.split(",")])

    # Generate unique task ID
    task_id = str(uuid.uuid4())

    # Temporary paths
    tmp_dir = tempfile.gettempdir()
    input_path = os.path.join(tmp_dir, secure_filename(file.filename))
    output_path = os.path.join(tmp_dir, f"searchable_{secure_filename(file.filename)}")

    # Save the uploaded PDF
    file.save(input_path)

    # Start OCR in a background thread
    threading.Thread(target=ocr_task, args=(task_id, input_path, output_path, language_string)).start()

    # Return task_id immediately
    return jsonify({"task_id": task_id}), 202


# ------------------------------
# Check OCR status
# ------------------------------
@ocr_pdf_bp.route("/status/<task_id>", methods=["GET"])
def ocr_status(task_id):
    info = tasks.get(task_id)
    if not info:
        return jsonify({"error": "Invalid task id"}), 404
    return jsonify(info)


# ------------------------------
# Download processed PDF
# ------------------------------
@ocr_pdf_bp.route("/download/<task_id>", methods=["GET"])
def ocr_download(task_id):
    info = tasks.get(task_id)
    if not info or info.get("status") != "done":
        return jsonify({"error": "File not ready"}), 400
    return send_file(info["output"], as_attachment=True, download_name="searchable.pdf")
