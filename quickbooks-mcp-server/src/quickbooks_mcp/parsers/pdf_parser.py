"""
PDF parser for extracting transaction data from bank statements, invoices, and receipts.
Uses pdfplumber for text extraction and pytesseract for OCR when needed.
"""
import logging
import re
from datetime import datetime
from typing import List, Dict, Any
import pdfplumber
from pathlib import Path

logger = logging.getLogger(__name__)


class PDFParser:
    """Parse PDF files to extract transaction data."""
    
    def __init__(self):
        """Initialize PDF parser."""
        self.date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY or M/D/YY
            r'\d{1,2}-\d{1,2}-\d{2,4}',  # MM-DD-YYYY
            r'\d{4}-\d{1,2}-\d{1,2}',    # YYYY-MM-DD
        ]
        self.amount_pattern = r'\$?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?'
        
    async def parse_pdf(self, pdf_path: str, document_type: str = "general") -> List[Dict[str, Any]]:
        """
        Parse PDF and extract transactions.
        
        Args:
            pdf_path: Path to PDF file
            document_type: Type of document (bank_statement, invoice, receipt, general)
            
        Returns:
            List of extracted transactions
        """
        logger.info(f"Parsing PDF: {pdf_path} (type: {document_type})")
        
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        transactions = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    
                    if document_type == "bank_statement":
                        page_transactions = self._parse_bank_statement(text)
                    elif document_type == "invoice":
                        page_transactions = self._parse_invoice(text)
                    elif document_type == "receipt":
                        page_transactions = self._parse_receipt(text)
                    else:
                        page_transactions = self._parse_general(text)
                    
                    for txn in page_transactions:
                        txn["source_page"] = page_num
                        txn["source_file"] = pdf_path
                    
                    transactions.extend(page_transactions)
            
            logger.info(f"Extracted {len(transactions)} transactions from PDF")
            return transactions
            
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            raise
    
    def _parse_bank_statement(self, text: str) -> List[Dict[str, Any]]:
        """Parse bank statement format."""
        transactions = []
        lines = text.split('\n')
        
        for line in lines:
            # Look for lines with date, description, and amount
            date_match = None
            for pattern in self.date_patterns:
                date_match = re.search(pattern, line)
                if date_match:
                    break
            
            if not date_match:
                continue
            
            # Extract amount
            amount_matches = re.findall(self.amount_pattern, line)
            if not amount_matches:
                continue
            
            # Get description (text between date and amount)
            date_end = date_match.end()
            amount_start = line.find(amount_matches[-1])
            description = line[date_end:amount_start].strip()
            
            if description:
                transactions.append({
                    "date": self._normalize_date(date_match.group()),
                    "description": description,
                    "amount": self._parse_amount(amount_matches[-1]),
                    "type": "bank_transaction"
                })
        
        return transactions
    
    def _parse_invoice(self, text: str) -> List[Dict[str, Any]]:
        """Parse invoice format."""
        transactions = []
        
        # Extract invoice date
        invoice_date = None
        for pattern in self.date_patterns:
            match = re.search(f"(?:Invoice Date|Date):?\\s*({pattern})", text, re.IGNORECASE)
            if match:
                invoice_date = self._normalize_date(match.group(1))
                break
        
        # Extract line items
        lines = text.split('\n')
        for line in lines:
            amount_matches = re.findall(self.amount_pattern, line)
            if amount_matches and len(line.strip()) > 10:
                # This might be a line item
                transactions.append({
                    "date": invoice_date or datetime.now().strftime("%Y-%m-%d"),
                    "description": line.strip(),
                    "amount": self._parse_amount(amount_matches[-1]),
                    "type": "invoice_line"
                })
        
        return transactions
    
    def _parse_receipt(self, text: str) -> List[Dict[str, Any]]:
        """Parse receipt format."""
        transactions = []
        
        # Extract receipt date
        receipt_date = None
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                receipt_date = self._normalize_date(match.group())
                break
        
        # Extract total amount
        total_match = re.search(f"(?:Total|Amount):?\\s*({self.amount_pattern})", text, re.IGNORECASE)
        if total_match:
            transactions.append({
                "date": receipt_date or datetime.now().strftime("%Y-%m-%d"),
                "description": "Receipt transaction",
                "amount": self._parse_amount(total_match.group(1)),
                "type": "receipt"
            })
        
        return transactions
    
    def _parse_general(self, text: str) -> List[Dict[str, Any]]:
        """Parse general document format."""
        transactions = []
        lines = text.split('\n')
        
        for line in lines:
            # Look for any line with both date and amount
            date_match = None
            for pattern in self.date_patterns:
                date_match = re.search(pattern, line)
                if date_match:
                    break
            
            amount_matches = re.findall(self.amount_pattern, line)
            
            if date_match and amount_matches:
                transactions.append({
                    "date": self._normalize_date(date_match.group()),
                    "description": line.strip(),
                    "amount": self._parse_amount(amount_matches[-1]),
                    "type": "general"
                })
        
        return transactions
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to YYYY-MM-DD format."""
        try:
            # Try different date formats
            for fmt in ["%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            
            # If all fail, return original
            return date_str
        except:
            return date_str
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float."""
        try:
            # Remove $ and commas
            clean_amount = amount_str.replace('$', '').replace(',', '').strip()
            return float(clean_amount)
        except:
            return 0.0
