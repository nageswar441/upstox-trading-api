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
            # TODO: Add custom logic
            # - Store in database
            # - Send notification (email/SMS/Telegram)
            # - Update trading strategy
            # - Calculate P&L
            
        elif webhook.status == "rejected":
            logger.warning(
                f"❌ Order {webhook.order_id} rejected | "
                f"Symbol: {webhook.symbol} | "
                f"Side: {webhook.side}"
            )
            # TODO: Alert user, implement retry logic if needed
            
        elif webhook.status == "cancelled":
            logger.info(f"🚫 Order {webhook.order_id} cancelled")
            # TODO: Update order tracking system
            
        elif webhook.status == "partially_filled":
            logger.info(
                f"⚡ Order {webhook.order_id} partially filled | "
                f"Avg Price: {webhook.average_price}"
            )
            # TODO: Track partial fills, trigger next order if needed
            
        elif webhook.status == "open":
            logger.info(f"📤 Order {webhook.order_id} sent to exchange")
            # TODO: Update order status in tracking system
            
        elif webhook.status == "pending":
            logger.info(f"⏳ Order {webhook.order_id} pending")
            # TODO: Track pending orders
        
        else:
            logger.warning(f"⚠️  Unknown order status: {webhook.status} for order {webhook.order_id}")
        
        return {
            "status": "success",
            "message": "Order update received and processed",
            "order_id": webhook.order_id,
            "event_status": webhook.status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing order webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


@router.post(
    "/position-update",
    summary="Receive Position Update Webhook",
    response_description="Acknowledgment of received position update",
    dependencies=[Depends(verify_api_key)]
)
async def position_update_webhook(
    webhook: PositionUpdateWebhook,
    request: Request,
    x_signature: Optional[str] = Header(None, description="Webhook signature")
):
    """
    Endpoint to receive position update webhooks
    
    Tracks real-time P&L and position changes
    
    Args:
        webhook: Position update data
        request: FastAPI request object
        x_signature: Optional signature for verification
        
    Returns:
        Acknowledgment response
    """
    try:
        # Verify signature if provided
        if x_signature and WEBHOOK_SECRET:
            body = await request.body()
            if not verify_webhook_signature(body, x_signature, WEBHOOK_SECRET):
                logger.warning(f"Invalid webhook signature for position {webhook.symbol}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        logger.info(
            f"📊 Position Update: {webhook.symbol} | "
            f"Qty: {webhook.quantity} | "
            f"Unrealized P&L: ₹{webhook.unrealized_pnl:.2f} | "
            f"Realized P&L: ₹{webhook.realized_pnl:.2f}"
        )
        
        # TODO: Add custom logic
        # - Calculate risk metrics
        # - Trigger stop-loss if P&L crosses threshold
        # - Send alerts for large drawdowns
        # - Update dashboard/analytics
        # - Store historical P&L data
        
        # Example: Check for significant drawdown
        if webhook.unrealized_pnl < -5000:
            logger.warning(f"⚠️  Large unrealized loss detected: ₹{webhook.unrealized_pnl:.2f}")
            # TODO: Send alert or trigger risk management action
        
        return {
            "status": "success",
            "message": "Position update received and processed",
            "symbol": webhook.symbol,
            "quantity": webhook.quantity,
            "unrealized_pnl": webhook.unrealized_pnl,
            "realized_pnl": webhook.realized_pnl,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing position webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


@router.post(
    "/generic",
    summary="Generic Webhook Endpoint",
    response_description="Acknowledgment of received webhook",
    dependencies=[Depends(verify_api_key)]
)
async def generic_webhook(
    webhook: GenericWebhook,
    request: Request,
    x_signature: Optional[str] = Header(None, description="Webhook signature")
):
    """
    Generic webhook endpoint for custom integrations
    
    Can handle any event type with flexible data structure
    
    Args:
        webhook: Generic webhook data
        request: FastAPI request object
        x_signature: Optional signature for verification
        
    Returns:
        Acknowledgment response
    """
    try:
        # Verify signature if provided
        if x_signature and WEBHOOK_SECRET:
            body = await request.body()
            if not verify_webhook_signature(body, x_signature, WEBHOOK_SECRET):
                logger.warning(f"Invalid webhook signature for event {webhook.event}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        logger.info(f"📬 Generic Webhook Received - Event: {webhook.event}")
        
        # Route to specific handlers based on event type
        if webhook.event == "market.alert":
            logger.info(f"🔔 Market Alert: {webhook.data}")
            # TODO: Handle market alerts
            
        elif webhook.event == "strategy.signal":
            logger.info(f"📈 Trading Signal: {webhook.data}")
            # TODO: Handle trading signals
            
        elif webhook.event == "risk.breach":
            logger.warning(f"⚠️  Risk Breach: {webhook.data}")
            # TODO: Handle risk management events
            
        else:
            logger.info(f"Event {webhook.event} received with data: {webhook.data}")
        
        return {
            "status": "success",
            "message": f"Webhook event '{webhook.event}' processed successfully",
            "event": webhook.event,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing generic webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


@router.get(
    "/health",
    summary="Webhook Health Check",
    response_description="Health status of webhook service"
)
async def webhook_health():
    """
    Health check endpoint for webhook service
    
    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "webhook_handler",
        "signature_verification": "enabled" if WEBHOOK_SECRET else "disabled",
        "timestamp": datetime.now().isoformat()
    }


# --- Optional: Webhook Event Storage Model ---

class WebhookEvent(BaseModel):
    """Model for storing webhook events in database (optional)"""
    id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]
    received_at: datetime
    processed: bool = False
    processing_error: Optional[str] = None

# TODO: Implement database storage
# You can add SQLAlchemy or MongoDB integration here to persist webhook events
