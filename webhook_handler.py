from fastapi import APIRouter, HTTPException, Header, Request
import logging
from config import WEBHOOK_SECRET
from models import WebhookPayload

router = APIRouter()
logging.basicConfig(level=logging.INFO)

@router.post(
    "/webhook/upstox",
    summary="Receive Upstox Webhooks",
    description="Endpoint for Upstox to send order updates, trade confirmations, etc.",
    tags=["Webhooks"]
)
async def receive_webhook(request: Request, payload: WebhookPayload):
    """
    Handle incoming webhooks from Upstox
    Events: order.placed, order.completed, order.cancelled, trade.created, etc.
    """
    try:
        # Verify webhook signature
        signature = request.headers.get("x-webhook-signature", "")
        
        if signature != WEBHOOK_SECRET:
            logging.warning(f"⚠️ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        event_type = payload.event
        event_data = payload.data
        
        logging.info(f"📨 Webhook received: {event_type}")
        logging.info(f"Data: {event_data}")
        
        # Process different event types
        if event_type == "order.placed":
            # Handle order placed event
            order_id = event_data.get("order_id")
            symbol = event_data.get("symbol")
            quantity = event_data.get("quantity")
            logging.info(f"✅ Order placed: {order_id} - {symbol} x{quantity}")
            # Add your custom logic here: database update, notifications, etc.
            
        elif event_type == "order.completed":
            # Handle order completion
            order_id = event_data.get("order_id")
            status = event_data.get("status")
            logging.info(f"✅ Order completed: {order_id} - Status: {status}")
            
        elif event_type == "order.cancelled":
            # Handle order cancellation
            order_id = event_data.get("order_id")
            reason = event_data.get("cancel_reason", "User cancelled")
            logging.info(f"❌ Order cancelled: {order_id} - Reason: {reason}")
            
        elif event_type == "trade.created":
            # Handle trade execution
            trade_id = event_data.get("trade_id")
            order_id = event_data.get("order_id")
            symbol = event_data.get("symbol")
            quantity = event_data.get("quantity")
            price = event_data.get("price")
            trade_type = event_data.get("trade_type", "BUY")
            
            logging.info(f"💰 Trade executed: {trade_id}")
            logging.info(f"   Order ID: {order_id}")
            logging.info(f"   Symbol: {symbol}")
            logging.info(f"   Quantity: {quantity}")
            logging.info(f"   Price: ₹{price}")
            logging.info(f"   Type: {trade_type}")
            
            # Add your custom logic here:
            # - Update portfolio
            # - Calculate P&L
            # - Send notifications
            # - Update database
            # - Trigger other strategies
            
        elif event_type == "order.rejected":
            # Handle order rejection
            order_id = event_data.get("order_id")
            reason = event_data.get("rejection_reason")
            logging.error(f"🚫 Order rejected: {order_id} - Reason: {reason}")
            
        elif event_type == "position.updated":
            # Handle position updates
            symbol = event_data.get("symbol")
            quantity = event_data.get("quantity")
            avg_price = event_data.get("average_price")
            pnl = event_data.get("unrealized_pnl")
            logging.info(f"📊 Position updated: {symbol} - Qty: {quantity}, Avg: ₹{avg_price}, P&L: ₹{pnl}")
            
        elif event_type == "margin.updated":
            # Handle margin updates
            available_margin = event_data.get("available_margin")
            used_margin = event_data.get("used_margin")
            logging.info(f"💳 Margin updated - Available: ₹{available_margin}, Used: ₹{used_margin}")
            
        else:
            logging.warning(f"⚠️ Unknown event type: {event_type}")
        
        # Return success response to Upstox
        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "event": event_type,
            "timestamp": payload.timestamp
        }
        
    except Exception as e:
        logging.error(f"❌ Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/webhook/test",
    summary="Test Webhook Endpoint",
    description="Test if webhook endpoint is accessible",
    tags=["Webhooks"]
)
async def test_webhook():
    """Test endpoint to verify webhook is working"""
    return {
        "status": "success",
        "message": "Webhook endpoint is active and ready to receive events",
        "endpoint": "/webhook/upstox"
    }

