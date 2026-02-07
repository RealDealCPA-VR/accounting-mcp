"""
QuickBooks Online report generation.
Handles tax mapping reports, financial reports, and UltraTax integration.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from .client import QBOClient
from ..utils.excel import ExcelGenerator

logger = logging.getLogger(__name__)


class ReportManager:
    """Manage QuickBooks Online reports."""
    
    def __init__(self, qbo_client: QBOClient):
        """
        Initialize report manager.
        
        Args:
            qbo_client: QBOClient instance
        """
        self.client = qbo_client
        self.excel_generator = ExcelGenerator()
        
    async def generate_tax_report(
        self,
        company_id: str,
        start_date: str,
        end_date: str,
        report_type: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Generate tax mapping report for UltraTax integration.
        
        Args:
            company_id: QuickBooks company ID
            start_date: Report start date (YYYY-MM-DD)
            end_date: Report end date (YYYY-MM-DD)
            report_type: Type of report (profit_loss, balance_sheet, both)
            output_path: Path to save Excel report
            
        Returns:
            Report generation results
        """
        logger.info(f"Generating tax report for {company_id} from {start_date} to {end_date}")
        
        try:
            reports_data = {}
            
            # Generate P&L if requested
            if report_type in ['profit_loss', 'both']:
                pl_data = await self.get_financial_report(
                    company_id,
                    'profit_loss',
                    start_date,
                    end_date
                )
                reports_data['profit_loss'] = pl_data
            
            # Generate Balance Sheet if requested
            if report_type in ['balance_sheet', 'both']:
                bs_data = await self.get_financial_report(
                    company_id,
                    'balance_sheet',
                    start_date,
                    end_date
                )
                reports_data['balance_sheet'] = bs_data
            
            # Generate Excel file
            excel_path = await self.excel_generator.generate_tax_report(
                reports_data,
                output_path,
                start_date,
                end_date
            )
            
            logger.info(f"Tax report generated: {excel_path}")
            
            return {
                'success': True,
                'output_path': excel_path,
                'report_type': report_type,
                'date_range': f"{start_date} to {end_date}"
            }
            
        except Exception as e:
            logger.error(f"Error generating tax report: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_financial_report(
        self,
        company_id: str,
        report_type: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Get financial report from QuickBooks Online.
        
        Args:
            company_id: QuickBooks company ID
            report_type: Type of report (profit_loss, balance_sheet, cash_flow)
            start_date: Report start date (YYYY-MM-DD)
            end_date: Report end date (YYYY-MM-DD)
            
        Returns:
            Report data
        """
        logger.info(f"Fetching {report_type} report for {company_id}")
        
        try:
            # Map report type to QuickBooks report name
            report_mapping = {
                'profit_loss': 'ProfitAndLoss',
                'balance_sheet': 'BalanceSheet',
                'cash_flow': 'CashFlow'
            }
            
            qb_report_name = report_mapping.get(report_type)
            if not qb_report_name:
                raise ValueError(f"Invalid report type: {report_type}")
            
            # Build report parameters
            params = {
                'start_date': start_date,
                'end_date': end_date,
                'accounting_method': 'Accrual',
                'summarize_column_by': 'Total'
            }
            
            # Get report from QuickBooks
            response = await self.client.get_report(company_id, qb_report_name, params)
            
            # Parse report data
            report_data = self._parse_report_response(response, report_type)
            
            logger.info(f"Retrieved {report_type} report with {len(report_data.get('rows', []))} rows")
            return report_data
            
        except Exception as e:
            logger.error(f"Error fetching financial report: {str(e)}")
            raise
    
    def _parse_report_response(self, response: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """
        Parse QuickBooks report response.
        
        Args:
            response: Raw report response from QuickBooks
            report_type: Type of report
            
        Returns:
            Parsed report data
        """
        try:
            report_data = {
                'report_type': report_type,
                'report_name': response.get('Header', {}).get('ReportName', ''),
                'start_date': response.get('Header', {}).get('StartPeriod', ''),
                'end_date': response.get('Header', {}).get('EndPeriod', ''),
                'currency': response.get('Header', {}).get('Currency', 'USD'),
                'rows': []
            }
            
            # Parse rows
            if 'Rows' in response and 'Row' in response['Rows']:
                rows = response['Rows']['Row']
                if not isinstance(rows, list):
                    rows = [rows]
                
                for row in rows:
                    parsed_row = self._parse_row(row)
                    if parsed_row:
                        report_data['rows'].append(parsed_row)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error parsing report response: {str(e)}")
            return {
                'report_type': report_type,
                'rows': [],
                'error': str(e)
            }
    
    def _parse_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single report row."""
        try:
            row_type = row.get('type', '')
            
            if row_type == 'Section':
                # Section header
                return {
                    'type': 'section',
                    'name': row.get('Header', {}).get('ColData', [{}])[0].get('value', ''),
                    'rows': [self._parse_row(r) for r in row.get('Rows', {}).get('Row', [])]
                }
            elif row_type == 'Data':
                # Data row
                col_data = row.get('ColData', [])
                return {
                    'type': 'data',
                    'account': col_data[0].get('value', '') if len(col_data) > 0 else '',
                    'amount': float(col_data[1].get('value', 0)) if len(col_data) > 1 else 0.0
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing row: {str(e)}")
            return None
    
    async def get_trial_balance(
        self,
        company_id: str,
        as_of_date: str
    ) -> Dict[str, Any]:
        """
        Get trial balance report.
        
        Args:
            company_id: QuickBooks company ID
            as_of_date: As of date (YYYY-MM-DD)
            
        Returns:
            Trial balance data
        """
        try:
            params = {
                'end_date': as_of_date,
                'accounting_method': 'Accrual'
            }
            
            response = await self.client.get_report(company_id, 'TrialBalance', params)
            return self._parse_report_response(response, 'trial_balance')
            
        except Exception as e:
            logger.error(f"Error fetching trial balance: {str(e)}")
            raise
    
    async def get_general_ledger(
        self,
        company_id: str,
        start_date: str,
        end_date: str,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get general ledger report.
        
        Args:
            company_id: QuickBooks company ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            account_id: Optional account ID to filter
            
        Returns:
            General ledger data
        """
        try:
            params = {
                'start_date': start_date,
                'end_date': end_date,
                'accounting_method': 'Accrual'
            }
            
            if account_id:
                params['account'] = account_id
            
            response = await self.client.get_report(company_id, 'GeneralLedger', params)
            return self._parse_report_response(response, 'general_ledger')
            
        except Exception as e:
            logger.error(f"Error fetching general ledger: {str(e)}")
            raise
    
    async def get_account_list(self, company_id: str) -> Dict[str, Any]:
        """
        Get account list report.
        
        Args:
            company_id: QuickBooks company ID
            
        Returns:
            Account list data
        """
        try:
            response = await self.client.get_report(company_id, 'AccountList', {})
            return self._parse_report_response(response, 'account_list')
            
        except Exception as e:
            logger.error(f"Error fetching account list: {str(e)}")
            raise
    
    def generate_audit_trail(
        self,
        transactions: List[Dict[str, Any]],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Generate audit trail documentation.
        
        Args:
            transactions: List of transactions
            output_path: Path to save audit trail
            
        Returns:
            Audit trail generation results
        """
        logger.info(f"Generating audit trail for {len(transactions)} transactions")
        
        try:
            # Generate audit trail Excel file
            excel_path = self.excel_generator.generate_audit_trail(
                transactions,
                output_path
            )
            
            return {
                'success': True,
                'output_path': excel_path,
                'transaction_count': len(transactions)
            }
            
        except Exception as e:
            logger.error(f"Error generating audit trail: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
