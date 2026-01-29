from flask import Blueprint, request, send_file
from PIL import Image
from io import BytesIO

image_to_pdf_bp = Blueprint('image_to_pdf', __name__)

@image_to_pdf_bp.route("/image-to-pdf", methods=["POST"])
def image_to_pdf():
    if 'images' not in request.files:
        return {"error": "No images uploaded"}, 400

    images = request.files.getlist("images")
    if not images:
        return {"error": "No images uploaded"}, 400

    pil_images = []
    for img_file in images:
        img = Image.open(img_file).convert("RGB")
        pil_images.append(img)

    pdf_bytes = BytesIO()
    if pil_images:
        first_image, *rest_images = pil_images
        first_image.save(pdf_bytes, format="PDF", save_all=True, append_images=rest_images)

    pdf_bytes.seek(0)
    return send_file(pdf_bytes, mimetype="application/pdf", as_attachment=True, download_name="converted.pdf")
