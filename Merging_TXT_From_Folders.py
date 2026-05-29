import os
import shutil

# === CHANGE THESE TWO PATHS ===
source_folder = r"brsr_333_txt_outputs"  # Your main folder with company subfolders
destination_folder = r"D:\Python Annual Report\BRSR 333_txt_outputs_combine"  # New folder for all .txt files

# Create destination folder if it doesn't exist
os.makedirs(destination_folder, exist_ok=True)

# Track copied files
copied_files = []

# Walk through all subfolders
for company_folder in os.listdir(source_folder):
    company_path = os.path.join(source_folder, company_folder)
    
    # Check if it's a directory
    if os.path.isdir(company_path):
        # Look for all .txt files in this company folder
        for filename in os.listdir(company_path):
            if filename.lower().endswith(".txt"):
                source_file = os.path.join(company_path, filename)
                destination_file = os.path.join(destination_folder, filename)  # ← NO company prefix
                
                # Handle duplicate filenames (if two companies have same filename)
                counter = 1
                while os.path.exists(destination_file):
                    name_without_ext = os.path.splitext(filename)[0]
                    ext = os.path.splitext(filename)[1]
                    destination_file = os.path.join(destination_folder, f"{name_without_ext}_{counter}{ext}")
                    counter += 1
                
                # Copy the .txt file
                shutil.copy2(source_file, destination_file)
                copied_files.append(destination_file)
                print(f"Copied: {filename}")

print(f"\n✅ Copied {len(copied_files)} .txt files to: {destination_folder}")