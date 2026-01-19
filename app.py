from flask import Flask
from flask_cors import CORS
from routes.scan_document import scan_doc_bp
from routes.merge_pdf import merge_pdf_bp
from routes.ocr import ocr_bp

app = Flask(__name__)
CORS(app)

# Register Blueprints
app.register_blueprint(scan_doc_bp)
app.register_blueprint(merge_pdf_bp)
app.register_blueprint(ocr_bp)

@app.route("/", methods=["GET"])
def health():
    return {"status":"Backend running","endpoints":["/scan","/detect-corners","/merge-pdf","/ocr","/tesseract-check"]}

if __name__=="__main__":
    import os
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=True)
