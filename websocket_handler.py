from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import websockets
import json
import logging
import asyncio
from typing import List, Dict
from config import UPSTOX_API_TOKEN, UPSTOX_WEBSOCKET_URL
from models import WebSocketSubscription, SubscriptionResponse

router = APIRouter()
logging.basicConfig(level=logging.INFO)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.upstox_ws = None
        self.subscribed_instruments: List[str] = []
        self.is_listening = False

    async def connect(self, websocket: WebSocket):
        """Accept and store client WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"✅ Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove client WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logging.info(f"❌ Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast market data to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.error(f"Error broadcasting: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def connect_to_upstox(self):
        """Connect to Upstox WebSocket feed"""
        headers = {
            "Authorization": f"Bearer {UPSTOX_API_TOKEN}",
            "Accept": "application/json"
        }
        try:
            self.upstox_ws = await websockets.connect(
                UPSTOX_WEBSOCKET_URL,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            logging.info("🔗 Connected to Upstox WebSocket")
            return True
        except Exception as e:
            logging.error(f"❌ Upstox WebSocket connection failed: {e}")
            return False

    async def subscribe_instruments(self, instrument_keys: List[str], mode: str = "full"):
        """
        Subscribe to market data for instruments
        
        Args:
            instrument_keys: List of instrument keys (e.g., ["NSE_EQ|INE155A01022"])
            mode: Data mode - "ltpc" (Last Traded Price), "full", or "option_greeks"
        """
        if not self.upstox_ws:
            success = await self.connect_to_upstox()
            if not success:
                raise Exception("Failed to connect to Upstox WebSocket")
        
        subscribe_message = {
            "guid": "someguid",
            "method": "sub",
            "data": {
                "mode": mode,
                "instrumentKeys": instrument_keys
            }
        }
        
        try:
            await self.upstox_ws.send(json.dumps(subscribe_message))
            self.subscribed_instruments.extend(instrument_keys)
            logging.info(f"📊 Subscribed to: {instrument_keys}")
            return True
        except Exception as e:
            logging.error(f"❌ Subscription failed: {e}")
            return False

    async def unsubscribe_instruments(self, instrument_keys: List[str]):
        """Unsubscribe from market data"""
        if not self.upstox_ws:
            return False
        
        unsubscribe_message = {
            "guid": "someguid",
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        
        try:
            await self.upstox_ws.send(json.dumps(unsubscribe_message))
            for key in instrument_keys:
                if key in self.subscribed_instruments:
                    self.subscribed_instruments.remove(key)
            logging.info(f"🔕 Unsubscribed from: {instrument_keys}")
            return True
        except Exception as e:
            logging.error(f"❌ Unsubscribe failed: {e}")
            return False

    async def listen_upstox_feed(self):
        """Listen to Upstox feed and broadcast to clients"""
        if self.is_listening:
            return
        
        self.is_listening = True
        logging.info("👂 Started listening to Upstox feed...")
        
        while self.is_listening:
            try:
                if self.upstox_ws and not self.upstox_ws.closed:
                    message = await asyncio.wait_for(
                        self.upstox_ws.recv(), 
                        timeout=30
                    )
                    
                    # Parse binary or text message
                    if isinstance(message, bytes):
                        # Handle binary protobuf data if needed
                        # You may need to decode protobuf here
                        await self.broadcast({
                            "type": "binary_data",
                            "message": "Binary market data received",
                            "size": len(message)
                        })
                    else:
                        data = json.loads(message)
                        await self.broadcast(data)
                else:
                    logging.warning("⚠️ WebSocket disconnected. Reconnecting...")
                    await self.connect_to_upstox()
                    if self.subscribed_instruments:
                        await self.subscribe_instruments(self.subscribed_instruments)
                    
            except asyncio.TimeoutError:
                logging.debug("⏱️ No data received (timeout)")
            except websockets.exceptions.ConnectionClosed:
                logging.warning("⚠️ Connection closed. Reconnecting...")
                await asyncio.sleep(2)
                await self.connect_to_upstox()
            except Exception as e:
                logging.error(f"❌ Feed listener error: {e}")
                await asyncio.sleep(1)

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
    """
    await manager.connect(websocket)
    
    # Start listener task if not running
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
                
                success = await manager.subscribe_instruments(instruments, mode)
                
                await websocket.send_json({
                    "status": "success" if success else "error",
                    "action": "subscribed",
                    "instruments": instruments
                })
                
            elif action == "unsubscribe":
                instruments = message.get("instruments", [])
                success = await manager.unsubscribe_instruments(instruments)
                
                await websocket.send_json({
                    "status": "success" if success else "error",
                    "action": "unsubscribed",
                    "instruments": instruments
                })
            
            elif action == "ping":
                await websocket.send_json({"action": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logging.info("Client disconnected gracefully")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
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
    - "ltpc": Last Traded Price, Change
    - "full": Full market depth
    - "option_greeks": Option Greeks data
    """
    try:
        if not manager.upstox_ws:
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
        logging.error(f"Subscription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/subscriptions",
    summary="Get Active Subscriptions",
    tags=["WebSocket"]
)
async def get_subscriptions():
    """Get list of currently subscribed instruments"""
    return {
        "status": "success",
        "subscribed_instruments": manager.subscribed_instruments,
        "total": len(manager.subscribed_instruments),
        "active_connections": len(manager.active_connections)
    }


@router.delete(
    "/subscriptions/{instrument_key}",
    summary="Unsubscribe from Instrument",
    tags=["WebSocket"]
)
async def unsubscribe_instrument(instrument_key: str):
    """Unsubscribe from a specific instrument"""
    try:
        success = await manager.unsubscribe_instruments([instrument_key])
        if success:
            return {
                "status": "success",
                "message": f"Unsubscribed from {instrument_key}"
            }
        else:
            raise HTTPException(status_code=500, detail="Unsubscribe failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
