# Document Scanner Setup Instructions

## Fixed Issues ✅

1. **Fixed `cropper.ready is not a function` error** - Changed from method call to event listener in Cropper initialization
2. **Implemented OCR functionality** - Added Tesseract OCR integration with text extraction, copy, and download features

## System Requirements

### Installing Tesseract OCR

Tesseract OCR must be installed on your system before running the application.

#### **Windows**
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (tesseract-ocr-w64-setup-5.x.x.exe)
3. During installation, note the installation path (default: `C:\Program Files\Tesseract-OCR`)
4. Add to system PATH or update `app.py`:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

#### **macOS**
```bash
brew install tesseract
```

#### **Linux (Ubuntu/Debian)**
```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install libtesseract-dev
```

#### **Linux (CentOS/RHEL)**
```bash
sudo yum install tesseract
```

### Verify Tesseract Installation
```bash
tesseract --version
```
You should see output like: `tesseract 5.x.x`

## Installation Steps

### 1. Clone/Download Project
```bash
cd your-project-folder
```

### 2. Create Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Tesseract Path (Windows Only)
If Tesseract is not in your PATH, uncomment and update this line in `app.py`:
```python
# Line ~10 in app.py
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### 5. Run the Backend
```bash
python app.py
```

You should see:
```
==================================================
PDFMaster Backend v2.0 - Enhanced Edge Detection
Running on http://127.0.0.1:5000
==================================================
```

### 6. Open the Frontend
Open `index.html` in your web browser, or serve it locally:
```bash
# Using Python's built-in server
python -m http.server 8000

# Then open http://localhost:8000
```

## Features

### ✅ Fixed Issues
- **Cropper.js Error Fixed**: Changed from `.ready()` method to event listener
- **Auto Edge Detection**: Enhanced algorithm with multiple edge detection techniques
- **Better Crop Box**: Larger handles (12-18px), easier to grab and manipulate

### 🆕 New OCR Features
1. **Text Extraction**: Extract text from scanned documents
2. **Copy to Clipboard**: One-click copy of extracted text
3. **Download as TXT**: Save extracted text as a text file
4. **Preprocessed OCR**: Image preprocessing for better accuracy:
   - Grayscale conversion
   - Adaptive thresholding
   - Denoising
   - Optimized Tesseract config

### 📷 Scanning Features
- **Camera Support**: Use device camera to capture documents
- **Upload Images**: Upload existing photos
- **Auto Edge Detection**: Automatically detects document boundaries
- **Manual Adjustment**: Drag corners to fine-tune crop area
- **Image Enhancement**: Auto-enhance with CLAHE and sharpening
- **Multiple Formats**: Export as JPG or PDF
- **Share Feature**: Native share on mobile devices

## Usage Guide

### 1. Capture Document
- Click "Open Camera" to use your device camera
- OR click "Upload Image" to select from files

### 2. Auto-Detection
- The system automatically detects document edges
- Blue crop box appears around detected document

### 3. Adjust Crop (if needed)
- Drag the **corners** of the blue box to adjust
- Pinch to zoom, drag to pan
- Larger corner handles make it easier to grab

### 4. Process Document
- Click "Process & Save"
- System enhances and saves the document

### 5. Extract Text (OCR)
- Click "Extract Text (OCR)" button
- Wait for text extraction
- Copy text or download as TXT file

### 6. Download/Share
- Download as JPG or PDF
- Share using native device share

## Troubleshooting

### Cropper.js Error
✅ **Fixed** - If you still see "cropper.ready is not a function":
- Make sure you're using the updated `index.html`
- Clear browser cache (Ctrl+F5)

### OCR Not Working

**Error: "Tesseract not found"**
- Verify Tesseract installation: `tesseract --version`
- Windows: Check path in `app.py` line ~10
- Linux/Mac: Install via package manager

**Error: "No text detected"**
- Image quality may be too low
- Try better lighting when capturing
- Ensure text is clear and readable

**Poor OCR Accuracy**
- Use higher resolution images
- Ensure good contrast between text and background
- Avoid skewed or rotated text
- Try enhancing the image first

### Backend Connection Error
- Make sure backend is running: `python app.py`
- Check console for errors
- Verify port 5000 is not blocked
- Update `BACKEND_URL` in `index.html` if using different host

### Edge Detection Not Working
- Try better lighting
- Place document on contrasting background
- Ensure document fills most of frame
- Manually adjust crop box if auto-detection fails

### Mobile Issues
- Grant camera permissions when prompted
- Use "environment" (back) camera for better quality
- Larger touch targets (18px) make corners easier to grab

## Advanced Configuration

### Improve OCR Accuracy
Edit `app.py`, line ~220:
```python
# Current config
custom_config = r'--oem 3 --psm 6'

# Try different PSM modes:
# --psm 6: Uniform block of text (default)
# --psm 3: Fully automatic page segmentation
# --psm 4: Single column of text
# --psm 11: Sparse text
```

### Add More Languages
```bash
# Install language packs
# Ubuntu/Debian
sudo apt install tesseract-ocr-fra  # French
sudo apt install tesseract-ocr-deu  # German
sudo apt install tesseract-ocr-spa  # Spanish

# Update app.py
text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng+fra')
```

### Adjust Edge Detection Sensitivity
Edit `app.py`, line ~50:
```python
# Make detection more sensitive (lower threshold)
min_area = (w * h) * 0.03  # Changed from 0.05

# Make detection less sensitive (higher threshold)
min_area = (w * h) * 0.10  # Changed from 0.05
```

## Production Deployment

### Update Backend URL
In `index.html`, line ~383:
```javascript
const BACKEND_URL = "https://your-production-url.com";
```

### Deploy Backend
- Use Railway, Heroku, or any Python hosting
- Set environment variable: `PORT=5000`
- Ensure Tesseract is installed in production environment

### Deploy Frontend
- Host on Netlify, Vercel, or any static hosting
- Update `BACKEND_URL` to production backend

## Support

If you encounter issues:
1. Check browser console (F12) for errors
2. Check backend terminal for error logs
3. Verify all dependencies are installed
4. Ensure Tesseract is properly installed and accessible

## License
MIT License - Free to use and modify