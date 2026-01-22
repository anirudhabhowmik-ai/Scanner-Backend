from flask import Blueprint, request, send_file, jsonify
import fitz  # PyMuPDF
import tempfile
import json

add_page_numbers_bp = Blueprint(
    "add_page_numbers",
    __name__,
    url_prefix="/add-page-numbers"
)

@add_page_numbers_bp.route("/", methods=["POST"])
def add_page_numbers():
    """
    Add customizable page numbers to uploaded PDF files
    """
    try:
        # Validate file upload
        if "files" not in request.files:
            return jsonify({"error": "No files uploaded"}), 400

        files = request.files.getlist("files")
        
        if not files or len(files) == 0:
            return jsonify({"error": "No files provided"}), 400

        # Parse options
        options = json.loads(request.form.get("options", "{}"))
        
        position = options.get("position", "bottom-center")
        font_family = options.get("fontFamily", "helvetica")
        font_size = int(options.get("fontSize", 12))
        font_color = options.get("fontColor", "#000000")
        bold = options.get("bold", False)
        italic = options.get("italic", False)
        underline = options.get("underline", False)
        custom_text = options.get("customText", "{n}")
        start_page = int(options.get("startPage", 1)) - 1  # Convert to 0-indexed
        end_page = int(options.get("endPage", 999999))  # Default to large number
        start_number = int(options.get("startNumber", 1))

        # Validate options
        if font_size < 8 or font_size > 72:
            return jsonify({"error": "Font size must be between 8 and 72"}), 400
        
        if start_page < 0:
            return jsonify({"error": "Start page must be at least 1"}), 400

        # Create output PDF
        output_pdf = fitz.open()

        # Merge all uploaded PDFs
        for file in files:
            try:
                pdf_data = file.read()
                pdf = fitz.open(stream=pdf_data, filetype="pdf")
                output_pdf.insert_pdf(pdf)
                pdf.close()
            except Exception as e:
                return jsonify({"error": f"Error processing {file.filename}: {str(e)}"}), 400

        total_pages = len(output_pdf)
        
        # Adjust end_page if it exceeds total pages
        end_page_index = min(end_page - 1, total_pages - 1)

        # Add page numbers to the merged PDF
        for page_index, page in enumerate(output_pdf):
            # Skip pages before start_page or after end_page
            if page_index < start_page or page_index > end_page_index:
                continue

            # Calculate the page number to display
            page_number = start_number + (page_index - start_page)

            # Format custom text
            text = custom_text or "{n}"
            
            # Replace placeholders - handle both {n} and {1} style
            text = text.replace("{n}", str(page_number))
            text = text.replace("{1}", str(page_number))
            text = text.replace("{total}", str(total_pages))

            # Get position coordinates
            x, y = get_position(page.rect, position)

            # Convert hex color to RGB
            rgb = hex_to_rgb(font_color)

            # Get font name with style
            font_name = get_font_name(font_family, bold, italic)

            # Insert the page number text
            text_writer = fitz.TextWriter(page.rect)
            
            # Calculate text position and insert
            try:
                page.insert_text(
                    (x, y),
                    text,
                    fontsize=font_size,
                    fontname=font_name,
                    color=rgb
                )

                # Add underline if requested
                if underline:
                    text_rect = fitz.get_text_length(text, fontname=font_name, fontsize=font_size)
                    line_y = y + 2
                    
                    # Calculate text width for underline
                    if "center" in position:
                        line_start = x - (text_rect / 2)
                        line_end = x + (text_rect / 2)
                    elif "right" in position:
                        line_start = x - text_rect
                        line_end = x
                    else:
                        line_start = x
                        line_end = x + text_rect
                    
                    page.draw_line((line_start, line_y), (line_end, line_y), color=rgb, width=1)

            except Exception as e:
                print(f"Error inserting text on page {page_index + 1}: {e}")

        # Save to temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmp.name
        tmp.close()  # Close the file handle before saving
        
        output_pdf.save(tmp_path)
        output_pdf.close()

        # Send the file and schedule cleanup
        response = send_file(
            tmp_path,
            as_attachment=True,
            download_name="page-numbered.pdf",
            mimetype="application/pdf"
        )
        
        # Clean up temp file after sending
        @response.call_on_close
        def cleanup():
            try:
                import os
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except:
                pass
        
        return response

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


def get_position(rect, position):
    """
    Calculate the position coordinates for page numbers based on selected position
    
    Args:
        rect: Page rectangle from PyMuPDF
        position: Position string (e.g., "bottom-center", "top-right")
        
    Returns:
        Tuple of (x, y) coordinates
    """
    margin = 40  # Distance from edge
    
    # Determine vertical position
    if position.startswith("top"):
        y = margin
    else:  # bottom
        y = rect.height - margin

    # Determine horizontal position
    if "left" in position:
        x = margin
    elif "right" in position:
        x = rect.width - margin
    else:  # center
        x = rect.width / 2

    return (x, y)


def get_font_name(family, bold, italic):
    """
    Get PyMuPDF font name based on family and style
    
    Args:
        family: Font family (helvetica, times, courier, symbol, zapfdingbats)
        bold: Boolean for bold
        italic: Boolean for italic
        
    Returns:
        Font name string for PyMuPDF
    """
    # Font mapping for PyMuPDF
    fonts = {
        "helvetica": {
            "normal": "helv",
            "bold": "hebo",
            "italic": "heit",
            "bold-italic": "hebi"
        },
        "times": {
            "normal": "tiro",
            "bold": "tibo",
            "italic": "tiit",
            "bold-italic": "tibi"
        },
        "courier": {
            "normal": "cour",
            "bold": "cobo",
            "italic": "coit",
            "bold-italic": "cobi"
        },
        "symbol": {
            "normal": "symb",
            "bold": "symb",
            "italic": "symb",
            "bold-italic": "symb"
        },
        "zapfdingbats": {
            "normal": "zadb",
            "bold": "zadb",
            "italic": "zadb",
            "bold-italic": "zadb"
        }
    }
    
    # Determine style
    if bold and italic:
        style = "bold-italic"
    elif bold:
        style = "bold"
    elif italic:
        style = "italic"
    else:
        style = "normal"
    
    return fonts.get(family, fonts["helvetica"]).get(style, "helv")


def hex_to_rgb(hex_color):
    """
    Convert hex color to RGB tuple (normalized 0-1)
    
    Args:
        hex_color: Hex color string (e.g., "#FF0000")
        
    Returns:
        Tuple of (r, g, b) values normalized to 0-1
    """
    hex_color = hex_color.lstrip('#')
    
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except:
        return (0, 0, 0)  # Default to black if conversion fails