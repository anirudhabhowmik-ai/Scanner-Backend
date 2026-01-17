from flask import Flask, request, send_file
from flask_cors import CORS
import cv2
import numpy as np
import tempfile

app = Flask(__name__)
CORS(app)  # 👈 VERY IMPORTANT for frontend connection

@app.route('/scan', methods=['POST'])
def scan():
    file = request.files['image']
    img = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edges = cv2.Canny(blur, 75, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    doc = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            doc = approx
            break

    mask = np.zeros(gray.shape, dtype="uint8")
    if doc is not None:
        cv2.drawContours(mask, [doc], -1, 255, -1)

    result = cv2.bitwise_and(img, img, mask=mask)
    enhanced = cv2.detailEnhance(result, sigma_s=10, sigma_r=0.15)

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    cv2.imwrite(temp.name, enhanced)

    return send_file(temp.name, mimetype='image/jpeg')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
