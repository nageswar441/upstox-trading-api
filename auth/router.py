from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from pydantic import BaseModel

from database import get_db
from auth.models import OAuth2Client, Account, Role
from auth.jwt_handler import jwt_handler
from auth.utils import verify_password, get_password_hash

router = APIRouter(prefix="/auth", tags=["Internal Authentication"])

class TokenRequest(BaseModel):
    grant_type: str
    client_id: str
    client_secret: str

# Additional imports needed
import base64
from fastapi.security import OAuth2PasswordRequestForm

@router.post("/token")
async def get_client_token(
    token_request: TokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 Client Credentials Grant
    """
    if token_request.grant_type != "client_credentials":
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid grant_type for this endpoint. Use 'client_credentials'"
        )

    # Authenticate Client
    stmt = select(OAuth2Client).where(OAuth2Client.client_id == token_request.client_id)
    result = await db.execute(stmt)
    client = result.scalars().first()

    if not client or client.client_secret != token_request.client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get Owner Account
    stmt_owner = select(Account).where(Account.id == client.account_id)
    res_owner = await db.execute(stmt_owner)
    owner = res_owner.scalars().first()
    
    if not owner:
         raise HTTPException(status_code=401, detail="Client owner not found")
         
    access_token = jwt_handler.create_access_token(
        data={"sub": str(owner.id), "client_id": client.client_id, "type": "client"}
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "expires_in": jwt_handler.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/login")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 Password Grant (User Login)
    - Client Authentication: Basic Auth (client_id:client_secret)
    - User Authentication: Form Body (username, password)
    """
    # 1. Extract Client Credentials from Basic Auth
    client_id = form_data.client_id # Fallback
    client_secret = form_data.client_secret # Fallback
    
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            encoded_creds = auth_header.split(" ")[1]
            decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
            if ":" in decoded_creds:
                client_id, client_secret = decoded_creds.split(":", 1)
        except Exception:
             pass
             
    if not client_id or not client_secret:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client credentials missing (Basic Auth required)",
            headers={"WWW-Authenticate": "Basic"},
        )

    # 2. Authenticate Client
    stmt = select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    result = await db.execute(stmt)
    client = result.scalars().first()

    if not client or client.client_secret != client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # 3. Authenticate User
    if not form_data.username or not form_data.password:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
        
    stmt_user = select(Account).where(Account.username == form_data.username)
    res_user = await db.execute(stmt_user)
    user = res_user.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 4. Issue Tokens
    access_token = jwt_handler.create_access_token(
        data={"sub": str(user.id), "username": user.username, "aud": client_id}
    )
    refresh_token = jwt_handler.create_refresh_token(
        data={"sub": str(user.id), "username": user.username, "aud": client_id}
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": jwt_handler.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/refresh")
async def refresh_access_token(
    token_req: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh Access Token
    """
    # 1. Verify Refresh Token
    try:
        payload = jwt_handler.decode_token(token_req.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not jwt_handler.verify_token_type(payload, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = payload.get("sub")
    client_id = payload.get("aud")
    username = payload.get("username")
    
    if not user_id:
         raise HTTPException(status_code=401, detail="Invalid token payload")

    # 2. Check if user still exists/active (optional but good practice)
    stmt = select(Account).where(Account.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user or not user.is_active:
         raise HTTPException(status_code=401, detail="User no longer active")

    # 3. Issue New Access Token
    # We can also rotate refresh token here if we wanted (security best practice),
    # but for now we just issue a new access token.
    
    new_access_token = jwt_handler.create_access_token(
        data={"sub": str(user.id), "username": username, "aud": client_id}
    )
    
    return {
        "access_token": new_access_token, 
        "token_type": "bearer",
        "expires_in": jwt_handler.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

class UserRegistrationModel(BaseModel):
    username: str
    email: str
    password: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistrationModel,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account
    """
    # Check if user already exists
    stmt = select(Account).where((Account.username == user_data.username) | (Account.email == user_data.email))
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
        
    # Get default role (e.g., 'trader')
    stmt_role = select(Role).where(Role.name == "trader")
    result_role = await db.execute(stmt_role)
    default_role = result_role.scalars().first()
    
    if not default_role:
        # Fallback if role doesn't exist, though it should if seeded
        # Ideally we might create it or create user without role
        pass

    # Create new account
    new_account = Account(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=default_role,
        is_active=True
    )
    
    db.add(new_account)
    await db.commit()
    await db.refresh(new_account)
    
    return {
        "id": new_account.id,
        "username": new_account.username,
        "email": new_account.email,
        "message": "User registered successfully"
    }
