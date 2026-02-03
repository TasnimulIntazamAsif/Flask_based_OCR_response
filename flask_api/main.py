from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import easyocr
import pytesseract
import cv2
import os
import re

# ------------------ Paddle safety ------------------
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR

# ------------------ Flask App ------------------
app = Flask(__name__)
CORS(app)
Swagger(app)

# ------------------ OCR Engines ------------------
easy_reader = easyocr.Reader(['en'])
paddle_ocr = PaddleOCR(
    use_textline_orientation=True,
    lang='en'
)

# ------------------ OCR FUNCTIONS ------------------
def ocr_with_tesseract(image_path):
    try:
        image = cv2.imread(image_path)
        return pytesseract.image_to_string(image)
    except:
        return ""

def ocr_with_paddle(image_path):
    try:
        result = paddle_ocr.ocr(image_path)
        texts = [line[1][0] for block in result for line in block]
        return "\n".join(texts)
    except:
        return ""

# ------------------ REGEX CLEAN & EXTRACTORS ------------------
def clean_text_regex(text):
    if not text:
        return ""
    text = re.sub(r"[^A-Za-z0-9\s\.\,\-\(\)\/@:+]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_emails(text):
    return list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))

def extract_phones(text):
    pattern = r"(?:\+880|\+88|01|\+?\d{1,3})[\s\-]?\d{8,11}"
    return list(set(re.findall(pattern, text)))

def extract_addresses(text):
    address_keywords = [
        "road", "rd", "street", "st", "avenue", "ave",
        "house", "floor", "level", "block", "sector",
        "dhaka", "bangladesh", "city", "tower", "building"
    ]
    lines = re.split(r"[,.]", text)
    addresses = []
    for line in lines:
        for key in address_keywords:
            if key.lower() in line.lower() and len(line) > 10:
                addresses.append(line.strip())
                break
    return list(set(addresses))

def extract_numbers(text):
    return list(set(re.findall(r"\d+", text)))

# ------------------ VISITING CARD OCR / TEXT API ------------------
@app.route('/process', methods=['POST'])
def process_visiting_card():
    """
    Accepts either an image or raw text from a visiting card and extracts info.
    ---
    parameters:
      - name: image
        in: formData
        type: file
        required: false
      - name: text
        in: formData
        type: string
        required: false
    responses:
      200:
        description: Extracted data from visiting card
    """
    text_input = request.form.get('text', '').strip()
    image_file = request.files.get('image', None)

    if not text_input and not image_file:
        return jsonify({'error': 'No input provided. Submit an image or text.'}), 400

    ocr_results = {}

    # OCR from image if provided
    if image_file:
        if not image_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            return jsonify({'error': 'Invalid file type'}), 400

        os.makedirs('uploads', exist_ok=True)
        image_path = os.path.join('uploads', image_file.filename)
        image_file.save(image_path)

        try:
            easy_raw = "\n".join([t[1] for t in easy_reader.readtext(image_path)])
            tesseract_raw = ocr_with_tesseract(image_path)
            paddle_raw = ocr_with_paddle(image_path)

            easy_clean = clean_text_regex(easy_raw)
            tesseract_clean = clean_text_regex(tesseract_raw)
            paddle_clean = clean_text_regex(paddle_raw)

            ocr_results = {
                "easyocr": {"raw": easy_raw, "cleaned": easy_clean},
                "tesseract": {"raw": tesseract_raw, "cleaned": tesseract_clean},
                "paddleocr": {"raw": paddle_raw, "cleaned": paddle_clean},
            }

            combined_text = f"{easy_clean} {tesseract_clean} {paddle_clean}"
            os.remove(image_path)

        except Exception as e:
            return jsonify({'error': f'OCR failed: {str(e)}'}), 500
    else:
        combined_text = ""

    # If raw text is provided, append it
    if text_input:
        cleaned_text_input = clean_text_regex(text_input)
        combined_text = f"{combined_text} {cleaned_text_input}".strip()

    combined_text = clean_text_regex(combined_text)

    response = {
        "ocr_results": ocr_results,
        "combined_cleaned_text": combined_text,
        "extracted": {
            "emails": extract_emails(combined_text),
            "phones": extract_phones(combined_text),
            "addresses": extract_addresses(combined_text),
            "numbers": extract_numbers(combined_text)
        }
    }

    return jsonify(response)

# ------------------ Health Check ------------------
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Visiting Card API running. Use /process to extract info from image or text."
    })

# ------------------ Run ------------------
if __name__ == '__main__':
    app.run(debug=True)
