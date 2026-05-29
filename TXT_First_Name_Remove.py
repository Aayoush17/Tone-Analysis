import os
import shutil
from pathlib import Path

# ===========================================
# CONFIGURATION - Edit these two paths
# ===========================================
INPUT_FOLDER = r"D:\Python Annual Report\Noise Remove_txt"  # Folder with original files
OUTPUT_FOLDER = r"D:\Python Annual Report\Renamed Noise Remove_txt"       # Folder for renamed files

# ===========================================
# Create output folder if it doesn't exist
# ===========================================
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ===========================================
# Process each file
# ===========================================
renamed_count = 0
skipped_count = 0

for filename in os.listdir(INPUT_FOLDER):
    if filename.endswith(".txt"):
        # Original filename: "AARTIND_AARTIND_Annual Report_2023-24.txt"
        # Remove everything before the first underscore
        
        # Find the position of first underscore
        if "_" in filename:
            # Remove first part: "AARTIND_" → keep "AARTIND_Annual Report_2023-24.txt"
            new_filename = filename.split("_", 1)[1]
            
            # Source and destination paths
            source_path = os.path.join(INPUT_FOLDER, filename)
            destination_path = os.path.join(OUTPUT_FOLDER, new_filename)
            
            # Handle duplicate filenames
            counter = 1
            original_dest = destination_path
            while os.path.exists(destination_path):
                name_without_ext = os.path.splitext(new_filename)[0]
                ext = os.path.splitext(new_filename)[1]
                destination_path = os.path.join(OUTPUT_FOLDER, f"{name_without_ext}_dup{counter}{ext}")
                counter += 1
            
            # Copy the file with new name
            shutil.copy2(source_path, destination_path)
            renamed_count += 1
            print(f"✓ {filename} → {os.path.basename(destination_path)}")
        else:
            # No underscore found, just copy as is
            source_path = os.path.join(INPUT_FOLDER, filename)
            destination_path = os.path.join(OUTPUT_FOLDER, filename)
            shutil.copy2(source_path, destination_path)
            skipped_count += 1
            print(f"? {filename} (no underscore, copied as is)")

# ===========================================
# Summary
# ===========================================
print("\n" + "=" * 60)
print(f"✅ Renamed and copied: {renamed_count} files")
print(f"📁 Output folder: {OUTPUT_FOLDER}")
print("=" * 60)