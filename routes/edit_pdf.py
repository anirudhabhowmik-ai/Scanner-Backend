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

# Store PDF in memory for image extraction (temporary solution)
# In production, use proper session management or database
pdf_cache = {}

@edit_pdf_bp.route('/edit-pdf', methods=['POST'])
def edit_pdf():
    """
    Advanced PDF editor: add text, images, shapes, and drawings
    Properly handles edited OCR text and deleted images
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

            # STEP 1: Remove deleted images
            deleted_images = page_data.get('deletedImages', [])
            if deleted_images and len(deleted_images) > 0:
                for img_info in deleted_images:
                    try:
                        # Cover image area with white rectangle
                        shape = page.new_shape()
                        rect = fitz.Rect(
                            img_info['x'],
                            img_info['y'],
                            img_info['x'] + img_info['width'],
                            img_info['y'] + img_info['height']
                        )
                        shape.draw_rect(rect)
                        shape.finish(fill=(1, 1, 1), color=(1, 1, 1), width=0)
                        shape.commit()
                    except Exception as e:
                        print(f"Error deleting image: {e}")

            # STEP 2: Remove deleted text regions (original OCR text locations)
            deleted_regions = page_data.get('deletedRegions', [])
            if deleted_regions and len(deleted_regions) > 0:
                shape = page.new_shape()
                for region in deleted_regions:
                    rect = fitz.Rect(
                        region['x'],
                        region['y'],
                        region['x'] + region['width'],
                        region['y'] + region['height']
                    )
                    shape.draw_rect(rect)
                shape.finish(fill=(1, 1, 1), color=(1, 1, 1), width=0)
                shape.commit()

            # STEP 3: Add drawing layer if present
            if 'drawing' in page_data and page_data['drawing']:
                try:
                    drawing_data = page_data['drawing'].split(',')[1] if ',' in page_data['drawing'] else page_data['drawing']
                    drawing_bytes = base64.b64decode(drawing_data)
                    img_rect = page.rect
                    page.insert_image(img_rect, stream=drawing_bytes, overlay=True)
                except Exception as e:
                    print(f"Error adding drawing: {e}")

            # STEP 4: Add new annotations (text, images, shapes)
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
        print(f"Error in edit_pdf: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@edit_pdf_bp.route('/extract-text-ocr', methods=['POST'])
def extract_text_ocr():
    """
    Extract text and images from PDF using native extraction first, then OCR as fallback
    Returns text blocks and images with positions for each page
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        pdf_file = request.files['file']
        
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Invalid file type"}), 400

        pdf_content = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        # Cache PDF for image extraction
        pdf_id = str(hash(pdf_content))[:16]
        pdf_cache[pdf_id] = pdf_content

        all_pages_data = []

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Extract text blocks (native first, then OCR if needed)
            text_blocks = extract_text_blocks_native(page)
            
            # If very little native text, use OCR
            if len(text_blocks) < 5:
                ocr_blocks = extract_text_blocks_ocr(page)
                text_blocks.extend(ocr_blocks)
            
            # Extract images from the page
            images = extract_images_from_page(page, page_num)
            
            all_pages_data.append({
                "pageNum": page_num + 1,
                "textBlocks": text_blocks,
                "images": images,
                "width": page.rect.width,
                "height": page.rect.height,
                "pdfId": pdf_id
            })

        pdf_document.close()

        return jsonify({
            "success": True,
            "pages": all_pages_data
        })

    except Exception as e:
        print(f"Error in extract_text_ocr: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@edit_pdf_bp.route('/get-pdf-image', methods=['POST'])
def get_pdf_image():
    """
    Extract a specific image from a PDF page
    """
    try:
        data = request.json
        xref = data.get('xref')
        page_num = data.get('pageNum', 1) - 1
        pdf_id = data.get('pdfId')

        if pdf_id not in pdf_cache:
            return jsonify({"error": "PDF not found in cache"}), 404

        pdf_content = pdf_cache[pdf_id]
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        if page_num < 0 or page_num >= pdf_document.page_count:
            return jsonify({"error": "Invalid page number"}), 400

        page = pdf_document[page_num]

        try:
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            pdf_document.close()

            mimetype_map = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'tiff': 'image/tiff',
                'gif': 'image/gif'
            }
            mimetype = mimetype_map.get(image_ext, 'image/png')

            return send_file(
                BytesIO(image_bytes),
                mimetype=mimetype
            )

        except Exception as e:
            print(f"Error extracting image: {e}")
            pdf_document.close()
            return jsonify({"error": f"Failed to extract image: {str(e)}"}), 500

    except Exception as e:
        print(f"Error in get_pdf_image: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


def extract_text_blocks_native(page):
    """
    Extract text blocks from text-based PDF
    Returns list of text blocks with position and style information
    """
    text_blocks = []
    
    try:
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text and len(text) > 0:
                            bbox = span["bbox"]
                            
                            font_size = span.get("size", 12)
                            font_name = span.get("font", "helvetica").lower()
                            font_family = map_font_family(font_name)
                            
                            text_blocks.append({
                                "text": text,
                                "x": bbox[0],
                                "y": bbox[1],
                                "width": bbox[2] - bbox[0],
                                "height": bbox[3] - bbox[1],
                                "fontSize": font_size,
                                "fontFamily": font_family,
                                "color": rgb_to_hex(span.get("color", 0)),
                                "source": "native"
                            })
    except Exception as e:
        print(f"Error extracting native text: {e}")
    
    return text_blocks


def extract_text_blocks_ocr(page):
    """
    Extract text blocks using OCR for scanned PDFs
    """
    text_blocks = []
    
    try:
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img_data = pix.tobytes("png")
        img = Image.open(BytesIO(img_data))
        
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
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
                
                estimated_font_size = max(8, h * 0.8)
                
                text_blocks.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "fontSize": estimated_font_size,
                    "fontFamily": "helvetica",
                    "color": "#000000",
                    "confidence": conf,
                    "source": "ocr"
                })
    
    except Exception as e:
        print(f"Error in OCR extraction: {e}")
    
    return text_blocks


def extract_images_from_page(page, page_num):
    """
    Extract embedded images from PDF page
    """
    images = []
    
    try:
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            
            if rects:
                for rect in rects:
                    images.append({
                        "xref": xref,
                        "x": rect.x0,
                        "y": rect.y0,
                        "width": rect.width,
                        "height": rect.height,
                        "index": img_index,
                        "pageNum": page_num + 1
                    })
    
    except Exception as e:
        print(f"Error extracting images: {e}")
    
    return images


def map_font_family(font_name):
    """
    Map PDF font names to common web font families
    """
    font_name = font_name.lower()
    
    if 'arial' in font_name or 'helvetica' in font_name or 'sans' in font_name:
        return 'Arial'
    elif 'times' in font_name or 'roman' in font_name or 'serif' in font_name:
        return 'Times New Roman'
    elif 'courier' in font_name or 'mono' in font_name:
        return 'Courier New'
    elif 'georgia' in font_name:
        return 'Georgia'
    elif 'verdana' in font_name:
        return 'Verdana'
    else:
        return 'Arial'


def add_text_annotation(page, annotation):
    """
    Add text annotation to PDF page with proper font styling
    """
    try:
        text = annotation.get('text', '')
        if not text:
            return
            
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
            'times': 'times',
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
    """
    Add image annotation to PDF page
    """
    try:
        image_data = annotation.get('imageData', '')
        if not image_data:
            return
            
        x = float(annotation.get('x', 0))
        y = float(annotation.get('y', 0))
        width = float(annotation.get('width', 100))
        height = float(annotation.get('height', 100))

        if image_data.startswith('data:'):
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
        elif image_data.startswith('blob:'):
            print("Warning: Cannot process blob URLs")
            return
        else:
            try:
                image_bytes = base64.b64decode(image_data)
            except:
                print("Error: Invalid image data format")
                return
        
        rect = fitz.Rect(x, y, x + width, y + height)
        page.insert_image(rect, stream=image_bytes)

    except Exception as e:
        print(f"Error adding image: {e}")


def add_shape_annotation(page, annotation):
    """
    Add shape annotation (rectangle, circle, line) to PDF page
    """
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
    """
    Convert hex color to RGB tuple (0-1 range) for PyMuPDF
    """
    try:
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except:
        return (0, 0, 0)


def rgb_to_hex(rgb_int):
    """
    Convert PyMuPDF RGB integer to hex color string
    """
    try:
        if isinstance(rgb_int, int):
            r = (rgb_int >> 16) & 0xFF
            g = (rgb_int >> 8) & 0xFF
            b = rgb_int & 0xFF
            return f"#{r:02x}{g:02x}{b:02x}"
        return "#000000"
    except:
        return "#000000"