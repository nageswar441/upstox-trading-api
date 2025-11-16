from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import websockets
import json
import logging
import asyncio
import uuid
from typing import List, Dict
from datetime import datetime

from config import UPSTOX_API_TOKEN, UPSTOX_WEBSOCKET_URL
from models import WebSocketSubscription, SubscriptionResponse

router = APIRouter()

# Use centralized logger
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and Upstox feed"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.upstox_ws = None
        self.subscribed_instruments: List[str] = []
        self.is_listening = False
        self._listener_lock = asyncio.Lock()  # Prevent race conditions
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
    
    async def connect(self, websocket: WebSocket) -> None:
        """Accept and store client WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove client WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"❌ Client disconnected. Remaining connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict) -> None:
        """Broadcast market data to all connected clients"""
        if not self.active_connections:
            return
        
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError) as e:
                logger.warning(f"Client disconnected during broadcast: {e}")
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def connect_to_upstox(self) -> bool:
        """Connect to Upstox WebSocket feed"""
        headers = {
            "Authorization": f"Bearer {UPSTOX_API_TOKEN}",
            "Accept": "application/json"
        }
        
        try:
            # Close existing connection if any
            if self.upstox_ws and not self.upstox_ws.closed:
                logger.info("Closing existing Upstox WebSocket connection")
                await self.upstox_ws.close()
            
            self.upstox_ws = await websockets.connect(
                UPSTOX_WEBSOCKET_URL,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info("🔗 Connected to Upstox WebSocket")
            self._reconnect_attempts = 0
            return True
            
        except Exception as e:
            self._reconnect_attempts += 1
            logger.error(f"❌ Upstox WebSocket connection failed (attempt {self._reconnect_attempts}): {e}")
            return False
    
    async def subscribe_instruments(self, instrument_keys: List[str], mode: str = "full") -> bool:
        """
        Subscribe to market data for instruments
        
        Args:
            instrument_keys: List of instrument keys (e.g., ["NSE_EQ|INE155A01022"])
            mode: Data mode - "ltpc" (Last Traded Price), "full", or "option_greeks"
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self.upstox_ws or self.upstox_ws.closed:
            success = await self.connect_to_upstox()
            if not success:
                raise Exception("Failed to connect to Upstox WebSocket")
        
        # Generate unique GUID for each subscription
        subscription_guid = str(uuid.uuid4())
        
        subscribe_message = {
            "guid": subscription_guid,
            "method": "sub",
            "data": {
                "mode": mode,
                "instrumentKeys": instrument_keys
            }
        }
        
        try:
            await self.upstox_ws.send(json.dumps(subscribe_message))
            
            # Add to subscribed list (avoid duplicates)
            for key in instrument_keys:
                if key not in self.subscribed_instruments:
                    self.subscribed_instruments.append(key)
            
            logger.info(f"📊 Subscribed to {len(instrument_keys)} instruments with mode '{mode}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Subscription failed: {e}")
            return False
    
    async def unsubscribe_instruments(self, instrument_keys: List[str]) -> bool:
        """Unsubscribe from market data"""
        if not self.upstox_ws or self.upstox_ws.closed:
            logger.warning("Cannot unsubscribe: WebSocket not connected")
            return False
        
        unsubscribe_guid = str(uuid.uuid4())
        
        unsubscribe_message = {
            "guid": unsubscribe_guid,
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        
        try:
            await self.upstox_ws.send(json.dumps(unsubscribe_message))
            
            # Remove from subscribed list
            for key in instrument_keys:
                if key in self.subscribed_instruments:
                    self.subscribed_instruments.remove(key)
            
            logger.info(f"🔕 Unsubscribed from {len(instrument_keys)} instruments")
            return True
            
        except Exception as e:
            logger.error(f"❌ Unsubscribe failed: {e}")
            return False
    
    async def listen_upstox_feed(self) -> None:
        """Listen to Upstox feed and broadcast to clients"""
        async with self._listener_lock:
            if self.is_listening:
                logger.warning("Listener already running")
                return
            
            self.is_listening = True
        
        logger.info("👂 Started listening to Upstox feed...")
        
        while self.is_listening:
            try:
                if not self.upstox_ws or self.upstox_ws.closed:
                    logger.warning("⚠️  WebSocket disconnected. Reconnecting...")
                    
                    if self._reconnect_attempts >= self._max_reconnect_attempts:
                        logger.error("❌ Max reconnection attempts reached. Stopping listener.")
                        self.is_listening = False
                        break
                    
                    await asyncio.sleep(2)
                    success = await self.connect_to_upstox()
                    
                    if success and self.subscribed_instruments:
                        # Re-subscribe to instruments after reconnection
                        await self.subscribe_instruments(self.subscribed_instruments)
                    continue
                
                # Receive message with timeout
                message = await asyncio.wait_for(
                    self.upstox_ws.recv(),
                    timeout=30
                )
                
                # Parse and broadcast message
                if isinstance(message, bytes):
                    # Handle binary protobuf data
                    await self.broadcast({
                        "type": "binary_data",
                        "message": "Binary market data received",
                        "size": len(message),
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    # Handle JSON text message
                    try:
                        data = json.loads(message)
                        await self.broadcast(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON message: {e}")
                
            except asyncio.TimeoutError:
                logger.debug("⏱️  No data received (timeout)")
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("⚠️  Connection closed by Upstox. Reconnecting...")
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Feed listener error: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info("Stopped listening to Upstox feed")


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/market-feed")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time market data WebSocket endpoint
    
    Connect: ws://localhost:8000/api/v1/ws/market-feed
    
    Send JSON to subscribe:
    {
        "action": "subscribe",
        "instruments": ["NSE_EQ|INE155A01022"],
        "mode": "full"
    }
    
    Send JSON to unsubscribe:
    {
        "action": "unsubscribe",
        "instruments": ["NSE_EQ|INE155A01022"]
    }
    
    Send ping:
    {
        "action": "ping"
    }
    """
    await manager.connect(websocket)
    
    # Start listener task if not running (with lock to prevent duplicates)
    if not manager.is_listening:
        asyncio.create_task(manager.listen_upstox_feed())
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            action = message.get("action")
            
            if action == "subscribe":
                instruments = message.get("instruments", [])
                mode = message.get("mode", "full")
                
                if not instruments:
                    await websocket.send_json({
                        "status": "error",
                        "message": "No instruments provided"
                    })
                    continue
                
                success = await manager.subscribe_instruments(instruments, mode)
                
                await websocket.send_json({
                    "status": "success" if success else "error",
                    "action": "subscribed",
                    "instruments": instruments,
                    "mode": mode,
                    "timestamp": datetime.now().isoformat()
                })
            
            elif action == "unsubscribe":
                instruments = message.get("instruments", [])
                
                if not instruments:
                    await websocket.send_json({
                        "status": "error",
                        "message": "No instruments provided"
                    })
                    continue
                
                success = await manager.unsubscribe_instruments(instruments)
                
                await websocket.send_json({
                    "status": "success" if success else "error",
                    "action": "unsubscribed",
                    "instruments": instruments,
                    "timestamp": datetime.now().isoformat()
                })
            
            elif action == "ping":
                await websocket.send_json({
                    "action": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            else:
                await websocket.send_json({
                    "status": "error",
                    "message": f"Unknown action: {action}"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected gracefully")
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    summary="Subscribe to Market Data",
    description="Subscribe to real-time market feed for specified instruments",
    tags=["WebSocket"]
)
async def subscribe_market_data(subscription: WebSocketSubscription):
    """
    Subscribe to instruments via REST (prepares WebSocket subscription)
    
    Example:
    {
        "instrument_keys": ["NSE_EQ|INE155A01022", "NSE_EQ|INE208A01029"],
        "mode": "full"
    }
    
    Modes:
    - "ltpc": Last Traded Price, Change (lightweight)
    - "full": Full market depth with bid/ask
    - "option_greeks": Option Greeks data (for options only)
    
    Returns:
        Subscription confirmation
    """
    try:
        if not manager.upstox_ws or manager.upstox_ws.closed:
            await manager.connect_to_upstox()
        
        if not manager.is_listening:
            asyncio.create_task(manager.listen_upstox_feed())
        
        success = await manager.subscribe_instruments(
            subscription.instrument_keys,
            subscription.mode
        )
        
        if success:
            return SubscriptionResponse(
                status="success",
                message=f"Subscribed to {len(subscription.instrument_keys)} instruments",
                subscribed_instruments=subscription.instrument_keys
            )
        else:
            raise HTTPException(status_code=500, detail="Subscription failed")
    
    except Exception as e:
        logger.error(f"Subscription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/subscriptions",
    summary="Get Active Subscriptions",
    description="Get list of currently subscribed instruments",
    tags=["WebSocket"]
)
async def get_subscriptions():
    """Get list of currently subscribed instruments"""
    return {
        "status": "success",
        "subscribed_instruments": manager.subscribed_instruments,
        "total_subscriptions": len(manager.subscribed_instruments),
        "active_connections": len(manager.active_connections),
        "websocket_status": "connected" if (manager.upstox_ws and not manager.upstox_ws.closed) else "disconnected",
        "timestamp": datetime.now().isoformat()
    }


@router.delete(
    "/subscriptions/{instrument_key}",
    summary="Unsubscribe from Instrument",
    description="Unsubscribe from a specific instrument",
    tags=["WebSocket"]
)
async def unsubscribe_instrument(instrument_key: str):
    """Unsubscribe from a specific instrument"""
    try:
        success = await manager.unsubscribe_instruments([instrument_key])
        
        if success:
            return {
                "status": "success",
                "message": f"Unsubscribed from {instrument_key}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Unsubscribe failed")
            
    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
