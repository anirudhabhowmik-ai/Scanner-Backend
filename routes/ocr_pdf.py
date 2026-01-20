from flask import Blueprint, request, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PyPDF2 import PdfReader, PdfWriter
import io
import traceback
import platform

ocr_pdf_bp = Blueprint('ocr_pdf', __name__)

# -------------------------------
# CONFIGURE PATHS BASED ON OS
# -------------------------------
if platform.system() == "Windows":
    # Windows Tesseract path
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    POPPLER_PATH = r"C:\poppler\Library\bin"  # path to Poppler bin
else:
    # Linux / Railway: use system-installed binaries
    POPPLER_PATH = None

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def has_text_content(pdf_path):
    """Check if PDF already has text content"""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text = page.extract_text()
            if text and len(text.strip()) > 50:
                return True
        return False
    except Exception as e:
        print(f"Error checking text content: {str(e)}")
        return False

def create_searchable_pdf(image_paths, texts, output_path, language='eng'):
    """Create a searchable PDF with OCR text layer"""
    try:
        writer = PdfWriter()
        
        for img_path, ocr_text in zip(image_paths, texts):
            # Get image dimensions
            img = Image.open(img_path)
            img_width, img_height = img.size
            
            # Create PDF page with same dimensions as image
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(img_width, img_height))
            
            # Draw the image first
            can.drawImage(img_path, 0, 0, width=img_width, height=img_height)
            
            # Add invisible text layer for searchability
            can.setFillColorRGB(0, 0, 0, alpha=0)  # Invisible text
            can.setFont("Helvetica", 8)
            
            # Add OCR text as invisible layer
            text_object = can.beginText(10, img_height - 20)
            text_object.setTextRenderMode(3)  # Invisible text mode
            
            # Split text into lines and add
            lines = ocr_text.split('\n')
            for line in lines[:100]:  # Limit lines to prevent issues
                if line.strip():
                    try:
                        text_object.textLine(line.strip())
                    except:
                        continue
            
            can.drawText(text_object)
            can.save()
            
            # Add page to writer
            packet.seek(0)
            page_reader = PdfReader(packet)
            writer.add_page(page_reader.pages[0])
        
        # Write final PDF
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        return True
        
    except Exception as e:
        print(f"Error creating searchable PDF: {str(e)}")
        traceback.print_exc()
        return False

@ocr_pdf_bp.route('/ocr-pdf', methods=['POST'])
def ocr_pdf():
    """Convert image-based PDF to searchable PDF using OCR"""
    
    try:
        # Validate file in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        language = request.form.get('language', 'eng')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400
        
        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded PDF
            input_path = os.path.join(temp_dir, secure_filename(file.filename))
            file.save(input_path)
            
            print(f"Processing file: {file.filename}")
            
            # Check if PDF already has text
            if has_text_content(input_path):
                print("PDF already contains text, returning as-is")
                return send_file(
                    input_path,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'searchable_{secure_filename(file.filename)}'
                )
            
            # Convert PDF to images
            print("Converting PDF to images...")
            try:
                images = convert_from_path(input_path, dpi=300, poppler_path=POPPLER_PATH)
            except Exception as e:
                print(f"PDF conversion error: {str(e)}")
                return jsonify({'error': 'Failed to convert PDF to images. Ensure Poppler is installed and poppler_path is correct.'}), 500
            
            print(f"Processing {len(images)} pages with OCR...")
            
            # Perform OCR on each page
            image_paths = []
            ocr_texts = []
            
            for i, image in enumerate(images):
                # Save image temporarily
                img_path = os.path.join(temp_dir, f'page_{i}.png')
                image.save(img_path, 'PNG')
                image_paths.append(img_path)
                
                # Perform OCR
                print(f"OCR processing page {i+1}/{len(images)}...")
                try:
                    ocr_text = pytesseract.image_to_string(image, lang=language)
                    ocr_texts.append(ocr_text)
                except Exception as e:
                    print(f"OCR error on page {i+1}: {str(e)}")
                    ocr_texts.append("")  # Add empty text if OCR fails
            
            # Create searchable PDF
            output_path = os.path.join(temp_dir, 'searchable_output.pdf')
            
            print("Creating searchable PDF...")
            success = create_searchable_pdf(image_paths, ocr_texts, output_path, language)
            
            if not success:
                return jsonify({'error': 'Failed to create searchable PDF'}), 500
            
            print("Successfully created searchable PDF")
            
            # Return the searchable PDF
            response = send_file(
                output_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'searchable_{secure_filename(file.filename)}'
            )
            
            # Add custom header with page count
            response.headers['X-Page-Count'] = str(len(images))
            
            return response
            
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
