from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class OrderRequest(BaseModel):
    symbol: str = Field(..., example="NSE_EQ|INE155A01022", description="Instrument key")
    quantity: int = Field(..., example=1, description="Order quantity")
    order_type: str = Field(..., example="MARKET", description="MARKET or LIMIT")
    side: str = Field(..., example="BUY", description="BUY or SELL")
    product: str = Field("D", example="D", description="D=Delivery, I=Intraday")
    validity: str = Field("DAY", example="DAY", description="DAY or IOC")
    price: Optional[float] = Field(0, example=0)
    trigger_price: Optional[float] = Field(0, example=0)
    disclosed_quantity: Optional[int] = Field(0, example=0)
    transaction_type: str = Field(..., example="BUY")

class OrderResponse(BaseModel):
    status: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class AccountInfo(BaseModel):
    status: str
    data: Dict[str, Any]

class MarketFeedResponse(BaseModel):
    status: str
    data: Dict[str, Any]

class WebhookPayload(BaseModel):
    event: str = Field(..., example="order.placed")
    data: Dict[str, Any]
    timestamp: Optional[str] = None

class WebSocketSubscription(BaseModel):
    instrument_keys: List[str] = Field(..., example=["NSE_EQ|INE155A01022"])
    mode: str = Field("full", example="full")
