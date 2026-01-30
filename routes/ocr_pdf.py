from flask import Blueprint, request, send_file, jsonify
from werkzeug.utils import secure_filename
import tempfile
import os
import traceback
import subprocess
import ocrmypdf

ocr_pdf_bp = Blueprint("ocr_pdf", __name__, url_prefix="/ocr-pdf")

ALLOWED_EXTENSIONS = {"pdf"}

# ----------------------------------
# LANGUAGE MAP (frontend → tesseract)
# ----------------------------------
LANGUAGE_MAP = {
    "eng": "eng",
    "ben": "ben",
    "spa": "spa",
    "fra": "fra",
    "deu": "deu",
    "ita": "ita",
    "por": "por",
    "rus": "rus",
    "jpn": "jpn",
    "kor": "kor",
    "chi_sim": "chi_sim",
    "chi_tra": "chi_tra",
    "ara": "ara",
    "hin": "hin"
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def check_tesseract_languages():
    """Return installed Tesseract language codes"""
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            check=True
        )
        langs = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.lower().startswith("list of")
        ]
        return langs
    except Exception:
        return []

@ocr_pdf_bp.route("/", methods=["POST"])
def ocr_pdf():
    try:
        # --------------------
        # Validate upload
        # --------------------
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Only PDF files are allowed"}), 400

        # --------------------
        # Parse languages
        # --------------------
        languages_input = request.form.get("languages", "eng")
        language_codes = [l.strip() for l in languages_input.split(",")]
        tesseract_langs = [LANGUAGE_MAP.get(l, l) for l in language_codes]
        language_string = "+".join(tesseract_langs)

        # --------------------
        # Verify language packs
        # --------------------
        installed_langs = check_tesseract_languages()
        missing = [l for l in tesseract_langs if l not in installed_langs]

        if missing:
            return jsonify({
                "error": "Language packs not installed",
                "missing": missing,
                "installed": installed_langs
            }), 400

        # --------------------
        # OCR processing
        # --------------------
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, secure_filename(file.filename))
            output_path = os.path.join(tmp, f"searchable_{secure_filename(file.filename)}")
            file.save(input_path)

            try:
                # KEY FIX: Use parameters that guarantee text selection
                ocrmypdf.ocr(
                    input_path,
                    output_path,
                    language=language_string,
                    force_ocr=True,           # run OCR on all pages
                    deskew=True,              # auto-rotate / deskew pages
                    rotate_pages=True,        # auto-rotate pages
                    clean=True,               # clean pages before OCR (IMPORTANT)
                    remove_background=False,  # keep original quality
                    optimize=0,               # NO optimization to preserve text (CRITICAL)
                    output_type="pdf",        # standard PDF
                    skip_text=False,          # don't skip existing text
                    redo_ocr=False,           # don't redo if text exists
                    sidecar=None,             # no text file needed
                    pdf_renderer="auto",      # let ocrmypdf choose best renderer
                    invalidate_digital_signatures=True,  # allow processing signed PDFs
                    tesseract_timeout=300     # 5 min timeout per page
                )
            except Exception as e:
                msg = str(e).lower()
                if "tesseract" in msg:
                    return jsonify({"error": "Tesseract OCR not available"}), 500
                if "ghostscript" in msg:
                    return jsonify({"error": "Ghostscript missing"}), 500
                traceback.print_exc()
                return jsonify({
                    "error": "OCR processing failed",
                    "details": str(e)
                }), 500

            return send_file(
                output_path,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"searchable_{secure_filename(file.filename)}"
            )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ocr_pdf_bp.route("/tesseract-check", methods=["GET"])
def tesseract_check():
    try:
        version = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True
        ).stdout.splitlines()[0]

        langs = check_tesseract_languages()

        return jsonify({
            "installed": True,
            "version": version,
            "languages": langs,
            "language_count": len(langs)
        })
    except Exception as e:
        return jsonify({
            "installed": False,
            "error": str(e)
        }), 500

@ocr_pdf_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ocr-pdf"})