"""OAuth 2.0 Authentication for Upstox Trading API

This module handles OAuth 2.0 flow for authenticating users with Upstox.
Users authorize your app via Upstox login, and you receive access/refresh tokens.
"""

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
import requests
import logging
from config import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Upstox OAuth Configuration
UPSTOX_OAUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


class OAuthManager:
    """Manages OAuth 2.0 flow for Upstox"""
    
    def __init__(self):
        self.client_id = settings.UPSTOX_API_KEY
        self.client_secret = settings.UPSTOX_API_SECRET
        self.redirect_uri = settings.UPSTOX_REDIRECT_URI
        self.tokens = {}  # In production, use Redis/DB for token storage
    
    def get_authorization_url(self, state: str = None) -> str:
        """Generate Upstox OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
        }
        if state:
            params["state"] = state
        
        url = f"{UPSTOX_OAUTH_URL}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        return url
    
    def exchange_code_for_token(self, code: str) -> dict:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            response = requests.post(UPSTOX_TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            logger.info("Successfully exchanged code for access token")
            
            # Store token with expiry time
            token_data["expires_at"] = datetime.now() + timedelta(
                seconds=token_data.get("expires_in", 86400)
            )
            
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain access token from Upstox"
            )
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh expired access token"""
        try:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            response = requests.post(UPSTOX_TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            logger.info("Successfully refreshed access token")
            
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh access token"
            )


oauth_manager = OAuthManager()


@router.get("/login")
def login_upstox(request: Request):
    """Redirect user to Upstox OAuth login page"""
    state = request.session.get("oauth_state", "random_state_string")
    auth_url = oauth_manager.get_authorization_url(state=state)
    logger.info("Redirecting user to Upstox OAuth login")
    return RedirectResponse(auth_url)


@router.get("/callback")
async def auth_callback(code: str, state: str = None):
    """Handle OAuth callback from Upstox"""
    try:
        # Exchange code for access token
        token_data = oauth_manager.exchange_code_for_token(code)
        
        # In production:
        # 1. Store tokens securely (Redis/Database)
        # 2. Create user session
        # 3. Generate JWT for your app
        
        logger.info("OAuth callback successful")
        return {
            "status": "success",
            "message": "Authentication successful",
            "access_token": token_data.get("access_token"),
            "expires_in": token_data.get("expires_in"),
        }
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed"
        )


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh expired access token"""
    try:
        token_data = oauth_manager.refresh_access_token(refresh_token)
        return {
            "status": "success",
            "access_token": token_data.get("access_token"),
            "expires_in": token_data.get("expires_in"),
        }
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )
