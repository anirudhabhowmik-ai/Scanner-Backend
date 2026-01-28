from flask import Blueprint, request, send_file, jsonify
import fitz
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime

crop_pdf_bp = Blueprint("crop_pdf", __name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@crop_pdf_bp.route("/crop-pdf", methods=["POST"])
def crop_pdf():
    """Crop PDF pages - supports both single and multiple PDFs with merging"""
    try:
        # Check if multiple files or single file
        uploaded_files = request.files.getlist("files")
        
        # Fallback to single file upload for backward compatibility
        if not uploaded_files or len(uploaded_files) == 0:
            if "file" in request.files:
                uploaded_files = [request.files["file"]]
            else:
                return jsonify({"error": "No files uploaded"}), 400
        
        # Validate files
        for file in uploaded_files:
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400
            
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({"error": "Only PDF files are supported"}), 400

        # Validate crop data
        crop_data_raw = request.form.get("cropData")
        if not crop_data_raw:
            return jsonify({"error": "No crop data provided"}), 400
        
        try:
            crop_data = json.loads(crop_data_raw)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid crop data format"}), 400

        # Determine if we're processing multiple files or single file
        is_multiple_files = isinstance(crop_data, list)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_paths = []
        cropped_docs = []

        try:
            # Process each file
            if is_multiple_files:
                # Multiple files - each with their own crop data
                for file_index, file in enumerate(uploaded_files):
                    if file_index >= len(crop_data):
                        continue
                    
                    file_crop_data = crop_data[file_index]
                    boxes = file_crop_data.get("boxes", [])
                    
                    if not boxes or len(boxes) == 0:
                        continue
                    
                    # Save uploaded file
                    filename = secure_filename(file.filename)
                    unique_filename = f"{timestamp}_{file_index}_{filename}"
                    input_path = os.path.join(UPLOAD_DIR, unique_filename)
                    file.save(input_path)
                    input_paths.append(input_path)
                    
                    # Open and crop PDF
                    doc = fitz.open(input_path)
                    
                    # Apply crop to each page
                    for box in boxes:
                        if not all(key in box for key in ["page", "x", "y", "width", "height"]):
                            continue
                        
                        page_num = int(box["page"]) - 1
                        
                        if page_num < 0 or page_num >= len(doc):
                            continue
                        
                        crop_rect = fitz.Rect(
                            float(box["x"]), 
                            float(box["y"]), 
                            float(box["x"]) + float(box["width"]), 
                            float(box["y"]) + float(box["height"])
                        )
                        
                        page = doc[page_num]
                        page_rect = page.rect
                        adjusted_rect = fitz.Rect(crop_rect)
                        
                        # Clamp to page dimensions
                        adjusted_rect.x0 = max(0, min(adjusted_rect.x0, page_rect.width))
                        adjusted_rect.y0 = max(0, min(adjusted_rect.y0, page_rect.height))
                        adjusted_rect.x1 = max(adjusted_rect.x0, min(adjusted_rect.x1, page_rect.width))
                        adjusted_rect.y1 = max(adjusted_rect.y0, min(adjusted_rect.y1, page_rect.height))
                        
                        page.set_cropbox(adjusted_rect)
                    
                    cropped_docs.append(doc)
                
                # Merge all cropped PDFs into one
                if len(cropped_docs) == 0:
                    return jsonify({"error": "No valid PDFs to process"}), 400
                
                merged_doc = fitz.open()
                for doc in cropped_docs:
                    merged_doc.insert_pdf(doc)
                    doc.close()
                
                # Save merged PDF
                output_filename = f"cropped_merged_{timestamp}.pdf"
                output_path = os.path.join(UPLOAD_DIR, output_filename)
                merged_doc.save(output_path)
                merged_doc.close()
                
            else:
                # Single file - original behavior
                file = uploaded_files[0]
                filename = secure_filename(file.filename)
                unique_filename = f"{timestamp}_{filename}"
                input_path = os.path.join(UPLOAD_DIR, unique_filename)
                file.save(input_path)
                input_paths.append(input_path)
                
                doc = fitz.open(input_path)
                
                mode = crop_data.get("mode", "all")
                boxes = crop_data.get("boxes", [])
                
                if not boxes or len(boxes) == 0:
                    doc.close()
                    return jsonify({"error": "No crop boxes provided"}), 400
                
                if mode == "all":
                    # Apply first crop box to all pages
                    box = boxes[0]
                    
                    if not all(key in box for key in ["x", "y", "width", "height"]):
                        doc.close()
                        raise ValueError("Invalid crop box format")
                    
                    crop_rect = fitz.Rect(
                        float(box["x"]), 
                        float(box["y"]), 
                        float(box["x"]) + float(box["width"]), 
                        float(box["y"]) + float(box["height"])
                    )
                    
                    # Apply to all pages
                    for page in doc:
                        page_rect = page.rect
                        adjusted_rect = fitz.Rect(crop_rect)
                        
                        # Clamp to page dimensions
                        adjusted_rect.x0 = max(0, min(adjusted_rect.x0, page_rect.width))
                        adjusted_rect.y0 = max(0, min(adjusted_rect.y0, page_rect.height))
                        adjusted_rect.x1 = max(adjusted_rect.x0, min(adjusted_rect.x1, page_rect.width))
                        adjusted_rect.y1 = max(adjusted_rect.y0, min(adjusted_rect.y1, page_rect.height))
                        
                        page.set_cropbox(adjusted_rect)
                
                else:  # individual mode
                    # Apply each crop box to corresponding page
                    for box in boxes:
                        if not all(key in box for key in ["page", "x", "y", "width", "height"]):
                            continue
                        
                        page_num = int(box["page"]) - 1
                        
                        if page_num < 0 or page_num >= len(doc):
                            continue
                        
                        crop_rect = fitz.Rect(
                            float(box["x"]), 
                            float(box["y"]), 
                            float(box["x"]) + float(box["width"]), 
                            float(box["y"]) + float(box["height"])
                        )
                        
                        page = doc[page_num]
                        page_rect = page.rect
                        adjusted_rect = fitz.Rect(crop_rect)
                        
                        # Clamp to page dimensions
                        adjusted_rect.x0 = max(0, min(adjusted_rect.x0, page_rect.width))
                        adjusted_rect.y0 = max(0, min(adjusted_rect.y0, page_rect.height))
                        adjusted_rect.x1 = max(adjusted_rect.x0, min(adjusted_rect.x1, page_rect.width))
                        adjusted_rect.y1 = max(adjusted_rect.y0, min(adjusted_rect.y1, page_rect.height))
                        
                        page.set_cropbox(adjusted_rect)
                
                # Save cropped PDF
                output_filename = f"cropped_{timestamp}_{filename}"
                output_path = os.path.join(UPLOAD_DIR, output_filename)
                doc.save(output_path)
                doc.close()

            # Clean up input files
            for path in input_paths:
                if os.path.exists(path):
                    os.remove(path)

            # Send the cropped file
            download_name = "cropped_merged.pdf" if is_multiple_files else f"cropped_{uploaded_files[0].filename}"
            
            return send_file(
                output_path, 
                as_attachment=True, 
                download_name=download_name,
                mimetype="application/pdf"
            )

        except Exception as e:
            # Clean up on error
            for doc in cropped_docs:
                try:
                    doc.close()
                except:
                    pass
            
            for path in input_paths:
                if os.path.exists(path):
                    os.remove(path)
            
            raise e

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500