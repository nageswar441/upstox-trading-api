from fastapi import APIRouter, Request, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import hmac
import hashlib
from datetime import datetime

from config import INTERNAL_API_KEY, WEBHOOK_SECRET

router = APIRouter(prefix="/webhook", tags=["Webhooks"])

# Use the centralized logger
logger = logging.getLogger(__name__)


# --- Webhook Models ---

class OrderUpdateWebhook(BaseModel):
    """Model for order update webhook from Upstox"""
    event: str = Field(..., example="order.update", description="Event type")
    order_id: str = Field(..., example="240101000012345", description="Upstox order ID")
    exchange_order_id: Optional[str] = Field(None, description="Exchange order ID")
    symbol: str = Field(..., example="NSE_EQ|INE123A01016", description="Trading symbol")
    quantity: int = Field(..., example=10, description="Order quantity")
    status: str = Field(..., example="complete", description="Order status")
    order_type: str = Field(..., example="MARKET", description="Order type")
    side: str = Field(..., example="BUY", description="BUY or SELL")
    price: Optional[float] = Field(None, example=520.50, description="Order price")
    average_price: Optional[float] = Field(None, example=520.35, description="Average execution price")
    timestamp: str = Field(..., example="2025-11-16T13:30:45+05:30", description="Event timestamp")
    product: str = Field(..., example="INTRADAY", description="Product type")


class PositionUpdateWebhook(BaseModel):
    """Model for position update webhook"""
    event: str = Field(..., example="position.update", description="Event type")
    symbol: str = Field(..., example="NSE_EQ|INE123A01016", description="Trading symbol")
    quantity: int = Field(..., example=50, description="Position quantity")
    average_price: float = Field(..., example=515.20, description="Average price")
    unrealized_pnl: float = Field(..., example=265.00, description="Unrealized P&L")
    realized_pnl: float = Field(..., example=0.00, description="Realized P&L")
    timestamp: str = Field(..., example="2025-11-16T13:30:45+05:30", description="Event timestamp")


class GenericWebhook(BaseModel):
    """Generic webhook model for custom integrations"""
    event: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: Optional[str] = Field(None, description="Event timestamp")


# --- Security: Verify webhook signature ---

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 signature for webhook payload
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Signature header
        secret: Webhook secret for verification
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not secret:
        logger.warning("Webhook secret not configured - skipping signature verification")
        return True
    
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False


# --- Authentication dependency ---

def verify_api_key(x_api_key: str = Header(..., description="Internal API key")):
    """Verify internal API key for webhook endpoints"""
    if x_api_key != INTERNAL_API_KEY:
        logger.warning("Unauthorized webhook attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# --- Webhook Endpoints ---

@router.post(
    "/order-update",
    summary="Receive Order Update Webhook",
    response_description="Acknowledgment of received order update",
    dependencies=[Depends(verify_api_key)]
)
async def order_update_webhook(
    webhook: OrderUpdateWebhook,
    request: Request,
    x_signature: Optional[str] = Header(None, description="Webhook signature")
):
    """
    Endpoint to receive order update webhooks from Upstox
    
    Handles all order status transitions:
    - pending: Order placed but not yet sent to exchange
    - open: Order sent to exchange
    - complete: Order fully executed
    - rejected: Order rejected by exchange
    - cancelled: Order cancelled by user
    - partially_filled: Order partially executed
    
    Args:
        webhook: Order update data
        request: FastAPI request object
        x_signature: Optional signature for verification
        
    Returns:
        Acknowledgment response
    """
    try:
        # Verify signature if provided and secret is configured
        if x_signature and WEBHOOK_SECRET:
            body = await request.body()
            if not verify_webhook_signature(body, x_signature, WEBHOOK_SECRET):
                logger.warning(f"Invalid webhook signature for order {webhook.order_id}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        logger.info(f"📨 Order Update: {webhook.order_id} - Status: {webhook.status}")
        
        # Handle different order statuses
        if webhook.status == "complete":
            logger.info(
                f"✅ Order {webhook.order_id} completed | "
                f"Symbol: {webhook.symbol} | "
                f"Side: {webhook.side} | "
                f"Qty: {webhook.quantity} | "
                f"Avg Price: {webhook.average_price}"
            )
            # Add custom logic: Database update, notifications, etc.
            
        elif webhook.status == "rejected":
            logger.warning(
                f"❌ Order {webhook.order_id} rejected | "
                f"Symbol: {webhook.symbol} | "
                f"Side: {webhook.side}"
            )
            # Add custom logic: Alert user, retry logic, etc.
            
        elif webhook.status == "cancelled":
            logger.info(f"🚫 Order {webhook.order_id} cancelled")
            # Add custom logic: Update order tracking
            
        elif webhook.status == "partially_filled":
            logger.info(
                f"⚡ Order {webhook.order_id} partially filled | "
                f"Avg Price: {webhook.average_price}"
            )
            # Add custom logic: Track partial fills
            
        elif webhook.status == "open":
            logger.info(f"📤 Order {webhook.order_id} sent to exchange")
            
        elif webhook
