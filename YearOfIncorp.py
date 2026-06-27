import os
import re
import pdfplumber
import pandas as pd

def extract_year_of_incorporation(pdf_path):
    """
    Extract Year of Incorporation from BRSR PDF report.
    Searches for patterns like "Year of Incorporation: 1996" or "3. Year of Incorporation 1996"
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + " "
            
            # Search patterns for Year of Incorporation
            patterns = [
                r'Year of Incorporation\s*[:.]?\s*(\d{4})',
                r'Incorporation\s*Year\s*[:.]?\s*(\d{4})',
                r'3\.\s*Year of Incorporation\s*[:.]?\s*(\d{4})',
                r'Year of Incorporation\s*-\s*(\d{4})',
                r'Incorporated\s*in\s*(\d{4})',
                r'Date of Incorporation\s*[:.]?\s*.*?(\d{4})',
                r'Incorporation Date\s*[:.]?\s*.*?(\d{4})',
                r'Year of incorporation\s*[:.]?\s*(\d{4})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            return "Not Found"
            
    except Exception as e:
        return f"Error: {str(e)}"

def process_brsr_reports(folder_path):
    """
    Process all PDF files ending with _2024-25.pdf and extract Year of Incorporation
    """
    results = []
    
    # Get all PDF files in folder
    all_files = os.listdir(folder_path)
    
    # Filter for _2024-25.pdf files only
    target_files = [f for f in all_files if f.endswith('_2024-25.pdf')]
    
    print(f"📂 Found {len(target_files)} BRSR 2024-25 reports")
    print("=" * 60)
    
    for filename in target_files:
        file_path = os.path.join(folder_path, filename)
        
        # Extract company name (remove _BRSR_2024-25.pdf)
        company_name = filename.replace('_BRSR_2024-25.pdf', '')
        
        print(f"📄 Processing: {company_name}")
        
        # Extract Year of Incorporation
        year = extract_year_of_incorporation(file_path)
        
        results.append({
            'Company Name': company_name,
            'Year of Incorporation': year
        })
        
        print(f"   ✅ Year of Incorporation: {year}")
        print("-" * 40)
    
    return results

def save_to_excel(results, output_file="BRSR_Year_of_Incorporation.xlsx"):
    """
    Save results to Excel file with two columns: Company Name and Year of Incorporation
    """
    # Create DataFrame with exactly two columns
    df = pd.DataFrame(results, columns=['Company Name', 'Year of Incorporation'])
    
    # Save to Excel
    df.to_excel(output_file, index=False, sheet_name='BRSR Data')
    
    print(f"\n✅ Excel file saved as: {output_file}")
    print(f"📊 Total companies processed: {len(results)}")
    
    return df

# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    # SET YOUR FOLDER PATH HERE
    FOLDER_PATH = r"D:\Python Annual Report\BRSR-BRR_Manual Combined PDF"
    
    # Alternative: Use file dialog to select folder
    # from tkinter import filedialog, Tk
    # root = Tk()
    # root.withdraw()
    # FOLDER_PATH = filedialog.askdirectory(title="Select folder with BRSR PDFs")
    
    # Process all reports
    results = process_brsr_reports(FOLDER_PATH)
    
    # Save to Excel
    df = save_to_excel(results)
    
    # Display preview
    print("\n📋 Preview of data:")
    print("=" * 50)
    print(df.to_string(index=False))
    
    # Summary statistics
    found = df[df['Year of Incorporation'] != 'Not Found'].shape[0]
    not_found = df[df['Year of Incorporation'] == 'Not Found'].shape[0]
    errors = df[df['Year of Incorporation'].str.startswith('Error', na=False)].shape[0]
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"Total files processed: {len(results)}")
    print(f"✅ Year found: {found}")
    print(f"❌ Not found: {not_found}")
    print(f"⚠️  Errors: {errors}")