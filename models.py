from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
import re


class OrderRequest(BaseModel):
    """Model for placing an order request"""
    symbol: str = Field(
        ...,
        example="NSE_EQ|INE155A01022",
        description="Instrument key in format: EXCHANGE_SEGMENT|ISIN"
    )
    quantity: int = Field(..., gt=0, example=1, description="Order quantity (must be positive)")
    order_type: str = Field(..., example="MARKET", description="MARKET or LIMIT")
    side: str = Field(..., example="BUY", description="BUY or SELL")
    product: str = Field("D", example="D", description="D=Delivery, I=Intraday")
    validity: str = Field("DAY", example="DAY", description="DAY or IOC")
    price: Optional[float] = Field(None, ge=0, example=100.50, description="Price for LIMIT orders")
    trigger_price: Optional[float] = Field(None, ge=0, example=0, description="Trigger price for SL orders")
    disclosed_quantity: Optional[int] = Field(0, ge=0, example=0, description="Disclosed quantity")
    
    @validator('symbol')
    def validate_symbol_format(cls, v):
        """Validate symbol format: EXCHANGE_SEGMENT|ISIN"""
        if not re.match(r'^[A-Z_]+\|[A-Z0-9]+$', v):
            raise ValueError('Symbol must be in format: EXCHANGE_SEGMENT|ISIN (e.g., NSE_EQ|INE155A01022)')
        return v
    
    @validator('order_type')
    def validate_order_type(cls, v):
        """Validate order type"""
        if v not in ['MARKET', 'LIMIT', 'SL', 'SL-M']:
            raise ValueError('order_type must be MARKET, LIMIT, SL, or SL-M')
        return v
    
    @validator('side')
    def validate_side(cls, v):
        """Validate side"""
        if v not in ['BUY', 'SELL']:
            raise ValueError('side must be BUY or SELL')
        return v
    
    @validator('price')
    def validate_price(cls, v, values):
        """Validate price is required for LIMIT orders"""
        order_type = values.get('order_type')
        if order_type == 'LIMIT' and (v is None or v <= 0):
            raise ValueError('price must be greater than 0 for LIMIT orders')
        return v
    
    @validator('product')
    def validate_product(cls, v):
        """Validate product type"""
        if v not in ['D', 'I', 'CO', 'OCO']:
            raise ValueError('product must be D (Delivery), I (Intraday), CO (Cover Order), or OCO (One Cancels Other)')
        return v
    
    @validator('validity')
    def validate_validity(cls, v):
        """Validate validity"""
        if v not in ['DAY', 'IOC']:
            raise ValueError('validity must be DAY or IOC')
        return v


class OrderResponse(BaseModel):
    """Response model for order operations"""
    status: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class AccountInfo(BaseModel):
    """Model for account information"""
    status: str
    data: Dict[str, Any]


class MarketFeedResponse(BaseModel):
    """Response model for market feed data"""
    status: str
    data: Dict[str, Any]


class WebhookPayload(BaseModel):
    """Generic webhook payload model"""
    event: str = Field(..., example="order.placed", description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: Optional[str] = Field(None, description="Event timestamp")


class WebSocketSubscription(BaseModel):
    """Model for WebSocket subscription request"""
    instrument_keys: List[str] = Field(
        ...,
        example=["NSE_EQ|INE155A01022"],
        min_items=1,
        max_items=100,
        description="List of instrument keys to subscribe (max 100)"
    )
    mode: str = Field(
        "full",
        example="full",
        description="Data mode: ltpc, full, or option_greeks"
    )
    
    @validator('mode')
    def validate_mode(cls, v):
        """Validate subscription mode"""
        if v not in ['ltpc', 'full', 'option_greeks']:
            raise ValueError('mode must be ltpc, full, or option_greeks')
        return v


class SubscriptionResponse(BaseModel):
    """Response model for subscription operations"""
    status: str = Field(..., example="success")
    message: str = Field(..., example="Subscribed to 2 instruments")
    subscribed_instruments: List[str] = Field(..., example=["NSE_EQ|INE155A01022"])
