from flask import Blueprint, request, send_file, jsonify
from werkzeug.utils import secure_filename
import tempfile, os, uuid
from tasks import ocr_task, tasks

ocr_pdf_bp = Blueprint("ocr_pdf", __name__, url_prefix="/ocr-pdf")

ALLOWED_EXTENSIONS = {"pdf"}

LANGUAGE_MAP = {
    "eng": "eng", "ben": "ben", "spa": "spa", "fra": "fra", "deu": "deu",
    "ita": "ita", "por": "por", "rus": "rus", "jpn": "jpn", "kor": "kor",
    "chi_sim": "chi_sim", "chi_tra": "chi_tra", "ara": "ara", "hin": "hin"
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@ocr_pdf_bp.route("/", methods=["POST"])
def ocr_pdf_async():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    languages_input = request.form.get("languages", "eng")
    language_string = "+".join([LANGUAGE_MAP.get(l.strip(), l.strip()) for l in languages_input.split(",")])

    task_id = str(uuid.uuid4())
    tmp_dir = tempfile.gettempdir()
    input_path = os.path.join(tmp_dir, secure_filename(file.filename))
    output_path = os.path.join(tmp_dir, f"searchable_{secure_filename(file.filename)}")

    # Save the uploaded PDF
    file.save(input_path)

    # Start OCR in a background thread
    threading.Thread(target=ocr_task, args=(task_id, input_path, output_path, language_string)).start()

    return jsonify({"task_id": task_id}), 202
