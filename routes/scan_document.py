from flask import Blueprint, request, send_file, jsonify
import cv2
import numpy as np
from PIL import Image
import io

scan_doc_bp = Blueprint("scan_doc", __name__)

# Try to import docTR for ML-based detection
try:
    from doctr.models import detection_predictor
    DOCTR_AVAILABLE = True
    print("✓ docTR loaded successfully - Using AI-powered edge detection")
    # Initialize detector (only once at startup)
    detector = detection_predictor(arch='db_resnet50', pretrained=True)
except ImportError:
    DOCTR_AVAILABLE = False
    print("⚠ docTR not available - Using traditional CV edge detection")
    detector = None

def order_points(pts):
    """Order points: top-left, top-right, bottom-right, bottom-left"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left
    rect[2] = pts[np.argmax(s)]      # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]   # top-right
    rect[3] = pts[np.argmax(diff)]   # bottom-left
    return rect

def detect_with_doctr(img):
    """AI-powered document detection using docTR"""
    if not DOCTR_AVAILABLE or detector is None:
        return None
    
    try:
        h, w = img.shape[:2]
        # Convert BGR to RGB for docTR
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Resize if too large (docTR works best with moderate sizes)
        max_dim = 1024
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            rgb_resized = cv2.resize(rgb, (int(w * scale), int(h * scale)))
        else:
            rgb_resized = rgb
            scale = 1.0
        
        # Run detection
        result = detector([rgb_resized])
        
        if result and len(result) > 0:
            # Get all detected boxes
            boxes = result[0]
            
            if len(boxes) > 0:
                # Find the largest box (likely the main document)
                largest_box = None
                max_area = 0
                
                for box in boxes:
                    # box format: [x_min, y_min, x_max, y_max] (normalized 0-1)
                    area = (box[2] - box[0]) * (box[3] - box[1])
                    if area > max_area:
                        max_area = area
                        largest_box = box
                
                if largest_box is not None and max_area > 0.05:  # At least 5% of image
                    # Convert normalized coords to pixels
                    h_resized, w_resized = rgb_resized.shape[:2]
                    x1 = int(largest_box[0] * w_resized / scale)
                    y1 = int(largest_box[1] * h_resized / scale)
                    x2 = int(largest_box[2] * w_resized / scale)
                    y2 = int(largest_box[3] * h_resized / scale)
                    
                    # Create corners array
                    corners = np.array([
                        [x1, y1],  # top-left
                        [x2, y1],  # top-right
                        [x2, y2],  # bottom-right
                        [x1, y2]   # bottom-left
                    ], dtype=np.float32)
                    
                    print(f"✓ docTR detected document: area={max_area:.2%}")
                    return corners
        
        return None
    except Exception as e:
        print(f"docTR detection error: {e}")
        return None

def detect_document_contour_cv(img):
    """Traditional CV-based document detection (fallback)"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Enhanced preprocessing
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Morphological gradient
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    morph_gradient = cv2.morphologyEx(blur, cv2.MORPH_GRADIENT, kernel)
    
    # Multiple Canny passes
    edges1 = cv2.Canny(blur, 30, 100)
    edges2 = cv2.Canny(blur, 50, 150)
    edges3 = cv2.Canny(blur, 75, 200)
    edges4 = cv2.Canny(morph_gradient, 30, 100)
    
    # Combine edges
    edges = cv2.bitwise_or(edges1, edges2)
    edges = cv2.bitwise_or(edges, edges3)
    edges = cv2.bitwise_or(edges, edges4)
    
    # Dilate and close
    dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3,3)), iterations=2)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5,5)))
    
    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:25]
    
    min_area = (w * h) * 0.05
    max_area = (w * h) * 0.98
    
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        
        peri = cv2.arcLength(c, True)
        for eps in [0.015, 0.02, 0.03, 0.04, 0.05]:
            approx = cv2.approxPolyDP(c, eps * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                ordered = order_points(pts)
                
                # Validate aspect ratio
                widthA = np.linalg.norm(ordered[0] - ordered[1])
                widthB = np.linalg.norm(ordered[2] - ordered[3])
                heightA = np.linalg.norm(ordered[0] - ordered[3])
                heightB = np.linalg.norm(ordered[1] - ordered[2])
                
                avg_width = (widthA + widthB) / 2
                avg_height = (heightA + heightB) / 2
                
                if avg_width > 0 and avg_height > 0:
                    aspect_ratio = max(avg_width, avg_height) / min(avg_width, avg_height)
                    if aspect_ratio < 10:  # Reasonable aspect ratio
                        print(f"✓ CV detected document: area={area/(w*h):.2%}")
                        return ordered
    
    return None

def enhance_image(img):
    """Enhanced image processing for better quality"""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    
    # Sharpening
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    img = cv2.filter2D(img, -1, kernel)
    return img

@scan_doc_bp.route("/detect-corners", methods=["POST"])
def detect_corners():
    """Detect document corners with AI-first approach"""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    file = request.files["image"]
    img_bytes = file.read()
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
    
    h, w = img.shape[:2]
    print(f"\n=== DETECT CORNERS: {w}x{h} ===")
    
    # Resize for faster processing
    max_dim = 1500
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img_resized = cv2.resize(img, (int(w * scale), int(h * scale)))
        scale_back = max(h, w) / max_dim
    else:
        img_resized = img
        scale_back = 1.0
    
    # Try AI detection first (if available)
    corners = None
    detection_method = "none"
    
    if DOCTR_AVAILABLE:
        corners = detect_with_doctr(img_resized)
        if corners is not None:
            detection_method = "doctr"
    
    # Fallback to traditional CV
    if corners is None:
        corners = detect_document_contour_cv(img_resized)
        if corners is not None:
            detection_method = "opencv"
    
    # Scale back to original size
    if corners is not None:
        corners = (corners * scale_back).tolist()
        print(f"✓ Detection method: {detection_method}")
        return jsonify({
            "detected": True,
            "corners": corners,
            "width": w,
            "height": h,
            "method": detection_method
        })
    else:
        # Use full image with margins
        margin_w = int(w * 0.02)
        margin_h = int(h * 0.02)
        print("⚠ No document detected, using full image")
        return jsonify({
            "detected": False,
            "corners": [
                [margin_w, margin_h],
                [w - margin_w, margin_h],
                [w - margin_w, h - margin_h],
                [margin_w, h - margin_h]
            ],
            "width": w,
            "height": h,
            "method": "default"
        })

@scan_doc_bp.route("/scan", methods=["POST"])
def scan_and_convert():
    """Process and convert scanned document"""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    file = request.files["image"]
    output_format = request.form.get("format", "jpg").lower()
    enhance = request.form.get("enhance", "true").lower() == "true"
    
    np_img = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
    
    print(f"\n=== SCAN: format={output_format}, enhance={enhance} ===")
    
    if enhance:
        img = enhance_image(img)
    
    # Convert BGR to RGB
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    output = io.BytesIO()
    
    if output_format in ["jpg", "jpeg"]:
        pil_img.save(output, format="JPEG", quality=95)
        mimetype = "image/jpeg"
        filename = "scanned.jpg"
    elif output_format == "pdf":
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        pil_img.save(output, format="PDF", resolution=300.0)
        mimetype = "application/pdf"
        filename = "scanned.pdf"
    else:
        return jsonify({"error": "Unsupported format"}), 400
    
    output.seek(0)
    print(f"✓ Saved as {filename}: {output.getbuffer().nbytes} bytes")
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)