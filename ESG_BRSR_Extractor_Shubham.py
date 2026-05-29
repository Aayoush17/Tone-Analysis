"""
ESG / BRSR Text Extractor — Research Grade v2.1
=================================================
Research: "Does Mandatory ESG Assurance Minimize Greenwashing?"
PIPELINE SUMMARY:
1. Extract text page-by-page (PyMuPDF + OCR fallback for scanned PDFs)
2. Full-document scan for BRSR / ESG / BRR / GRI / TCFD presence
3. Page classification: keep ESG/BRSR/MD&A/CSR; drop financials/AGM/admin
- Section-status RESETS when a relevant header follows an irrelevant one
- Directors' Report kept ONLY if ESG content found inside it
4. Remove boilerplate, numeric table rows, stray characters
5. Lowercase → strip punctuation → NLTK tokenize → remove stopwords
(English stopwords + 60+ domain-specific annual-report filler words)
6. ONE clean .txt per PDF — space-joined token string, ready for:
TF-IDF, LDA topic modelling, word2vec, VADER sentiment, regression
7. ESG keyword density, greenwashing signal count, assurance signal count
logged per file (scored on pre-tokenized text for accuracy)
8. brsr_absent_manifest.csv — lists every file without BRSR for manual follow-up
OUTPUT PER PDF:
<filename>.txt → single clean tokenized corpus file
OUTPUT LOGS:
conversion_log.csv → full metadata for every PDF
brsr_absent_manifest.csv → files needing separate BRSR source
Requirements:
pip install pymupdf pytesseract Pillow tqdm nltk
First run (download NLTK data):
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt');
nltk.download('punkt_tab')"
Usage:
1. Set INPUT_FOLDER and TEXT_OUT_DIR in the CONFIGURATION block below
2. python esg_brsr_extractor.py
"""
import os
import re
import csv
import logging
import unicodedata
from pathlib import Path
from collections import Counter

# ── Poppler PATH (Windows) ────────────────────────────────────────────────────
os.environ["PATH"] += r";C:\poppler\poppler-26.02.0\Library\bin"

# ── OCR setup ─────────────────────────────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    STOPWORDS = set(stopwords.words("english"))
    NLTK_AVAILABLE = True
except Exception:
    STOPWORDS = set()
    NLTK_AVAILABLE = False

import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION ← Edit these two lines only
# ══════════════════════════════════════════════════════════════════════════════
INPUT_FOLDER = r"D:\Python Annual Report\BRSR333 + TOP 83_pdf"
TEXT_OUT_DIR = r"D:\Python Annual Report\Noise Remove_txt"
# ══════════════════════════════════════════════════════════════════════════════

# ── BRSR / ESG PRESENCE DETECTION ────────────────────────────────────────────
BRSR_PRESENT_RE = re.compile(r"""
\b(
business\s+responsibility\s+(and\s+)?sustainability\s+report |
brsr |
business\s+responsibility\s+report |
\bbrr\b |
\bnvg\b |
national\s+voluntary\s+guidelines |
principle[\s\-]wise\s+(performance|disclosure|reporting|data) |
national\s+guidelines\s+(on\s+)?responsible\s+business |
\bngrbc\b |
sebi.{0,80}(brsr|sustainability\s+report) |
mandatory\s+(brsr|sustainability\s+reporting) |
global\s+reporting\s+initiative |
\bgri\b |
\btcfd\b |
task\s+force\s+on\s+climate[\s\-]related\s+financial\s+disclosures |
\bsasb\b |
sustainability\s+accounting\s+standards |
\bcdp\b |
carbon\s+disclosure\s+project |
un\s+sustainable\s+development\s+goals |
\bsdg\b |
\bungc\b |
un\s+global\s+compact |
integrated\s+reporting |
\b<ir>\b |
esg\s+(report|disclosure|framework|strategy|performance|assurance) |
sustainability\s+(report|disclosure|framework|strategy|performance)
)\b""", re.IGNORECASE | re.VERBOSE)

BRSR_MISSING_RE = re.compile(r"""
\b(
not\s+applicable.{0,80}brsr |
brsr.{0,80}not\s+applicable |
no\s+brsr |
brsr\s+not\s+mandatory |
not\s+required.{0,80}(brsr|business\s+responsibility) |
(brsr|business\s+responsibility).{0,80}not\s+required |
exempted.{0,80}(brsr|business\s+responsibility) |
top\s+1000.{0,80}not\s+applicable |
not\s+listed.{0,80}(brsr|sustainability\s+report) |
below\s+top\s+\d+\s+listed
)\b
""", re.IGNORECASE | re.VERBOSE)

GREENWASHING_SIGNALS_RE = re.compile(r"""
\b(
eco[\s\-]?friendly |
green\s+(initiative|product|company|business|effort|solution) |
environmentally\s+(friendly|responsible|conscious|aware) |
sustainable\s+future |
committed\s+to\s+(sustainability|environment|net\s+zero|carbon\s+neutral) |
carbon\s+neutral(?!\s+(by\s+(20\d{2})|certified|verified|assured)) |
net[\s\-]zero\s+(by\s+20\d{2})? |
planet[\s\-]?positive |
going\s+green |
we\s+(believe|strive|aspire|aim|endeavour)\s+to.{0,60}(environment|sustain|green|carbon|climate) |
our\s+(commitment|pledge|promise)\s+to.{0,60}(environment|sustain|green|carbon|climate) |
industry[\s\-]leading\s+(esg|sustainability|environment) |
best[\s\-]in[\s\-]class\s+(esg|sustainability) |
responsible\s+(company|corporate\s+citizen|business) |
greener\s+(tomorrow|future|world) |
conscious\s+(capitalism|business|company)
)\b
""", re.IGNORECASE | re.VERBOSE)

ASSURANCE_SIGNALS_RE = re.compile(r"""
\b(
third[\s\-]party\s+assurance |
independent\s+assurance |
limited\s+assurance |
reasonable\s+assurance |
assured\s+by |
assurance\s+provider |
assurance\s+statement |
verification\s+statement |
verified\s+by |
externally\s+(verified|assured|audited) |
sustainability\s+assurance |
esg\s+assurance |
brsr\s+assurance |
assurance\s+standard |
\bisae\s*3000\b |
\baa1000\b |
\biso\s*14064\b |
\biso\s*14001\b |
assurance\s+engagement |
assurance\s+report |
practitioner[s\']?\s+report
)\b
""", re.IGNORECASE | re.VERBOSE)

ESG_DENSITY_KEYWORDS = re.compile(r"""
\b(
esg | sustainability | environment(?:al)? | social | governance |
carbon | emission(?:s)? | climate | greenhouse | ghg | renewable |
energy | water | waste | biodiversity | net\s+zero | decarboni\w+ |
circular | human\s+rights | diversity | inclusion | community |
health\s+safety | supply\s+chain | stakeholder | assurance |
brsr | brr | nvg | ngrbc | gri | tcfd | sasb | sdg |
greenwash\w* | disclosure | transparency | accountability |
materiality | double\s+materiality | scope\s+[123] |
carbon\s+neutral | carbon\s+offset | carbon\s+credit |
csr | responsible | ethical | equitable
)\b
""", re.IGNORECASE | re.VERBOSE)

# ── IRRELEVANT SECTION HEADERS ────────────────────────────────────────────────
IRRELEVANT_HEADERS_RE = re.compile(r"""
^[\s\W]*?(
notice\s+of\s+(annual|extraordinary)\s+general\s+meeting |
annual\s+general\s+meeting |
agm\s+notice |
notice\s+to\s+(shareholders|members) |
proxy\s+statement |
proxy\s+form |
attendance\s+slip |
e[\-\s]?voting |
remote\s+e[\-\s]?voting |
postal\s+ballot |
route\s+map\s+to\s+agm |
standalone\s+financial\s+statements |
consolidated\s+financial\s+statements |
balance\s+sheet |
statement\s+of\s+profit\s+(and|&)\s+loss |
profit\s+(and|&)\s+loss\s+account |
cash\s+flow\s+statement |
statement\s+of\s+changes\s+in\s+equity |
notes\s+to\s+(the\s+)?financial\s+statements |
notes\s+forming\s+part\s+of |
significant\s+accounting\s+policies |
summary\s+of\s+(significant\s+)?accounting\s+policies |
independent\s+auditor[s\']?\s+report\s+on\s+(standalone|consolidated|financial) |
auditor[s\']?\s+report\s+on\s+(standalone|consolidated|financial) |
report\s+of\s+(the\s+)?statutory\s+auditor |
secretarial\s+audit\s+report |
cost\s+audit\s+report |
ten[\s\-]year\s+(financial\s+)?highlights |
five[\s\-]year\s+(financial\s+)?summary |
profile\s+of\s+(the\s+)?board |
director[s\']?\s+biograph |
brief\s+profile\s+of |
key\s+managerial\s+personnel |
shareholder\s+information |
investor\s+information |
share\s+capital\s+history |
glossary\s+of\s+terms |
list\s+of\s+abbreviations |
index\s+of\s+forms
)\b
""", re.IGNORECASE | re.VERBOSE | re.MULTILINE)

# ── RELEVANT SECTION HEADERS ──────────────────────────────────────────────────
RELEVANT_HEADERS_RE = re.compile(r"""
\b(
sustainability |
\besg\b |
environmental\s+(social|management|performance|report|policy|initiative) |
social\s+responsibility |
corporate\s+social\s+responsibility |
\bcsr\b |
\bbrsr\b |
business\s+responsibility |
responsible\s+business |
responsible\s+conduct |
\bbrr\b |
\bnvg\b |
\bngrbc\b |
national\s+voluntary\s+guidelines |
national\s+guidelines\s+on\s+responsible |
climate\s+(change|action|strategy|risk|resilience|transition) |
carbon |
greenhouse\s+gas |
\bghg\b |
emission\s+(reduction|intensity|disclosure|target|inventory) |
renewable\s+energy |
energy\s+(management|efficiency|intensity|consumption|transition) |
water\s+(management|conservation|stewardship|risk|intensity) |
waste\s+(management|reduction|recycling|circular) |
biodiversity |
net\s+zero |
decarboni |
circular\s+economy |
scope\s+[123] |
carbon\s+neutral |
carbon\s+offset |
plastic\s+waste |
extended\s+producer\s+responsibility |
human\s+rights |
employee\s+wellbeing |
diversity\s+(and|&)\s+inclusion |
\bd[\s&]i\b |
community\s+development |
health\s+(and|&)\s+safety |
occupational\s+health |
supply\s+chain\s+(responsibility|sustainability|due\s+diligence) |
stakeholder\s+engagement |
gender\s+(equality|diversity|pay) |
child\s+labour |
forced\s+labour |
modern\s+slavery |
labour\s+(rights|practices|standards) |
esg\s+governance |
sustainability\s+governance |
sustainability\s+committee |
board\s+(oversight|diversity|esg|sustainability) |
anti[\s\-]corruption |
anti[\s\-]bribery |
business\s+ethics |
whistleblower |
data\s+privacy |
data\s+protection |
cybersecurity\s+governance |
esg\s+assurance |
sustainability\s+assurance |
brsr\s+assurance |
third[\s\-]party\s+assurance |
independent\s+assurance |
limited\s+assurance |
reasonable\s+assurance |
assurance\s+statement |
verification\s+statement |
esg\s+risk |
climate\s+risk |
\btcfd\b |
physical\s+risk |
transition\s+risk |
stranded\s+asset |
climate\s+scenario |
\bgri\b |
global\s+reporting\s+initiative |
\bsasb\b |
\bcdp\b |
carbon\s+disclosure\s+project |
\bsdg\b |
un\s+sustainable\s+development |
\bungc\b |
integrated\s+report |
management\s+(discussion|discussion\s+(and|&)\s+analysis) |
chairman[s\']?\s+(message|statement|letter) |
managing\s+director[s\']?\s+(message|statement|letter) |
ceo[s\']?\s+(message|statement|letter) |
from\s+the\s+(chairman|managing\s+director|ceo|desk\s+of) |
letter\s+to\s+shareholders |
principle[\s\-]wise |
essential\s+indicators |
leadership\s+indicators |
section\s+[abc]\s+of\s+brsr |
brsr\s+section |
material(ity)?\s+(assessment|matrix|issue|topic|analysis) |
double\s+materiality |
green\s+(bond|finance|taxonomy|loan|project) |
sustainability[\s\-]linked |
esg[\s\-]linked |
impact\s+(invest|measur|report|assessment)
)\b
""", re.IGNORECASE | re.VERBOSE)

# ── DIRECTORS' REPORT special handling ───────────────────────────────────────
DIRECTORS_REPORT_RE = re.compile(
    r"\bdirectors?\s*['\s]?\s*report\b", re.IGNORECASE
)
DIRECTORS_REPORT_ESG_RE = re.compile(
    r"\b(sustainability|esg|csr|brsr|brr|environment|climate|emission|"
    r"renewable|social\s+responsibility|human\s+rights|diversity|"
    r"community|stakeholder|governance|assurance|disclosure)\b",
    re.IGNORECASE
)

# ── BOILERPLATE REMOVAL ───────────────────────────────────────────────────────
BOILERPLATE_PATTERNS = [
    r"this\s+(report|document)\s+(has\s+been|is).{0,120}(prepared|produced|issued)",
    r"forward[\-\s]looking\s+statement[s]?",
    r"safe\s+harb[ou]+r\s+statement",
    r"cautionary\s+(note|statement|language)",
    r"no\s+reliance\s+should\s+be\s+placed",
    r"past\s+performance\s+is\s+not\s+(a\s+)?indicat",
    r"all\s+rights\s+reserved",
    r"copyright\s*[©]?\s*\d{4}",
    r"[®™]",
    r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$",
    r"^\s*[-–—]\s*\d+\s*[-–—]\s*$",
    r"^\s*\d+\s*$",
    r"^\s*(contents|index|table\s+of\s+contents)\s*$",
    r"www\.[^\s]+",
    r"http[s]?://[^\s]+",
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    r"\bcin\s*:\s*[A-Z0-9\/\-]+",
    r"\bgstin\s*:\s*[A-Z0-9]+",
    r"\bpan\s*:\s*[A-Z0-9]+",
    r"\bin\s*:\s*[A-Z0-9]+",
    r"registered\s+office\s*:.*",
    r"corporate\s+office\s*:.*",
    r"tel(ephone)?\s*[:\-]?\s*[\+\d\s\-\(\)]{7,}",
    r"fax\s*[:\-]?\s*[\+\d\s\-\(\)]{7,}",
    r"^\s*(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\s*$",
    r"cin\s*[:\-]",
    r"llpin\s*[:\-]",
]
BOILERPLATE_RE = re.compile(
    "|".join(BOILERPLATE_PATTERNS),
    re.IGNORECASE | re.MULTILINE
)

FINANCIAL_LINE_RE = re.compile(
    r"^\s*[\d,\.\s\(\)\-\+%₹\$£€\|×÷=~<>]+\s*$"
)
STUB_LINE_RE = re.compile(r"^\s*[^A-Za-z]*\s*$")

# ── ADDITIONAL ESG-CONTEXT STOPWORDS ─────────────────────────────────────────
DOMAIN_STOPWORDS = {
    "company", "limited", "ltd", "pvt", "private", "public",
    "annual", "report", "year", "board", "director", "directors",
    "management", "officer", "india", "indian", "rupees", "crore",
    "lakh", "lakhs", "crores", "inr", "rs", "fy", "fiscal",
    "quarter", "half", "ended", "march", "april", "page", "date",
    "signed", "chairman", "managing", "executive", "chief",
    "mumbai", "delhi", "chennai", "bangalore", "hyderabad",
    "kolkata", "ahmedabad", "pune", "secretary", "registered",
    "office", "corporate", "hereby", "pursuant", "herein",
    "aforesaid", "aforementioned", "thereof", "thereto", "therein",
    "whereby", "whereas", "hereof", "hereunder", "herewith",
    "abovementioned", "abovesaid", "afore", "vide", "inter",
    "alia", "viz", "ibid", "supra", "infra",
}

# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def contains_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def get_page_text_with_ocr(page) -> tuple:
    used_ocr = False
    try:
        text = page.get_text()
    except Exception:
        text = ""
    if not text or len(text.strip()) < 50:
        if OCR_AVAILABLE:
            try:
                pix = page.get_pixmap(dpi=200)
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                if mode == "RGBA":
                    img = img.convert("RGB")
                text = pytesseract.image_to_string(img, lang="eng")
                if text.strip():
                    used_ocr = True
            except Exception:
                text = ""
    return text, used_ocr


def is_numeric_page(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    numeric = sum(
        1 for l in lines
        if FINANCIAL_LINE_RE.match(l) or STUB_LINE_RE.match(l)
    )
    word_count = len(text.split())
    return (numeric / len(lines)) > 0.60 and word_count < 300


def classify_page(text: str) -> str:
    header = text[:800]
    if DIRECTORS_REPORT_RE.search(header):
        if DIRECTORS_REPORT_ESG_RE.search(text):
            return "relevant"
        else:
            return "irrelevant"
    if IRRELEVANT_HEADERS_RE.search(header):
        return "irrelevant"
    if RELEVANT_HEADERS_RE.search(text[:1200]):
        return "relevant"
    return "unknown"


def remove_boilerplate_lines(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if BOILERPLATE_RE.search(line):
            continue
        if FINANCIAL_LINE_RE.match(line):
            continue
        if STUB_LINE_RE.match(line):
            continue
        if len(line) < 4:
            continue
        lines.append(line)
    return " ".join(lines)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = remove_boilerplate_lines(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    if NLTK_AVAILABLE:
        tokens = word_tokenize(text)
    else:
        tokens = text.split()
    all_stopwords = STOPWORDS | DOMAIN_STOPWORDS
    tokens = [
        t for t in tokens
        if t.isalpha()
        and len(t) > 2
        and t not in all_stopwords
    ]
    return " ".join(tokens)


def score_esg_density(text: str) -> dict:
    word_count = max(len(text.split()), 1)
    esg_hits = len(ESG_DENSITY_KEYWORDS.findall(text))
    gw_hits = len(GREENWASHING_SIGNALS_RE.findall(text))
    assur_hits = len(ASSURANCE_SIGNALS_RE.findall(text))
    return {
        "esg_keyword_count": esg_hits,
        "esg_keyword_density_pct": round(esg_hits / word_count * 100, 2),
        "greenwashing_signal_count": gw_hits,
        "assurance_signal_count": assur_hits,
    }


def extract_top_esg_terms(tokenized_text: str, top_n: int = 20) -> str:
    tokens = tokenized_text.split()
    esg_tokens = [t for t in tokens if ESG_DENSITY_KEYWORDS.match(t)]
    if not esg_tokens:
        return ""
    freq = Counter(esg_tokens).most_common(top_n)
    return "; ".join(f"{w}:{c}" for w, c in freq)


def process_pdf(pdf_path: str) -> dict:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {
            "text": "", "has_brsr": False, "brsr_missing_flag": False,
            "used_ocr": False, "has_devanagari": False,
            "total_pages": 0, "kept_pages": 0, "skipped_pages": 0,
            "error": str(e)
        }

    all_page_texts = []
    ocr_flags = []

    for page in doc:
        text, used_ocr = get_page_text_with_ocr(page)
        all_page_texts.append(text)
        ocr_flags.append(used_ocr)

    full_text = "\n".join(all_page_texts)
    has_brsr = bool(BRSR_PRESENT_RE.search(full_text))
    brsr_missing_flag = bool(BRSR_MISSING_RE.search(full_text))
    has_devanagari = contains_devanagari(full_text)
    used_ocr_any = any(ocr_flags)

    kept = []
    skipped = 0
    section_status = "unknown"

    for page_text in all_page_texts:
        if not page_text.strip():
            skipped += 1
            continue

        classification = classify_page(page_text)

        if classification == "irrelevant":
            section_status = "irrelevant"
        elif classification == "relevant":
            section_status = "relevant"

        if section_status == "irrelevant":
            skipped += 1
            continue

        if is_numeric_page(page_text):
            skipped += 1
            continue

        kept.append(page_text)

    doc.close()

    return {
        "text": "\n\n".join(kept),
        "has_brsr": has_brsr,
        "brsr_missing_flag": brsr_missing_flag,
        "used_ocr": used_ocr_any,
        "has_devanagari": has_devanagari,
        "total_pages": len(all_page_texts),
        "kept_pages": len(kept),
        "skipped_pages": skipped,
        "error": ""
    }

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run():
    in_dir = Path(INPUT_FOLDER)
    out_dir = Path(TEXT_OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_dir.exists():
        log.error(f"Input folder not found: {in_dir}")
        return

    all_pdfs = sorted({p.resolve() for p in in_dir.glob("*.[pP][dD][fF]")})
    if not all_pdfs:
        log.error(f"No PDFs found in: {in_dir}")
        return

    log.info(f"Found {len(all_pdfs)} PDFs in: {in_dir}\n")

    log_rows = []
    brsr_absent_rows = []
    success = 0
    skipped_count = 0
    used_names = {}

    iterator = tqdm(all_pdfs, desc="Processing PDFs") if TQDM_AVAILABLE else all_pdfs

    for pdf_path in iterator:
        if not TQDM_AVAILABLE:
            log.info(f"Processing: {pdf_path.name}")

        result = process_pdf(str(pdf_path))

        if result["has_brsr"]:
            brsr_status = "BRSR_PRESENT"
        elif result["brsr_missing_flag"]:
            brsr_status = "BRSR_EXPLICITLY_ABSENT"
        else:
            brsr_status = "BRSR_NOT_DETECTED"

        base_row = {
            "filename": pdf_path.name,
            "brsr_status": brsr_status,
        }

        if result["error"]:
            log.error(f"  Error opening {pdf_path.name}: {result['error']}")
            skipped_count += 1
            log_rows.append({
                **base_row,
                "status": f"error: {result['error'][:80]}",
                "word_count_tokens": 0,
                "total_pages": 0,
                "kept_pages": 0,
                "skipped_pages": 0,
                "noise_removed_pct": 0,
                "esg_keyword_count": 0,
                "esg_keyword_density_pct": 0,
                "greenwashing_signal_count": 0,
                "assurance_signal_count": 0,
                "top_esg_terms": "",
                "used_ocr": False,
                "has_devanagari": False,
                "output_file": "",
            })
            continue

        if not result["text"].strip():
            skipped_count += 1
            log_rows.append({
                **base_row,
                "status": "skipped_no_text",
                "word_count_tokens": 0,
                "total_pages": result["total_pages"],
                "kept_pages": result["kept_pages"],
                "skipped_pages": result["skipped_pages"],
                "noise_removed_pct": 0,
                "esg_keyword_count": 0,
                "esg_keyword_density_pct": 0,
                "greenwashing_signal_count": 0,
                "assurance_signal_count": 0,
                "top_esg_terms": "",
                "used_ocr": result["used_ocr"],
                "has_devanagari": result["has_devanagari"],
                "output_file": "",
            })
            continue

        normalized = normalize_text(result["text"])
        corpus = clean_text(result["text"])
        wc_corpus = len(corpus.split())

        if wc_corpus < 80:
            skipped_count += 1
            log.warning(
                f"  SKIPPED (too short after cleaning): {pdf_path.name} "
                f"— {wc_corpus} tokens"
            )
            log_rows.append({
                **base_row,
                "status": "skipped_too_short",
                "word_count_tokens": wc_corpus,
                "total_pages": result["total_pages"],
                "kept_pages": result["kept_pages"],
                "skipped_pages": result["skipped_pages"],
                "noise_removed_pct": round(
                    result["skipped_pages"] / max(result["total_pages"], 1) * 100, 1
                ),
                "esg_keyword_count": 0,
                "esg_keyword_density_pct": 0,
                "greenwashing_signal_count": 0,
                "assurance_signal_count": 0,
                "top_esg_terms": "",
                "used_ocr": result["used_ocr"],
                "has_devanagari": result["has_devanagari"],
                "output_file": "",
            })
            continue

        density = score_esg_density(normalized)
        top_terms = extract_top_esg_terms(corpus)
        noise_pct = round(
            result["skipped_pages"] / max(result["total_pages"], 1) * 100, 1
        )

        stem = pdf_path.stem
        if stem in used_names:
            used_names[stem] += 1
            out_stem = f"{stem}_dup{used_names[stem]}"
            log.warning(
                f"  Filename collision: '{stem}' already used. "
                f"Saving as '{out_stem}'"
            )
        else:
            used_names[stem] = 0
            out_stem = stem

        out_file = out_dir / f"{out_stem}.txt"
        out_file.write_text(corpus, encoding="utf-8")

        if not TQDM_AVAILABLE:
            log.info(
                f"  ✓ {out_stem}.txt | tokens:{wc_corpus:,} | BRSR:{brsr_status} | "
                f"ESG density:{density['esg_keyword_density_pct']}% | "
                f"Noise removed:{noise_pct}%"
            )

        success += 1
        row = {
            **base_row,
            "status": "success",
            "word_count_tokens": wc_corpus,
            "total_pages": result["total_pages"],
            "kept_pages": result["kept_pages"],
            "skipped_pages": result["skipped_pages"],
            "noise_removed_pct": noise_pct,
            **density,
            "top_esg_terms": top_terms,
            "used_ocr": result["used_ocr"],
            "has_devanagari": result["has_devanagari"],
            "output_file": out_file.name,
        }
        log_rows.append(row)

        if brsr_status in ("BRSR_EXPLICITLY_ABSENT", "BRSR_NOT_DETECTED"):
            brsr_absent_rows.append({
                "filename": pdf_path.name,
                "brsr_status": brsr_status,
                "esg_keyword_count": density["esg_keyword_count"],
                "assurance_signals": density["assurance_signal_count"],
                "action_required": (
                    "Manually locate separate BRSR/BRR/Sustainability Report"
                    if brsr_status == "BRSR_NOT_DETECTED"
                    else "Company states BRSR not applicable — verify exemption eligibility"
                ),
            })

    # ── Save main conversion log ──────────────────────────────────────────────
    log_path = out_dir / "conversion_log.csv"
    fieldnames = [
        "filename", "brsr_status", "status",
        "word_count_tokens",
        "total_pages", "kept_pages", "skipped_pages", "noise_removed_pct",
        "esg_keyword_count", "esg_keyword_density_pct",
        "greenwashing_signal_count", "assurance_signal_count",
        "top_esg_terms", "used_ocr", "has_devanagari",
        "output_file",
    ]
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(log_rows)

    # ── Save BRSR-absent manifest ─────────────────────────────────────────────
    absent_path = out_dir / "brsr_absent_manifest.csv"
    absent_fieldnames = [
        "filename", "brsr_status",
        "esg_keyword_count", "assurance_signals", "action_required",
    ]
    with open(absent_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=absent_fieldnames)
        writer.writeheader()
        writer.writerows(brsr_absent_rows)

    # ── Summary ───────────────────────────────────────────────────────────────
    brsr_present = sum(1 for r in log_rows if r["brsr_status"] == "BRSR_PRESENT")
    brsr_absent = sum(1 for r in log_rows if r["brsr_status"] == "BRSR_EXPLICITLY_ABSENT")
    brsr_unknown = sum(1 for r in log_rows if r["brsr_status"] == "BRSR_NOT_DETECTED")
    success_rows = [r for r in log_rows if r["status"] == "success"]
    avg_noise = (
        sum(r["noise_removed_pct"] for r in success_rows) / max(len(success_rows), 1)
    )
    avg_esg_density = (
        sum(r["esg_keyword_density_pct"] for r in success_rows) / max(len(success_rows), 1)
    )
    avg_gw_signals = (
        sum(r["greenwashing_signal_count"] for r in success_rows) / max(len(success_rows), 1)
    )
    avg_assur_signals = (
        sum(r["assurance_signal_count"] for r in success_rows) / max(len(success_rows), 1)
    )

    print("\n" + "=" * 65)
    print("  ESG / BRSR EXTRACTION COMPLETE — Research Grade v2.1")
    print("=" * 65)
    print(f"  Input folder          : {INPUT_FOLDER}")
    print(f"  Total PDFs found      : {len(all_pdfs)}")
    print(f"  Successfully converted: {success}")
    print(f"  Skipped / Failed      : {skipped_count}")
    print()
    print(f"  BRSR DETECTION RESULTS:")
    print(f"    ✓ BRSR / ESG present        : {brsr_present} PDFs")
    print(f"    ✗ BRSR explicitly absent    : {brsr_absent} PDFs")
    print(f"    ? BRSR not detected         : {brsr_unknown} PDFs ← review manifest")
    print()
    print(f"  QUALITY METRICS (successful files):")
    print(f"    Avg noise removed           : {avg_noise:.1f}% of pages")
    print(f"    Avg ESG keyword density     : {avg_esg_density:.2f}%")
    print(f"    Avg greenwashing signals    : {avg_gw_signals:.1f} per doc")
    print(f"    Avg assurance signals       : {avg_assur_signals:.1f} per doc")
    print(f"    OCR used on                 : "
          f"{sum(1 for r in log_rows if r.get('used_ocr'))} files")
    print()
    print(f"  OUTPUT FOLDER         : {TEXT_OUT_DIR}")
    print(f"  Main log (all files)  : conversion_log.csv")
    print(f"  BRSR-absent manifest  : brsr_absent_manifest.csv")
    print("=" * 65)
    print()
    print("  OUTPUT FORMAT (one .txt per PDF):")
    print("    <filename>.txt → lowercased, stopwords removed, tokenized")
    print("    ready for: TF-IDF, LDA, word2vec, VADER, regression")
    print()
    print("  BRSR STATUS CODES:")
    print("    BRSR_PRESENT           → BRSR / BRR / GRI / TCFD detected in PDF")
    print("    BRSR_EXPLICITLY_ABSENT → Company stated BRSR not applicable")
    print("    BRSR_NOT_DETECTED      → No signals found — check brsr_absent_manifest.csv")
    print("=" * 65)
    print()
    if NLTK_AVAILABLE:
        print("  [OK] NLTK stopword removal active")
    else:
        print("  [!!] NLTK not available — run:")
        print("       pip install nltk")
        print("       python -c \"import nltk; nltk.download('stopwords'); "
              "nltk.download('punkt')\"")
    if OCR_AVAILABLE:
        print("  [OK] OCR (Tesseract) active for scanned pages")
    else:
        print("  [!!] pytesseract / Tesseract not found — scanned pages will be empty")
    print("=" * 65)


if __name__ == "__main__":
    run()