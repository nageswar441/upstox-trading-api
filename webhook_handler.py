from fastapi import APIRouter, Request, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import hmac
import hashlib
from datetime import datetime

from config import INTERNAL_API_KEY

router = APIRouter(prefix="/webhook", tags=["Webhooks"])
logging.basicConfig(level=logging.INFO)

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

# --- Security: Verify webhook signature (optional but recommended) ---
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC signature for webhook payload
    Usage: Pass webhook secret from Upstox/your system
    """
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)

# --- Authentication dependency ---
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != INTERNAL_API_KEY:
        logging.warning("Unauthorized webhook attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")

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
    x_signature: Optional[str] = Header(None)
):
    """
    Endpoint to receive order update webhooks from Upstox
    Logs order status changes and can trigger custom logic
    """
    try:
        # Optional: Verify signature if Upstox provides one
        # body = await request.body()
        # if x_signature and not verify_webhook_signature(body, x_signature, WEBHOOK_SECRET):
        #     raise HTTPException(status_code=401, detail="Invalid signature")
        
        logging.info(f"Order Update Received: {webhook.order_id} - Status: {webhook.status}")
        
        # Add your custom logic here:
        # - Store in database
        # - Send notification (email/SMS/Telegram)
        # - Update trading strategy
        # - Calculate P&L
        # - Trigger next order in a strategy chain
        
        if webhook.status == "complete":
            logging.info(f"Order {webhook.order_id} completed at avg price: {webhook.average_price}")
        elif webhook.status == "rejected":
            logging.warning(f"Order {webhook.order_id} rejected")
        
        return {
            "status": "success",
            "message": "Order update received",
            "order_id": webhook.order_id,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logging.error(f"Error processing order webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/position-update",
    summary="Receive Position Update Webhook",
    response_description="Acknowledgment of received position update",
    dependencies=[Depends(verify_api_key)]
)
async def position_update_webhook(
    webhook: PositionUpdateWebhook,
    request: Request
):
    """
    Endpoint to receive position update webhooks
    Tracks real-time P&L and position changes
    """
    try:
        logging.info(f"Position Update: {webhook.symbol} - Qty: {webhook.quantity}, PnL: {webhook.unrealized_pnl}")
        
        # Add your custom logic:
        # - Calculate risk metrics
        # - Trigger stop-loss if PnL crosses threshold
        # - Send alerts for large drawdowns
        # - Update dashboard/analytics
        
        return {
            "status": "success",
            "message": "Position update received",
            "symbol": webhook.symbol,
            "pnl": webhook.unrealized_pnl
        }
    
    except Exception as e:
        logging.error(f"Error processing position webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/generic",
    summary="Generic Webhook Endpoint",
    response_description="Acknowledgment of received webhook",
    dependencies=[Depends(verify_api_key)]
)
async def generic_webhook(webhook: GenericWebhook):
    """
    Generic webhook endpoint for custom integrations
    Can handle any event type with flexible data structure
    """
    try:
        logging.info(f"Generic Webhook Received - Event: {webhook.event}")
        
        # Route to specific handlers based on event type
        if webhook.event == "market.alert":
            # Handle market alerts
            pass
        elif webhook.event == "strategy.signal":
            # Handle trading signals
            pass
        
        return {
            "status": "success",
            "message": f"Webhook {webhook.event} processed",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logging.error(f"Error processing generic webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/health",
    summary="Webhook Health Check",
    response_description="Health status of webhook service"
)
async def webhook_health():
    """Health check endpoint for webhook service"""
    return {
        "status": "healthy",
        "service": "webhook_handler",
        "timestamp": datetime.now().isoformat()
    }

# --- Webhook Event Storage (optional) ---
class WebhookEvent(BaseModel):
    """Model for storing webhook events in database"""
    id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]
    received_at: datetime
    processed: bool = False
    processing_error: Optional[str] = None

# You can add database storage logic here
# Example with SQLAlchemy or MongoDB to persist webhook events
