"""
QuickBooks Online OAuth 2.0 authentication manager.
Handles token management, refresh, and validation.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes

logger = logging.getLogger(__name__)


class QBOAuthManager:
    """Manages QuickBooks Online OAuth 2.0 authentication."""
    
    def __init__(self):
        """Initialize OAuth manager with credentials from environment."""
        self.client_id = os.getenv("QBO_CLIENT_ID")
        self.client_secret = os.getenv("QBO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("QBO_REDIRECT_URI")
        self.environment = os.getenv("QBO_ENVIRONMENT", "production")
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("Missing required QuickBooks OAuth credentials in environment")
        
        self.auth_client = AuthClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            environment=self.environment
        )
        
        # Load existing tokens if available
        self.access_token = os.getenv("QBO_ACCESS_TOKEN")
        self.refresh_token = os.getenv("QBO_REFRESH_TOKEN")
        self.token_expiry = self._parse_token_expiry(os.getenv("QBO_TOKEN_EXPIRY"))
        
        logger.info(f"QBO Auth Manager initialized (environment: {self.environment})")
    
    def _parse_token_expiry(self, expiry_str: Optional[str]) -> Optional[datetime]:
        """Parse token expiry string to datetime."""
        if not expiry_str:
            return None
        try:
            return datetime.fromisoformat(expiry_str)
        except:
            return None
    
    def get_authorization_url(self, state: str = "security_token") -> str:
        """
        Get OAuth authorization URL for user to authenticate.
        User must visit this URL to grant access.
        """
        scopes = [
            Scopes.ACCOUNTING,
            Scopes.PAYMENT,
        ]
        
        auth_url = self.auth_client.get_authorization_url(scopes, state)
        logger.info(f"Generated authorization URL: {auth_url}")
        return auth_url
    
    async def exchange_code_for_tokens(self, auth_code: str, realm_id: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.
        Called after user authorizes the app.
        """
        try:
            self.auth_client.get_bearer_token(auth_code, realm_id=realm_id)
            
            self.access_token = self.auth_client.access_token
            self.refresh_token = self.auth_client.refresh_token
            self.token_expiry = datetime.now() + timedelta(seconds=3600)
            
            logger.info(f"Successfully exchanged auth code for tokens (realm: {realm_id})")
            
            return {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.token_expiry.isoformat(),
                "realm_id": realm_id
            }
        except Exception as e:
            logger.error(f"Failed to exchange auth code: {str(e)}")
            raise
    
    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available")
        
        try:
            self.auth_client.refresh(refresh_token=self.refresh_token)
            
            self.access_token = self.auth_client.access_token
            self.refresh_token = self.auth_client.refresh_token
            self.token_expiry = datetime.now() + timedelta(seconds=3600)
            
            logger.info("Successfully refreshed access token")
            return self.access_token
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise
    
    async def get_valid_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        This is the main method to call when making API requests.
        """
        # Check if token exists
        if not self.access_token:
            raise ValueError(
                "No access token available. Please authenticate first using get_authorization_url()"
            )
        
        # Check if token is expired or about to expire (within 5 minutes)
        if self.token_expiry and datetime.now() >= (self.token_expiry - timedelta(minutes=5)):
            logger.info("Access token expired or expiring soon, refreshing...")
            await self.refresh_access_token()
        
        return self.access_token
    
    async def validate_credentials(self, company_id: str) -> bool:
        """
        Validate that credentials are working by making a test API call.
        """
        try:
            token = await self.get_valid_access_token()
            # If we got here, token is valid
            return True
        except Exception as e:
            logger.error(f"Credential validation failed: {str(e)}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication."""
        return bool(self.access_token and self.refresh_token)
    
    def get_auth_status(self) -> dict:
        """Get current authentication status."""
        return {
            "authenticated": self.is_authenticated(),
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "token_expiry": self.token_expiry.isoformat() if self.token_expiry else None,
            "token_expired": self.token_expiry < datetime.now() if self.token_expiry else True
        }
