import os
import shutil
from pathlib import Path

def rename_annual_reports(input_folder, output_folder):
    """
    Rename PDF files by removing the first part before the first underscore.
    
    Example: "360ONE_360ONE_Annual Report_2021-22.pdf" 
    becomes: "360ONE_Annual Report_2021-22.pdf"
    
    Args:
        input_folder (str): Path to folder containing original PDF files
        output_folder (str): Path to folder where renamed files will be saved
    """
    
    # Convert to Path objects for easier handling
    input_path = Path(input_folder)  # Use the parameter, not hardcoded path
    output_path = Path(output_folder)  # Use the parameter, not hardcoded path
    
    # Check if input folder exists
    if not input_path.exists():
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return
    
    # Create output folder if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    print(f"Output folder created/verified at: {output_path}")
    
    # Counter for tracking operations
    renamed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Get all PDF files from input folder
    pdf_files = list(input_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in '{input_folder}'")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s) to process.\n")
    
    for pdf_file in pdf_files:
        try:
            # Get original filename without extension
            original_name = pdf_file.stem
            extension = pdf_file.suffix
            
            # Split by underscore and remove the first part
            parts = original_name.split('_')
            
            if len(parts) > 1:
                # Join from the second part onward
                new_name = '_'.join(parts[1:]) + extension
                
                # Source and destination paths
                source_path = pdf_file
                dest_path = output_path / new_name
                
                # Handle duplicate filenames in output folder
                counter = 1
                original_new_name = new_name
                while dest_path.exists():
                    # Add number suffix if file already exists
                    name_without_ext = Path(original_new_name).stem
                    new_name = f"{name_without_ext}_{counter}{extension}"
                    dest_path = output_path / new_name
                    counter += 1
                    if counter > 100:  # Safety break
                        break
                
                # Copy file to output folder with new name
                shutil.copy2(source_path, dest_path)
                
                print(f"✓ Renamed: '{pdf_file.name}' -> '{dest_path.name}'")
                renamed_count += 1
            else:
                # If no underscore found, just copy as is
                dest_path = output_path / pdf_file.name
                shutil.copy2(pdf_file, dest_path)
                print(f"⚠ Skipped (no underscore found): '{pdf_file.name}'")
                skipped_count += 1
                
        except Exception as e:
            print(f"✗ Error processing '{pdf_file.name}': {str(e)}")
            error_count += 1
    
    # Print summary
    print("\n" + "="*50)
    print("RENAMING COMPLETE")
    print("="*50)
    print(f"✓ Successfully renamed: {renamed_count} file(s)")
    print(f"⚠ Skipped: {skipped_count} file(s)")
    print(f"✗ Errors: {error_count} file(s)")
    print(f"📁 Output location: {output_path.absolute()}")
    print("="*50)

def main():
    """
    Main function to get user input and run the renaming process.
    """
    print("="*50)
    print("PDF ANNUAL REPORT RENAMING TOOL")
    print("="*50)
    print("This tool removes the duplicate company name from PDF filenames.")
    print("Example: '360ONE_360ONE_Annual Report_2021-22.pdf' ->")
    print("         '360ONE_Annual Report_2021-22.pdf'\n")
    
    # Get input folder path from user
    while True:
        input_folder = input("Enter input folder path: ").strip()
        if input_folder:
            break
        print("Please enter a valid folder path.")
    
    # Get output folder path from user
    while True:
        output_folder = input("Enter output folder path: ").strip()
        if output_folder:
            break
        print("Please enter a valid folder path.")
    
    print("\nProcessing...\n")
    
    # Run the renaming function
    rename_annual_reports(input_folder, output_folder)

if __name__ == "__main__":
    main()