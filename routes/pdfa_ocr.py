from flask import Blueprint, request, send_file, jsonify
import tempfile
import os
import subprocess
from io import BytesIO
import fitz  # PyMuPDF

pdfa_ocr_bp = Blueprint("pdfa_ocr", __name__)


# ------------------ AUTO LANGUAGE DETECTION (fallback) ------------------
def detect_language(input_pdf):
    try:
        doc = fitz.open(input_pdf)
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)

        img_path = input_pdf.replace(".pdf", ".png")
        pix.save(img_path)

        result = subprocess.run(
            ["tesseract", img_path, "stdout", "--psm", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        os.remove(img_path)
        output = result.stderr.lower()

        if "devanagari" in output:
            return "eng+hin"
        elif "arabic" in output:
            return "eng+ara"
        elif "latin" in output:
            return "eng"
        else:
            return "eng"

    except:
        return "eng"


# ------------------ MAIN ROUTE ------------------
@pdfa_ocr_bp.route("/pdfa-ocr", methods=["POST"])
def pdfa_ocr():

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    user_lang = request.form.get("lang")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:

            processed_paths = []

            # ---------- PROCESS EACH FILE ----------
            for idx, file in enumerate(files):
                input_path = os.path.join(tmpdir, f"input_{idx}.pdf")
                output_path = os.path.join(tmpdir, f"ocr_{idx}.pdf")

                file.save(input_path)

                languages = user_lang if user_lang else detect_language(input_path)

                cmd = [
                    "ocrmypdf",
                    "--force-ocr",
                    "--jobs", "2",                 # Parallel OCR
                    "--skip-text",                 # Skip pages with text
                    "--rotate-pages",
                    "--deskew",
                    "--fast-web-view", "1",
                    "--optimize", "1",             # Faster than level 3
                    "--output-type", "pdfa",
                    "--tesseract-timeout", "90",
                    "-l", languages,
                    input_path,
                    output_path
                ]

                process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if process.returncode != 0:
                    return jsonify({
                        "error": f"OCR failed for {file.filename}",
                        "details": process.stderr.decode()
                    }), 500

                processed_paths.append(output_path)

            # ---------- MERGE IF MULTIPLE FILES ----------
            final_output = os.path.join(tmpdir, "final_output.pdf")

            if len(processed_paths) == 1:
                final_output = processed_paths[0]
            else:
                merger = fitz.open()
                for p in processed_paths:
                    merger.insert_pdf(fitz.open(p))
                merger.save(final_output)
                merger.close()

            # ---------- RETURN FILE ----------
            with open(final_output, "rb") as f:
                pdf_bytes = BytesIO(f.read())

        pdf_bytes.seek(0)

        return send_file(
            pdf_bytes,
            as_attachment=True,
            download_name="pdfa_searchable.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
