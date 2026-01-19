from flask import Blueprint, request, jsonify
from PIL import Image
import cv2
import numpy as np
import pytesseract
import platform

ocr_bp = Blueprint("ocr", __name__)

# Tesseract path for Windows
if platform.system()=="Windows":
    pytesseract.pytesseract.tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"

@ocr_bp.route("/ocr", methods=["POST"])
def ocr_extract():
    if "image" not in request.files:
        return jsonify({"error":"No image uploaded"}),400
    np_img = np.frombuffer(request.files["image"].read(), np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None: return jsonify({"error":"Invalid image"}),400
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,11,2)
    denoised = cv2.fastNlMeansDenoising(thresh,None,10,7,21)
    pil_img = Image.fromarray(denoised)
    text = pytesseract.image_to_string(pil_img, config=r"--oem 3 --psm 6", lang="eng").strip()
    return jsonify({"success":True,"text":text,"length":len(text)})

@ocr_bp.route("/tesseract-check")
def tesseract_check():
    try:
        version=pytesseract.get_tesseract_version()
        return {"installed":True,"version":str(version)}
    except Exception as e:
        return {"installed":False,"error":str(e)}
