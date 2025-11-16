"""API Key Authentication for Webhooks and Bots

This module provides API key-based authentication for machine-to-machine
communication, webhooks, and automated trading bots.
"""

from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import hashlib
import secrets
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# API Key Header Configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# In production, store hashed API keys in database
# This is a simple in-memory store for demonstration
VALID_API_KEYS = set()


class APIKeyManager:
    """Manages API key generation, validation, and storage"""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure random API key
        
        Returns:
            32-byte hexadecimal API key string
        """
        api_key = secrets.token_hex(32)
        logger.info("Generated new API key")
        return api_key
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for secure storage
        
        Args:
            api_key: Plain text API key
            
        Returns:
            SHA-256 hash of the API key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def add_api_key(api_key: str, user_id: str = None) -> dict:
        """Add a new API key to the valid keys store
        
        Args:
            api_key: Plain text API key to add
            user_id: Optional user ID associated with the key
            
        Returns:
            Dictionary with API key info
        """
        hashed_key = APIKeyManager.hash_api_key(api_key)
        
        # In production, store in database with:
        # - hashed_key
        # - user_id
        # - created_at
        # - expires_at
        # - permissions/scopes
        # - rate_limit
        
        VALID_API_KEYS.add(hashed_key)
        logger.info(f"Added API key for user: {user_id or 'unknown'}")
        
        return {
            "api_key": api_key,
            "key_id": hashed_key[:16],  # Show only first 16 chars
            "user_id": user_id,
            "status": "active"
        }
    
    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """Validate an API key against stored keys
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not api_key:
            return False
        
        hashed_key = APIKeyManager.hash_api_key(api_key)
        is_valid = hashed_key in VALID_API_KEYS
        
        if is_valid:
            logger.info("API key validated successfully")
        else:
            logger.warning("Invalid API key attempt")
        
        return is_valid
    
    @staticmethod
    def revoke_api_key(api_key: str) -> bool:
        """Revoke an API key
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if revoked successfully
        """
        hashed_key = APIKeyManager.hash_api_key(api_key)
        
        if hashed_key in VALID_API_KEYS:
            VALID_API_KEYS.remove(hashed_key)
            logger.info("API key revoked")
            return True
        
        logger.warning("Attempted to revoke non-existent API key")
        return False


api_key_manager = APIKeyManager()


async def get_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Dependency to validate API key from header
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        Valid API key string
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not api_key:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if not api_key_manager.validate_api_key(api_key):
        logger.warning(f"Invalid API key provided: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired API key"
        )
    
    return api_key


def require_api_key(api_key: str = Security(get_api_key)) -> str:
    """Dependency that requires valid API key for endpoint access
    
    Usage:
        @app.post("/webhook")
        async def webhook(data: dict, api_key: str = Depends(require_api_key)):
            # Your webhook logic here
            pass
    
    Args:
        api_key: Validated API key
        
    Returns:
        Valid API key
    """
    return api_key


# Initialize with a demo API key (remove in production)
if settings.ENVIRONMENT == "dev":
    demo_key = "demo_api_key_for_development_only"
    api_key_manager.add_api_key(demo_key, user_id="demo_user")
    logger.info(f"Demo API key initialized: {demo_key}")
