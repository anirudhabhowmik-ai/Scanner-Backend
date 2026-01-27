from flask import Blueprint, request, send_file, jsonify
import fitz  # PyMuPDF
from io import BytesIO
import json
import base64
from PIL import Image
import pytesseract
import cv2
import numpy as np

edit_pdf_bp = Blueprint('edit_pdf', __name__)

@edit_pdf_bp.route('/edit-pdf', methods=['POST'])
def edit_pdf():
    """
    Advanced PDF editor: add text, images, shapes, and drawings
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        pdf_file = request.files['file']
        
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Invalid file type. Please upload a PDF file."}), 400

        annotations_data = []
        if 'annotations' in request.form:
            try:
                annotations_data = json.loads(request.form['annotations'])
            except json.JSONDecodeError:
                return jsonify({"error": "Invalid annotations format"}), 400

        pdf_content = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        for page_data in annotations_data:
            page_num = page_data.get('pageNum', 1) - 1
            
            if page_num < 0 or page_num >= pdf_document.page_count:
                continue

            page = pdf_document[page_num]

            # Remove regions marked for deletion (existing text)
            deleted_regions = page_data.get('deletedRegions', [])
            for region in deleted_regions:
                rect = fitz.Rect(
                    region['x'],
                    region['y'],
                    region['x'] + region['width'],
                    region['y'] + region['height']
                )
                shape = page.new_shape()
                shape.draw_rect(rect)
                shape.finish(fill=(1, 1, 1), color=(1, 1, 1), width=0)
                shape.commit()

            # Add drawing layer if present
            if 'drawing' in page_data and page_data['drawing']:
                try:
                    drawing_data = page_data['drawing'].split(',')[1] if ',' in page_data['drawing'] else page_data['drawing']
                    drawing_bytes = base64.b64decode(drawing_data)
                    img_rect = page.rect
                    page.insert_image(img_rect, stream=drawing_bytes, overlay=True)
                except Exception as e:
                    print(f"Error adding drawing: {e}")

            # Process annotations
            annotations = page_data.get('annotations', [])
            for annotation in annotations:
                ann_type = annotation.get('type')

                if ann_type == 'text':
                    add_text_annotation(page, annotation)
                elif ann_type == 'image':
                    add_image_annotation(page, annotation)
                elif ann_type == 'shape':
                    add_shape_annotation(page, annotation)

        output = BytesIO()
        pdf_document.save(output)
        pdf_document.close()
        output.seek(0)

        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='edited.pdf'
        )

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@edit_pdf_bp.route('/extract-text-ocr', methods=['POST'])
def extract_text_ocr():
    """
    Extract text from PDF using OCR and native text extraction
    Returns text blocks with positions for each page
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        pdf_file = request.files['file']
        
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Invalid file type"}), 400

        pdf_content = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        all_pages_data = []

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Try native text extraction first
            text_blocks = extract_text_blocks_native(page)
            
            # If no native text found, use OCR
            if not text_blocks or len(text_blocks) == 0:
                text_blocks = extract_text_blocks_ocr(page)
            
            all_pages_data.append({
                "pageNum": page_num + 1,
                "textBlocks": text_blocks,
                "width": page.rect.width,
                "height": page.rect.height
            })

        pdf_document.close()

        return jsonify({
            "success": True,
            "pages": all_pages_data
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


def extract_text_blocks_native(page):
    """Extract text blocks from text-based PDF"""
    text_blocks = []
    
    try:
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            bbox = span["bbox"]
                            text_blocks.append({
                                "text": text,
                                "x": bbox[0],
                                "y": bbox[1],
                                "width": bbox[2] - bbox[0],
                                "height": bbox[3] - bbox[1],
                                "fontSize": span.get("size", 12),
                                "fontFamily": span.get("font", "helvetica"),
                                "color": rgb_to_hex(span.get("color", 0))
                            })
    except Exception as e:
        print(f"Error extracting native text: {e}")
    
    return text_blocks


def extract_text_blocks_ocr(page):
    """Extract text blocks using OCR for scanned PDFs"""
    text_blocks = []
    
    try:
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img_data = pix.tobytes("png")
        img = Image.open(BytesIO(img_data))
        
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        ocr_data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        
        n_boxes = len(ocr_data['text'])
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            
            if text and conf > 30:
                x = ocr_data['left'][i] / zoom
                y = ocr_data['top'][i] / zoom
                w = ocr_data['width'][i] / zoom
                h = ocr_data['height'][i] / zoom
                
                text_blocks.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "fontSize": h * 0.8,
                    "fontFamily": "helvetica",
                    "color": "#000000",
                    "confidence": conf
                })
    
    except Exception as e:
        print(f"Error in OCR extraction: {e}")
    
    return text_blocks


def add_text_annotation(page, annotation):
    """Add text annotation to PDF page"""
    try:
        text = annotation.get('text', '')
        x = float(annotation.get('x', 0))
        y = float(annotation.get('y', 0))
        font_size = int(annotation.get('fontSize', 12))
        font_family = annotation.get('fontFamily', 'helvetica').lower()
        color_hex = annotation.get('color', '#000000')
        font_weight = annotation.get('fontWeight', 'normal')
        font_style = annotation.get('fontStyle', 'normal')

        color = hex_to_rgb(color_hex)

        font_map = {
            'arial': 'helv',
            'helvetica': 'helv',
            'times new roman': 'times',
            'courier new': 'courier',
            'courier': 'courier',
            'georgia': 'times',
            'verdana': 'helv'
        }
        font = font_map.get(font_family, 'helv')

        if font_weight == 'bold' and font_style == 'italic':
            font = font + '-boldoblique'
        elif font_weight == 'bold':
            font = font + '-bold'
        elif font_style == 'italic':
            font = font + '-oblique'

        point = fitz.Point(x, y + font_size)
        page.insert_text(
            point,
            text,
            fontsize=font_size,
            fontname=font,
            color=color
        )

    except Exception as e:
        print(f"Error adding text: {e}")


def add_image_annotation(page, annotation):
    """Add image annotation to PDF page"""
    try:
        image_data = annotation.get('imageData', '')
        x = float(annotation.get('x', 0))
        y = float(annotation.get('y', 0))
        width = float(annotation.get('width', 100))
        height = float(annotation.get('height', 100))

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        rect = fitz.Rect(x, y, x + width, y + height)
        page.insert_image(rect, stream=image_bytes)

    except Exception as e:
        print(f"Error adding image: {e}")


def add_shape_annotation(page, annotation):
    """Add shape annotation to PDF page"""
    try:
        shape_type = annotation.get('shapeType', 'rectangle')
        x = float(annotation.get('x', 0))
        y = float(annotation.get('y', 0))
        width = float(annotation.get('width', 100))
        height = float(annotation.get('height', 100))
        fill_color_hex = annotation.get('fillColor', '#4f46e5')
        border_color_hex = annotation.get('borderColor', '#1e3a8a')
        border_width = float(annotation.get('borderWidth', 2))

        fill_color = hex_to_rgb(fill_color_hex)
        border_color = hex_to_rgb(border_color_hex)

        shape = page.new_shape()

        if shape_type == 'rectangle':
            rect = fitz.Rect(x, y, x + width, y + height)
            shape.draw_rect(rect)
        elif shape_type == 'circle':
            center_x = x + width / 2
            center_y = y + height / 2
            radius = min(width, height) / 2
            center = fitz.Point(center_x, center_y)
            shape.draw_circle(center, radius)
        elif shape_type == 'line':
            p1 = fitz.Point(x, y + height / 2)
            p2 = fitz.Point(x + width, y + height / 2)
            shape.draw_line(p1, p2)

        shape.finish(
            fill=fill_color,
            color=border_color,
            width=border_width
        )
        shape.commit()

    except Exception as e:
        print(f"Error adding shape: {e}")


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple (0-1 range)"""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)


def rgb_to_hex(rgb_int):
    """Convert PyMuPDF RGB integer to hex color"""
    try:
        if isinstance(rgb_int, int):
            r = (rgb_int >> 16) & 0xFF
            g = (rgb_int >> 8) & 0xFF
            b = rgb_int & 0xFF
            return f"#{r:02x}{g:02x}{b:02x}"
        return "#000000"
    except:
        return "#000000"