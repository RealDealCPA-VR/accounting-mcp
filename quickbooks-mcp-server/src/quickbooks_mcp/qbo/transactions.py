"""
QuickBooks Online transaction management.
Handles creation and management of expenses, invoices, bills, and journal entries.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from .client import QBOClient
from .accounts import AccountManager

logger = logging.getLogger(__name__)


class TransactionManager:
    """Manage QuickBooks Online transactions."""
    
    def __init__(self, qbo_client: QBOClient):
        """
        Initialize transaction manager.
        
        Args:
            qbo_client: QBOClient instance
        """
        self.client = qbo_client
        self.account_manager = AccountManager(qbo_client)
        
    async def create_expense(
        self,
        company_id: str,
        vendor_name: str,
        account_name: str,
        amount: float,
        date: str,
        memo: str = ''
    ) -> Dict[str, Any]:
        """
        Create an expense transaction in QuickBooks Online.
        
        Args:
            company_id: QuickBooks company ID
            vendor_name: Vendor or payee name
            account_name: Expense account name
            amount: Transaction amount
            date: Transaction date (YYYY-MM-DD)
            memo: Optional memo
            
        Returns:
            Created expense details
        """
        logger.info(f"Creating expense: {vendor_name} - ${amount}")
        
        try:
            # Get or create vendor
            vendor = await self._get_or_create_vendor(company_id, vendor_name)
            
            # Get account
            account = await self.account_manager.get_account_by_name(company_id, account_name)
            if not account:
                raise ValueError(f"Account not found: {account_name}")
            
            # Build expense data
            expense_data = {
                'PaymentType': 'Cash',
                'AccountRef': {
                    'value': account['id'],
                    'name': account['name']
                },
                'EntityRef': {
                    'value': vendor['id'],
                    'name': vendor['name'],
                    'type': 'Vendor'
                },
                'TxnDate': date,
                'Line': [{
                    'Amount': amount,
                    'DetailType': 'AccountBasedExpenseLineDetail',
                    'AccountBasedExpenseLineDetail': {
                        'AccountRef': {
                            'value': account['id'],
                            'name': account['name']
                        }
                    },
                    'Description': memo
                }]
            }
            
            if memo:
                expense_data['PrivateNote'] = memo
            
            # Create expense
            response = await self.client.create_entity(company_id, 'Purchase', expense_data)
            
            if 'Purchase' in response:
                purchase = response['Purchase']
                logger.info(f"Created expense ID: {purchase['Id']}")
                
                return {
                    'success': True,
                    'id': purchase['Id'],
                    'vendor': vendor_name,
                    'amount': amount,
                    'date': date,
                    'account': account_name
                }
            
            raise Exception("Failed to create expense")
            
        except Exception as e:
            logger.error(f"Error creating expense: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def create_invoice(
        self,
        company_id: str,
        customer_name: str,
        line_items: List[Dict[str, Any]],
        invoice_date: str,
        due_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an invoice in QuickBooks Online.
        
        Args:
            company_id: QuickBooks company ID
            customer_name: Customer name
            line_items: List of line items with description, quantity, rate, account_name
            invoice_date: Invoice date (YYYY-MM-DD)
            due_date: Optional due date (YYYY-MM-DD)
            
        Returns:
            Created invoice details
        """
        logger.info(f"Creating invoice for: {customer_name}")
        
        try:
            # Get or create customer
            customer = await self._get_or_create_customer(company_id, customer_name)
            
            # Build line items
            lines = []
            total_amount = 0
            
            for idx, item in enumerate(line_items, 1):
                # Get income account
                account = await self.account_manager.get_account_by_name(
                    company_id,
                    item.get('account_name', 'Sales')
                )
                
                if not account:
                    # Use default income account
                    income_accounts = await self.account_manager.get_income_accounts(company_id)
                    account = income_accounts[0] if income_accounts else None
                
                if not account:
                    raise ValueError("No income account found")
                
                line_amount = item['quantity'] * item['rate']
                total_amount += line_amount
                
                lines.append({
                    'LineNum': idx,
                    'Amount': line_amount,
                    'DetailType': 'SalesItemLineDetail',
                    'SalesItemLineDetail': {
                        'Qty': item['quantity'],
                        'UnitPrice': item['rate'],
                        'ItemRef': {
                            'value': account['id'],
                            'name': account['name']
                        }
                    },
                    'Description': item.get('description', '')
                })
            
            # Build invoice data
            invoice_data = {
                'CustomerRef': {
                    'value': customer['id'],
                    'name': customer['name']
                },
                'TxnDate': invoice_date,
                'Line': lines
            }
            
            if due_date:
                invoice_data['DueDate'] = due_date
            
            # Create invoice
            response = await self.client.create_entity(company_id, 'Invoice', invoice_data)
            
            if 'Invoice' in response:
                invoice = response['Invoice']
                logger.info(f"Created invoice ID: {invoice['Id']}")
                
                return {
                    'success': True,
                    'id': invoice['Id'],
                    'customer': customer_name,
                    'total_amount': total_amount,
                    'date': invoice_date,
                    'doc_number': invoice.get('DocNumber', '')
                }
            
            raise Exception("Failed to create invoice")
            
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def create_journal_entry(
        self,
        company_id: str,
        date: str,
        lines: List[Dict[str, Any]],
        memo: str = ''
    ) -> Dict[str, Any]:
        """
        Create a journal entry in QuickBooks Online.
        
        Args:
            company_id: QuickBooks company ID
            date: Journal entry date (YYYY-MM-DD)
            lines: List of lines with account_name, debit, credit, description
            memo: Optional memo
            
        Returns:
            Created journal entry details
        """
        logger.info(f"Creating journal entry with {len(lines)} lines")
        
        try:
            # Validate that debits equal credits
            total_debit = sum(line.get('debit', 0) for line in lines)
            total_credit = sum(line.get('credit', 0) for line in lines)
            
            if abs(total_debit - total_credit) > 0.01:
                raise ValueError(f"Journal entry not balanced: Debits={total_debit}, Credits={total_credit}")
            
            # Build journal entry lines
            je_lines = []
            
            for idx, line in enumerate(lines, 1):
                # Get account
                account = await self.account_manager.get_account_by_name(
                    company_id,
                    line['account_name']
                )
                
                if not account:
                    raise ValueError(f"Account not found: {line['account_name']}")
                
                # Determine posting type
                amount = line.get('debit', 0) or line.get('credit', 0)
                posting_type = 'Debit' if line.get('debit', 0) > 0 else 'Credit'
                
                je_lines.append({
                    'LineNum': idx,
                    'Amount': amount,
                    'DetailType': 'JournalEntryLineDetail',
                    'JournalEntryLineDetail': {
                        'PostingType': posting_type,
                        'AccountRef': {
                            'value': account['id'],
                            'name': account['name']
                        }
                    },
                    'Description': line.get('description', '')
                })
            
            # Build journal entry data
            je_data = {
                'TxnDate': date,
                'Line': je_lines
            }
            
            if memo:
                je_data['PrivateNote'] = memo
            
            # Create journal entry
            response = await self.client.create_entity(company_id, 'JournalEntry', je_data)
            
            if 'JournalEntry' in response:
                je = response['JournalEntry']
                logger.info(f"Created journal entry ID: {je['Id']}")
                
                return {
                    'success': True,
                    'id': je['Id'],
                    'date': date,
                    'total_debit': total_debit,
                    'total_credit': total_credit,
                    'line_count': len(lines)
                }
            
            raise Exception("Failed to create journal entry")
            
        except Exception as e:
            logger.error(f"Error creating journal entry: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def batch_import(
        self,
        company_id: str,
        transactions: List[Dict[str, Any]],
        validate_only: bool = False
    ) -> Dict[str, Any]:
        """
        Batch import multiple transactions.
        
        Args:
            company_id: QuickBooks company ID
            transactions: List of transactions to import
            validate_only: If True, only validate without importing
            
        Returns:
            Import results with success/failure counts
        """
        logger.info(f"Batch importing {len(transactions)} transactions (validate_only={validate_only})")
        
        results = {
            'total': len(transactions),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': []
        }
        
        for idx, txn in enumerate(transactions):
            try:
                txn_type = txn.get('type', 'expense')
                
                if validate_only:
                    # Just validate the transaction
                    is_valid = await self._validate_transaction(company_id, txn)
                    if is_valid:
                        results['successful'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'index': idx,
                            'error': 'Validation failed'
                        })
                else:
                    # Create the transaction
                    if txn_type == 'expense':
                        result = await self.create_expense(
                            company_id=company_id,
                            vendor_name=txn['vendor_name'],
                            account_name=txn['account_name'],
                            amount=txn['amount'],
                            date=txn['date'],
                            memo=txn.get('description', '')
                        )
                    elif txn_type == 'invoice':
                        result = await self.create_invoice(
                            company_id=company_id,
                            customer_name=txn['customer_name'],
                            line_items=txn['line_items'],
                            invoice_date=txn['date'],
                            due_date=txn.get('due_date')
                        )
                    elif txn_type == 'journal_entry':
                        result = await self.create_journal_entry(
                            company_id=company_id,
                            date=txn['date'],
                            lines=txn['lines'],
                            memo=txn.get('memo', '')
                        )
                    else:
                        raise ValueError(f"Unknown transaction type: {txn_type}")
                    
                    if result.get('success'):
                        results['successful'] += 1
                        results['created_ids'].append(result.get('id'))
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'index': idx,
                            'error': result.get('error', 'Unknown error')
                        })
                
            except Exception as e:
                logger.error(f"Error processing transaction {idx}: {str(e)}")
                results['failed'] += 1
                results['errors'].append({
                    'index': idx,
                    'error': str(e)
                })
        
        logger.info(f"Batch import complete: {results['successful']} successful, {results['failed']} failed")
        return results
    
    async def _validate_transaction(self, company_id: str, txn: Dict[str, Any]) -> bool:
        """Validate a transaction before import."""
        try:
            # Check required fields
            if 'date' not in txn or 'amount' not in txn:
                return False
            
            # Validate date format
            datetime.strptime(txn['date'], '%Y-%m-%d')
            
            # Validate amount
            if txn['amount'] <= 0:
                return False
            
            return True
        except:
            return False
    
    async def _get_or_create_vendor(self, company_id: str, vendor_name: str) -> Dict[str, Any]:
        """Get existing vendor or create new one."""
        try:
            # Search for existing vendor
            query = f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name}'"
            response = await self.client.query(company_id, query)
            
            if 'QueryResponse' in response and 'Vendor' in response['QueryResponse']:
                vendors = response['QueryResponse']['Vendor']
                if vendors:
                    return {
                        'id': vendors[0]['Id'],
                        'name': vendors[0]['DisplayName']
                    }
            
            # Create new vendor
            vendor_data = {
                'DisplayName': vendor_name
            }
            
            response = await self.client.create_entity(company_id, 'Vendor', vendor_data)
            
            if 'Vendor' in response:
                vendor = response['Vendor']
                logger.info(f"Created vendor: {vendor['DisplayName']} (ID: {vendor['Id']})")
                return {
                    'id': vendor['Id'],
                    'name': vendor['DisplayName']
                }
            
            raise Exception("Failed to create vendor")
            
        except Exception as e:
            logger.error(f"Error getting/creating vendor: {str(e)}")
            raise
    
    async def _get_or_create_customer(self, company_id: str, customer_name: str) -> Dict[str, Any]:
        """Get existing customer or create new one."""
        try:
            # Search for existing customer
            query = f"SELECT * FROM Customer WHERE DisplayName = '{customer_name}'"
            response = await self.client.query(company_id, query)
            
            if 'QueryResponse' in response and 'Customer' in response['QueryResponse']:
                customers = response['QueryResponse']['Customer']
                if customers:
                    return {
                        'id': customers[0]['Id'],
                        'name': customers[0]['DisplayName']
                    }
            
            # Create new customer
            customer_data = {
                'DisplayName': customer_name
            }
            
            response = await self.client.create_entity(company_id, 'Customer', customer_data)
            
            if 'Customer' in response:
                customer = response['Customer']
                logger.info(f"Created customer: {customer['DisplayName']} (ID: {customer['Id']})")
                return {
                    'id': customer['Id'],
                    'name': customer['DisplayName']
                }
            
            raise Exception("Failed to create customer")
            
        except Exception as e:
            logger.error(f"Error getting/creating customer: {str(e)}")
            raise
    
    async def get_bank_transactions(
        self,
        company_id: str,
        account_name: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch bank transactions for reconciliation.
        
        Args:
            company_id: QuickBooks company ID
            account_name: Bank account name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of bank transactions
        """
        logger.info(f"Fetching bank transactions for {account_name} from {start_date} to {end_date}")
        
        try:
            # Get bank account
            account = await self.account_manager.get_account_by_name(company_id, account_name)
            if not account:
                raise ValueError(f"Bank account not found: {account_name}")
            
            # Query transactions
            query = f"""
                SELECT * FROM Purchase 
                WHERE AccountRef = '{account['id']}' 
                AND TxnDate >= '{start_date}' 
                AND TxnDate <= '{end_date}'
            """
            
            response = await self.client.query(company_id, query)
            
            transactions = []
            if 'QueryResponse' in response and 'Purchase' in response['QueryResponse']:
                for txn in response['QueryResponse']['Purchase']:
                    transactions.append({
                        'id': txn['Id'],
                        'date': txn['TxnDate'],
                        'amount': float(txn.get('TotalAmt', 0)),
                        'vendor': txn.get('EntityRef', {}).get('name', ''),
                        'memo': txn.get('PrivateNote', ''),
                        'type': 'Purchase'
                    })
            
            logger.info(f"Retrieved {len(transactions)} bank transactions")
            return transactions
            
        except Exception as e:
            logger.error(f"Error fetching bank transactions: {str(e)}")
            return []
    
    async def reconcile_bank(
        self,
        company_id: str,
        account_name: str,
        bank_transactions: List[Dict[str, Any]],
        statement_date: str,
        start_date: str = None,
        bank_ending_balance: float = 0.0,
        date_tolerance_days: int = 3,
        confidence_threshold: float = 0.75,
        output_excel: str = None
    ) -> Dict[str, Any]:
        """
        Auto-reconcile bank account using fuzzy matching.
        
        Args:
            company_id: QuickBooks company ID
            account_name: Bank account name
            bank_transactions: List of bank statement transactions
            statement_date: Statement ending date (YYYY-MM-DD)
            start_date: Start date for QBO transactions (defaults to 30 days before statement_date)
            bank_ending_balance: Ending balance per bank statement
            date_tolerance_days: Days tolerance for date matching (default 3)
            confidence_threshold: Minimum confidence for matches (default 0.75)
            output_excel: Optional path to save Excel reconciliation report
            
        Returns:
            Reconciliation results with matched/unmatched transactions
        """
        from ..reconciliation.reconciler import BankReconciler, generate_reconciliation_excel
        from datetime import datetime, timedelta
        
        logger.info(f"Reconciling {account_name} for statement date {statement_date}")
        
        try:
            # Calculate start date if not provided (30 days before statement date)
            if not start_date:
                stmt_date = datetime.strptime(statement_date, '%Y-%m-%d')
                start_date = (stmt_date - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Fetch QBO transactions for the period
            qbo_transactions = await self.get_bank_transactions(
                company_id=company_id,
                account_name=account_name,
                start_date=start_date,
                end_date=statement_date
            )
            
            logger.info(f"Retrieved {len(qbo_transactions)} QBO transactions")
            logger.info(f"Received {len(bank_transactions)} bank transactions")
            
            # Initialize reconciler
            reconciler = BankReconciler(
                date_tolerance_days=date_tolerance_days,
                confidence_threshold=confidence_threshold
            )
            
            # Get QBO ending balance (simplified - sum of transactions)
            qbo_ending_balance = sum(t.get('amount', 0) for t in qbo_transactions)
            
            # Perform reconciliation
            report = reconciler.reconcile(
                qbo_transactions=qbo_transactions,
                bank_transactions=bank_transactions,
                account_name=account_name,
                statement_date=statement_date,
                bank_ending_balance=bank_ending_balance,
                qbo_ending_balance=qbo_ending_balance
            )
            
            # Generate Excel report if requested
            excel_path = None
            if output_excel:
                excel_path = generate_reconciliation_excel(report, output_excel)
                logger.info(f"Reconciliation Excel saved to: {excel_path}")
            
            result = report.to_dict()
            result['success'] = True
            result['excel_report'] = excel_path
            
            return result
            
        except Exception as e:
            logger.error(f"Error during reconciliation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'matched': 0,
                'unmatched_qbo': 0,
                'unmatched_bank': 0
            }
