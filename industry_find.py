import requests
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
from typing import Dict, Optional

class ScreenerIndustryFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.delay = 1  # Delay between requests to avoid being blocked
        
    def get_industry_info(self, ticker: str) -> Dict:
        """
        Fetch industry information for a given ticker from Screener.in
        """
        ticker = ticker.upper().strip()
        
        result = {
            'ticker': ticker,
            'company_name': 'Not Found',
            'sector': 'Not Found',
            'industry': 'Not Found',
            'sub_industry': 'Not Found',
            'status': 'Pending'
        }
        
        try:
            # Construct URL for the company page
            url = f'https://www.screener.in/company/{ticker}/'
            
            # Make the request
            response = self.session.get(url, timeout=30)
            
            # Check if page exists
            if response.status_code == 404:
                result['status'] = 'Company not found'
                return result
            elif response.status_code != 200:
                result['status'] = f'HTTP Error: {response.status_code}'
                return result
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract company name
            name_element = soup.find('h1', {'class': 'company'})
            if name_element:
                result['company_name'] = name_element.text.strip()
            
            # Method 1: Look for peer comparison section
            peer_section = soup.find('section', {'id': 'peer-comparison'})
            if peer_section:
                # Find all divs with company info in peer section
                peer_info = peer_section.find_all('div', {'class': 'company-info'})
                if peer_info:
                    info_text = peer_info[0].text
                    # Try to extract sector/industry using regex
                    sector_match = re.search(r'Sector[:\s]+([^\n]+)', info_text)
                    industry_match = re.search(r'Industry[:\s]+([^\n]+)', info_text)
                    
                    if sector_match:
                        result['sector'] = sector_match.group(1).strip()
                    if industry_match:
                        result['industry'] = industry_match.group(1).strip()
            
            # Method 2: Look for inline information in the page
            if result['sector'] == 'Not Found':
                # Look for any text containing "Sector" or "Industry"
                page_text = soup.get_text()
                
                # Try to find sector pattern
                sector_patterns = [
                    r'Sector\s*:\s*([^\n]+)',
                    r'Sector\s+([^\n]+)',
                    r'Industry\s*:\s*([^\n]+)',
                    r'Industry\s+([^\n]+)'
                ]
                
                for pattern in sector_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        if 'sector' in pattern.lower() and result['sector'] == 'Not Found':
                            result['sector'] = value
                        elif 'industry' in pattern.lower() and result['industry'] == 'Not Found':
                            result['industry'] = value
            
            # Method 3: Look for industry in any table or description
            if result['industry'] == 'Not Found' or result['sector'] == 'Not Found':
                # Find all tables and look for industry-related rows
                all_tables = soup.find_all('table')
                for table in all_tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        row_text = row.get_text().lower()
                        if 'sector' in row_text and result['sector'] == 'Not Found':
                            cells = row.find_all('td')
                            if len(cells) > 1:
                                result['sector'] = cells[1].text.strip()
                        elif 'industry' in row_text and result['industry'] == 'Not Found':
                            cells = row.find_all('td')
                            if len(cells) > 1:
                                result['industry'] = cells[1].text.strip()
            
            # Determine status
            if result['sector'] != 'Not Found' or result['industry'] != 'Not Found':
                result['status'] = 'Found'
            else:
                result['status'] = 'No industry data found'
                
        except requests.exceptions.RequestException as e:
            result['status'] = f'Request Error: {str(e)}'
        except Exception as e:
            result['status'] = f'Parse Error: {str(e)}'
        
        return result
    
    def process_tickers(self, tickers, input_file=None, ticker_column='Symbol', output_file='company_industries.xlsx'):
        """
        Process a list of tickers and save results to Excel
        
        Args:
            tickers: List of tickers OR path to Excel file
            input_file: Path to Excel file (if tickers is None)
            ticker_column: Column name in Excel file
            output_file: Output Excel file name
        """
        results = []
        
        # Load tickers from Excel if provided
        if input_file:
            print(f"📁 Reading tickers from {input_file}...")
            df_input = pd.read_excel(input_file)
            if ticker_column in df_input.columns:
                tickers = df_input[ticker_column].dropna().tolist()
                print(f"✅ Found {len(tickers)} tickers")
            else:
                print(f"❌ Column '{ticker_column}' not found!")
                print(f"Available columns: {df_input.columns.tolist()}")
                return None
        
        if not tickers:
            print("❌ No tickers to process")
            return None
        
        print(f"\n🔄 Processing {len(tickers)} tickers...")
        print("-" * 60)
        
        for i, ticker in enumerate(tickers):
            ticker = str(ticker).upper().strip()
            print(f"[{i+1}/{len(tickers)}] Fetching {ticker}...", end=" ", flush=True)
            
            # Get industry info
            result = self.get_industry_info(ticker)
            results.append(result)
            
            # Print status
            print(f"✅ {result['status']}" if result['status'] == 'Found' else f"❌ {result['status']}")
            
            # Add delay to avoid rate limiting
            if i < len(tickers) - 1:  # Don't delay after the last one
                time.sleep(self.delay)
        
        # Convert to DataFrame
        df_results = pd.DataFrame(results)
        
        # Reorder columns
        column_order = ['ticker', 'company_name', 'sector', 'industry', 'sub_industry', 'status']
        df_results = df_results[[col for col in column_order if col in df_results.columns]]
        
        # Save to Excel
        df_results.to_excel(output_file, index=False)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        found_count = len(df_results[df_results['status'] == 'Found'])
        print(f"Total tickers: {len(tickers)}")
        print(f"✅ Successfully found: {found_count}")
        print(f"❌ Not found: {len(tickers) - found_count}")
        print(f"Success rate: {(found_count/len(tickers)*100):.1f}%")
        print(f"\n💾 Results saved to: {output_file}")
        
        # Show samples
        print("\n📋 Sample Results (First 10 found):")
        print("-" * 80)
        sample = df_results[df_results['status'] == 'Found'].head(10)
        for _, row in sample.iterrows():
            print(f"{row['ticker']:15} | {row['sector']:30} | {row['industry']:30}")
        
        return df_results


# Alternative: Using a different approach - Direct API simulation
class ScreenerAlternativeAPI:
    """
    Alternative approach using Screener's company listing pages
    """
    
    @staticmethod
    def get_industry_from_nse_bse(ticker):
        """
        Fallback method using NSE/BSE data
        """
        # This is a fallback dictionary for common tickers
        fallback_data = {
            'JIOFIN': {'sector': 'Financial Services', 'industry': 'Financial Services', 'company_name': 'Jio Financial Services Ltd'},
            'RELIANCE': {'sector': 'Energy', 'industry': 'Oil, Gas & Consumable Fuels', 'company_name': 'Reliance Industries Ltd'},
            'TCS': {'sector': 'IT', 'industry': 'IT - Software', 'company_name': 'Tata Consultancy Services Ltd'},
            'INFY': {'sector': 'IT', 'industry': 'IT - Software', 'company_name': 'Infosys Ltd'},
            'HDFCBANK': {'sector': 'Financial Services', 'industry': 'Banks', 'company_name': 'HDFC Bank Ltd'},
            'ICICIBANK': {'sector': 'Financial Services', 'industry': 'Banks', 'company_name': 'ICICI Bank Ltd'},
            'ITC': {'sector': 'Consumer Goods', 'industry': 'Diversified', 'company_name': 'ITC Ltd'},
            'WIPRO': {'sector': 'IT', 'industry': 'IT - Software', 'company_name': 'Wipro Ltd'},
        }
        
        if ticker in fallback_data:
            result = fallback_data[ticker].copy()
            result['ticker'] = ticker
            result['status'] = 'Found (Fallback)'
            return result
        
        return {'ticker': ticker, 'status': 'Not in fallback database'}
    

# =============================================
# MAIN EXECUTION
# =============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🏢 Screener.in Industry Finder")
    print("=" * 60)
    
    # Initialize the finder
    finder = ScreenerIndustryFinder()
    
    # Configuration
    INPUT_FILE = r"D:\Python Annual Report\Industry Companies.xlsx"
    TICKER_COLUMN = "Symbol"  # Change this to match your column name
    OUTPUT_FILE = r"D:\Python Annual Report\companies_with_industries.xlsx"
    
    # Process tickers
    results = finder.process_tickers(
        tickers=None,  # Will be read from file
        input_file=INPUT_FILE,
        ticker_column=TICKER_COLUMN,
        output_file=OUTPUT_FILE
    )
    
    # If many tickers fail, try alternative method
    if results and len(results[results['status'] == 'Found']) < 50:
        print("\n⚠️ Low success rate detected! Trying alternative method for failed tickers...")
        
        # Get failed tickers
        failed_tickers = results[results['status'] != 'Found']['ticker'].tolist()
        
        if failed_tickers:
            print(f"Attempting fallback for {len(failed_tickers)} tickers...")
            
            alt_finder = ScreenerAlternativeAPI()
            alt_results = []
            
            for ticker in failed_tickers:
                result = alt_finder.get_industry_from_nse_bse(ticker)
                alt_results.append(result)
            
            # Convert to DataFrame
            df_alt = pd.DataFrame(alt_results)
            
            # Merge with original results
            results = results[results['status'] == 'Found']  # Keep successful ones
            results = pd.concat([results, df_alt], ignore_index=True)
            
            # Save updated results
            results.to_excel(OUTPUT_FILE.replace('.xlsx', '_with_fallback.xlsx'), index=False)
            print(f"💾 Updated results saved with fallback data")