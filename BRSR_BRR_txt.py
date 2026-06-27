import os
import re
import csv
import json
import fitz
import unicodedata
import pytesseract
import pdfplumber
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# EDIT THESE 3 PATHS FOR YOUR USE:
INPUT_DIR        = r"D:\Python Annual Report\BRSR-BRR_Manual Combined PDF"
OUTPUT_DIR       = r"D:\Python Annual Report\BRSR-BRR_txt"
LM_STOPWORDS_FILE = r"D:\Python Annual Report\Moti Sir Sent Words and Tone Analysis Code\words\Stop.txt"
LOG_FILE         = os.path.join(OUTPUT_DIR, "conversion_log.csv")

FINANCIAL_SKIP_PATTERNS = [
    r"balance sheet",
    r"auditor.{0,10}report",
    r"cash flow statement",
    r"notes to (the )?financial",
    r"statement of profit",
    r"standalone financial",
    r"consolidated financial",
    r"independent auditor",
    r"board of directors report",
    r"profit and loss",
    r"income statement",
    r"schedule[s]? forming",
    r"significant accounting policies",
]

# Built-in English stopwords (replacing NLTK)
ENGLISH_STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
    'yourself', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its',
    'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'a', 'an', 'and', 'if', 'or',
    'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'without', 'after',
    'upon', 'between', 'into', 'through', 'during', 'before', 'above', 'below', 'between',
    'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'here', 'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
    'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'that',
    'the', 'these', 'those', 'through', 'until', 'unto', 'upon', 'with', 'were', 'has', 'have',
    'having', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'does', 'did', 'doing',
    'will', 'would', 'should', 'could', 'may', 'might', 'must', 'this', 'that', 'these', 'those'
}

HARDCODED_STOPWORDS = {
    "crore", "lakh", "pursuant", "herein", "hereinafter", "viz", "sebi",
    "brsr", "bsr", "fy", "rin", "cin", "din", "llp", "ltd", "limited",
    "india", "indian", "company", "companies", "annual", "report",
    "financial", "year", "quarter", "board", "director", "directors",
    "meeting", "held", "said", "per", "also", "may", "shall", "would",
    "could", "within", "thereof", "therein", "hereby", "whereas",
    "aforesaid", "amongst", "abovementioned", "hereunder", "thereunder",
    "thereto", "therewith", "therefrom", "wherefrom", "whereof", "whereon",
    "whereto", "whereupon", "whereby", "notwithstanding", "aforementioned",
    "accordingly", "andor", "nil", "na", "total", "sub", "grand", "please",
    "etc", "viz", "ibid", "supra", "infra",
}

def load_lm_stopwords(filepath):
    candidates = [
        filepath,
        filepath + ".txt",
        filepath.replace("lm stopwords", "lm_stopwords"),
        filepath.replace("lm stopwords", "lm_stopwords") + ".txt",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    words = {
                        line.strip().lower()
                        for line in f
                        if line.strip() and not line.strip().startswith(";")
                    }
                print(f"Loaded {len(words)} LM stopwords from: {path}")
                return words
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue
    print(f"WARNING: LM stopwords file not found. Tried:")
    for p in candidates:
        print(f"  {p}")
    print("Continuing with hardcoded stopwords only.")
    return set()

# Load stopwords
LM_STOPWORDS = load_lm_stopwords(LM_STOPWORDS_FILE)
ALL_STOPWORDS = ENGLISH_STOPWORDS | HARDCODED_STOPWORDS | LM_STOPWORDS
print(f"Total stopwords loaded: {len(ALL_STOPWORDS)}")

FINANCIAL_SKIP_RE = [re.compile(p, re.IGNORECASE) for p in FINANCIAL_SKIP_PATTERNS]

# Simple word tokenizer (replaces nltk.word_tokenize)
def simple_tokenize(text):
    """Simple tokenizer that splits on whitespace and removes punctuation."""
    # Split on whitespace and clean each token
    tokens = []
    for word in text.split():
        # Remove any remaining punctuation from ends
        word = word.strip("""!"#$%&'()*+, -./:;<=>?@[\]^_`{|}~""")
        if word:  # Only add non-empty tokens
            tokens.append(word)
    return tokens

def is_financial_page(text):
    sample = text[:800].lower()
    for pattern in FINANCIAL_SKIP_RE:
        if pattern.search(sample):
            return True
    return False

def is_numeric_dense(text):
    if not text:
        return False
    digits = sum(c.isdigit() for c in text)
    total = len(text.replace(" ", "").replace("\n", ""))
    if total == 0:
        return False
    return (digits / total) > 0.28

def detect_orientation(page):
    width = page.rect.width
    height = page.rect.height
    return "landscape" if width > height else "portrait"

def preprocess_image_for_ocr(pil_image):
    image = pil_image.convert("L")
    image = image.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    image = image.point(lambda x: 0 if x < 140 else 255)
    return image

def ocr_page(page, dpi=250):
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img = preprocess_image_for_ocr(img)
    config = r"--oem 3 --psm 6 -l eng"
    text = pytesseract.image_to_string(img, config=config)
    return text.strip()

def extract_table_text_with_pdfplumber(pdf_path, page_num):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return ""
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            parts = []
            for table in tables:
                for row in table:
                    cells = [str(c).strip() for c in row if c and str(c).strip()]
                    if cells:
                        parts.append(" ".join(cells))
            return " ".join(parts)
    except Exception:
        return ""

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pages_text = []
    skip_log = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        orientation = detect_orientation(page)

        if orientation == "landscape":
            blocks = page.get_text("blocks", sort=True)
            raw = "\n".join(b[4] for b in blocks if b[4].strip())
        else:
            raw = page.get_text("text")

        if is_financial_page(raw):
            skip_log.append(page_num + 1)
            continue

        if is_numeric_dense(raw):
            table_text = extract_table_text_with_pdfplumber(pdf_path, page_num)
            if table_text:
                pages_text.append(table_text)
            skip_log.append(page_num + 1)
            continue

        if len(raw.strip()) < 80:
            ocr_text = ocr_page(page)
            if len(ocr_text.strip()) > 50:
                pages_text.append(ocr_text)
            else:
                skip_log.append(page_num + 1)
            continue

        pages_text.append(raw)

    doc.close()
    return "\n\n".join(pages_text), skip_log

def fix_split_words(text):
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"([a-z])\n([a-z])", r"\1 \2", text)
    return text

def remove_boilerplate(text):
    patterns = [
        r"page\s+\d+\s+of\s+\d+",
        r"^\s*\d+\s*$",
        r"confidential.*?$",
        r"for\s+internal\s+use\s+only",
        r"annual\s+report\s+20\d{2}[-\u2013]\d{2,4}",
        r"business\s+responsibility\s+(&|and)\s+sustainability\s+report",
        r"^\s*(sl\.?\s*no\.?|sr\.?\s*no\.?|s\.?\s*no\.?)\s*$",
    ]
    for pat in patterns:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE | re.MULTILINE)
    return text

def normalize_unicode(text):
    return unicodedata.normalize("NFKC", text)

def clean_text(text):
    text = normalize_unicode(text)
    text = fix_split_words(text)
    text = remove_boilerplate(text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\S+@\S+\.\S+", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    # Use simple tokenizer instead of nltk
    tokens = simple_tokenize(text)
    tokens = [
        t for t in tokens
        if t.isalpha()
        and len(t) >= 3
        and t not in ALL_STOPWORDS
    ]
    return tokens

def process_single_pdf(pdf_path):
    try:
        raw_text, skipped_pages = extract_text_from_pdf(pdf_path)
        tokens = clean_text(raw_text)
        clean_str = " ".join(tokens)
        return {
            "status": "success",
            "tokens": tokens,
            "clean_text": clean_str,
            "total_tokens": len(tokens),
            "skipped_pages": skipped_pages,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "tokens": [],
            "clean_text": "",
            "total_tokens": 0,
            "skipped_pages": [],
        }

def run_pipeline():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    txt_output_dir = os.path.join(OUTPUT_DIR, "cleaned_texts")
    os.makedirs(txt_output_dir, exist_ok=True)

    pdf_files = list(set(
        list(Path(INPUT_DIR).rglob("*.pdf")) +
        list(Path(INPUT_DIR).rglob("*.PDF"))
    ))

    print(f"Found {len(pdf_files)} PDF files.\n")

    log_rows = []

    for idx, pdf_path in enumerate(pdf_files, 1):
        filename = pdf_path.name
        print(f"[{idx}/{len(pdf_files)}] Processing: {filename}")

        result = process_single_pdf(str(pdf_path))

        out_filename = pdf_path.stem + ".txt"
        out_path = os.path.join(txt_output_dir, out_filename)

        if result["status"] == "success":
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result["clean_text"])
            log_rows.append({
                "filename": filename,
                "status": "success",
                "total_tokens": result["total_tokens"],
                "skipped_pages": json.dumps(result["skipped_pages"]),
                "output_file": out_filename,
                "error": "",
            })
            print(f"   ✓ {result['total_tokens']} tokens extracted")
        else:
            print(f"   ERROR: {result['error']}")
            log_rows.append({
                "filename": filename,
                "status": "error",
                "total_tokens": 0,
                "skipped_pages": "[]",
                "output_file": "",
                "error": result["error"],
            })

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "filename", "status", "total_tokens",
            "skipped_pages", "output_file", "error"
        ])
        writer.writeheader()
        writer.writerows(log_rows)

    success = sum(1 for r in log_rows if r["status"] == "success")
    failed = sum(1 for r in log_rows if r["status"] == "error")

    print(f"\n{'='*50}")
    print(f"Done. {success} succeeded, {failed} failed.")
    print(f"Cleaned texts : {txt_output_dir}")
    print(f"Log file      : {LOG_FILE}")
    print(f"{'='*50}")

if __name__ == "__main__":
    run_pipeline()