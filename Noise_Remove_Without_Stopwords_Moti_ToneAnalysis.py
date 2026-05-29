import os
import pandas as pd
from pathlib import Path

# ===========================================
# STEP 1: Load Word Lists from Dictionary Files
# ===========================================
def load_wordlist(filepath):
    """Load words from a text file, one word per line."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return set(
                line.strip().lower()
                for line in file
                if line.strip() and not line.startswith(';') and not line.startswith('#')
            )
    except FileNotFoundError:
        print(f"  ⚠️ Warning: File not found - {filepath}")
        return set()

# ===========================================
# STEP 2: CONFIGURE YOUR PATHS
# ===========================================

# Path to folder containing ALL dictionary .txt files
DICTIONARY_FOLDER = r"D:\Python Annual Report\Moti Sir Sent Words and Tone Analysis Code\words"

# Path to folder containing ALL company annual reports (single folder with all .txt files)
REPORTS_FOLDER = r"D:\Python Annual Report\Noise Removed_txt"

# Output Excel file path
OUTPUT_EXCEL = r"D:\Python Annual Report\Noise_Removed_Moti_ToneAnalysis.xlsx"

# Dictionary file names (EXACT names from your image)
DICT_FILES = {
    "positive": "Positive.txt",           # Positive words
    "negative": "Negative.txt",           # Negative words
    "stopwords": "Stop.txt",              # Stop words
    "complexity": "Complexity.txt",       # Complexity words
    "constraining": "Constraining.txt",   # Constraining words
    "litigious": "Litigious.txt",         # Litigious words
    "strong_modal": "Strong.txt",         # Strong modal words
    "weak_modal": "Weak.txt",             # Weak modal words
    "uncertainty": "Uncertainity.txt"     # Uncertainty words (note spelling)
}

# ===========================================
# STEP 3: Load All Dictionaries
# ===========================================
print("=" * 70)
print("LOADING DICTIONARIES")
print("=" * 70)

word_lists = {}
for category, filename in DICT_FILES.items():
    filepath = os.path.join(DICTIONARY_FOLDER, filename)
    word_lists[category] = load_wordlist(filepath)
    print(f"✓ Loaded {len(word_lists[category])} {category} words from {filename}")

# Check if any dictionary is empty (file missing)
print("\n" + "-" * 70)
empty_dicts = [cat for cat, words in word_lists.items() if len(words) == 0]
if empty_dicts:
    print(f"⚠️ Warning: These dictionary files were not found or are empty: {empty_dicts}")
    print("   Please check that all files exist in:", DICTIONARY_FOLDER)
print("-" * 70)

# ===========================================
# STEP 4: Function to Extract Company Name and Year from Filename
# ===========================================
def extract_company_and_year(filename):
    """
    Extract company name and year from filename.
    Example: "AARTIND_Annual_Report_2023-24.txt" -> Company: "AARTIND", Year: "2023"
    """
    # Remove .txt extension
    name_without_ext = filename.replace('.txt', '')
    
    # Try to find year (4-digit number)
    year = "Unknown"
    parts = name_without_ext.replace('_', ' ').replace('-', ' ').split()
    for part in parts:
        if part.isdigit() and len(part) == 4:
            year = part
            break
        # Handle year ranges like 2023-24
        if '-' in part and len(part) >= 5:
            potential_year = part.split('-')[0]
            if potential_year.isdigit() and len(potential_year) == 4:
                year = potential_year
                break
    
    # Extract company name (first part before first underscore)
    if '_' in name_without_ext:
        company = name_without_ext.split('_')[0]
    else:
        company = name_without_ext
    
    return company, year

# ===========================================
# STEP 5: Function to Analyze a Single Text File
# ===========================================
def analyze_text_file(file_path, word_lists):
    """Analyze a text file and return counts for all categories."""
    
    # Read file with multiple encoding attempts
    text = None
    for encoding in ['utf-8', 'cp1252', 'iso-8859-1', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                text = f.read().lower()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if text is None:
        print(f"  ❌ Could not decode file: {file_path}")
        return None
    
    # Tokenize into words (simple whitespace splitting)
    words = []
    for word in text.split():
        # Remove common punctuation from start/end
        word = word.strip('.,!?;:"\'()[]{}<>-–—')
        if word and any(c.isalpha() for c in word):  # Only keep words with letters
            words.append(word)
    
    # Remove stop words
    stopwords = word_lists.get("stopwords", set())
    filtered_words = [w for w in words if w not in stopwords]
    
    # Initialize counters
    counts = {
        "total_words_raw": len(words),
        "total_words_clean": len(filtered_words),
        "positive": 0,
        "negative": 0,
        "complexity": 0,
        "constraining": 0,
        "litigious": 0,
        "strong_modal": 0,
        "weak_modal": 0,
        "uncertainty": 0
    }
    
    # Count words in each category (a word can belong to multiple categories)
    for word in filtered_words:
        if word in word_lists.get("positive", set()):
            counts["positive"] += 1
        if word in word_lists.get("negative", set()):
            counts["negative"] += 1
        if word in word_lists.get("complexity", set()):
            counts["complexity"] += 1
        if word in word_lists.get("constraining", set()):
            counts["constraining"] += 1
        if word in word_lists.get("litigious", set()):
            counts["litigious"] += 1
        if word in word_lists.get("strong_modal", set()):
            counts["strong_modal"] += 1
        if word in word_lists.get("weak_modal", set()):
            counts["weak_modal"] += 1
        if word in word_lists.get("uncertainty", set()):
            counts["uncertainty"] += 1
    
    # Calculate derived metrics
    counts["net_tone"] = counts["positive"] - counts["negative"]
    counts["total_sentiment_words"] = counts["positive"] + counts["negative"]
    
    # Tone ratio (avoid division by zero)
    if counts["total_sentiment_words"] > 0:
        counts["tone_ratio"] = counts["positive"] / counts["total_sentiment_words"]
    else:
        counts["tone_ratio"] = 0
    
    return counts

# ===========================================
# STEP 6: Process All Report Files in the Single Folder
# ===========================================
print("\n" + "=" * 70)
print("PROCESSING COMPANY REPORTS")
print("=" * 70)
print(f"Reports folder: {REPORTS_FOLDER}\n")

if not os.path.exists(REPORTS_FOLDER):
    print(f"❌ ERROR: Reports folder not found: {REPORTS_FOLDER}")
    print("Please update the REPORTS_FOLDER path in the code.")
    input("\nPress Enter to exit...")
    exit()

# Get all .txt files in the folder
txt_files = [f for f in os.listdir(REPORTS_FOLDER) if f.endswith('.txt')]
print(f"Found {len(txt_files)} .txt files to process\n")

results = []

for idx, filename in enumerate(txt_files, 1):
    file_path = os.path.join(REPORTS_FOLDER, filename)
    
    # Extract company name and year from filename
    company, year = extract_company_and_year(filename)
    
    # Clean filename (remove .txt)
    clean_name = os.path.splitext(filename)[0]
    
    print(f"[{idx}/{len(txt_files)}] 📄 Processing: {filename}")
    print(f"   Company: {company}, Year: {year}")
    
    # Analyze the file
    counts = analyze_text_file(file_path, word_lists)
    
    if counts:
        # Store results
        result = {
            "Company": company,
            "Year": year,
            "File_Name": clean_name,
            "Total_Words_Raw": counts["total_words_raw"],
            "Total_Words_Clean": counts["total_words_clean"],
            "Positive_Words": counts["positive"],
            "Negative_Words": counts["negative"],
            "Net_Tone": counts["net_tone"],
            "Tone_Ratio": round(counts["tone_ratio"], 4),
            "Complexity_Words": counts["complexity"],
            "Constraining_Words": counts["constraining"],
            "Litigious_Words": counts["litigious"],
            "Strong_Modal_Words": counts["strong_modal"],
            "Weak_Modal_Words": counts["weak_modal"],
            "Uncertainty_Words": counts["uncertainty"]
        }
        results.append(result)
        
        # Print summary for this file
        print(f"   📊 Pos:{counts['positive']} | Neg:{counts['negative']} | Net:{counts['net_tone']}")
        print(f"      Complex:{counts['complexity']} | Constrain:{counts['constraining']} | Litigious:{counts['litigious']}")
        print(f"      Strong:{counts['strong_modal']} | Weak:{counts['weak_modal']} | Uncertain:{counts['uncertainty']}")
    else:
        print(f"   ❌ Failed to analyze file")
    
    print()  # Empty line for readability

print("=" * 70)

# ===========================================
# STEP 7: Save Results to Excel
# ===========================================
if results:
    df = pd.DataFrame(results)
    
    # Create Excel with two sheets
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Raw_Data', index=False)
        
        # Create summary by company
        summary = df.groupby('Company').agg({
            'Net_Tone': 'mean',
            'Tone_Ratio': 'mean',
            'Positive_Words': 'mean',
            'Negative_Words': 'mean',
            'Complexity_Words': 'mean',
            'Constraining_Words': 'mean',
            'Litigious_Words': 'mean',
            'Strong_Modal_Words': 'mean',
            'Weak_Modal_Words': 'mean',
            'Uncertainty_Words': 'mean',
            'Total_Words_Clean': 'mean'
        }).round(2)
        
        summary.columns = [f'Avg_{col}' for col in summary.columns]
        summary['Number_of_Files'] = df.groupby('Company').size()
        summary.to_excel(writer, sheet_name='Company_Summary')
    
    print(f"\n✅ Results saved to: {OUTPUT_EXCEL}")
    
    print("\n" + "=" * 70)
    print("SUMMARY BY COMPANY (Averages per file)")
    print("=" * 70)
    print(summary.to_string())
    
    # Print top 5 companies by Net Tone
    print("\n" + "=" * 70)
    print("TOP 5 COMPANIES BY AVERAGE NET TONE")
    print("=" * 70)
    top_companies = summary.nlargest(5, 'Avg_Net_Tone')[['Avg_Net_Tone', 'Number_of_Files']]
    print(top_companies)
    
else:
    print("\n❌ No text files found to analyze or all files failed to process.")

print("\n" + "=" * 70)
print("Analysis Complete!")
print("=" * 70)

input("\nPress Enter to exit...")