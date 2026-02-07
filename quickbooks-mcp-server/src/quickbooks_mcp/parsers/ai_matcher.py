"""
AI-powered account matcher using fuzzy matching and historical patterns.
Intelligently matches transaction descriptions to chart of accounts.
"""
import logging
from typing import Dict, List, Any, Optional
from fuzzywuzzy import fuzz, process
import re

logger = logging.getLogger(__name__)


class AIAccountMatcher:
    """AI-powered account matching for transactions."""
    
    def __init__(self, account_manager):
        """
        Initialize AI account matcher.
        
        Args:
            account_manager: AccountManager instance for fetching chart of accounts
        """
        self.account_manager = account_manager
        self.match_history = {}  # Cache for learning patterns
        self.common_patterns = self._load_common_patterns()
        
    def _load_common_patterns(self) -> Dict[str, List[str]]:
        """Load common transaction patterns for different account types."""
        return {
            'Office Supplies': [
                'office depot', 'staples', 'office max', 'amazon', 'supplies',
                'paper', 'pens', 'folders', 'toner', 'ink'
            ],
            'Utilities': [
                'electric', 'power', 'water', 'gas', 'utility', 'fpl', 'duke energy',
                'internet', 'phone', 'at&t', 'verizon', 'comcast'
            ],
            'Rent Expense': [
                'rent', 'lease', 'property management', 'landlord'
            ],
            'Meals and Entertainment': [
                'restaurant', 'cafe', 'coffee', 'lunch', 'dinner', 'starbucks',
                'mcdonalds', 'chipotle', 'catering'
            ],
            'Auto Expense': [
                'gas', 'fuel', 'shell', 'exxon', 'chevron', 'bp', 'auto',
                'car wash', 'parking', 'toll', 'repair', 'maintenance'
            ],
            'Insurance': [
                'insurance', 'policy', 'premium', 'coverage', 'liability'
            ],
            'Professional Fees': [
                'attorney', 'lawyer', 'accountant', 'cpa', 'consultant',
                'professional services', 'legal'
            ],
            'Bank Charges': [
                'bank fee', 'service charge', 'overdraft', 'atm fee',
                'monthly fee', 'wire transfer'
            ],
            'Advertising': [
                'advertising', 'marketing', 'google ads', 'facebook ads',
                'promotion', 'social media'
            ],
            'Payroll Expenses': [
                'payroll', 'salary', 'wages', 'employee', 'compensation',
                'paycheck', 'direct deposit'
            ],
            'Taxes': [
                'tax', 'irs', 'federal', 'state tax', 'sales tax',
                'property tax', 'payroll tax'
            ],
            'Software': [
                'software', 'subscription', 'saas', 'microsoft', 'adobe',
                'quickbooks', 'app', 'license'
            ],
            'Travel': [
                'hotel', 'airfare', 'airline', 'uber', 'lyft', 'rental car',
                'travel', 'lodging', 'flight'
            ],
            'Postage': [
                'postage', 'shipping', 'fedex', 'ups', 'usps', 'mail'
            ]
        }
    
    async def match_account(
        self,
        description: str,
        amount: Optional[float],
        company_id: str
    ) -> Dict[str, Any]:
        """
        Match transaction description to chart of accounts using AI.
        
        Args:
            description: Transaction description or vendor name
            amount: Transaction amount (optional, helps with matching)
            company_id: QuickBooks company ID
            
        Returns:
            Match result with account name, confidence score, and alternatives
        """
        logger.info(f"Matching account for: {description}")
        
        try:
            # Get chart of accounts
            accounts = await self.account_manager.get_chart_of_accounts(company_id, 'expense')
            
            if not accounts:
                return {
                    'account_name': 'Uncategorized Expense',
                    'confidence': 0.0,
                    'alternatives': [],
                    'method': 'default'
                }
            
            # Clean description
            clean_desc = self._clean_description(description)
            
            # Try pattern matching first (highest confidence)
            pattern_match = self._match_by_pattern(clean_desc, accounts)
            if pattern_match and pattern_match['confidence'] >= 0.9:
                return pattern_match
            
            # Try fuzzy matching on account names
            fuzzy_match = self._fuzzy_match_accounts(clean_desc, accounts)
            if fuzzy_match and fuzzy_match['confidence'] >= 0.8:
                return fuzzy_match
            
            # Try keyword matching
            keyword_match = self._match_by_keywords(clean_desc, accounts)
            if keyword_match and keyword_match['confidence'] >= 0.7:
                return keyword_match
            
            # Return best match or default
            best_match = pattern_match or fuzzy_match or keyword_match
            if best_match:
                return best_match
            
            return {
                'account_name': 'Uncategorized Expense',
                'confidence': 0.0,
                'alternatives': [acc['name'] for acc in accounts[:5]],
                'method': 'default',
                'suggestion': 'Please manually select the correct account'
            }
            
        except Exception as e:
            logger.error(f"Error matching account: {str(e)}")
            return {
                'account_name': 'Uncategorized Expense',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _clean_description(self, description: str) -> str:
        """Clean and normalize transaction description."""
        # Convert to lowercase
        clean = description.lower().strip()
        
        # Remove common prefixes
        prefixes = ['purchase at', 'payment to', 'debit card purchase', 'pos purchase']
        for prefix in prefixes:
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()
        
        # Remove transaction IDs and numbers
        clean = re.sub(r'#\d+', '', clean)
        clean = re.sub(r'\d{10,}', '', clean)  # Remove long numbers
        
        # Remove special characters but keep spaces
        clean = re.sub(r'[^\w\s]', ' ', clean)
        
        # Remove extra whitespace
        clean = ' '.join(clean.split())
        
        return clean
    
    def _match_by_pattern(self, description: str, accounts: List[Dict]) -> Optional[Dict[str, Any]]:
        """Match using predefined patterns."""
        desc_lower = description.lower()
        
        for account_name, keywords in self.common_patterns.items():
            for keyword in keywords:
                if keyword.lower() in desc_lower:
                    # Find this account in the chart of accounts
                    matching_accounts = [
                        acc for acc in accounts
                        if account_name.lower() in acc['name'].lower()
                    ]
                    
                    if matching_accounts:
                        return {
                            'account_name': matching_accounts[0]['name'],
                            'account_id': matching_accounts[0].get('id'),
                            'confidence': 0.95,
                            'method': 'pattern',
                            'matched_keyword': keyword,
                            'alternatives': [acc['name'] for acc in matching_accounts[1:3]]
                        }
        
        return None
    
    def _fuzzy_match_accounts(self, description: str, accounts: List[Dict]) -> Optional[Dict[str, Any]]:
        """Match using fuzzy string matching."""
        account_names = [acc['name'] for acc in accounts]
        
        # Get best matches
        matches = process.extract(description, account_names, scorer=fuzz.token_set_ratio, limit=5)
        
        if matches and matches[0][1] >= 70:  # 70% similarity threshold
            best_match = matches[0]
            matched_account = next(acc for acc in accounts if acc['name'] == best_match[0])
            
            return {
                'account_name': matched_account['name'],
                'account_id': matched_account.get('id'),
                'confidence': best_match[1] / 100.0,
                'method': 'fuzzy',
                'alternatives': [m[0] for m in matches[1:4]]
            }
        
        return None
    
    def _match_by_keywords(self, description: str, accounts: List[Dict]) -> Optional[Dict[str, Any]]:
        """Match using keyword extraction from description."""
        # Extract meaningful words (remove common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        words = [w for w in description.split() if w not in stop_words and len(w) > 2]
        
        if not words:
            return None
        
        # Score each account based on keyword matches
        scores = []
        for account in accounts:
            account_name_lower = account['name'].lower()
            score = sum(1 for word in words if word in account_name_lower)
            if score > 0:
                scores.append((account, score))
        
        if scores:
            # Sort by score
            scores.sort(key=lambda x: x[1], reverse=True)
            best_account, best_score = scores[0]
            
            # Calculate confidence based on match ratio
            confidence = min(0.85, (best_score / len(words)) * 0.85)
            
            return {
                'account_name': best_account['name'],
                'account_id': best_account.get('id'),
                'confidence': confidence,
                'method': 'keyword',
                'matched_words': [w for w in words if w in best_account['name'].lower()],
                'alternatives': [acc[0]['name'] for acc in scores[1:4]]
            }
        
        return None
    
    def learn_from_match(self, description: str, account_name: str):
        """
        Learn from user corrections to improve future matching.
        
        Args:
            description: Transaction description
            account_name: Correct account name chosen by user
        """
        clean_desc = self._clean_description(description)
        
        if clean_desc not in self.match_history:
            self.match_history[clean_desc] = []
        
        self.match_history[clean_desc].append(account_name)
        logger.info(f"Learned: '{clean_desc}' -> '{account_name}'")
    
    def get_match_suggestions(self, description: str, company_id: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Get multiple account suggestions for a transaction.
        
        Args:
            description: Transaction description
            company_id: QuickBooks company ID
            top_n: Number of suggestions to return
            
        Returns:
            List of account suggestions with confidence scores
        """
        # This would return multiple suggestions for user to choose from
        # Useful for UI where user can select from top matches
        pass
