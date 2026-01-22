# routes/organize_pdf.py

from flask import Blueprint, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import json
import os

organize_pdf_bp = Blueprint(
    "organize_pdf",
    __name__,
    url_prefix="/organize-pdf"
)

@organize_pdf_bp.route("", methods=["POST"])
def organize_pdf():
    if "files" not in request.files:
        return jsonify({"error": "PDF files required"}), 400

    if "layout" not in request.form:
        return jsonify({"error": "Layout data missing"}), 400

    try:
        layout = json.loads(request.form["layout"])
    except Exception as e:
        return jsonify({"error": "Invalid layout JSON"}), 400

    try:
        # Get all uploaded files
        uploaded_files = request.files.getlist("files")
        readers = [PdfReader(f) for f in uploaded_files]
        
        writer = PdfWriter()

        # Track which pages belong to which file
        page_mapping = []
        for file_idx, reader in enumerate(readers):
            for page_idx in range(len(reader.pages)):
                page_mapping.append({
                    'file_idx': file_idx,
                    'page_idx': page_idx
                })

        # Process layout
        for item in layout:
            if item["type"] == "page":
                global_index = item["pageIndex"]
                rotation = item.get("rotation", 0)
                
                # Get the correct file and page
                if global_index < len(page_mapping):
                    mapping = page_mapping[global_index]
                    file_idx = mapping['file_idx']
                    page_idx = mapping['page_idx']
                    
                    # Get the page from correct reader
                    page = readers[file_idx].pages[page_idx]
                    
                    # Apply rotation if needed
                    if rotation != 0:
                        page.rotate(rotation)
                    
                    writer.add_page(page)

            elif item["type"] == "blank":
                rotation = item.get("rotation", 0)
                
                # Get dimensions from first page of first file
                if len(readers) > 0 and len(readers[0].pages) > 0:
                    first_page = readers[0].pages[0]
                    width = float(first_page.mediabox.width)
                    height = float(first_page.mediabox.height)
                else:
                    # Default A4 size
                    width = 612
                    height = 792
                
                # Add blank page
                blank_page = writer.add_blank_page(width=width, height=height)
                
                # Apply rotation if needed
                if rotation != 0:
                    blank_page.rotate(rotation)

        # Write to temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        writer.write(tmp)
        tmp.close()

        # Send file and schedule cleanup
        response = send_file(
            tmp.name,
            as_attachment=True,
            download_name="organized.pdf",
            mimetype="application/pdf"
        )
        
        # Clean up temp file after response
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(tmp.name)
            except:
                pass
        
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500