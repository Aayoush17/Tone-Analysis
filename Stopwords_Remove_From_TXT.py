"""
Simple Stopword Remover
"""
import os
from pathlib import Path

# ==================================================
# CONFIGURE THESE PATHS
# ==================================================
INPUT_FOLDER = r"D:\Python Annual Report\Noise Removed_txt"      # Your input folder with .txt files
OUTPUT_FOLDER = r"D:\Python Annual Report\Noise_removed_stop_words_txt"      # Where to save cleaned files
STOPWORDS_FILE = r"D:\Python Annual Report\Moti Sir Sent Words and Tone Analysis Code\words\Stop.txt"  # Your stopwords file
# ==================================================

# Load stopwords
print("Loading stopwords...")
with open(STOPWORDS_FILE, 'r', encoding='utf-8') as f:
    stopwords = set(line.strip().lower() for line in f if line.strip() and not line.startswith('#'))

print(f"Loaded {len(stopwords)} stopwords")

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Process each txt file
txt_files = list(Path(INPUT_FOLDER).glob("*.txt")) + list(Path(INPUT_FOLDER).glob("*.TXT"))

print(f"\nFound {len(txt_files)} text files\n")

for txt_file in txt_files:
    print(f"Processing: {txt_file.name}")
    
    # Read file
    with open(txt_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Remove stopwords
    words = text.split()
    filtered_words = [word for word in words if word.lower() not in stopwords]
    cleaned_text = ' '.join(filtered_words)
    
    # Save cleaned file
    output_file = Path(OUTPUT_FOLDER) / f"{txt_file.stem}_cleaned.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)
    
    print(f"  Original: {len(words)} words → After: {len(filtered_words)} words")
    print(f"  Saved to: {output_file.name}\n")

print("Done!")