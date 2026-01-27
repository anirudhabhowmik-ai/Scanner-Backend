from flask import Blueprint, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from io import BytesIO
from PIL import Image
import json

add_watermark_bp = Blueprint('add_watermark', __name__)

@add_watermark_bp.route("/add-watermark", methods=["POST"])
def add_watermark():
    """
    Add watermark to PDF files with advanced options:
    - Text or Image watermarks
    - Custom positioning per page
    - Text styling (bold, italic, underline)
    - Rotation support
    - Page range selection
    - Image resizing
    """
    try:
        # Get uploaded files
        files = request.files.getlist("files")
        if not files or len(files) == 0:
            return jsonify({"error": "No PDF files uploaded"}), 400

        # Get watermark configuration
        wm_type = request.form.get("type", "text")
        text = request.form.get("text", "")
        font_size = int(request.form.get("fontSize", 36))
        opacity = float(request.form.get("opacity", 0.3))
        rotation_deg = int(request.form.get("rotation", 0))
        font_family = request.form.get("fontFamily", "Helvetica")
        text_color = request.form.get("color", "#000000")
        
        # Text styling options
        is_bold = request.form.get("bold", "false").lower() == "true"
        is_italic = request.form.get("italic", "false").lower() == "true"
        is_underline = request.form.get("underline", "false").lower() == "true"
        
        # Page range
        page_start = int(request.form.get("pageStart", 1))
        page_end = int(request.form.get("pageEnd", 0))
        
        # Position data for each page (JSON array)
        positions_json = request.form.get("positions", "[]")
        positions = json.loads(positions_json)
        
        # Image file (if image watermark)
        image_file = request.files.get("image")

        # Validate inputs
        if wm_type == "text" and not text.strip():
            return jsonify({"error": "Watermark text cannot be empty"}), 400
        
        if wm_type == "image" and not image_file:
            return jsonify({"error": "No watermark image provided"}), 400

        # Step 1: Merge all PDFs into one
        merged_writer = PdfWriter()
        total_pages = 0
        
        for file in files:
            try:
                reader = PdfReader(file)
                for page in reader.pages:
                    merged_writer.add_page(page)
                    total_pages += 1
            except Exception as e:
                return jsonify({"error": f"Error reading PDF: {str(e)}"}), 400

        # Apply page range validation
        if page_end == 0:
            page_end = total_pages
        else:
            page_end = min(page_end, total_pages)
        
        page_start = max(1, page_start)

        if page_start > total_pages:
            return jsonify({"error": f"Page start ({page_start}) exceeds total pages ({total_pages})"}), 400

        # Step 2: Process each page and add watermark
        output_writer = PdfWriter()
        
        # Pre-load and process image if needed
        image_data = None
        if wm_type == "image" and image_file:
            try:
                image_file.seek(0)
                img = Image.open(image_file)
                # Convert to RGB if necessary
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')
                image_data = img
            except Exception as e:
                return jsonify({"error": f"Error processing image: {str(e)}"}), 400
        
        for page_num in range(total_pages):
            page = merged_writer.pages[page_num]
            current_page_num = page_num + 1
            
            # Check if watermark should be applied to this page
            if current_page_num < page_start or current_page_num > page_end:
                output_writer.add_page(page)
                continue
            
            # Find position data for this page
            page_position = None
            for pos in positions:
                if pos.get("pageNum") == current_page_num:
                    page_position = pos
                    break
            
            # Skip if no position data found
            if not page_position:
                output_writer.add_page(page)
                continue
            
            # Create watermark overlay
            watermark_page = create_watermark_page(
                page=page,
                wm_type=wm_type,
                text=text,
                font_size=font_size,
                opacity=opacity,
                rotation_deg=rotation_deg,
                font_family=font_family,
                text_color=text_color,
                is_bold=is_bold,
                is_italic=is_italic,
                is_underline=is_underline,
                page_position=page_position,
                image_data=image_data
            )
            
            # Merge watermark with page (always over content)
            page.merge_page(watermark_page)
            output_writer.add_page(page)

        # Step 3: Save and return the watermarked PDF
        output = BytesIO()
        output_writer.write(output)
        output.seek(0)

        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name="watermarked.pdf"
        )

    except Exception as e:
        print(f"Error in add_watermark: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


def create_watermark_page(page, wm_type, text, font_size, opacity, rotation_deg, 
                         font_family, text_color, is_bold, is_italic, is_underline, 
                         page_position, image_data):
    """
    Create a watermark overlay for a single page
    """
    packet = BytesIO()
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)

    c = canvas.Canvas(packet, pagesize=(width, height))
    
    # Convert hex color to RGB
    r, g, b = hex_to_rgb(text_color)
    
    # Set opacity and color
    c.setFillColor(Color(r/255, g/255, b/255, alpha=opacity))
    c.setStrokeColor(Color(r/255, g/255, b/255, alpha=opacity))

    # Calculate position from percentage or pixels
    left_str = page_position.get("left", "50%")
    top_str = page_position.get("top", "50%")
    
    # Handle both percentage and pixel values
    if isinstance(left_str, str):
        if "%" in left_str:
            left_pct = float(left_str.replace("%", ""))
            x = (left_pct / 100) * width
        else:
            x = float(left_str.replace("px", ""))
    else:
        x = float(left_str)
    
    if isinstance(top_str, str):
        if "%" in top_str:
            top_pct = float(top_str.replace("%", ""))
            # Convert from top-based to bottom-based coordinate system
            y = height - ((top_pct / 100) * height)
        else:
            y = height - float(top_str.replace("px", ""))
    else:
        y = height - float(top_str)
    
    # Get rotation from position data (or use global rotation)
    page_rotation = float(page_position.get("rotation", rotation_deg))
    
    if wm_type == "image" and image_data:
        # Image watermark
        img_width = page_position.get("width", 150)
        
        # Calculate height maintaining aspect ratio
        aspect_ratio = image_data.height / image_data.width
        img_height = img_width * aspect_ratio
        
        c.saveState()
        c.translate(x, y)
        c.rotate(page_rotation)
        
        try:
            # Convert PIL Image to ImageReader for reportlab
            img_buffer = BytesIO()
            
            # Save with proper format
            if image_data.mode == 'RGBA':
                # For RGBA images, save as PNG to preserve transparency
                image_data.save(img_buffer, format='PNG')
            else:
                # For RGB images, can use JPEG or PNG
                image_data.save(img_buffer, format='PNG')
            
            img_buffer.seek(0)
            img_reader = ImageReader(img_buffer)
            
            # Draw image centered at origin with alpha support
            c.drawImage(
                img_reader,
                -img_width/2,
                -img_height/2,
                width=img_width,
                height=img_height,
                mask='auto',
                preserveAspectRatio=True
            )
        except Exception as e:
            print(f"Error drawing image: {str(e)}")
            import traceback
            traceback.print_exc()
        
        c.restoreState()
        
    elif wm_type == "text" and text:
        # Text watermark
        
        # Determine font based on family and styling
        font = get_font_name(font_family, is_bold, is_italic)
        
        c.setFont(font, font_size)
        
        c.saveState()
        c.translate(x, y)
        c.rotate(page_rotation)
        
        # Calculate text dimensions
        text_width = c.stringWidth(text, font, font_size)
        text_height = font_size
        
        # Draw text centered at origin
        c.drawString(-text_width/2, -text_height/3, text)
        
        # Add underline if requested
        if is_underline:
            underline_y = -text_height/2 - 2
            c.line(-text_width/2, underline_y, text_width/2, underline_y)
        
        c.restoreState()

    c.save()
    packet.seek(0)
    
    # Return the watermark page
    watermark_reader = PdfReader(packet)
    return watermark_reader.pages[0]


def get_font_name(font_family, is_bold, is_italic):
    """
    Get the correct font name based on family and styling options
    """
    font_map = {
        "Helvetica": {
            (False, False): "Helvetica",
            (True, False): "Helvetica-Bold",
            (False, True): "Helvetica-Oblique",
            (True, True): "Helvetica-BoldOblique"
        },
        "Helvetica-Bold": {
            (False, False): "Helvetica-Bold",
            (True, False): "Helvetica-Bold",
            (False, True): "Helvetica-BoldOblique",
            (True, True): "Helvetica-BoldOblique"
        },
        "Times-Roman": {
            (False, False): "Times-Roman",
            (True, False): "Times-Bold",
            (False, True): "Times-Italic",
            (True, True): "Times-BoldItalic"
        },
        "Courier": {
            (False, False): "Courier",
            (True, False): "Courier-Bold",
            (False, True): "Courier-Oblique",
            (True, True): "Courier-BoldOblique"
        }
    }
    
    # Default to Helvetica if font family not found
    family_fonts = font_map.get(font_family, font_map["Helvetica"])
    return family_fonts.get((is_bold, is_italic), "Helvetica")


def hex_to_rgb(hex_color):
    """
    Convert hex color to RGB tuple
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))