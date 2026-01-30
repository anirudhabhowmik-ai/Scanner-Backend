from flask import Blueprint, request, send_file, jsonify
import tempfile
import os
import subprocess
from io import BytesIO
import fitz  # PyMuPDF

pdfa_ocr_bp = Blueprint("pdfa_ocr", __name__)

def detect_language(input_pdf):
    """
    Auto-detect language from the first page if no language selected.
    Returns tesseract language codes like "eng", "eng+hin"
    """
    try:
        doc = fitz.open(input_pdf)
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)

        img_path = input_pdf.replace(".pdf", ".png")
        pix.save(img_path)

        # Quick tesseract script detection
        result = subprocess.run(
            ["tesseract", img_path, "stdout", "--psm", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output = result.stderr.lower()

        if "devanagari" in output:
            return "eng+hin"
        elif "latin" in output:
            return "eng"
        else:
            return "eng"

    except Exception:
        return "eng"


@pdfa_ocr_bp.route("/pdfa-ocr", methods=["POST"])
def pdfa_ocr():
    """
    Accept multiple PDF files and selected OCR languages.
    Merges PDFs and converts to searchable PDF/A.
    """
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    # Get languages from frontend or auto-detect first file
    selected_langs = request.form.get("lang")
    if not selected_langs:
        # Use temp path to save first file for detection
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            files[0].save(tmp.name)
            selected_langs = detect_language(tmp.name)
        os.unlink(tmp.name)  # clean temp file

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_paths = []

            # Save each uploaded PDF to temp folder
            for i, file in enumerate(files):
                path = os.path.join(tmpdir, f"input_{i}.pdf")
                file.save(path)
                input_paths.append(path)

            # Merge all PDFs into one file
            merged_path = os.path.join(tmpdir, "merged_input.pdf")
            subprocess.run(["qpdf", "--empty", "--pages", *input_paths, "--", merged_path], check=True)

            # Output path for OCR PDF/A
            output_path = os.path.join(tmpdir, "output_pdfa.pdf")

            # OCR command
            cmd = [
                "ocrmypdf",
                "--force-ocr",
                "--jobs", "2",            # Faster parallel OCR
                "--fast-web-view", "1",
                "--optimize", "1",        # Fast conversion
                "--skip-text",            # Skip pages with text
                "--output-type", "pdfa",
                "--tesseract-timeout", "60",
                "--rotate-pages",
                "--deskew",
                "-l", selected_langs,
                merged_path,
                output_path
            ]

            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if process.returncode != 0:
                return jsonify({
                    "error": "OCR conversion failed",
                    "details": process.stderr
                }), 500

            # Return PDF as download
            with open(output_path, "rb") as f:
                pdf_bytes = BytesIO(f.read())

        pdf_bytes.seek(0)
        return send_file(
            pdf_bytes,
            as_attachment=True,
            download_name="searchable_pdfa.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
