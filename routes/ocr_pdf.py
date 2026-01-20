from flask import Blueprint, request, send_file, jsonify
from werkzeug.utils import secure_filename
import tempfile
import os
import traceback
import pytesseract
import platform
import ocrmypdf

ocr_pdf_bp = Blueprint('ocr_pdf', __name__)

# -------------------------------
# CONFIGURE TESSERACT PATH BASED ON OS
# -------------------------------
if platform.system() == "Windows":
    # Windows Tesseract path
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ALLOWED_EXTENSIONS = {'pdf'}

# -------------------------------
# LANGUAGE MAP (frontend -> Tesseract)
# -------------------------------
LANGUAGE_MAP = {
    "eng": "eng",
    "beng": "ben",
    "spa": "spa",
    "fra": "fra",
    "deu": "deu",
    "ita": "ita",
    "por": "por",
    "rus": "rus",
    "jpn": "jpn",
    "kor": "kor",
    "chi_sim": "chi-sim",
    "chi_tra": "chi-tra",
    "ara": "ara",
    "hin": "hin"
}

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def has_text_content(pdf_path):
    """Check if PDF already has text content"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text = page.extract_text()
            if text and len(text.strip()) > 50:
                return True
        return False
    except Exception as e:
        print(f"Error checking text content: {str(e)}")
        return False

@ocr_pdf_bp.route('/ocr-pdf', methods=['POST'])
def ocr_pdf():
    """Convert image-based PDF to searchable PDF using OCR via ocrmypdf"""
    try:
        # Validate file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        language_code = request.form.get('language', 'eng')
        language = LANGUAGE_MAP.get(language_code, 'eng')  # Map to Tesseract language code
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400
        
        # Use temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, secure_filename(file.filename))
            output_path = os.path.join(temp_dir, f'searchable_{secure_filename(file.filename)}')
            
            # Save uploaded file
            file.save(input_path)
            
            # Check if PDF already has selectable text
            if has_text_content(input_path):
                print("PDF already contains text, returning as-is")
                return send_file(
                    input_path,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'searchable_{secure_filename(file.filename)}'
                )
            
            # Perform OCR using ocrmypdf
            try:
                ocrmypdf.ocr(
                    input_path,
                    output_path,
                    language=language,  # mapped Tesseract code
                    force_ocr=True,
                    output_type='pdf',
                    deskew=True
                )
            except Exception as e:
                print(f"OCR processing failed: {str(e)}")
                traceback.print_exc()
                return jsonify({'error': 'OCR processing failed. Ensure Tesseract is installed and the language code is correct.'}), 500
            
            print("Successfully created searchable PDF")
            
            # Return the searchable PDF
            return send_file(
                output_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'searchable_{secure_filename(file.filename)}'
            )
            
    except Exception as e:
        print(f"OCR Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'OCR processing failed: {str(e)}'}), 500

@ocr_pdf_bp.route('/tesseract-check', methods=['GET'])
def check_tesseract():
    """Check if Tesseract is installed and working"""
    try:
        version = pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages()
        return jsonify({
            'installed': True,
            'version': str(version),
            'languages': languages
        })
    except Exception as e:
        return jsonify({
            'installed': False,
            'error': str(e),
            'message': 'Tesseract OCR is not installed or not in PATH'
        }), 500

@ocr_pdf_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'OCR PDF'}), 200
