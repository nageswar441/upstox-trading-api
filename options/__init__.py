"""Options Trading Package for Upstox Trading API.

This package provides comprehensive options trading functionality including:
- Strike price and option type (CE/PE/BOTH) validation
- Price configuration for market, limit, and stop loss orders
- Multi-leg strategy support (straddles, strangles)
- Automatic lot size detection
- Trading hours validation
- Margin calculation
"""

from .routes import router as options_router
from .models import (
    OptionType,
    OrderType,
    TransactionType,
    Validity,
    PriceConfig,
    OptionsOrderRequest,
    OptionsOrderResponse
)
from .position_monitor import PositionMonitor, MonitorStatus, get_monitor

__version__ = "1.0.0"

__all__ = [
    "options_router",
    "OptionType",
    "OrderType",
    "TransactionType",
    "Validity",
    "PriceConfig",
    "OptionsOrderRequest",
    "OptionsOrderResponse",
    "PositionMonitor",
    "MonitorStatus",
    "get_monitor"
]
