from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import httpx
import logging
from contextlib import asynccontextmanager
from typing import Optional

from config import UPSTOX_API_TOKEN, UPSTOX_BASE_URL, INTERNAL_API_KEY, ALLOWED_ORIGINS
from models import OrderRequest, OrderResponse, AccountInfo, MarketFeedResponse
from webhook_handler import router as webhook_router
from pydantic import BaseModel
from auth.jwt_handler import jwt_handler
from websocket_handler import router as websocket_router, manager
from options import options_router

# Configure logging (centralized)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    logger.info("🚀 Starting Upstox Trading API...")
    yield
    # Cleanup on shutdown
    logger.info("🛑 Shutting down gracefully...")
    if manager.upstox_ws and not manager.upstox_ws.closed:
        await manager.upstox_ws.close()
    logger.info("✅ Cleanup completed")

app = FastAPI(
    title="Upstox Trading API",
    description="Production-ready API for Upstox trading with WebSocket and Webhook support",
    version="2.1.0",
    lifespan=lifespan
)

# Fixed CORS configuration - specify allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # No more wildcard!
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(webhook_router)
app.include_router(websocket_router, prefix="/api/v1")
app.include_router(options_router)  # Options trading API


def upstox_headers() -> dict:
    """Generate headers for Upstox API requests"""
    return {
        "Authorization": f"Bearer {UPSTOX_API_TOKEN}",
        "Api-Version": "2.0",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def verify_api_key(x_api_key: str = Header(..., description="Internal API key for authentication")) -> bool:
    """
    Verify internal API key from request header
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Raises:
        HTTPException: If API key is invalid
        
    Returns:
        True if valid
    """
    if x_api_key != INTERNAL_API_KEY:
        logger.warning(f"Unauthorized access attempt with key: {x_api_key[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/")
@limiter.limit("10/minute")
async def root():
    """
    Root endpoint - API health check
    
    Returns:
        API status and documentation link
    """
    return {
        "status": "active",
        "message": "Upstox Trading API",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    
    Returns:
        Health status of the service
    """
    return {
        "status": "healthy",
        "service": "upstox-trading-api",
        "websocket_connections": len(manager.active_connections),
        "subscribed_instruments": len(manager.subscribed_instruments)
    }


@app.get(
    "/api/v1/account/profile",
    response_model=AccountInfo,
    dependencies=[Depends(verify_api_key)],
    summary="Get Account Profile",
    description="Retrieve user account information from Upstox"
)
@limiter.limit("30/minute")
async def get_account_profile():
    """
    Fetch user profile from Upstox
    
    Returns:
        AccountInfo with user details
        
    Raises:
        HTTPException: If API request fails
    """
    url = f"{UPSTOX_BASE_URL}/user/profile"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=upstox_headers())
            response.raise_for_status()
            return response.json()
            
    except httpx.TimeoutException:
        logger.error("Upstox API timeout while fetching profile")
        raise HTTPException(status_code=504, detail="Upstox API timeout")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from Upstox: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Upstox API error: {e.response.text}"
        )
        
    except httpx.RequestError as e:
        logger.error(f"Network error while connecting to Upstox: {str(e)}")
        raise HTTPException(status_code=503, detail="Failed to connect to Upstox API")
        
    except Exception as e:
        logger.error(f"Unexpected error fetching profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/api/v1/orders/place",
    response_model=OrderResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Place Order",
    description="Place a new order on Upstox"
)
@limiter.limit("20/minute")
async def place_order(order: OrderRequest):
    """
    Place a trading order on Upstox
    
    Args:
        order: Order details including symbol, quantity, type, and side
        
    Returns:
        OrderResponse with order ID and status
        
    Raises:
        HTTPException: If order placement fails
    """
    url = f"{UPSTOX_BASE_URL}/order/place"
    
    # Build payload
    payload = {
        "quantity": order.quantity,
        "product": order.product,
        "validity": order.validity,
        "price": order.price if order.order_type == "LIMIT" else 0,
        "instrument_token": order.symbol,
        "order_type": order.order_type,
        "transaction_type": order.side,  # Use side field consistently
        "disclosed_quantity": order.disclosed_quantity or 0,
        "trigger_price": order.trigger_price or 0
    }
    
    logger.info(f"Placing order: {order.side} {order.quantity} {order.symbol} @ {order.order_type}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=upstox_headers(), json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Order placed successfully: {result}")
            return result
            
    except httpx.TimeoutException:
        logger.error("Upstox API timeout while placing order")
        raise HTTPException(status_code=504, detail="Order placement timeout")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Order placement failed: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Order failed: {e.response.text}"
        )
        
    except httpx.RequestError as e:
        logger.error(f"Network error during order placement: {str(e)}")
        raise HTTPException(status_code=503, detail="Failed to connect to Upstox API")
        
    except Exception as e:
        logger.error(f"Unexpected error placing order: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/v1/market/quote",
    response_model=MarketFeedResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Get Market Quote",
    description="Fetch real-time market quote for a symbol"
)
@limiter.limit("60/minute")
async def get_market_quote(
    symbol: str = Query(..., example="NSE_EQ|INE155A01022", description="Instrument key")
):
    """
    Get market quote for a specific instrument
    
    Args:
        symbol: Instrument key (e.g., NSE_EQ|INE155A01022)
        
    Returns:
        MarketFeedResponse with price and market data
        
    Raises:
        HTTPException: If quote fetch fails
    """
    url = f"{UPSTOX_BASE_URL}/market-quote/quotes"
    params = {"symbols": symbol}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=upstox_headers(), params=params)
            response.raise_for_status()
            return response.json()
            
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching quote for {symbol}")
        raise HTTPException(status_code=504, detail="Market quote fetch timeout")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Quote fetch failed: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Quote fetch error: {e.response.text}"
        )
        
    except httpx.RequestError as e:
        logger.error(f"Network error fetching quote: {str(e)}")
        raise HTTPException(status_code=503, detail="Failed to connect to Upstox API")
        
    except Exception as e:
        logger.error(f"Unexpected error fetching quote: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



# Pydantic model for refresh token request
class RefreshTokenRequest(BaseModel):
    refresh_token: str


@app.post(
    "/api/v1/auth/refresh",
    summary="Refresh Access Token",
    description="Get a new access token using a valid refresh token"
)
@limiter.limit("10/minute")
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Refresh expired access token using refresh token
    
    Args:
        request: RefreshTokenRequest containing refresh_token
    
    Returns:
        New access token and expiration info
    
    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    try:
        # Decode and validate refresh token
        payload = jwt_handler.decode_token(request.refresh_token)
        
        # Verify it's a refresh token (not access token)
        if not jwt_handler.verify_token_type(payload, "refresh"):
            logger.warning("Invalid token type provided for refresh")
            raise HTTPException(
                status_code=401,
                detail="Invalid token type. Refresh token required."
            )
        
        # Extract user info from refresh token
        user_id = payload.get("sub")
        email = payload.get("email")
        upstox_token = payload.get("upstox_access_token")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Generate NEW access token (refresh token stays the same)
        new_access_token = jwt_handler.create_access_token({
            "sub": user_id,
            "email": email,
            "upstox_access_token": upstox_token
        })
        
        logger.info(f"Access token refreshed for user: {user_id}")
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 1800,  # 30 minutes in seconds
            "message": "Access token refreshed successfully"
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
