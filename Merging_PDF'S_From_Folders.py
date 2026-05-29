import os
import shutil

# Define paths
source_folder = r"D:\BRSR 333"
destination_folder = r"D:\Merged PDF BRSR 333"

# Create destination folder if it doesn't exist
os.makedirs(destination_folder, exist_ok=True)

# Track copied files
copied_files = []

# Walk through all subfolders
for company_folder in os.listdir(source_folder):
    company_path = os.path.join(source_folder, company_folder)
    
    # Check if it's a directory
    if os.path.isdir(company_path):
        # Look for all .pdf files in this company folder
        for filename in os.listdir(company_path):
            if filename.lower().endswith(".pdf"):  # Case-insensitive check
                source_file = os.path.join(company_path, filename)
                
                # Create new filename with company prefix
                new_filename = f"{company_folder}_{filename}"
                destination_file = os.path.join(destination_folder, new_filename)
                
                # Handle duplicate filenames
                counter = 1
                while os.path.exists(destination_file):
                    name_without_ext = os.path.splitext(new_filename)[0]
                    ext = os.path.splitext(new_filename)[1]
                    destination_file = os.path.join(destination_folder, f"{name_without_ext}_{counter}{ext}")
                    counter += 1
                
                # Copy the PDF file
                shutil.copy2(source_file, destination_file)
                copied_files.append(destination_file)
                print(f"Copied: {new_filename}")

print(f"\n✅ Copied {len(copied_files)} PDF files to: {destination_folder}")

