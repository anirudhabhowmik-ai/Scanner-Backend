from flask import Blueprint, request, send_file, jsonify
from werkzeug.utils import secure_filename
import tempfile
import os
import traceback
import pytesseract
import platform
import ocrmypdf
import subprocess

ocr_pdf_bp = Blueprint('ocr_pdf', __name__)

# -------------------------------
# CONFIGURE TESSERACT PATH BASED ON OS
# -------------------------------
if platform.system() == "Windows":
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
    "chi_sim": "chi_sim",
    "chi_tra": "chi_tra",
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

def check_tesseract_languages():
    """Check which Tesseract languages are installed"""
    try:
        result = subprocess.run(
            ['tesseract', '--list-langs'],
            capture_output=True,
            text=True,
            check=True
        )
        installed_langs = result.stdout.strip().split('\n')[1:]  # Skip first line
        print(f"Installed Tesseract languages: {installed_langs}")
        return installed_langs
    except Exception as e:
        print(f"Error checking Tesseract languages: {str(e)}")
        return []

@ocr_pdf_bp.route('/ocr-pdf', methods=['POST'])
def ocr_pdf():
    """Convert image-based PDF to searchable PDF using OCR via ocrmypdf"""
    try:
        # Validate file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Get languages from request (can be comma-separated string or list)
        languages_input = request.form.get('languages', 'eng')
        
        # Parse languages
        if isinstance(languages_input, str):
            language_codes = [lang.strip() for lang in languages_input.split(',')]
        else:
            language_codes = languages_input
        
        # Map to Tesseract language codes
        tesseract_langs = [LANGUAGE_MAP.get(code, code) for code in language_codes]
        language_string = '+'.join(tesseract_langs)  # ocrmypdf uses + to join languages
        
        print(f"Requested languages: {language_codes}")
        print(f"Tesseract language string: {language_string}")
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400
        
        # Check installed languages
        installed_langs = check_tesseract_languages()
        
        # Verify requested languages are installed
        missing_langs = [lang for lang in tesseract_langs if lang not in installed_langs]
        if missing_langs:
            print(f"Warning: Missing language packs: {missing_langs}")
            return jsonify({
                'error': f'Language packs not installed: {", ".join(missing_langs)}',
                'installed': installed_langs,
                'requested': tesseract_langs
            }), 400
        
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
                print(f"Starting OCR with languages: {language_string}")
                ocrmypdf.ocr(
                    input_path,
                    output_path,
                    language=language_string,  # Use + separated languages
                    force_ocr=True,
                    output_type='pdf',
                    deskew=True,
                    rotate_pages=True,
                    skip_text=True,
                    invalidate_digital_signatures=True
                )
                print("OCR completed successfully")
            except ocrmypdf.exceptions.MissingDependencyError as e:
                print(f"Missing dependency: {str(e)}")
                return jsonify({
                    'error': 'Missing system dependency',
                    'details': str(e),
                    'message': 'Please ensure Tesseract and language packs are installed'
                }), 500
            except ocrmypdf.exceptions.UnsupportedImageFormatError as e:
                print(f"Unsupported image format: {str(e)}")
                return jsonify({
                    'error': 'Unsupported image format in PDF',
                    'details': str(e)
                }), 500
            except Exception as e:
                print(f"OCR processing failed: {str(e)}")
                traceback.print_exc()
                return jsonify({
                    'error': 'OCR processing failed',
                    'details': str(e),
                    'message': 'Check server logs for more details'
                }), 500
            
            print("Successfully created searchable PDF")
            
            # Get page count
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(output_path)
                page_count = len(reader.pages)
            except:
                page_count = "Unknown"
            
            # Return the searchable PDF
            response = send_file(
                output_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'searchable_{secure_filename(file.filename)}'
            )
            response.headers['X-Page-Count'] = str(page_count)
            return response
            
    except Exception as e:
        print(f"OCR Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'OCR processing failed: {str(e)}'}), 500

@ocr_pdf_bp.route('/tesseract-check', methods=['GET'])
def check_tesseract():
    """Check if Tesseract is installed and working"""
    try:
        # Check version
        result = subprocess.run(
            ['tesseract', '--version'],
            capture_output=True,
            text=True
        )
        version = result.stdout.split('\n')[0]
        
        # Check languages
        languages = check_tesseract_languages()
        
        return jsonify({
            'installed': True,
            'version': version,
            'languages': languages,
            'language_count': len(languages)
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