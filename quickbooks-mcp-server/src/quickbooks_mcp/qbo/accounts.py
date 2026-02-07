"""
QuickBooks Online account management.
Handles chart of accounts operations.
"""
import logging
from typing import List, Dict, Any, Optional
from .client import QBOClient

logger = logging.getLogger(__name__)


class AccountManager:
    """Manage QuickBooks Online chart of accounts."""
    
    def __init__(self, qbo_client: QBOClient):
        """
        Initialize account manager.
        
        Args:
            qbo_client: QBOClient instance
        """
        self.client = qbo_client
        self.account_cache = {}  # Cache accounts by company_id
        
    async def get_chart_of_accounts(
        self,
        company_id: str,
        account_type: str = 'all'
    ) -> List[Dict[str, Any]]:
        """
        Get chart of accounts from QuickBooks Online.
        
        Args:
            company_id: QuickBooks company ID
            account_type: Filter by type (all, expense, income, asset, liability, equity)
            
        Returns:
            List of accounts with name, type, and ID
        """
        logger.info(f"Fetching chart of accounts for company {company_id} (type: {account_type})")
        
        try:
            # Check cache first
            cache_key = f"{company_id}_{account_type}"
            if cache_key in self.account_cache:
                logger.info("Returning cached chart of accounts")
                return self.account_cache[cache_key]
            
            # Build query based on account type
            if account_type == 'all':
                query = "SELECT * FROM Account"
            else:
                # Map account type to QuickBooks types
                type_mapping = {
                    'expense': ['Expense', 'Cost of Goods Sold', 'Other Expense'],
                    'income': ['Income', 'Other Income'],
                    'asset': ['Bank', 'Other Current Asset', 'Fixed Asset', 'Other Asset'],
                    'liability': ['Accounts Payable', 'Credit Card', 'Other Current Liability', 'Long Term Liability'],
                    'equity': ['Equity']
                }
                
                qb_types = type_mapping.get(account_type, ['Expense'])
                type_filter = " OR ".join([f"AccountType = '{t}'" for t in qb_types])
                query = f"SELECT * FROM Account WHERE {type_filter}"
            
            # Execute query
            response = await self.client.query(company_id, query)
            
            # Parse response
            accounts = []
            if 'QueryResponse' in response and 'Account' in response['QueryResponse']:
                for acc in response['QueryResponse']['Account']:
                    accounts.append({
                        'id': acc['Id'],
                        'name': acc['Name'],
                        'type': acc['AccountType'],
                        'sub_type': acc.get('AccountSubType', ''),
                        'active': acc.get('Active', True),
                        'classification': acc.get('Classification', ''),
                        'account_number': acc.get('AcctNum', ''),
                        'current_balance': float(acc.get('CurrentBalance', 0))
                    })
            
            # Cache the results
            self.account_cache[cache_key] = accounts
            
            logger.info(f"Retrieved {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error fetching chart of accounts: {str(e)}")
            raise
    
    async def get_account_by_name(
        self,
        company_id: str,
        account_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get account by name.
        
        Args:
            company_id: QuickBooks company ID
            account_name: Account name to search for
            
        Returns:
            Account details or None if not found
        """
        try:
            # Get all accounts
            accounts = await self.get_chart_of_accounts(company_id, 'all')
            
            # Search for exact match first
            for acc in accounts:
                if acc['name'].lower() == account_name.lower():
                    return acc
            
            # Try partial match
            for acc in accounts:
                if account_name.lower() in acc['name'].lower():
                    return acc
            
            logger.warning(f"Account not found: {account_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding account: {str(e)}")
            return None
    
    async def get_account_by_id(
        self,
        company_id: str,
        account_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get account by ID.
        
        Args:
            company_id: QuickBooks company ID
            account_id: Account ID
            
        Returns:
            Account details or None if not found
        """
        try:
            response = await self.client.get_entity(company_id, 'Account', account_id)
            
            if 'Account' in response:
                acc = response['Account']
                return {
                    'id': acc['Id'],
                    'name': acc['Name'],
                    'type': acc['AccountType'],
                    'sub_type': acc.get('AccountSubType', ''),
                    'active': acc.get('Active', True),
                    'current_balance': float(acc.get('CurrentBalance', 0))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching account by ID: {str(e)}")
            return None
    
    async def create_account(
        self,
        company_id: str,
        account_name: str,
        account_type: str,
        account_sub_type: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new account in QuickBooks Online.
        
        Args:
            company_id: QuickBooks company ID
            account_name: Name for the new account
            account_type: Account type (Expense, Income, Asset, Liability, Equity)
            account_sub_type: Account sub-type
            description: Optional description
            
        Returns:
            Created account details
        """
        try:
            account_data = {
                'Name': account_name,
                'AccountType': account_type,
                'AccountSubType': account_sub_type
            }
            
            if description:
                account_data['Description'] = description
            
            response = await self.client.create_entity(company_id, 'Account', account_data)
            
            if 'Account' in response:
                acc = response['Account']
                logger.info(f"Created account: {acc['Name']} (ID: {acc['Id']})")
                
                # Clear cache
                self.account_cache.clear()
                
                return {
                    'id': acc['Id'],
                    'name': acc['Name'],
                    'type': acc['AccountType'],
                    'sub_type': acc.get('AccountSubType', ''),
                    'success': True
                }
            
            raise Exception("Failed to create account")
            
        except Exception as e:
            logger.error(f"Error creating account: {str(e)}")
            raise
    
    async def search_accounts(
        self,
        company_id: str,
        search_term: str,
        account_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search accounts by name or description.
        
        Args:
            company_id: QuickBooks company ID
            search_term: Search term
            account_type: Optional account type filter
            
        Returns:
            List of matching accounts
        """
        try:
            # Get all accounts of specified type
            accounts = await self.get_chart_of_accounts(
                company_id,
                account_type or 'all'
            )
            
            # Filter by search term
            search_lower = search_term.lower()
            matching = [
                acc for acc in accounts
                if search_lower in acc['name'].lower()
            ]
            
            return matching
            
        except Exception as e:
            logger.error(f"Error searching accounts: {str(e)}")
            return []
    
    def clear_cache(self):
        """Clear the account cache."""
        self.account_cache.clear()
        logger.info("Account cache cleared")
    
    async def get_expense_accounts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all expense accounts."""
        return await self.get_chart_of_accounts(company_id, 'expense')
    
    async def get_income_accounts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all income accounts."""
        return await self.get_chart_of_accounts(company_id, 'income')
    
    async def get_asset_accounts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all asset accounts."""
        return await self.get_chart_of_accounts(company_id, 'asset')
    
    async def get_bank_accounts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all bank accounts."""
        try:
            query = "SELECT * FROM Account WHERE AccountType = 'Bank'"
            response = await self.client.query(company_id, query)
            
            accounts = []
            if 'QueryResponse' in response and 'Account' in response['QueryResponse']:
                for acc in response['QueryResponse']['Account']:
                    accounts.append({
                        'id': acc['Id'],
                        'name': acc['Name'],
                        'type': acc['AccountType'],
                        'current_balance': float(acc.get('CurrentBalance', 0)),
                        'account_number': acc.get('AcctNum', '')
                    })
            
            return accounts
            
        except Exception as e:
            logger.error(f"Error fetching bank accounts: {str(e)}")
            return []
