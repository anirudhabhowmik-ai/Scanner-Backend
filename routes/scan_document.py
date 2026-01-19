from flask import Blueprint, request, send_file, jsonify
import cv2
import numpy as np
from PIL import Image
import io

scan_doc_bp = Blueprint("scan_doc", __name__)

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def detect_document_contour(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(blur, 30, 150)
    dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3,3)), iterations=2)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5,5)))
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:25]
    min_area = (w*h)*0.05
    max_area = (w*h)*0.98
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        peri = cv2.arcLength(c, True)
        for eps in [0.015,0.02,0.03,0.04,0.05]:
            approx = cv2.approxPolyDP(c, eps*peri, True)
            if len(approx)==4:
                return order_points(approx.reshape(4,2))
    return None

def enhance_image(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l,a,b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    l = clahe.apply(l)
    img = cv2.cvtColor(cv2.merge((l,a,b)), cv2.COLOR_LAB2BGR)
    kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    img = cv2.filter2D(img, -1, kernel)
    return img

@scan_doc_bp.route("/detect-corners", methods=["POST"])
def detect_corners():
    if "image" not in request.files:
        return jsonify({"error":"No image uploaded"}),400
    file = request.files["image"]
    img_bytes = file.read()
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None: return jsonify({"error":"Invalid image"}),400
    h,w = img.shape[:2]
    max_dim=1500
    if max(h,w)>max_dim:
        scale = max_dim/max(h,w)
        img_resized = cv2.resize(img,(int(w*scale),int(h*scale)))
        scale_back = max(h,w)/max_dim
    else:
        img_resized = img
        scale_back=1.0
    doc_contour = detect_document_contour(img_resized)
    if doc_contour is not None:
        corners = (doc_contour*scale_back).tolist()
        return jsonify({"detected":True,"corners":corners,"width":w,"height":h})
    else:
        margin_w=int(w*0.02)
        margin_h=int(h*0.02)
        return jsonify({
            "detected":False,
            "corners":[[margin_w,margin_h],[w-margin_w,margin_h],[w-margin_w,h-margin_h],[margin_w,h-margin_h]],
            "width":w,"height":h
        })

@scan_doc_bp.route("/scan", methods=["POST"])
def scan_and_convert():
    if "image" not in request.files:
        return jsonify({"error":"No image uploaded"}),400
    file = request.files["image"]
    output_format = request.form.get("format","jpg").lower()
    enhance = request.form.get("enhance","true").lower()=="true"
    np_img = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None: return jsonify({"error":"Invalid image"}),400
    if enhance: img = enhance_image(img)
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    output = io.BytesIO()
    if output_format in ["jpg","jpeg"]:
        pil_img.save(output,format="JPEG",quality=95)
        mimetype="image/jpeg"; filename="scanned.jpg"
    elif output_format=="pdf":
        if pil_img.mode!="RGB": pil_img=pil_img.convert("RGB")
        pil_img.save(output,format="PDF",resolution=300.0)
        mimetype="application/pdf"; filename="scanned.pdf"
    else:
        return jsonify({"error":"Unsupported format"}),400
    output.seek(0)
    return send_file(output,mimetype=mimetype,as_attachment=True,download_name=filename)
