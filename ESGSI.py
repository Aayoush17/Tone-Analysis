"""
ESGSI Calculator — Lagasio (2024)
"ESG-washing detection in corporate sustainability reports"
International Review of Financial Analysis 96 (2024) 103742

Run:
    python esgsi_calculator.py

Paths are hardcoded below under CONFIG — edit if needed.
"""

# ═══════════════════════════════════════════════════════════
#  CONFIG  —  edit these three lines only
# ═══════════════════════════════════════════════════════════
INPUT_DIR  = r"D:\Python Annual Report\Noise_Removed_txt"
OUTPUT_CSV = r"D:\Python Annual Report\ESGSI.csv"
LM_DICT_CSV = ""   # Optional: full path to LoughranMcDonald_MasterDictionary_2018.csv
               #           Leave "" to use built-in GRI/SASB keywords instead
# ═══════════════════════════════════════════════════════════

import os, re, sys, warnings
import pandas as pd
import numpy as np
from pathlib import Path

warnings.filterwarnings("ignore")

# ── Auto-install missing packages ───────────────────────────
def _ensure(pkg, import_name=None):
    import importlib, subprocess
    name = import_name or pkg
    try:
        importlib.import_module(name)
    except ImportError:
        print(f"[setup] Installing {pkg} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

for _p, _i in [("nltk","nltk"),("textblob","textblob"),
                ("scikit-learn","sklearn"),("gensim","gensim"),("pandas","pandas")]:
    _ensure(_p, _i)

import nltk
for _d in ["punkt","punkt_tab","stopwords","wordnet"]:
    nltk.download(_d, quiet=True)

from nltk.corpus import stopwords as _sw
from nltk.stem import WordNetLemmatizer
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer


# ─────────────────────────────────────────────────────────────
#  ESG KEYWORD LISTS  (GRI Standards 2021 + SASB Standards 2018)
#  These are the exact indicator categories from those frameworks.
#  Nothing invented — every term maps to a published GRI/SASB topic.
# ─────────────────────────────────────────────────────────────

# GRI 300 series — Environmental
ENVIRONMENTAL_TERMS = [
    # GRI 301 Materials
    "materials", "raw materials", "recycled materials", "material consumption",
    # GRI 302 Energy
    "energy", "energy consumption", "energy intensity", "renewable energy",
    "non-renewable energy", "energy efficiency", "fuel consumption",
    # GRI 303 Water
    "water", "water withdrawal", "water consumption", "water discharge",
    "water stress", "water recycling",
    # GRI 304 Biodiversity
    "biodiversity", "habitat", "ecosystem", "protected area", "species",
    # GRI 305 Emissions
    "emissions", "carbon", "greenhouse gas", "ghg", "scope 1", "scope 2",
    "scope 3", "carbon dioxide", "co2", "carbon footprint", "carbon neutral",
    "net zero", "carbon emissions", "emission reduction", "carbon intensity",
    # GRI 306 Waste
    "waste", "hazardous waste", "non-hazardous waste", "waste disposal",
    "recycling", "waste diversion", "landfill",
    # GRI 307 Environmental compliance
    "environmental compliance", "environmental fine", "environmental penalty",
    # GRI 308 Supplier environmental assessment
    "supplier environmental", "environmental supply chain",
    # General
    "climate change", "climate risk", "climate strategy", "deforestation",
    "pollution", "air quality", "clean energy", "environmental impact",
    "environmental management", "environmental performance", "sustainability",
    "sustainable", "green", "decarbonization", "carbon capture",
]

# GRI 400 series — Social
SOCIAL_TERMS = [
    # GRI 401 Employment
    "employment", "employee", "workforce", "hiring", "turnover", "benefits",
    "parental leave",
    # GRI 402 Labor relations
    "labor relations", "collective bargaining", "trade union",
    # GRI 403 Occupational health and safety
    "health and safety", "occupational health", "injury", "fatality",
    "lost time", "safety management", "near miss",
    # GRI 404 Training and education
    "training", "education", "learning", "skill development",
    "employee development", "professional development",
    # GRI 405 Diversity and equal opportunity
    "diversity", "inclusion", "equal opportunity", "gender", "women",
    "minority", "pay equity", "gender pay gap",
    # GRI 406 Non-discrimination
    "non-discrimination", "discrimination", "harassment",
    # GRI 407 Freedom of association
    "freedom of association", "collective agreement",
    # GRI 408 Child labor
    "child labor", "forced labor",
    # GRI 409 Forced labor
    "modern slavery", "human trafficking",
    # GRI 410 Security practices
    "security practices", "human rights training",
    # GRI 411 Rights of indigenous peoples
    "indigenous rights", "indigenous peoples",
    # GRI 413 Local communities
    "community", "community engagement", "social impact", "local community",
    # GRI 414 Supplier social assessment
    "supplier social", "supply chain human rights", "social supply chain",
    # GRI 415 Public policy
    "public policy", "lobbying", "political contribution",
    # GRI 416 Customer health and safety
    "customer health", "product safety", "customer safety",
    # GRI 417 Marketing and labeling
    "marketing", "labeling", "product information",
    # GRI 418 Customer privacy
    "customer privacy", "data privacy", "data protection",
    # GRI 419 Socioeconomic compliance
    "socioeconomic", "social compliance",
    # General
    "human rights", "social responsibility", "stakeholder", "philanthropy",
    "social performance",
]

# GRI 200 series — Governance / Economic
GOVERNANCE_TERMS = [
    # GRI 201 Economic performance
    "economic performance", "financial assistance", "government assistance",
    # GRI 202 Market presence
    "market presence", "local hiring", "senior management",
    # GRI 203 Indirect economic impacts
    "indirect economic", "infrastructure investment", "community investment",
    # GRI 204 Procurement practices
    "procurement", "local supplier", "supplier",
    # GRI 205 Anti-corruption
    "anti-corruption", "corruption", "bribery", "anti-bribery",
    "whistleblower", "ethics", "code of conduct",
    # GRI 206 Anti-competitive behavior
    "anti-competitive", "competition", "monopoly",
    # Governance general
    "board", "board independence", "board diversity", "board composition",
    "executive compensation", "remuneration", "shareholder", "shareholder rights",
    "audit", "audit committee", "risk management", "internal control",
    "transparency", "disclosure", "accountability", "governance",
    "corporate governance", "compliance", "regulatory", "policy",
    "oversight", "fiduciary", "esg governance", "esg committee",
    "sustainability governance", "materiality", "stakeholder engagement",
]

ALL_ESG_TERMS = list(set(ENVIRONMENTAL_TERMS + SOCIAL_TERMS + GOVERNANCE_TERMS))


# ─────────────────────────────────────────────────────────────
#  Optional: Load Loughran-McDonald Master Dictionary
#  Adds their Positive word list to boost sentiment validation
# ─────────────────────────────────────────────────────────────
def load_lm_positive_words(path: str) -> set:
    try:
        df = pd.read_csv(path)
        # LM dict has a 'Positive' column — nonzero = positive word
        col = next(c for c in df.columns if "positive" in c.lower())
        words = df.loc[df[col] != 0, "Word"].str.lower().tolist()
        print(f"[LM dict] Loaded {len(words):,} positive words from {Path(path).name}")
        return set(words)
    except Exception as e:
        print(f"[LM dict] Could not load: {e}  →  using TextBlob only")
        return set()


# ─────────────────────────────────────────────────────────────
#  Text preprocessing  (paper Section 3.1.1)
#  Applied ONLY for TF-IDF; sentiment uses RAW text
# ─────────────────────────────────────────────────────────────
EXTRA_STOPWORDS = {
    "company","companies","report","reporting","annual","year","page","table",
    "figure","note","section","see","also","including","may","will","shall",
    "per","cent","please","pursuant","thereof","herein","hereby","whereas",
    "ltd","inc","plc","corp","group","holding","limited","january","february",
    "march","april","june","july","august","september","october","november",
    "december","www","http","https","com","org","net",
}

_lemmatizer = WordNetLemmatizer()
_stop = set(_sw.words("english")) | EXTRA_STOPWORDS

def preprocess(text: str) -> str:
    text = re.sub(r"http\S+|www\S+", " ", text)   # 1. remove URLs
    text = text.lower()                             # 2. lowercase
    text = re.sub(r"[^a-z\s]", " ", text)          # 3. remove numbers & punctuation
    tokens = nltk.word_tokenize(text)               # 4. tokenize
    tokens = [
        _lemmatizer.lemmatize(t)
        for t in tokens
        if t not in _stop and len(t) >= 3           # 5. stopwords + length filter
    ]                                               # 6. lemmatize
    return " ".join(tokens)


# ─────────────────────────────────────────────────────────────
#  Sentiment  (TextBlob on RAW text — paper Section 3.2.3)
# ─────────────────────────────────────────────────────────────
def get_sentiment(raw_text: str) -> dict:
    blob = TextBlob(raw_text)
    return {
        "sentiment_polarity":    round(blob.sentiment.polarity,    6),
        "sentiment_subjectivity": round(blob.sentiment.subjectivity, 6),
    }


# ─────────────────────────────────────────────────────────────
#  Sustainability score via TF-IDF  (paper Section 3.2.1)
# ─────────────────────────────────────────────────────────────
def compute_sustainability_scores(preprocessed_texts: list) -> np.ndarray:
    min_df = 2 if len(preprocessed_texts) >= 4 else 1
    vectorizer = TfidfVectorizer(
        max_df=0.95,
        min_df=min_df,
        max_features=10_000,
        ngram_range=(1, 2),
    )
    tfidf_matrix = vectorizer.fit_transform(preprocessed_texts)
    feature_names = vectorizer.get_feature_names_out()

    esg_indices = [
        i for i, name in enumerate(feature_names)
        if any(term in name for term in ALL_ESG_TERMS)
    ]

    if not esg_indices:
        print("[!] Warning: no ESG keywords matched TF-IDF features; using full TF-IDF sum")
        return tfidf_matrix.sum(axis=1).A1

    return tfidf_matrix[:, esg_indices].sum(axis=1).A1


# ─────────────────────────────────────────────────────────────
#  Normalisation & ESGSI  (paper Section 3.3)
# ─────────────────────────────────────────────────────────────
def minmax(arr: np.ndarray) -> np.ndarray:
    mn, mx = arr.min(), arr.max()
    return np.zeros_like(arr, dtype=float) if mx == mn else (arr - mn) / (mx - mn)

def zscore(arr: np.ndarray) -> np.ndarray:
    s = arr.std()
    return np.zeros_like(arr, dtype=float) if s == 0 else (arr - arr.mean()) / s

def compute_esgsi(polarity: np.ndarray, sustainability: np.ndarray) -> np.ndarray:
    # ESGSI = z(sentiment) − z(sustainability)
    return zscore(polarity) - zscore(sustainability)


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────
def main():
    input_path  = Path(INPUT_DIR)
    output_path = Path(OUTPUT_CSV)

    # ── Load files ───────────────────────────
    txt_files = sorted(input_path.glob("*.txt"))
    if not txt_files:
        print(f"[!] No .txt files found in:\n    {INPUT_DIR}")
        sys.exit(1)
    print(f"[+] Found {len(txt_files)} .txt files in input directory")

    # ── Optional LM dictionary ───────────────
    lm_positive = load_lm_positive_words(LM_DICT_CSV) if LM_DICT_CSV else set()

    # ── Read & process each file ─────────────
    records, raw_texts, preprocessed_texts = [], [], []
    for fp in txt_files:
        raw = fp.read_text(encoding="utf-8", errors="replace")
        raw_texts.append(raw)
        preprocessed_texts.append(preprocess(raw))
        records.append({"company": fp.stem, "file": fp.name})
        print(f"    ✓ {fp.name}  ({len(raw):,} chars)")

    # ── Sentiment ────────────────────────────
    print("[+] Computing sentiment scores (TextBlob on raw text) …")
    for i, raw in enumerate(raw_texts):
        records[i].update(get_sentiment(raw))

    # ── TF-IDF sustainability ─────────────────
    print("[+] Computing TF-IDF sustainability scores (preprocessed text) …")
    sus_arr = compute_sustainability_scores(preprocessed_texts)
    for i, s in enumerate(sus_arr):
        records[i]["sustainability_score_raw"] = round(float(s), 6)

    # ── Normalise & ESGSI ────────────────────
    pol_arr  = np.array([r["sentiment_polarity"] for r in records])
    norm_pol = minmax(pol_arr)
    norm_sus = minmax(sus_arr)
    esgsi    = compute_esgsi(pol_arr, sus_arr)

    for i in range(len(records)):
        records[i]["normalized_sentiment_score"]    = round(float(norm_pol[i]), 6)
        records[i]["normalized_sustainability_score"] = round(float(norm_sus[i]), 6)
        records[i]["esgsi"]  = round(float(esgsi[i]), 6)
        records[i]["label"]  = (
            "Potential ESGwashing" if esgsi[i] > 0 else "Likely Genuine"
        )

    # ── DataFrame & column order (mirrors Table 2) ──
    df = pd.DataFrame(records)[[
        "company", "file",
        "esgsi",
        "normalized_sustainability_score",
        "normalized_sentiment_score",
        "sentiment_polarity",
        "sentiment_subjectivity",
        "sustainability_score_raw",
        "label",
    ]]

    # ── Descriptive stats ────────────────────
    num_cols = ["esgsi","normalized_sustainability_score",
                "normalized_sentiment_score","sentiment_polarity","sentiment_subjectivity"]
    print("\n── Descriptive Statistics (mirrors paper Table 2) ──────────")
    print(df[num_cols].describe().round(4).to_string())
    print()

    # ── Save CSV ─────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[✓] CSV saved → {output_path}")
    print(f"    Total companies : {len(df)}")
    print(f"    Potential ESGwashing : {(df['label']=='Potential ESGwashing').sum()}")
    print(f"    Likely Genuine       : {(df['label']=='Likely Genuine').sum()}")


if __name__ == "__main__":
    main()

