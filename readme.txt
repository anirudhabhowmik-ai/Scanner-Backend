Backend Deployment
https://railway.com/project

Frontend Deployment
https://vercel.com

Create Virtual Environment
py -3.11 -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py

These command need to run each time
venv\Scripts\activate
python app.py






For Railway/Production Deployment:

Create aptfile (for Poppler system dependency):

poppler-utils
tesseract-ocr
tesseract-ocr-eng

System dependencies installation - Add to your deployment configuration or create a Procfile:

web: pip install -r requirements.txt && python app.py






Windows:

Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
Install Poppler from: https://github.com/oschwartz10612/poppler-windows/releases
Update the path in your Python code
Run: pip install -r requirements.txt