# OCR Feature Guide

## What is OCR?
Optical Character Recognition (OCR) extracts text from images of documents, making it searchable, editable, and copyable.

## How It Works

### Image Preprocessing Pipeline
```
Original Image
    ↓
Grayscale Conversion
    ↓
Adaptive Thresholding (binarization)
    ↓
Noise Removal (denoising)
    ↓
Tesseract OCR Engine
    ↓
Extracted Text
```

## Using the OCR Feature

### Step-by-Step Guide

1. **Scan Your Document**
   - Capture or upload an image
   - Adjust crop box if needed
   - Click "Process & Save"

2. **Extract Text**
   - Click "📝 Extract Text (OCR)" button
   - Wait for processing (usually 2-5 seconds)
   - Modal window opens with extracted text

3. **Use Extracted Text**
   - **Copy**: Click "📋 Copy Text" to copy to clipboard
   - **Download**: Click "📥 Download TXT" to save as text file
   - **Close**: Click "×" or click outside modal to close

## Best Practices for Better OCR Results

### 📸 Image Quality
- **Resolution**: Use at least 300 DPI for best results
- **Focus**: Ensure text is sharp and in focus
- **Lighting**: Use even, bright lighting without glare
- **Contrast**: High contrast between text and background

### 📄 Document Preparation
- **Flat Surface**: Avoid curved or wrinkled documents
- **Alignment**: Keep text horizontal (not rotated)
- **Clean Background**: Use plain, contrasting background
- **Full View**: Capture entire text area without cropping important parts

### ⚙️ System Tips
- **Language**: Currently supports English (can be extended)
- **Font**: Works best with standard fonts (Arial, Times, etc.)
- **Text Size**: Minimum 10-12pt font recommended
- **Handwriting**: Works poorly with handwriting (use printed text)

## OCR Configuration Options

### Page Segmentation Modes (PSM)
In `app.py`, you can change the OCR mode:

```python
# Current setting
custom_config = r'--oem 3 --psm 6'
```

**Available PSM Modes:**
- `--psm 0`: Orientation and script detection only
- `--psm 1`: Automatic page segmentation with OSD
- `--psm 3`: Fully automatic page segmentation (default)
- `--psm 4`: Assume single column of text
- `--psm 5`: Assume single uniform block of vertical text
- `--psm 6`: Assume single uniform block of text *(current)*
- `--psm 7`: Treat image as single text line
- `--psm 8`: Treat image as single word
- `--psm 9`: Treat image as single word in circle
- `--psm 10`: Treat image as single character
- `--psm 11`: Sparse text - find as much text as possible
- `--psm 12`: Sparse text with OSD
- `--psm 13`: Raw line (bypass layout analysis)

### OCR Engine Modes (OEM)
```python
# --oem 0: Legacy engine only
# --oem 1: Neural nets LSTM engine only
# --oem 2: Legacy + LSTM engines
# --oem 3: Default, based on what's available (current)
```

## Supported Languages

### Default: English
```python
text = pytesseract.image_to_string(pil_img, lang='eng')
```

### Multiple Languages
```python
# English + French
text = pytesseract.image_to_string(pil_img, lang='eng+fra')

# English + Spanish + German
text = pytesseract.image_to_string(pil_img, lang='eng+spa+deu')
```

### Installing Language Packs

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr-fra  # French
sudo apt install tesseract-ocr-deu  # German
sudo apt install tesseract-ocr-spa  # Spanish
sudo apt install tesseract-ocr-chi-sim  # Chinese Simplified
sudo apt install tesseract-ocr-jpn  # Japanese
sudo apt install tesseract-ocr-kor  # Korean
sudo apt install tesseract-ocr-ara  # Arabic
sudo apt install tesseract-ocr-hin  # Hindi
```

**macOS:**
```bash
brew install tesseract-lang
```

**Windows:**
- Download language data from: https://github.com/tesseract-ocr/tessdata
- Place `.traineddata` files in: `C:\Program Files\Tesseract-OCR\tessdata\`

### List Available Languages
```bash
tesseract --list-langs
```

## Advanced OCR Customization

### 1. Improve Accuracy for Specific Use Cases

**For Invoices/Receipts:**
```python
# In app.py, modify the preprocessing
# Add more aggressive thresholding
thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

# Use PSM 6 for structured layout
custom_config = r'--oem 3 --psm 6'
```

**For Business Cards:**
```python
# Use sparse text mode
custom_config = r'--oem 3 --psm 11'
```

**For Single Line (License Plates, etc.):**
```python
custom_config = r'--oem 3 --psm 7'
```

### 2. Whitelist/Blacklist Characters

**Only Numbers (e.g., for phone numbers):**
```python
custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
```

**Exclude Similar Characters:**
```python
# Exclude lowercase 'l' and uppercase 'I' to reduce confusion
custom_config = r'--oem 3 --psm 6 -c tessedit_char_blacklist=lI'
```

### 3. Output Formats

**Get Confidence Scores:**
```python
data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
text = data['text']
conf = data['conf']  # Confidence scores
```

**Get Bounding Boxes:**
```python
boxes = pytesseract.image_to_boxes(pil_img)
# Returns: character, x, y, width, height
```

**Get Detailed Data:**
```python
data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
# Returns: level, page_num, block_num, par_num, line_num, word_num, 
#          left, top, width, height, conf, text
```

## Common OCR Issues & Solutions

### Issue: "No text detected"
**Solutions:**
- Increase image resolution
- Improve lighting/contrast
- Use image enhancement features
- Check if text is too small
- Verify document is not upside down

### Issue: Poor accuracy (gibberish output)
**Solutions:**
- Use higher quality images
- Preprocess image more aggressively
- Try different PSM modes
- Ensure correct language is selected
- Clean up background noise

### Issue: Numbers confused with letters (0 vs O, 1 vs I)
**Solutions:**
```python
# Use character whitelisting
custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
```

### Issue: Slow processing
**Solutions:**
- Reduce image size before OCR
- Use `--psm 6` instead of `--psm 3` (faster)
- Process smaller regions of interest
- Optimize preprocessing steps

### Issue: Special characters not recognized
**Solutions:**
- Install appropriate language pack
- Use UTF-8 encoding
- Check Tesseract version supports the characters

## Performance Tips

### 1. Optimize Image Size
```python
# Resize large images before OCR
max_dimension = 2400
if max(img.shape[:2]) > max_dimension:
    scale = max_dimension / max(img.shape[:2])
    img = cv2.resize(img, None, fx=scale, fy=scale)
```

### 2. Region of Interest (ROI)
```python
# Only OCR specific regions
roi = img[y1:y2, x1:x2]
text = pytesseract.image_to_string(roi)
```

### 3. Parallel Processing
```python
# For multiple documents
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor() as executor:
    results = executor.map(extract_text, images)
```

## API Response Format

### Success Response
```json
{
  "success": true,
  "text": "Extracted text content here...",
  "length": 1234
}
```

### Error Response
```json
{
  "error": "Error message here"
}
```

## Testing OCR

### Sample Test Documents
Test with various document types:
1. **Printed Text**: Books, articles, printouts
2. **Typed Documents**: Word documents, PDFs
3. **Receipts**: Thermal printer receipts
4. **Business Cards**: Various fonts and layouts
5. **Forms**: Structured data entry
6. **Screenshots**: Digital text capture

### Quality Metrics
- **Accuracy**: Compare to manual transcription
- **Speed**: Time to process (aim for <5 seconds)
- **Confidence**: Tesseract confidence scores (>80% is good)

## Future Enhancements

Potential improvements to consider:
1. **Layout Detection**: Preserve formatting (headers, paragraphs)
2. **Table Extraction**: Detect and extract tabular data
3. **Multi-language Auto-detect**: Automatically detect document language
4. **Handwriting Recognition**: Support for cursive/handwritten text
5. **Math Equations**: OCR for mathematical formulas
6. **Barcode/QR Code**: Detect and decode barcodes
7. **Batch Processing**: OCR multiple documents at once

## Resources

- **Tesseract Documentation**: https://tesseract-ocr.github.io/
- **Training Custom Models**: https://github.com/tesseract-ocr/tesseract/wiki/TrainingTesseract
- **Language Data**: https://github.com/tesseract-ocr/tessdata
- **Python Tesseract**: https://pypi.org/project/pytesseract/