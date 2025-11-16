"""Pydantic models for Options Trading API.

This module defines all request/response models with strict validation.
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, validator, root_validator


class OptionType(str, Enum):
    """Option type enum"""
    CE = "CE"  # Call Option
    PE = "PE"  # Put Option
    BOTH = "BOTH"  # Straddle/Strangle (both CE and PE)


class OrderType(str, Enum):
    """Order type enum"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"  # Stop Loss
    SLM = "SL-M"  # Stop Loss Market


class TransactionType(str, Enum):
    """Transaction type enum"""
    BUY = "BUY"
    SELL = "SELL"


class Validity(str, Enum):
    """Order validity enum"""
    DAY = "DAY"
    IOC = "IOC"  # Immediate or Cancel


class PriceConfig(BaseModel):
    """Price configuration for options orders"""
    order_type: OrderType = Field(
        default=OrderType.MARKET,
        description="Order type (MARKET/LIMIT/SL/SL-M)"
    )
    price: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Limit price (required for LIMIT/SL orders)"
    )
    trigger_price: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Trigger price (required for SL/SL-M orders)"
    )

    @root_validator
    def validate_prices(cls, values):
        """Validate price requirements based on order type"""
        order_type = values.get('order_type')
        price = values.get('price')
        trigger_price = values.get('trigger_price')

        if order_type in [OrderType.LIMIT, OrderType.SL] and not price:
            raise ValueError(f"{order_type} orders require a price")
        
        if order_type in [OrderType.SL, OrderType.SLM] and not trigger_price:
            raise ValueError(f"{order_type} orders require a trigger_price")
        
        return values


class OptionsOrderRequest(BaseModel):
    """Request model for placing options orders"""
    
    # Required fields
    symbol: str = Field(..., description="Underlying symbol (NIFTY/BANKNIFTY/FINNIFTY)", min_length=1)
    strike_price: Decimal = Field(..., gt=0, description="Strike price (required)")
    option_type: OptionType = Field(..., description="Option type: CE, PE, or BOTH (required)")
    expiry_date: date = Field(..., description="Expiry date in YYYY-MM-DD format")
    quantity: int = Field(..., gt=0, description="Number of lots")
    transaction_type: TransactionType = Field(..., description="BUY or SELL")
    validity: Validity = Field(..., description="Order validity: DAY or IOC (required)")
    
    # Price configurations
    ce_price_config: Optional[PriceConfig] = Field(default_factory=lambda: PriceConfig(), description="CE option price config (defaults to MARKET)")
    pe_price_config: Optional[PriceConfig] = Field(default_factory=lambda: PriceConfig(), description="PE option price config (defaults to MARKET)")
    
    # Optional fields
    disclosed_quantity: Optional[int] = Field(None, ge=0, description="Disclosed quantity for iceberg orders")
    is_amo: bool = Field(False, description="After Market Order flag")
    strategy_id: Optional[str] = Field(None, description="Strategy ID for multi-leg orders")
    target_profit_percent: Optional[Decimal] = Field(None, gt=0, le=1000, description="Target profit percentage")
    stop_loss_percent: Optional[Decimal] = Field(None, gt=0, le=100, description="Stop loss percentage")
    trailing_sl: bool = Field(False, description="Enable trailing stop loss")

    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate and uppercase symbol"""
        return v.upper().strip()

    @root_validator
    def validate_option_configs(cls, values):
        """Validate price configs based on option type"""
        option_type = values.get('option_type')
        ce_config = values.get('ce_price_config')
        pe_config = values.get('pe_price_config')

        if option_type == OptionType.CE:
            if not ce_config:
                values['ce_price_config'] = PriceConfig()
        elif option_type == OptionType.PE:
            if not pe_config:
                values['pe_price_config'] = PriceConfig()
        elif option_type == OptionType.BOTH:
            if not ce_config:
                values['ce_price_config'] = PriceConfig()
            if not pe_config:
                values['pe_price_config'] = PriceConfig()

        return values


class OrderLeg(BaseModel):
    """Individual order leg details"""
    option_type: OptionType
    strike_price: Decimal
    order_id: str
    status: str
    price: Optional[Decimal] = None
    quantity: int


class OptionsOrderResponse(BaseModel):
    """Response model for options orders"""
    success: bool
    message: str
    strategy_id: Optional[str] = None
    orders: List[OrderLeg] = []
    total_premium: Optional[Decimal] = None
    breakeven_price: Optional[Decimal] = None
    max_profit: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.now)
