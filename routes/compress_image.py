from flask import Blueprint, request, send_file, jsonify, after_this_request
from PIL import Image
import tempfile, os

compress_image_bp = Blueprint("compress_image", __name__, url_prefix="/compress-image")

@compress_image_bp.route("/", methods=["POST"])
def compress_image():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    input_path = tempfile.NamedTemporaryFile(delete=False).name
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name

    try:
        file.save(input_path)

        img = Image.open(input_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail((1920,1920))

        img.save(output_path, "JPEG", quality=60, optimize=True, progressive=True)

        @after_this_request
        def cleanup(response):
            for p in [input_path, output_path]:
                if os.path.exists(p): os.remove(p)
            return response

        return send_file(output_path, as_attachment=True, download_name=f"compressed_{file.filename}")

    except Exception as e:
        return jsonify({"error": str(e)}), 500
