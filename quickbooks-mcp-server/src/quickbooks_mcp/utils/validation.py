"""
Data validation utilities for transaction import.
Validates data integrity and detects duplicates.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate transaction data before import."""
    
    def __init__(self, account_manager):
        """
        Initialize data validator.
        
        Args:
            account_manager: AccountManager instance
        """
        self.account_manager = account_manager
        self.duplicate_threshold = 0.95  # 95% similarity for duplicate detection
        
    async def validate_transactions(
        self,
        transactions: List[Dict[str, Any]],
        company_id: str
    ) -> Dict[str, Any]:
        """
        Validate a list of transactions.
        
        Args:
            transactions: List of transactions to validate
            company_id: QuickBooks company ID
            
        Returns:
            Validation results with errors and warnings
        """
        logger.info(f"Validating {len(transactions)} transactions")
        
        results = {
            'valid_count': 0,
            'invalid_count': 0,
            'warnings': [],
            'errors': [],
            'duplicates': []
        }
        
        # Get chart of accounts for validation
        accounts = await self.account_manager.get_chart_of_accounts(company_id, 'all')
        account_names = [acc['name'].lower() for acc in accounts]
        
        for idx, txn in enumerate(transactions):
            validation = self._validate_single_transaction(txn, account_names)
            
            if validation['valid']:
                results['valid_count'] += 1
            else:
                results['invalid_count'] += 1
                results['errors'].append({
                    'index': idx,
                    'transaction': txn,
                    'errors': validation['errors']
                })
            
            # Add warnings
            if validation['warnings']:
                results['warnings'].append({
                    'index': idx,
                    'warnings': validation['warnings']
                })
        
        # Check for duplicates
        duplicates = self._detect_duplicates(transactions)
        if duplicates:
            results['duplicates'] = duplicates
            results['warnings'].append({
                'type': 'duplicates',
                'count': len(duplicates),
                'message': f'Found {len(duplicates)} potential duplicate transactions'
            })
        
        logger.info(f"Validation complete: {results['valid_count']} valid, {results['invalid_count']} invalid")
        return results
    
    def _validate_single_transaction(
        self,
        txn: Dict[str, Any],
        account_names: List[str]
    ) -> Dict[str, Any]:
        """
        Validate a single transaction.
        
        Args:
            txn: Transaction to validate
            account_names: List of valid account names
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Check required fields
        if 'date' not in txn or not txn['date']:
            errors.append('Missing required field: date')
        else:
            # Validate date format
            if not self._validate_date(txn['date']):
                errors.append(f"Invalid date format: {txn['date']} (expected YYYY-MM-DD)")
        
        if 'amount' not in txn or txn['amount'] is None:
            errors.append('Missing required field: amount')
        else:
            # Validate amount
            if not isinstance(txn['amount'], (int, float)):
                errors.append(f"Invalid amount type: {type(txn['amount'])}")
            elif txn['amount'] <= 0:
                warnings.append(f"Amount is zero or negative: {txn['amount']}")
        
        # Check transaction type
        txn_type = txn.get('type', 'expense')
        if txn_type not in ['expense', 'invoice', 'bill', 'journal_entry']:
            errors.append(f"Invalid transaction type: {txn_type}")
        
        # Type-specific validation
        if txn_type == 'expense':
            if 'vendor_name' not in txn or not txn['vendor_name']:
                warnings.append('Missing vendor name')
            if 'account_name' not in txn or not txn['account_name']:
                errors.append('Missing account name for expense')
            elif txn['account_name'].lower() not in account_names:
                warnings.append(f"Account not found in chart of accounts: {txn['account_name']}")
        
        elif txn_type == 'invoice':
            if 'customer_name' not in txn or not txn['customer_name']:
                errors.append('Missing customer name for invoice')
            if 'line_items' not in txn or not txn['line_items']:
                errors.append('Missing line items for invoice')
            else:
                # Validate line items
                for idx, item in enumerate(txn['line_items']):
                    if 'quantity' not in item or 'rate' not in item:
                        errors.append(f"Line item {idx + 1} missing quantity or rate")
        
        elif txn_type == 'journal_entry':
            if 'lines' not in txn or not txn['lines']:
                errors.append('Missing lines for journal entry')
            else:
                # Validate journal entry balance
                total_debit = sum(line.get('debit', 0) for line in txn['lines'])
                total_credit = sum(line.get('credit', 0) for line in txn['lines'])
                if abs(total_debit - total_credit) > 0.01:
                    errors.append(f"Journal entry not balanced: Debits={total_debit}, Credits={total_credit}")
        
        # Check for description
        if 'description' not in txn or not txn['description']:
            warnings.append('Missing description')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _validate_date(self, date_str: str) -> bool:
        """Validate date format (YYYY-MM-DD)."""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except:
            return False
    
    def _detect_duplicates(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate transactions.
        
        Args:
            transactions: List of transactions
            
        Returns:
            List of duplicate pairs
        """
        duplicates = []
        
        for i in range(len(transactions)):
            for j in range(i + 1, len(transactions)):
                if self._is_duplicate(transactions[i], transactions[j]):
                    duplicates.append({
                        'index1': i,
                        'index2': j,
                        'transaction1': transactions[i],
                        'transaction2': transactions[j],
                        'similarity': self._calculate_similarity(transactions[i], transactions[j])
                    })
        
        return duplicates
    
    def _is_duplicate(self, txn1: Dict[str, Any], txn2: Dict[str, Any]) -> bool:
        """
        Check if two transactions are duplicates.
        
        Args:
            txn1: First transaction
            txn2: Second transaction
            
        Returns:
            True if transactions are likely duplicates
        """
        # Check if dates match
        if txn1.get('date') != txn2.get('date'):
            return False
        
        # Check if amounts match (within 0.01)
        amount1 = txn1.get('amount', 0)
        amount2 = txn2.get('amount', 0)
        if abs(amount1 - amount2) > 0.01:
            return False
        
        # Check description similarity
        desc1 = txn1.get('description', '')
        desc2 = txn2.get('description', '')
        
        if desc1 and desc2:
            similarity = fuzz.ratio(desc1.lower(), desc2.lower()) / 100.0
            if similarity >= self.duplicate_threshold:
                return True
        
        # Check vendor/customer similarity
        vendor1 = txn1.get('vendor_name', '') or txn1.get('customer_name', '')
        vendor2 = txn2.get('vendor_name', '') or txn2.get('customer_name', '')
        
        if vendor1 and vendor2:
            similarity = fuzz.ratio(vendor1.lower(), vendor2.lower()) / 100.0
            if similarity >= self.duplicate_threshold:
                return True
        
        return False
    
    def _calculate_similarity(self, txn1: Dict[str, Any], txn2: Dict[str, Any]) -> float:
        """Calculate similarity score between two transactions."""
        scores = []
        
        # Date match (1.0 if same, 0.0 if different)
        if txn1.get('date') == txn2.get('date'):
            scores.append(1.0)
        else:
            scores.append(0.0)
        
        # Amount match
        amount1 = txn1.get('amount', 0)
        amount2 = txn2.get('amount', 0)
        if amount1 and amount2:
            amount_diff = abs(amount1 - amount2) / max(amount1, amount2)
            scores.append(1.0 - amount_diff)
        
        # Description similarity
        desc1 = txn1.get('description', '')
        desc2 = txn2.get('description', '')
        if desc1 and desc2:
            scores.append(fuzz.ratio(desc1.lower(), desc2.lower()) / 100.0)
        
        # Vendor/customer similarity
        vendor1 = txn1.get('vendor_name', '') or txn1.get('customer_name', '')
        vendor2 = txn2.get('vendor_name', '') or txn2.get('customer_name', '')
        if vendor1 and vendor2:
            scores.append(fuzz.ratio(vendor1.lower(), vendor2.lower()) / 100.0)
        
        # Return average similarity
        return sum(scores) / len(scores) if scores else 0.0
    
    def validate_account_name(self, account_name: str, account_names: List[str]) -> Dict[str, Any]:
        """
        Validate account name and suggest corrections.
        
        Args:
            account_name: Account name to validate
            account_names: List of valid account names
            
        Returns:
            Validation result with suggestions
        """
        # Check exact match
        if account_name.lower() in [name.lower() for name in account_names]:
            return {
                'valid': True,
                'account_name': account_name
            }
        
        # Find similar accounts
        from fuzzywuzzy import process
        matches = process.extract(account_name, account_names, limit=3)
        
        return {
            'valid': False,
            'account_name': account_name,
            'suggestions': [match[0] for match in matches if match[1] >= 70],
            'message': f"Account '{account_name}' not found. Did you mean one of these?"
        }
    
    def validate_amount(self, amount: Any) -> Dict[str, Any]:
        """
        Validate transaction amount.
        
        Args:
            amount: Amount to validate
            
        Returns:
            Validation result
        """
        try:
            amount_float = float(amount)
            
            if amount_float <= 0:
                return {
                    'valid': False,
                    'error': 'Amount must be greater than zero'
                }
            
            if amount_float > 1000000:
                return {
                    'valid': True,
                    'warning': 'Amount is unusually large (> $1,000,000)'
                }
            
            return {
                'valid': True,
                'amount': amount_float
            }
            
        except (ValueError, TypeError):
            return {
                'valid': False,
                'error': f"Invalid amount: {amount}"
            }
