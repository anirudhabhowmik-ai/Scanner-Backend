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

        # Convert PNG/WEBP with alpha to RGB
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize large images to reduce file size
        MAX_WIDTH = 1200
        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            img = img.resize(
                (int(img.width * ratio), int(img.height * ratio)),
                Image.LANCZOS
            )

        # Remove metadata (EXIF) to save extra bytes
        img.info.pop("exif", None)

        # Strong compression
        img.save(
            output_path,
            format="JPEG",
            quality=30,        # Sweet spot: 35–45
            optimize=True,
            progressive=True
        )

        @after_this_request
        def cleanup(response):
            for p in [input_path, output_path]:
                if os.path.exists(p):
                    os.remove(p)
            return response

        return send_file(output_path, as_attachment=True, download_name=f"compressed_{file.filename}")

    except Exception as e:
        return jsonify({"error": str(e)}), 500
