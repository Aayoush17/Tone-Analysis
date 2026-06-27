import os
import csv
import unicodedata
from pathlib import Path
from collections import Counter
import pandas as pd  # ADD THIS

INPUT_DIR   = r"D:\Python Annual Report\BRSR-BRR_txt\cleaned_texts"
LM_CSV      = r""
LM_DIR      = r"D:\Python Annual Report\Moti Sir Sent Words and Tone Analysis Code\words"
OUTPUT_FILE = r"D:\Python Annual Report\BRSR-BRR_Tone Analysis\BRSR-BRR Tone Analysis.xlsx"

# Fallback text files if a category is missing from the CSV
LM_FILE_MAP = {
    "Positive":     ["Positive.txt"],
    "Negative":     ["Negative.txt"],
    "Uncertainty":  ["Uncertainity.txt", "Uncertainty.txt"],
    "Litigious":    ["Litigious.txt"],
    "Strong":       ["Strong.txt"],
    "Weak":         ["Weak.txt"],
    "Constraining": ["Constraining.txt"],
    "Complexity":   ["Complexity.txt"],
}

LM_STOPWORDS_FILE = os.path.join(LM_DIR, "Stop.txt")

# Column names in the master CSV that flag each category (non-zero = member)
CSV_CATEGORY_COLS = {
    "Positive":     "Positive",
    "Negative":     "Negative",
    "Uncertainty":  "Uncertainty",
    "Litigious":    "Litigious",
    "Strong":       "Strong_Modal",
    "Weak":         "Weak_Modal",
    "Constraining": "Constraining",
    "Complexity":   "Complexity",
}

ESG_KEYWORDS = {
    "environment", "environmental", "emission", "emissions", "carbon",
    "greenhouse", "ghg", "climate", "renewable", "energy", "waste",
    "water", "biodiversity", "deforestation", "pollution", "recycling",
    "sustainability", "sustainable", "footprint", "ecological", "ecology",
    "solar", "wind", "biomass", "effluent", "afforestation", "reforestation",
    "conservation", "habitat", "species", "wetland", "watershed",
    "decarbonization", "decarbonisation", "circular", "cleanenergy",
    "netzero", "carbonneutral", "climaterisk",
    "social", "community", "diversity", "inclusion", "gender", "equity",
    "employee", "employees", "workforce", "training", "health", "safety",
    "wellbeing", "welfare", "humanrights", "labour", "labor",
    "discrimination", "harassment", "posh", "parental", "maternity",
    "paternity", "disability", "indigenous", "marginalized", "vulnerable",
    "livelihood", "empowerment", "education", "nutrition", "sanitation",
    "childlabour", "forcedlabour", "fairwage", "minimumwage",
    "governance", "transparent", "transparency", "accountability",
    "compliance", "ethics", "ethical", "integrity", "stakeholder",
    "disclosure", "policy", "policies", "regulation", "regulatory",
    "audit", "risk", "materiality", "esg", "csr", "responsibility",
    "responsible", "impact", "initiative", "target", "goal", "commitment",
    "whistleblower", "anticorruption", "antibribery",
    "supplychain", "vendor", "supplier", "grievance", "redressal",
    "brsr", "ngrbc", "sdg", "ungc", "gri", "sasb", "tcfd",
    "reporting", "assurance", "verification", "framework",
}

CUSTOM_STOPWORDS = {
    "crore", "lakh", "pursuant", "herein", "hereinafter", "viz", "sebi",
    "brsr", "bsr", "fy", "rin", "cin", "din", "llp", "ltd", "limited",
    "india", "indian", "company", "companies", "annual", "report",
    "financial", "year", "quarter", "board", "director", "directors",
    "meeting", "held", "said", "per", "also", "may", "shall", "would",
    "could", "within", "thereof", "therein", "hereby", "whereas",
    "aforesaid", "amongst", "abovementioned", "hereunder", "thereunder",
    "thereto", "therewith", "therefrom", "whereof", "whereon",
    "notwithstanding", "aforementioned", "accordingly", "andor",
    "nil", "na", "total", "sub", "grand", "please", "etc", "ibid",
}


# ── Dictionary loaders ────────────────────────────────────────────────────────

def load_txt_words(filepath):
    words = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                word = line.split()[0].lower()
                if word.isalpha():
                    words.add(word)
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
    return words


def load_master_csv(csv_path):
    """
    Parse LoughranMcDonald_MasterDictionary CSV.
    Returns dict: {category: set_of_lowercase_words}
    Also returns set of stopwords (where StopWords column != 0).
    """
    dicts     = {cat: set() for cat in CSV_CATEGORY_COLS}
    stopwords = set()
    found_cols = {}

    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in reader.fieldnames]

            # Map expected column names to actual headers (case-insensitive)
            header_map = {h.lower(): h for h in headers}

            for cat, col in CSV_CATEGORY_COLS.items():
                actual = header_map.get(col.lower())
                if actual:
                    found_cols[cat] = actual
                else:
                    # Try partial match
                    for h_lower, h_actual in header_map.items():
                        if col.lower() in h_lower:
                            found_cols[cat] = h_actual
                            break

            stop_col = header_map.get("stopwords") or header_map.get("stop_words")

            for row in reader:
                word_raw = row.get("Word", "") or row.get("word", "")
                if not word_raw:
                    # Try first column
                    word_raw = list(row.values())[0]
                word = word_raw.strip().lower()
                if not word or not word.isalpha():
                    continue

                for cat, col_actual in found_cols.items():
                    try:
                        val = row.get(col_actual, "0").strip()
                        if val and val != "0":
                            dicts[cat].add(word)
                    except Exception:
                        pass

                if stop_col:
                    try:
                        val = row.get(stop_col, "0").strip()
                        if val and val != "0":
                            stopwords.add(word)
                    except Exception:
                        pass

    except Exception as e:
        print(f"  ERROR reading master CSV: {e}")

    return dicts, stopwords


def load_all_dicts(lm_csv, lm_dir):
    dicts     = {cat: set() for cat in CSV_CATEGORY_COLS}
    stopwords = set()

    # ── Primary: master CSV ──────────────────────────────────────────────────
    csv_loaded = False
    if os.path.exists(lm_csv):
        print(f"  Loading master CSV: {os.path.basename(lm_csv)}")
        csv_dicts, csv_stops = load_master_csv(lm_csv)
        csv_loaded = True
        for cat in dicts:
            dicts[cat] = csv_dicts[cat]
        stopwords = csv_stops
        print(f"  {'Category':<15} {'CSV':>6}  {'TXT fallback':>12}")
        print(f"  {'-'*40}")
        for cat in dicts:
            print(f"  {cat:<15} {len(dicts[cat]):>6}")
        if stopwords:
            print(f"  {'Stopwords':<15} {len(stopwords):>6}  (from CSV)")
    else:
        print(f"  Master CSV not found at: {lm_csv}")
        print(f"  Falling back to individual .txt files only.")

    # ── Secondary: txt files to fill any empty categories ───────────────────
    txt_stop_path = os.path.join(lm_dir, "Stop.txt")
    if not stopwords and os.path.exists(txt_stop_path):
        stopwords = load_txt_words(txt_stop_path)
        print(f"  {'Stopwords':<15} {len(stopwords):>6}  (Stop.txt)")

    for cat, candidates in LM_FILE_MAP.items():
        if len(dicts[cat]) == 0:
            for fname in candidates:
                fpath = os.path.join(lm_dir, fname)
                if os.path.exists(fpath):
                    words = load_txt_words(fpath)
                    dicts[cat] = words
                    print(f"  {cat:<15} {len(words):>6}  (fallback: {fname})")
                    break
            else:
                if not csv_loaded:
                    print(f"  {cat:<15}      0  NOT FOUND")

    # ── Merge: CSV + TXT (union gives maximum coverage) ─────────────────────
    if csv_loaded:
        print(f"\n  Merging CSV + TXT files for maximum coverage...")
        for cat, candidates in LM_FILE_MAP.items():
            for fname in candidates:
                fpath = os.path.join(lm_dir, fname)
                if os.path.exists(fpath):
                    txt_words = load_txt_words(fpath)
                    before = len(dicts[cat])
                    dicts[cat] = dicts[cat] | txt_words
                    added = len(dicts[cat]) - before
                    if added > 0:
                        print(f"  {cat:<15} +{added:>4} words from {fname}  → total {len(dicts[cat])}")
                    break

        txt_stops = set()
        if os.path.exists(txt_stop_path):
            txt_stops = load_txt_words(txt_stop_path)
            before = len(stopwords)
            stopwords = stopwords | txt_stops
            print(f"  {'Stopwords':<15} +{len(stopwords)-before:>4} from Stop.txt  → total {len(stopwords)}")

    print()
    return dicts, stopwords


# ── Token cleaning ────────────────────────────────────────────────────────────

def normalize(text):
    return unicodedata.normalize("NFKC", text)


def clean_tokens(raw_tokens, lm_stopwords):
    all_stops = CUSTOM_STOPWORDS | lm_stopwords
    cleaned = []
    for t in raw_tokens:
        t = normalize(t).lower().strip()
        if not t.isalpha() or len(t) < 3:
            continue
        if t in all_stops:
            continue
        cleaned.append(t)
    return cleaned


def load_file(txt_path, lm_stopwords):
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read().strip().split()
    return clean_tokens(raw, lm_stopwords)


# ── Metrics ───────────────────────────────────────────────────────────────────

def count_lm(tokens, dicts):
    return {f"LM_{cat}": sum(1 for t in tokens if t in wordset)
            for cat, wordset in dicts.items()}


def count_esg(tokens):
    return sum(1 for t in tokens if t in ESG_KEYWORDS)


def net_tone(pos, neg, total):
    return round((pos - neg) / total, 6) if total else 0.0

def sentiment_score(pos, neg):
    return round((pos - neg) / (pos + neg + 1), 6)

def polarity_ratio(pos, neg):
    return round(pos / (pos + neg), 4) if (pos + neg) else 0.0

def esg_density(esg_n, total):
    return round((esg_n / total) * 1000, 4) if total else 0.0

def uncertainty_ratio(unc, total):
    return round(unc / total, 6) if total else 0.0

def litigiousness_ratio(lit, total):
    return round(lit / total, 6) if total else 0.0

def constraining_ratio(con, total):
    return round(con / total, 6) if total else 0.0

def modal_strength_ratio(stg, wk, total):
    return round((stg - wk) / total, 6) if total else 0.0

def complexity_ratio(cmp, total):
    return round(cmp / total, 6) if total else 0.0

def type_token_ratio(tokens):
    return round(len(set(tokens)) / len(tokens), 4) if tokens else 0.0

def avg_word_length(tokens):
    return round(sum(len(t) for t in tokens) / len(tokens), 4) if tokens else 0.0

def content_richness(lm_counts, total):
    if not total:
        return 0.0
    tone = sum([
        lm_counts.get("LM_Positive", 0),
        lm_counts.get("LM_Negative", 0),
        lm_counts.get("LM_Uncertainty", 0),
        lm_counts.get("LM_Strong", 0),
        lm_counts.get("LM_Weak", 0),
        lm_counts.get("LM_Constraining", 0),
    ])
    return round(tone / total, 6)

def top_words(tokens, n=20):
    return " | ".join(f"{w}:{c}" for w, c in Counter(tokens).most_common(n))


# ── Per-file analysis ─────────────────────────────────────────────────────────

def analyze_file(txt_path, dicts, lm_stopwords):
    tokens = load_file(txt_path, lm_stopwords)
    total  = len(tokens)

    lm     = count_lm(tokens, dicts)
    esg_n  = count_esg(tokens)

    pos = lm.get("LM_Positive", 0)
    neg = lm.get("LM_Negative", 0)
    unc = lm.get("LM_Uncertainty", 0)
    lit = lm.get("LM_Litigious", 0)
    con = lm.get("LM_Constraining", 0)
    stg = lm.get("LM_Strong", 0)
    wk  = lm.get("LM_Weak", 0)
    cmp = lm.get("LM_Complexity", 0)

    return {
        "filename"              : Path(txt_path).stem,
        "total_words"           : total,
        "unique_words"          : len(set(tokens)),
        "type_token_ratio"      : type_token_ratio(tokens),
        "avg_word_length"       : avg_word_length(tokens),
        "net_tone"              : net_tone(pos, neg, total),
        "sentiment_score"       : sentiment_score(pos, neg),
        "polarity_ratio"        : polarity_ratio(pos, neg),
        "esg_count"             : esg_n,
        "esg_density"           : esg_density(esg_n, total),
        "uncertainty_ratio"     : uncertainty_ratio(unc, total),
        "litigiousness_ratio"   : litigiousness_ratio(lit, total),
        "constraining_ratio"    : constraining_ratio(con, total),
        "modal_strength_ratio"  : modal_strength_ratio(stg, wk, total),
        "complexity_ratio"      : complexity_ratio(cmp, total),
        "content_richness"      : content_richness(lm, total),
        "top_20_words"          : top_words(tokens),
        "LM_Positive"           : pos,
        "LM_Negative"           : neg,
        "LM_Uncertainty"        : unc,
        "LM_Litigious"          : lit,
        "LM_Strong"             : stg,
        "LM_Weak"               : wk,
        "LM_Constraining"       : con,
        "LM_Complexity"         : cmp,
    }


FIELDNAMES = [
    "filename", "total_words", "unique_words", "type_token_ratio", "avg_word_length",
    "net_tone", "sentiment_score", "polarity_ratio",
    "esg_count", "esg_density",
    "uncertainty_ratio", "litigiousness_ratio", "constraining_ratio",
    "modal_strength_ratio", "complexity_ratio", "content_richness",
    "top_20_words",
    "LM_Positive", "LM_Negative", "LM_Uncertainty", "LM_Litigious",
    "LM_Strong", "LM_Weak", "LM_Constraining", "LM_Complexity",
]


# ── Entry point ───────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("BRSR Tone Analysis — LM Master Dictionary + TXT Merge")
    print("=" * 60)

    print("\nLoading dictionaries...")
    dicts, lm_stopwords = load_all_dicts(LM_CSV, LM_DIR)

    print("Final dictionary sizes:")
    for cat, wordset in dicts.items():
        print(f"  {cat:<15} {len(wordset):>6} words")
    print(f"  {'Stopwords':<15} {len(lm_stopwords):>6} words\n")

    txt_files = sorted(Path(INPUT_DIR).glob("*.txt"))
    print(f"Found {len(txt_files)} cleaned text files.\n")

    if not txt_files:
        print(f"No .txt files in: {INPUT_DIR}")
        return

    results = []
    errors  = 0

    for idx, txt_path in enumerate(txt_files, 1):
        print(f"[{idx}/{len(txt_files)}] {txt_path.name}")
        try:
            results.append(analyze_file(str(txt_path), dicts, lm_stopwords))
        except Exception as e:
            errors += 1
            print(f"   ERROR: {e}")
            results.append({"filename": txt_path.stem, "total_words": 0})

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Convert to Excel (.xlsx)
    df = pd.DataFrame(results)
    
    # Reorder columns to match FIELDNAMES
    df = df[FIELDNAMES]
    
    # Save as Excel file
    df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
    
    print(f"\n{'=' * 60}")
    print(f"Done. {len(results) - errors} succeeded, {errors} failed.")
    print(f"Output: {OUTPUT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run()