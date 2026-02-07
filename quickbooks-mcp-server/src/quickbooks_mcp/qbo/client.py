"""
QuickBooks Online API client.
Handles all API requests to QuickBooks Online.
"""
import logging
from typing import Any, Dict, Optional
import httpx
from .auth import QBOAuthManager

logger = logging.getLogger(__name__)


class QBOClient:
    """QuickBooks Online API client."""
    
    BASE_URL_PRODUCTION = "https://quickbooks.api.intuit.com/v3/company"
    BASE_URL_SANDBOX = "https://sandbox-quickbooks.api.intuit.com/v3/company"
    
    def __init__(self, auth_manager: QBOAuthManager):
        """Initialize QBO client with auth manager."""
        self.auth_manager = auth_manager
        self.base_url = (
            self.BASE_URL_PRODUCTION 
            if auth_manager.environment == "production" 
            else self.BASE_URL_SANDBOX
        )
        logger.info(f"QBO Client initialized (base URL: {self.base_url})")
    
    async def _make_request(
        self,
        method: str,
        company_id: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to QuickBooks API."""
        access_token = await self.auth_manager.get_valid_access_token()
        
        url = f"{self.base_url}/{company_id}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                raise
    
    async def query(self, company_id: str, query: str) -> Dict[str, Any]:
        """Execute a QuickBooks query."""
        return await self._make_request(
            "GET",
            company_id,
            "query",
            params={"query": query}
        )
    
    async def create_entity(self, company_id: str, entity_type: str, data: Dict) -> Dict[str, Any]:
        """Create a new entity (Invoice, Expense, etc.)."""
        return await self._make_request(
            "POST",
            company_id,
            entity_type.lower(),
            data=data
        )
    
    async def get_entity(self, company_id: str, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by ID."""
        return await self._make_request(
            "GET",
            company_id,
            f"{entity_type.lower()}/{entity_id}"
        )
    
    async def update_entity(self, company_id: str, entity_type: str, data: Dict) -> Dict[str, Any]:
        """Update an existing entity."""
        return await self._make_request(
            "POST",
            company_id,
            entity_type.lower(),
            data=data
        )
    
    async def get_report(self, company_id: str, report_name: str, params: Dict) -> Dict[str, Any]:
        """Get a QuickBooks report."""
        return await self._make_request(
            "GET",
            company_id,
            f"reports/{report_name}",
            params=params
        )
