from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from routes.scan_document import scan_doc_bp
from routes.merge_pdf import merge_pdf_bp
from routes.ocr import ocr_bp
from routes.split import split_pdf_bp
from routes.compress import compress_bp
from routes.ocr_pdf import ocr_pdf_bp
from routes.delete_pages import delete_pages_bp

app = Flask(__name__)
CORS(app)

# ✅ IMPORTANT: Fix HTTPS detection behind Railway proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ✅ IMPORTANT: Prevent 308 redirects due to trailing slash
app.url_map.strict_slashes = False

# Register Blueprints
app.register_blueprint(scan_doc_bp)
app.register_blueprint(merge_pdf_bp)
app.register_blueprint(ocr_bp)
app.register_blueprint(split_pdf_bp)
app.register_blueprint(compress_bp)
app.register_blueprint(ocr_pdf_bp)
app.register_blueprint(delete_pages_bp)

@app.route("/", methods=["GET"])
def health():
    return {
        "status": "Backend running",
        "endpoints": [
            "/scan",
            "/detect-corners",
            "/merge-pdf",
            "/ocr",
            "/ocr-pdf",
            "/tesseract-check",
            "/split-pdf",
            "/compress-pdf"
        ]
    }

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
