import os
import re
import pandas as pd
from pathlib import Path
import fitz  # PyMuPDF
from typing import Dict, List, Tuple, Optional, Set
import logging
from tqdm import tqdm
import json
from collections import OrderedDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('brsr_extraction.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class BRSRFormatReader:
    """Read and understand BRSR/BRR format from template PDF"""
    
    def __init__(self, template_path: str):
        self.template_path = template_path
        self.brsr_structure = {}
        self.brr_structure = {}
        
    def extract_template_structure(self) -> Dict:
        """Extract the structure of BRSR/BRR from template"""
        try:
            doc = fitz.open(self.template_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()
            
            # Identify BRSR structure
            structure = {
                'principles': [],
                'sections': [],
                'keywords': [],
                'table_headers': [],
                'section_patterns': {}
            }
            
            # Look for Principle patterns
            principle_pattern = r'Principle\s*(\d+)\s*[:\-]\s*([^\n]+)'
            principles = re.findall(principle_pattern, full_text, re.IGNORECASE)
            structure['principles'] = [(num, text.strip()) for num, text in principles]
            
            # Look for Section patterns
            section_pattern = r'Section\s*([A-C])\s*[:\-]\s*([^\n]+)'
            sections = re.findall(section_pattern, full_text, re.IGNORECASE)
            structure['sections'] = [(sec, text.strip()) for sec, text in sections]
            
            # Extract key BRSR indicators and headers
            lines = full_text.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['indicator', 'parameter', 'disclosure', 'response']):
                    structure['keywords'].append(line.strip())
                
                # Look for table structures
                if '|' in line or 'table' in line.lower():
                    structure['table_headers'].append(line.strip())
            
            # Create section patterns for precise matching
            for principle_num, principle_text in structure['principles']:
                structure['section_patterns'][f'Principle_{principle_num}'] = {
                    'pattern': rf'Principle\s*{principle_num}[:\s-]+{re.escape(principle_text[:50])}',
                    'title': principle_text
                }
            
            for section, section_text in structure['sections']:
                structure['section_patterns'][f'Section_{section}'] = {
                    'pattern': rf'Section\s*{section}[:\s-]+{re.escape(section_text[:50])}',
                    'title': section_text
                }
            
            logging.info(f"Extracted BRSR structure: {len(structure['principles'])} principles, {len(structure['sections'])} sections")
            return structure
            
        except Exception as e:
            logging.error(f"Error reading template: {str(e)}")
            return self.get_default_structure()
    
    def get_default_structure(self) -> Dict:
        """Return default BRSR structure if template reading fails"""
        return {
            'principles': [(str(i), f"Principle {i}") for i in range(1, 10)],
            'sections': [('A', 'General Disclosures'), ('B', 'Management and Process'), ('C', 'Principle-wise Performance')],
            'keywords': ['BRSR', 'Business Responsibility', 'Sustainability Report', 'ESG', 'Principle', 'Indicator'],
            'table_headers': ['Parameter', 'Disclosure', 'Response', 'Page Reference'],
            'section_patterns': {
                **{f'Principle_{i}': {'pattern': rf'Principle\s*{i}[:\s-]', 'title': f'Principle {i}'} for i in range(1, 10)},
                **{f'Section_{s}': {'pattern': rf'Section\s*{s}[:\s-]', 'title': f'Section {s}'} for s in ['A', 'B', 'C']}
            }
        }


class BRSRExtractor:
    """Extract BRSR/BRR sections from annual reports"""
    
    def __init__(self, template_path: str, output_folder: str):
        self.template_reader = BRSRFormatReader(template_path)
        self.brsr_structure = self.template_reader.extract_template_structure()
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Compile patterns from template
        self.compiled_patterns = self._compile_patterns()
        
        # Patterns for BRR (older format)
        self.brr_patterns = {
            'BRR': r'Business Responsibility Report',
            'BRR_Section_A': r'Section\s*A[:\s-].*?General',
            'BRR_Section_B': r'Section\s*B[:\s-].*?Principle',
            'BRR_Principles': r'Principle\s*[1-9][:\s-]'
        }
        
    def _compile_patterns(self) -> Dict:
        """Compile regex patterns from template structure"""
        patterns = {}
        
        # Add patterns from template
        for section_name, section_info in self.brsr_structure['section_patterns'].items():
            patterns[section_name] = re.compile(section_info['pattern'], re.IGNORECASE)
        
        # Add additional BRSR patterns
        patterns['BRSR_Main'] = re.compile(r'BRSR|Business Responsibility and Sustainability Reporting', re.IGNORECASE)
        patterns['BRR_Main'] = re.compile(r'Business Responsibility Report', re.IGNORECASE)
        
        # Add patterns for key indicators
        for keyword in self.brsr_structure['keywords'][:10]:
            patterns[f'Keyword_{keyword[:20]}'] = re.compile(re.escape(keyword), re.IGNORECASE)
        
        return patterns
    
    def extract_brsr_from_template(self) -> Dict:
        """Extract exact BRSR format from template for precise matching"""
        try:
            doc = fitz.open(self.template_reader.template_path)
            template_pages = []
            
            for page_num in range(len(doc)):
                page_text = doc[page_num].get_text()
                template_pages.append({
                    'page_num': page_num,
                    'text': page_text,
                    'has_principle': any(re.search(rf'Principle\s*{i}', page_text, re.IGNORECASE) for i in range(1, 10)),
                    'has_section': any(re.search(rf'Section\s*{s}', page_text, re.IGNORECASE) for s in ['A', 'B', 'C'])
                })
            
            doc.close()
            
            # Identify which pages contain BRSR content in template
            brsr_template_pages = [p for p in template_pages if p['has_principle'] or p['has_section']]
            
            # Extract sample text patterns from template
            sample_patterns = []
            for page in brsr_template_pages[:3]:  # First few pages of BRSR template
                lines = page['text'].split('\n')
                for line in lines[:50]:  # First 50 lines of each page
                    if len(line.strip()) > 20 and any(p in line for p in ['Principle', 'Section', 'Indicator']):
                        sample_patterns.append(line.strip())
            
            return {
                'template_pages': len(brsr_template_pages),
                'sample_patterns': sample_patterns,
                'has_principles': any(p['has_principle'] for p in brsr_template_pages),
                'has_sections': any(p['has_section'] for p in brsr_template_pages)
            }
            
        except Exception as e:
            logging.error(f"Error extracting from template: {str(e)}")
            return {'template_pages': 0, 'sample_patterns': [], 'has_principles': True, 'has_sections': True}
    
    def find_brsr_in_annual_report(self, pdf_path: str, year: str) -> Tuple[Optional[List[int]], str]:
        """Find BRSR/BRR pages in annual report"""
        try:
            doc = fitz.open(pdf_path)
            brsr_pages = set()
            report_type = None  # 'BRSR' or 'BRR'
            
            # Get template structure info
            template_info = self.extract_brsr_from_template()
            
            for page_num in range(len(doc)):
                page_text = doc[page_num].get_text()
                
                # Check for BRSR indicators
                has_brsr = False
                
                # Check if page matches BRSR template patterns
                for pattern_name, pattern in self.compiled_patterns.items():
                    if pattern.search(page_text):
                        has_brsr = True
                        if 'BRSR' in pattern_name or 'BRR' in pattern_name:
                            report_type = 'BRSR' if 'BRSR' in pattern_name else 'BRR'
                        break
                
                # Check for Principle patterns (1-9)
                for i in range(1, 10):
                    if re.search(rf'Principle\s*{i}[:\s-]', page_text, re.IGNORECASE):
                        has_brsr = True
                        if not report_type:
                            # Determine if it's BRSR or BRR based on context
                            if 'Sustainability' in page_text or 'ESG' in page_text:
                                report_type = 'BRSR'
                            else:
                                report_type = 'BRR'
                        break
                
                # Check for Section patterns (A, B, C)
                for section in ['A', 'B', 'C']:
                    if re.search(rf'Section\s*{section}[:\s-]', page_text, re.IGNORECASE):
                        has_brsr = True
                        break
                
                # Check for BRSR/BRR specific keywords
                if any(keyword in page_text for keyword in ['BRSR', 'Business Responsibility and Sustainability', 'BRR', 'Business Responsibility Report']):
                    has_brsr = True
                    report_type = 'BRSR' if 'BRSR' in page_text or 'Sustainability' in page_text else 'BRR'
                
                # Check for table indicators common in BRSR
                if any(indicator in page_text for indicator in ['Parameter', 'Disclosure', 'Response', 'Page Reference']):
                    # Verify it's part of BRSR by checking surrounding content
                    if any(principle in page_text for principle in [f'Principle {i}' for i in range(1, 10)]):
                        has_brsr = True
                
                if has_brsr:
                    brsr_pages.add(page_num)
            
            doc.close()
            
            if not brsr_pages:
                return None, 'Not Found'
            
            # Find continuous blocks of BRSR pages
            sorted_pages = sorted(brsr_pages)
            continuous_blocks = []
            current_block = [sorted_pages[0]]
            
            for i in range(1, len(sorted_pages)):
                if sorted_pages[i] == sorted_pages[i-1] + 1:
                    current_block.append(sorted_pages[i])
                else:
                    if len(current_block) >= 2:  # At least 2 pages for a valid BRSR section
                        continuous_blocks.append(current_block)
                    current_block = [sorted_pages[i]]
            
            if len(current_block) >= 2:
                continuous_blocks.append(current_block)
            
            # Select the largest continuous block as the BRSR section
            if continuous_blocks:
                largest_block = max(continuous_blocks, key=len)
                return largest_block, report_type if report_type else 'BRSR'
            else:
                # If no continuous block of 2+ pages, return all pages
                return list(brsr_pages), report_type if report_type else 'BRSR'
                
        except Exception as e:
            logging.error(f"Error finding BRSR in {pdf_path}: {str(e)}")
            return None, 'Error'
    
    def extract_pages_from_pdf(self, pdf_path: str, pages: List[int], output_path: str) -> bool:
        """Extract specific pages from PDF"""
        try:
            doc = fitz.open(pdf_path)
            new_doc = fitz.open()
            
            # Add pages before and after to ensure complete sections
            pages_to_extract = set()
            for page in pages:
                pages_to_extract.add(page)
                # Add one page before and after for context
                if page > 0:
                    pages_to_extract.add(page - 1)
                if page < len(doc) - 1:
                    pages_to_extract.add(page + 1)
            
            for page_num in sorted(pages_to_extract):
                if 0 <= page_num < len(doc):
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            new_doc.save(output_path)
            new_doc.close()
            doc.close()
            
            return True
            
        except Exception as e:
            logging.error(f"Error extracting pages: {str(e)}")
            return False
    
    def extract_year_from_filename(self, filename: str) -> str:
        """Extract year from filename"""
        # Pattern for years like 2021-22, 2022-23, etc.
        year_pattern = r'(\d{4}-\d{2})'
        match = re.search(year_pattern, filename)
        if match:
            return match.group(1)
        
        # Pattern for single year
        year_pattern2 = r'(\d{4})'
        match = re.search(year_pattern2, filename)
        if match:
            return match.group(1)
        
        return "Unknown"
    
    def process_annual_reports(self, reports_folder: str) -> pd.DataFrame:
        """Process all annual reports in folder"""
        reports_path = Path(reports_folder)
        pdf_files = list(reports_path.glob("*.pdf"))
        
        if not pdf_files:
            logging.error(f"No PDF files found in {reports_folder}")
            return pd.DataFrame()
        
        results = []
        
        for pdf_file in tqdm(pdf_files, desc="Processing annual reports"):
            company_name = pdf_file.stem
            # Extract company name (remove annual report and year)
            company_clean = re.sub(r'_Annual[_\s]Report.*$', '', company_name, flags=re.IGNORECASE)
            company_clean = re.sub(r'_\d{4}-\d{2}$', '', company_clean)
            
            year = self.extract_year_from_filename(pdf_file.name)
            
            # Find BRSR/BRR pages
            brsr_pages, report_type = self.find_brsr_in_annual_report(str(pdf_file), year)
            
            if brsr_pages and len(brsr_pages) > 0:
                # Save extracted BRSR
                output_filename = f"{company_clean}_{year}_{report_type}.pdf"
                output_path = self.output_folder / output_filename
                
                success = self.extract_pages_from_pdf(str(pdf_file), brsr_pages, str(output_path))
                
                if success:
                    results.append({
                        'Company Name': company_clean,
                        'Year': year,
                        'Original File': pdf_file.name,
                        'Report Type': report_type,
                        'Pages Extracted': len(brsr_pages),
                        'Extraction Status': 'Success',
                        'Output File': output_filename,
                        'BRSR/BRR Found': 'Yes'
                    })
                    logging.info(f"Successfully extracted {report_type} from {company_clean} ({year}) - {len(brsr_pages)} pages")
                else:
                    results.append({
                        'Company Name': company_clean,
                        'Year': year,
                        'Original File': pdf_file.name,
                        'Report Type': report_type,
                        'Pages Extracted': 0,
                        'Extraction Status': 'Failed',
                        'Output File': 'N/A',
                        'BRSR/BRR Found': 'Partial'
                    })
            else:
                results.append({
                    'Company Name': company_clean,
                    'Year': year,
                    'Original File': pdf_file.name,
                    'Report Type': 'None',
                    'Pages Extracted': 0,
                    'Extraction Status': 'Not Found',
                    'Output File': 'N/A',
                    'BRSR/BRR Found': 'No'
                })
                logging.warning(f"No BRSR/BRR found in {pdf_file.name}")
        
        return pd.DataFrame(results)
    
    def save_results_excel(self, results_df: pd.DataFrame, excel_path: str):
        """Save extraction results to Excel with detailed sheets"""
        excel_path = Path(excel_path)
        excel_path.parent.mkdir(parents=True, exist_ok=True)
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Summary sheet
            summary = results_df.groupby(['Year', 'Report Type']).agg({
                'BRSR/BRR Found': 'count',
                'Extraction Status': lambda x: (x == 'Success').sum()
            }).reset_index()
            summary.columns = ['Year', 'Report Type', 'Total Files', 'Successfully Extracted']
            summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Detailed results
            results_df.to_excel(writer, sheet_name='Detailed Results', index=False)
            
            # Companies with missing BRSR
            missing = results_df[results_df['BRSR/BRR Found'] == 'No'][['Company Name', 'Year', 'Original File']]
            missing.to_excel(writer, sheet_name='Missing BRSR/BRR', index=False)
            
            # Adjust column widths for all sheets
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
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
    """Main function to run BRSR extraction"""
    
    # Configuration - UPDATE THESE PATHS
    CONFIG = {
        'brsr_template_path': r"C:\Users\adhik\OneDrive\Desktop\Research Papers\BRSR-SEBI\Annexure_II-BRSR Reporting Format.PDF",
        'reports_folder': r"D:\Python Annual Report\BRSR 333 + Top 83 Companies",
        'output_folder': r"D:\Python Annual Report\Extracted_BRSR",
        'excel_output': r"D:\Python Annual Report\BRSR_Extraction_Status.xlsx"
    }
    
    # Validate paths
    if not os.path.exists(CONFIG['brsr_template_path']):
        logging.error(f"BRSR template not found at {CONFIG['brsr_template_path']}")
        logging.info("Please ensure the BRSR format PDF exists at this path")
        return
    
    if not os.path.exists(CONFIG['reports_folder']):
        logging.error(f"Reports folder not found at {CONFIG['reports_folder']}")
        logging.info("Please create the folder or update the path in CONFIG")
        return
    
    # Initialize extractor with template
    logging.info("Initializing BRSR extractor with template...")
    extractor = BRSRExtractor(
        template_path=CONFIG['brsr_template_path'],
        output_folder=CONFIG['output_folder']
    )
    
    # Extract and display template information
    template_info = extractor.extract_brsr_from_template()
    logging.info(f"Template analysis: {template_info['template_pages']} pages with BRSR content")
    if template_info['sample_patterns']:
        logging.info(f"Sample patterns from template: {template_info['sample_patterns'][:3]}")
    
    # Process annual reports
    logging.info("\nStarting BRSR/BRR extraction from annual reports...")
    results_df = extractor.process_annual_reports(CONFIG['reports_folder'])
    
    # Save results
    if not results_df.empty:
        extractor.save_results_excel(results_df, CONFIG['excel_output'])
        
        # Print detailed summary
        logging.info("\n" + "="*60)
        logging.info("EXTRACTION SUMMARY")
        logging.info("="*60)
        
        total_files = len(results_df)
        successful = len(results_df[results_df['Extraction Status'] == 'Success'])
        not_found = len(results_df[results_df['BRSR/BRR Found'] == 'No'])
        
        logging.info(f"Total annual reports processed: {total_files}")
        logging.info(f"Successfully extracted BRSR/BRR: {successful}")
        logging.info(f"BRSR/BRR not found: {not_found}")
        
        # Year-wise breakdown
        logging.info("\nYear-wise breakdown:")
        year_stats = results_df.groupby('Year').agg({
            'BRSR/BRR Found': lambda x: (x == 'Yes').sum(),
            'Extraction Status': lambda x: (x == 'Success').sum()
        }).reset_index()
        
        for _, row in year_stats.iterrows():
            logging.info(f"  {row['Year']}: {row['BRSR/BRR Found']} found, {row['Extraction Status']} extracted")
        
        # Report type breakdown
        logging.info("\nReport Type breakdown:")
        type_stats = results_df[results_df['BRSR/BRR Found'] == 'Yes'].groupby('Report Type').size()
        for report_type, count in type_stats.items():
            logging.info(f"  {report_type}: {count} files")
        
        logging.info(f"\nResults saved to: {CONFIG['excel_output']}")
        logging.info(f"Extracted BRSR/BRR files saved to: {CONFIG['output_folder']}")
        
        # List extracted files
        output_files = list(Path(CONFIG['output_folder']).glob("*.pdf"))
        if output_files:
            logging.info(f"\nExtracted files ({len(output_files)}):")
            for f in output_files[:10]:  # Show first 10
                logging.info(f"  - {f.name}")
            if len(output_files) > 10:
                logging.info(f"  ... and {len(output_files) - 10} more")
    else:
        logging.error("No results to save. Please check your input folder and try again.")


if __name__ == "__main__":
    main()