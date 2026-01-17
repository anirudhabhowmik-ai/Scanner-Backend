from flask import Flask, request, send_file
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains

@app.route("/scan", methods=["POST"])
def scan():
    if "image" not in request.files:
        return "No image uploaded", 400

    file = request.files["image"]
    img_bytes = file.read()

    # Read image with OpenCV
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    # Simple enhancement example: convert to grayscale + adaptive threshold
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)

    # Convert back to image bytes
    pil_img = Image.fromarray(enhanced)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG")
    buf.seek(0)

    return send_file(buf, mimetype="image/jpeg")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
