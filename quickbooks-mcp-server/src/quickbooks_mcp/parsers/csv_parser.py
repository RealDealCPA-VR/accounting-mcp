"""
CSV parser for importing transaction data with intelligent column mapping.
Automatically detects date, amount, description, and vendor columns.
"""
import logging
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


class CSVParser:
    """Parse CSV files and import transactions with intelligent column mapping."""
    
    def __init__(self):
        """Initialize CSV parser."""
        self.common_date_columns = ['date', 'transaction date', 'trans date', 'posting date', 'txn date']
        self.common_amount_columns = ['amount', 'total', 'debit', 'credit', 'transaction amount']
        self.common_description_columns = ['description', 'memo', 'details', 'transaction details', 'notes']
        self.common_vendor_columns = ['vendor', 'payee', 'merchant', 'name', 'company']
        self.common_account_columns = ['account', 'category', 'account name', 'gl account']
        
    async def parse_csv(
        self,
        csv_path: str,
        transaction_type: str,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse CSV file and extract transactions.
        
        Args:
            csv_path: Path to CSV file
            transaction_type: Type of transactions (expense, invoice, bill, journal_entry)
            column_mapping: Optional custom column mapping
            
        Returns:
            List of extracted transactions
        """
        logger.info(f"Parsing CSV: {csv_path} (type: {transaction_type})")
        
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        try:
            # Read CSV with pandas for better handling
            df = pd.read_csv(csv_path)
            
            # Auto-detect column mapping if not provided
            if not column_mapping:
                column_mapping = self._auto_detect_columns(df)
                logger.info(f"Auto-detected column mapping: {column_mapping}")
            
            # Parse transactions based on type
            transactions = []
            for idx, row in df.iterrows():
                try:
                    txn = self._parse_row(row, transaction_type, column_mapping)
                    if txn:
                        txn['source_row'] = idx + 2  # +2 for header and 0-indexing
                        txn['source_file'] = csv_path
                        transactions.append(txn)
                except Exception as e:
                    logger.warning(f"Error parsing row {idx + 2}: {str(e)}")
                    continue
            
            logger.info(f"Extracted {len(transactions)} transactions from CSV")
            return transactions
            
        except Exception as e:
            logger.error(f"Error parsing CSV: {str(e)}")
            raise
    
    def _auto_detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Auto-detect column mapping based on column names.
        
        Args:
            df: DataFrame with CSV data
            
        Returns:
            Dictionary mapping field names to column names
        """
        columns = [col.lower().strip() for col in df.columns]
        mapping = {}
        
        # Detect date column
        for col in columns:
            if any(date_col in col for date_col in self.common_date_columns):
                mapping['date'] = df.columns[columns.index(col)]
                break
        
        # Detect amount column
        for col in columns:
            if any(amt_col in col for amt_col in self.common_amount_columns):
                mapping['amount'] = df.columns[columns.index(col)]
                break
        
        # Detect description column
        for col in columns:
            if any(desc_col in col for desc_col in self.common_description_columns):
                mapping['description'] = df.columns[columns.index(col)]
                break
        
        # Detect vendor column
        for col in columns:
            if any(vendor_col in col for vendor_col in self.common_vendor_columns):
                mapping['vendor'] = df.columns[columns.index(col)]
                break
        
        # Detect account column
        for col in columns:
            if any(acct_col in col for acct_col in self.common_account_columns):
                mapping['account'] = df.columns[columns.index(col)]
                break
        
        return mapping
    
    def _parse_row(
        self,
        row: pd.Series,
        transaction_type: str,
        column_mapping: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single row into a transaction.
        
        Args:
            row: DataFrame row
            transaction_type: Type of transaction
            column_mapping: Column mapping dictionary
            
        Returns:
            Parsed transaction or None if invalid
        """
        try:
            # Extract basic fields
            date = self._extract_date(row, column_mapping.get('date'))
            amount = self._extract_amount(row, column_mapping.get('amount'))
            description = self._extract_text(row, column_mapping.get('description', ''))
            vendor = self._extract_text(row, column_mapping.get('vendor', ''))
            account = self._extract_text(row, column_mapping.get('account', ''))
            
            # Skip if missing required fields
            if not date or amount is None:
                return None
            
            # Build transaction based on type
            transaction = {
                'type': transaction_type,
                'date': date,
                'amount': abs(amount),
                'description': description or 'Imported transaction',
                'vendor_name': vendor,
                'account_name': account,
                'raw_data': row.to_dict()
            }
            
            # Add type-specific fields
            if transaction_type == 'expense':
                transaction['is_debit'] = amount < 0
            elif transaction_type == 'invoice':
                transaction['customer_name'] = vendor
                transaction['line_items'] = [{
                    'description': description,
                    'amount': amount,
                    'quantity': 1,
                    'rate': amount
                }]
            
            return transaction
            
        except Exception as e:
            logger.warning(f"Error parsing row: {str(e)}")
            return None
    
    def _extract_date(self, row: pd.Series, column: Optional[str]) -> Optional[str]:
        """Extract and normalize date from row."""
        if not column or column not in row:
            return None
        
        try:
            date_val = row[column]
            if pd.isna(date_val):
                return None
            
            # Try to parse date
            if isinstance(date_val, str):
                # Try common date formats
                for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(date_val, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
            elif isinstance(date_val, (datetime, pd.Timestamp)):
                return date_val.strftime('%Y-%m-%d')
            
            return None
        except:
            return None
    
    def _extract_amount(self, row: pd.Series, column: Optional[str]) -> Optional[float]:
        """Extract and normalize amount from row."""
        if not column or column not in row:
            return None
        
        try:
            amount_val = row[column]
            if pd.isna(amount_val):
                return None
            
            # Clean and convert to float
            if isinstance(amount_val, str):
                # Remove currency symbols and commas
                clean_amount = amount_val.replace('$', '').replace(',', '').strip()
                # Handle parentheses for negative numbers
                if clean_amount.startswith('(') and clean_amount.endswith(')'):
                    clean_amount = '-' + clean_amount[1:-1]
                return float(clean_amount)
            else:
                return float(amount_val)
        except:
            return None
    
    def _extract_text(self, row: pd.Series, column: str) -> str:
        """Extract text field from row."""
        if not column or column not in row:
            return ''
        
        try:
            text_val = row[column]
            if pd.isna(text_val):
                return ''
            return str(text_val).strip()
        except:
            return ''
    
    def validate_csv_format(self, csv_path: str) -> Dict[str, Any]:
        """
        Validate CSV format and provide feedback.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Validation results with detected columns and suggestions
        """
        try:
            df = pd.read_csv(csv_path)
            column_mapping = self._auto_detect_columns(df)
            
            validation = {
                'valid': True,
                'row_count': len(df),
                'column_count': len(df.columns),
                'detected_columns': column_mapping,
                'missing_columns': [],
                'suggestions': []
            }
            
            # Check for required columns
            required = ['date', 'amount']
            for req in required:
                if req not in column_mapping:
                    validation['missing_columns'].append(req)
                    validation['valid'] = False
            
            # Provide suggestions
            if 'description' not in column_mapping:
                validation['suggestions'].append('Consider adding a description column for better tracking')
            if 'vendor' not in column_mapping:
                validation['suggestions'].append('Vendor/payee column not detected - transactions may need manual vendor assignment')
            
            return validation
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'suggestions': ['Check that the file is a valid CSV format']
            }
