# PDF to TXT Converter

This repository includes `pdfs_to_text.py`, a script to convert all PDFs inside a folder (recursively) into `.txt` files.

Requirements
- Python 3.8+
- Install Python packages:

```bash
pip install -r requirements.txt
```

Notes on OCR
- The script extracts text using `PyMuPDF` (fast, accurate for text PDFs).
- If pages contain images/scans, enable OCR with `--ocr`. That requires Tesseract OCR to be installed on your system and `pytesseract` configured.

Tesseract install (Windows)
- Download and install from: https://github.com/tesseract-ocr/tesseract
- Add Tesseract install directory (e.g. `C:\Program Files\Tesseract-OCR`) to your PATH.

Usage

```bash
python pdfs_to_text.py --input "TOP 83 Companies" --output ./txt_outputs

# with OCR fallback (slower):
python pdfs_to_text.py --input "TOP 83 Companies" --output ./txt_outputs --ocr
```

Output
- The script preserves relative subfolders under the output directory. Each PDF will produce a `.txt` file with the same basename.
