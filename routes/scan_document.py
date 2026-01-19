from flask import Blueprint, request, send_file, jsonify
import cv2
import numpy as np
from PIL import Image
import io

scan_doc_bp = Blueprint("scan_doc", __name__)

def order_points(pts):
    """Order points in consistent order: top-left, top-right, bottom-right, bottom-left"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect

def four_point_transform(image, pts):
    """Apply perspective transform to get bird's eye view"""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    # Compute width of new image
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    # Compute height of new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # Construct destination points
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    
    # Calculate perspective transform matrix and warp
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warped

def detect_document_contour(img):
    """Detect document edges using advanced edge detection"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to reduce noise while keeping edges sharp
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Edge detection
    edges = cv2.Canny(blur, 30, 150)
    
    # Morphological operations to close gaps
    dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=2)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    
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
                return order_points(approx.reshape(4, 2))
    
    return None

def enhance_document(img):
    """Enhanced document processing with better quality preservation"""
    # Convert to LAB color space for better luminance processing
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE with gentler parameters
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    
    # Merge back
    img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    
    # Gentle sharpening using unsharp mask
    gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
    img = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
    
    # Denoise while preserving edges
    img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    
    return img

def adaptive_document_enhancement(img):
    """Apply adaptive enhancement based on image characteristics"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Check if image is mostly text (high edge density)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / edges.size
    
    if edge_density > 0.05:  # Text-heavy document
        # Increase contrast more aggressively
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        
        # Sharpen text
        kernel = np.array([[-0.5, -0.5, -0.5],
                          [-0.5,  5.0, -0.5],
                          [-0.5, -0.5, -0.5]])
        img = cv2.filter2D(img, -1, kernel)
    else:
        # Use gentler enhancement
        img = enhance_document(img)
    
    return img

@scan_doc_bp.route("/detect-corners", methods=["POST"])
def detect_corners():
    """Detect document corners for cropping"""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    file = request.files["image"]
    img_bytes = file.read()
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
    
    h, w = img.shape[:2]
    
    # Resize for faster processing
    max_dim = 1500
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img_resized = cv2.resize(img, (int(w * scale), int(h * scale)))
        scale_back = max(h, w) / max_dim
    else:
        img_resized = img
        scale_back = 1.0
    
    doc_contour = detect_document_contour(img_resized)
    
    if doc_contour is not None:
        corners = (doc_contour * scale_back).tolist()
        return jsonify({
            "detected": True,
            "corners": corners,
            "width": w,
            "height": h
        })
    else:
        # Return default corners with small margin
        margin_w = int(w * 0.02)
        margin_h = int(h * 0.02)
        return jsonify({
            "detected": False,
            "corners": [
                [margin_w, margin_h],
                [w - margin_w, margin_h],
                [w - margin_w, h - margin_h],
                [margin_w, h - margin_h]
            ],
            "width": w,
            "height": h
        })

@scan_doc_bp.route("/scan", methods=["POST"])
def scan_and_convert():
    """Process scanned document with high quality output"""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    file = request.files["image"]
    output_format = request.form.get("format", "jpg").lower()
    enhance = request.form.get("enhance", "true").lower() == "true"
    
    # Decode image with highest quality
    np_img = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
    
    # Apply enhancement if requested
    if enhance:
        img = adaptive_document_enhancement(img)
    
    # Convert to PIL for high-quality output
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    output = io.BytesIO()
    
    if output_format in ["jpg", "jpeg"]:
        # Maximum quality JPEG
        pil_img.save(output, format="JPEG", quality=98, optimize=True, subsampling=0)
        mimetype = "image/jpeg"
        filename = "scanned.jpg"
    elif output_format == "png":
        # Lossless PNG
        pil_img.save(output, format="PNG", optimize=True)
        mimetype = "image/png"
        filename = "scanned.png"
    elif output_format == "pdf":
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        # High resolution PDF
        pil_img.save(output, format="PDF", resolution=300.0, quality=95)
        mimetype = "application/pdf"
        filename = "scanned.pdf"
    else:
        return jsonify({"error": "Unsupported format"}), 400
    
    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)