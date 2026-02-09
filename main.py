from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import easyocr
import pytesseract
import cv2
import os
import re

# ------------------ Flask App ------------------
app = Flask(__name__)
CORS(app)
Swagger(app)  # Initialize Flasgger

# ------------------ OCR Engines ------------------
# EasyOCR supports English + Bangla
easy_reader = easyocr.Reader(['en', 'bn'])

# ------------------ OCR FUNCTIONS ------------------
def ocr_with_tesseract(image_path):
    """OCR using Tesseract for English + Bangla"""
    image = cv2.imread(image_path)
    custom_config = r'--oem 3 --psm 6 -l eng+ben'
    return pytesseract.image_to_string(image, config=custom_config)

# ------------------ TEXT CLEANING ------------------
def clean_text_regex(text):
    """Keep Bangla + English letters, numbers, punctuation, spaces"""
    text = re.sub(r"[^\u0980-\u09FFa-zA-Z0-9\s\.\,\-\(\)\/@:+<>]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ------------------ HOME ENDPOINT ------------------
@app.route('/', methods=['GET'])
def home():
    """
    Home endpoint
    ---
    responses:
      200:
        description: API is running
    """
    return jsonify({"message": "OCR API running (EasyOCR + Tesseract, English + Bangla supported)"})

# ------------------ PROCESS IMAGE ENDPOINT ------------------
@app.route('/process', methods=['POST'])
def process_document():
    """
    Process an image file with EasyOCR and Tesseract
    ---
    consumes:
      - multipart/form-data
    parameters:
      - name: image
        in: formData
        type: file
        required: true
        description: Image file to perform OCR on
    responses:
      200:
        description: OCR results (raw and cleaned)
        schema:
          type: object
    """
    image_file = request.files.get('image')
    if not image_file:
        return jsonify({"error": "Image is required"}), 400

    os.makedirs("uploads", exist_ok=True)
    image_path = os.path.join("uploads", image_file.filename)
    image_file.save(image_path)

    # ---- OCR ----
    easy_raw = "\n".join([t[1] for t in easy_reader.readtext(image_path)])
    tess_raw = ocr_with_tesseract(image_path)

    # ---- CLEAN ----
    easy_clean = clean_text_regex(easy_raw)
    tess_clean = clean_text_regex(tess_raw)
    combined_text = clean_text_regex(f"{easy_clean} {tess_clean}")

    # Remove uploaded file
    os.remove(image_path)

    return jsonify({
        "ocr_results": {
            "easyocr": {"raw": easy_raw, "cleaned": easy_clean},
            "tesseract": {"raw": tess_raw, "cleaned": tess_clean},
        },
        "combined_text": combined_text
    })

# ------------------ RUN ------------------
if __name__ == '__main__':
    app.run(debug=True)
