"""JWT Token Handler for Session Management

This module handles JWT token creation, validation, and user authentication
for maintaining secure sessions in the Upstox Trading API.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT Configuration
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES


class JWTHandler:
    """Handles JWT token operations"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a new JWT access token
        
        Args:
            data: Dictionary containing user information to encode
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Created access token for user: {data.get('sub', 'unknown')}")
        
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create a refresh token with longer expiry
        
        Args:
            data: Dictionary containing user information
            
        Returns:
            Encoded refresh token string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=7)  # Refresh tokens last 7 days
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Created refresh token for user: {data.get('sub', 'unknown')}")
        
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.error(f"JWT decode error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def verify_token_type(payload: dict, expected_type: str) -> bool:
        """Verify token type (access or refresh)
        
        Args:
            payload: Decoded token payload
            expected_type: Expected token type ('access' or 'refresh')
            
        Returns:
            True if token type matches
        """
        return payload.get("type") == expected_type


jwt_handler = JWTHandler()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency to get current authenticated user from JWT token
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt_handler.decode_token(token)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            logger.warning("Token missing 'sub' claim")
            raise credentials_exception
        
        # Verify it's an access token
        if not jwt_handler.verify_token_type(payload, "access"):
            logger.warning("Invalid token type provided")
            raise credentials_exception
        
        # In production, fetch user from database
        # For now, return payload data
        logger.info(f"Authenticated user: {user_id}")
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "upstox_access_token": payload.get("upstox_access_token"),
        }
        
    except JWTError:
        logger.error("JWT validation failed")
        raise credentials_exception


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency to ensure user is active
    
    Args:
        current_user: User dict from get_current_user
        
    Returns:
        Active user information
        
    Raises:
        HTTPException: If user is inactive
    """
    # In production, check if user is active in database
    if current_user.get("disabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return current_user


def create_tokens_for_user(user_id: str, email: str, upstox_token: str) -> dict:
    """Create both access and refresh tokens for a user
    
    Args:
        user_id: Unique user identifier
        email: User email
        upstox_token: Upstox OAuth access token
        
    Returns:
        Dictionary with access_token and refresh_token
    """
    token_data = {
        "sub": user_id,
        "email": email,
        "upstox_access_token": upstox_token,
    }
    
    access_token = jwt_handler.create_access_token(token_data)
    refresh_token = jwt_handler.create_refresh_token(token_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
