import os
import re
import PyPDF2
import pandas as pd
from pathlib import Path
import fitz  # PyMuPDF
from typing import Dict, List, Tuple, Optional
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('brsr_extraction.log'),
        logging.StreamHandler()
    ]
)

class BRSRExtractor:
    """Extract BRSR sections from annual reports"""
    
    def __init__(self, brsr_template_path: str, output_folder: str):
        """
        Initialize the BRSR extractor
        
        Args:
            brsr_template_path: Path to BRSR format PDF template
            output_folder: Folder to save extracted BRSR sections
        """
        self.brsr_template_path = brsr_template_path
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Define BRSR section patterns (these work without a template)
        self.brsr_patterns = {
            'Principle 1': r'(?:Principle|Section)\s*[1I][:\s\-]*(?:Business\s*Ethics|Conduct|Governance)',
            'Principle 2': r'(?:Principle|Section)\s*2[:\s\-]*(?:Product|Service|Quality|Safety)',
            'Principle 3': r'(?:Principle|Section)\s*3[:\s\-]*(?:Employees|Wellbeing|Welfare|Workforce)',
            'Principle 4': r'(?:Principle|Section)\s*4[:\s\-]*(?:Stakeholders|Inclusive|Value\s*Chain)',
            'Principle 5': r'(?:Principle|Section)\s*5[:\s\-]*(?:Human\s*Rights|Diversity|Inclusion)',
            'Principle 6': r'(?:Principle|Section)\s*6[:\s\-]*(?:Environment|Pollution|Waste|Resource)',
            'Principle 7': r'(?:Principle|Section)\s*7[:\s\-]*(?:Policy|Public|Advocacy|Enforcement)',
            'Principle 8': r'(?:Principle|Section)\s*8[:\s\-]*(?:Technology|Access|Digital|Innovation)',
            'Principle 9': r'(?:Principle|Section)\s*9[:\s\-]*(?:Value\s*Chain|Customers|Suppliers)',
            'BRSR': r'BRSR|Business Responsibility and Sustainability Reporting',
            'BRR': r'Business Responsibility Report',
            'Section A': r'Section\s*A[:\s\-].*?(?:General|Disclosures)',
            'Section B': r'Section\s*B[:\s\-].*?(?:Management|Process)',
            'Section C': r'Section\s*C[:\s\-].*?(?:Principle|Performance)'
        }
        
        # Compile regex patterns
        self.compiled_patterns = {
            key: re.compile(pattern, re.IGNORECASE) 
            for key, pattern in self.brsr_patterns.items()
        }
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            logging.error(f"Error extracting text from {pdf_path}: {str(e)}")
            return ""
    
    def find_brsr_sections(self, text: str) -> Dict[str, Tuple[int, str]]:
        """
        Find BRSR sections in the text and return their page numbers and content
        
        Returns:
            Dictionary with section names and tuple of (line_number, content_snippet)
        """
        sections_found = {}
        lines = text.split('\n')
        
        for section_name, pattern in self.compiled_patterns.items():
            for i, line in enumerate(lines):
                if pattern.search(line):
                    # Get surrounding context (10 lines before and after)
                    start = max(0, i - 10)
                    end = min(len(lines), i + 20)
                    context = '\n'.join(lines[start:end])
                    sections_found[section_name] = (i, context)
                    break
                    
        return sections_found
    
    def identify_brsr_pages(self, doc: fitz.Document) -> List[int]:
        """Identify pages that contain BRSR content"""
        brsr_pages = set()
        
        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text()
            
            # Check for BRSR keywords on this page
            for pattern in self.compiled_patterns.values():
                if pattern.search(page_text):
                    brsr_pages.add(page_num)
                    break
            
            # Additional check for BRSR table formats
            if 'Principle' in page_text and ('Page' in page_text or 'Parameter' in page_text):
                brsr_pages.add(page_num)
            elif 'BRSR' in page_text and ('Table' in page_text or 'Indicator' in page_text):
                brsr_pages.add(page_num)
        
        return sorted(list(brsr_pages))
    
    def extract_brsr_pages(self, pdf_path: str, output_path: str) -> bool:
        """
        Extract BRSR pages from PDF based on content detection
        
        Returns:
            Boolean indicating if extraction was successful
        """
        try:
            doc = fitz.open(pdf_path)
            text = self.extract_text_from_pdf(pdf_path)
            
            # Find BRSR sections
            sections = self.find_brsr_sections(text)
            
            if not sections:
                logging.warning(f"No BRSR sections found in {pdf_path}")
                doc.close()
                return False
            
            # Identify pages with BRSR content
            brsr_pages = self.identify_brsr_pages(doc)
            
            if not brsr_pages:
                logging.warning(f"Could not identify specific BRSR pages in {pdf_path}")
                doc.close()
                return False
            
            # Add surrounding pages to ensure complete sections
            pages_to_extract = set()
            for page_num in brsr_pages:
                pages_to_extract.add(page_num)
                # Add previous and next pages if they exist
                if page_num > 0:
                    pages_to_extract.add(page_num - 1)
                if page_num < len(doc) - 1:
                    pages_to_extract.add(page_num + 1)
            
            # Create new PDF with BRSR pages
            new_doc = fitz.open()
            for page_num in sorted(pages_to_extract):
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            new_doc.save(output_path)
            new_doc.close()
            doc.close()
            
            logging.info(f"Successfully extracted {len(pages_to_extract)} BRSR pages to {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error extracting BRSR from {pdf_path}: {str(e)}")
            return False
    
    def process_annual_reports(self, reports_folder: str) -> pd.DataFrame:
        """
        Process all annual reports in a folder
        
        Args:
            reports_folder: Path to folder containing annual reports
        
        Returns:
            DataFrame with extraction results
        """
        reports_path = Path(reports_folder)
        pdf_files = list(reports_path.glob("*.pdf"))
        
        if not pdf_files:
            logging.error(f"No PDF files found in {reports_folder}")
            return pd.DataFrame()
        
        results = []
        
        for pdf_file in tqdm(pdf_files, desc="Processing annual reports"):
            company_name = pdf_file.stem
            # Clean filename for Windows
            company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name)
            output_pdf = self.output_folder / f"{company_name}_BRSR.pdf"
            
            try:
                success = self.extract_brsr_pages(str(pdf_file), str(output_pdf))
                
                results.append({
                    'Company Name': company_name,
                    'Original File': pdf_file.name,
                    'BRSR Extracted': 'Yes' if success else 'No',
                    'Output File': output_pdf.name if success else 'N/A',
                    'Extraction Status': 'Success' if success else 'Failed',
                    'Remarks': '' if success else 'No BRSR section found or extraction failed'
                })
                
            except Exception as e:
                logging.error(f"Error processing {pdf_file.name}: {str(e)}")
                results.append({
                    'Company Name': company_name,
                    'Original File': pdf_file.name,
                    'BRSR Extracted': 'No',
                    'Output File': 'N/A',
                    'Extraction Status': 'Error',
                    'Remarks': str(e)[:100]
                })
        
        return pd.DataFrame(results)
    
    def save_results_excel(self, results_df: pd.DataFrame, excel_path: str):
        """Save extraction results to Excel file"""
        excel_path = Path(excel_path)
        excel_path.parent.mkdir(parents=True, exist_ok=True)
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            results_df.to_excel(writer, sheet_name='BRSR Extraction Status', index=False)
            
            # Adjust column widths
            worksheet = writer.sheets['BRSR Extraction Status']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logging.info(f"Results saved to {excel_path}")


def main():
    """Main function to run the BRSR extraction process"""
    
    # Configuration - UPDATE THESE PATHS
    CONFIG = {
        'brsr_template_path': r"C:\Users\adhik\OneDrive\Desktop\Research Papers\BRSR-SEBI\Annexure_II-BRSR Reporting Format.PDF",  # Remove the extra quote
        'reports_folder': r"D:\Python Annual Report\BRSR 333 + Top 83 Companies",  # Update this to your reports folder
        'output_folder': r"D:\Python Annual Report\Extracted_BRSR",
        'excel_output': r"D:\Python Annual Report\BRSR_Extraction_Status.xlsx"
    }
    
    # Check if BRSR template exists (optional - not strictly required)
    if not os.path.exists(CONFIG['brsr_template_path']):
        logging.warning(f"BRSR template not found at {CONFIG['brsr_template_path']}")
        logging.info("Continuing without template - using pattern matching only")
        # Don't create dummy file, just continue
    else:
        logging.info(f"Found BRSR template at {CONFIG['brsr_template_path']}")
    
    # Check if reports folder exists
    if not os.path.exists(CONFIG['reports_folder']):
        logging.error(f"Reports folder not found at {CONFIG['reports_folder']}")
        logging.info("Please create the folder or update the path in CONFIG")
        return
    
    # Initialize extractor (template is optional)
    extractor = BRSRExtractor(
        brsr_template_path=CONFIG['brsr_template_path'],
        output_folder=CONFIG['output_folder']
    )
    
    # Process annual reports
    logging.info("Starting BRSR extraction from annual reports...")
    results_df = extractor.process_annual_reports(CONFIG['reports_folder'])
    
    # Save results
    if not results_df.empty:
        extractor.save_results_excel(results_df, CONFIG['excel_output'])
        
        # Print summary
        logging.info("\n" + "="*50)
        logging.info("EXTRACTION SUMMARY")
        logging.info("="*50)
        logging.info(f"Total reports processed: {len(results_df)}")
        logging.info(f"Successfully extracted: {len(results_df[results_df['BRSR Extracted'] == 'Yes'])}")
        logging.info(f"Failed to extract: {len(results_df[results_df['BRSR Extracted'] == 'No'])}")
        logging.info(f"Results saved to: {CONFIG['excel_output']}")
        logging.info(f"Extracted BRSR files saved to: {CONFIG['output_folder']}")
    else:
        logging.error("No results to save. Please check your input folder and try again.")


if __name__ == "__main__":
    main()