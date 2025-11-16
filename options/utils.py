"""Utility functions for Options Trading.

This module provides helper functions for lot sizes, trading hours validation,
margin calculations, and option Greeks estimation.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Dict, Tuple


# Lot sizes for different underlying symbols
LOT_SIZES: Dict[str, int] = {
    "NIFTY": 50,
    "BANKNIFTY": 25,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 75,
    "SENSEX": 10,
    "BANKEX": 15
}

# Trading hours (IST)
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def get_lot_size(symbol: str) -> int:
    """Get lot size for the given symbol.
    
    Args:
        symbol: Underlying symbol (e.g., NIFTY, BANKNIFTY)
    
    Returns:
        Lot size for the symbol
    
    Raises:
        ValueError: If symbol not found
    """
    symbol = symbol.upper().strip()
    if symbol not in LOT_SIZES:
        raise ValueError(f"Unknown symbol: {symbol}. Supported: {list(LOT_SIZES.keys())}")
    return LOT_SIZES[symbol]


def is_trading_hours(check_time: datetime = None) -> bool:
    """Check if given time is within trading hours.
    
    Args:
        check_time: Time to check (defaults to current time)
    
    Returns:
        True if within trading hours, False otherwise
    """
    if check_time is None:
        check_time = datetime.now()
    
    current_time = check_time.time()
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if check_time.weekday() >= 5:  # Saturday or Sunday
        return False
    
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def calculate_total_quantity(lots: int, symbol: str) -> int:
    """Calculate total quantity from lots.
    
    Args:
        lots: Number of lots
        symbol: Underlying symbol
    
    Returns:
        Total quantity (lots * lot_size)
    """
    lot_size = get_lot_size(symbol)
    return lots * lot_size


def calculate_premium(price: Decimal, quantity: int) -> Decimal:
    """Calculate total premium.
    
    Args:
        price: Option price per unit
        quantity: Total quantity
    
    Returns:
        Total premium
    """
    return price * Decimal(quantity)


def calculate_margin_required(price: Decimal, quantity: int, is_sell: bool = True) -> Decimal:
    """Estimate margin required for options trade.
    
    Args:
        price: Option price
        quantity: Total quantity
        is_sell: True for SELL orders (requires margin), False for BUY
    
    Returns:
        Estimated margin required
    """
    if not is_sell:
        # For BUY orders, only premium is required
        return calculate_premium(price, quantity)
    
    # For SELL orders, approximate margin (simplified calculation)
    # Actual margin depends on SPAN + Exposure margin
    premium = calculate_premium(price, quantity)
    
    # Rough estimate: 20% of notional value + premium received
    # This is a simplified calculation
    estimated_margin = premium * Decimal("3.5")  # Approximate multiplier
    
    return estimated_margin


def calculate_breakeven_straddle(strike: Decimal, ce_premium: Decimal, pe_premium: Decimal) -> Tuple[Decimal, Decimal]:
    """Calculate breakeven points for a straddle.
    
    Args:
        strike: Strike price
        ce_premium: CE premium paid
        pe_premium: PE premium paid
    
    Returns:
        Tuple of (upper_breakeven, lower_breakeven)
    """
    total_premium = ce_premium + pe_premium
    upper_breakeven = strike + total_premium
    lower_breakeven = strike - total_premium
    return (upper_breakeven, lower_breakeven)


def calculate_max_profit_loss(option_type: str, strike: Decimal, premium: Decimal, 
                              transaction_type: str, quantity: int) -> Tuple[Decimal, Decimal]:
    """Calculate maximum profit and loss for an option.
    
    Args:
        option_type: "CE" or "PE"
        strike: Strike price
        premium: Option premium
        transaction_type: "BUY" or "SELL"
        quantity: Total quantity
    
    Returns:
        Tuple of (max_profit, max_loss)
    """
    total_premium = premium * Decimal(quantity)
    
    if transaction_type == "BUY":
        # Buying options: Limited loss (premium), unlimited profit
        max_loss = total_premium
        max_profit = None  # Unlimited for buyers
    else:  # SELL
        # Selling options: Limited profit (premium), unlimited loss
        max_profit = total_premium
        max_loss = None  # Unlimited for sellers
    
    return (max_profit, max_loss)


def estimate_option_greek_delta(option_type: str, spot_price: Decimal, strike: Decimal) -> float:
    """Estimate delta (very simplified).
    
    Args:
        option_type: "CE" or "PE"
        spot_price: Current spot price
        strike: Strike price
    
    Returns:
        Estimated delta value
    """
    # Simplified delta estimation
    # In reality, delta depends on many factors (volatility, time to expiry, etc.)
    
    moneyness = float(spot_price / strike)
    
    if option_type == "CE":
        if moneyness > 1.02:  # ITM
            return 0.7
        elif moneyness > 0.98:  # ATM
            return 0.5
        else:  # OTM
            return 0.3
    else:  # PE
        if moneyness < 0.98:  # ITM
            return -0.7
        elif moneyness < 1.02:  # ATM
            return -0.5
        else:  # OTM
            return -0.3


def validate_strike_price(strike: Decimal, symbol: str) -> bool:
    """Validate strike price for given symbol.
    
    Args:
        strike: Strike price
        symbol: Underlying symbol
    
    Returns:
        True if valid, False otherwise
    """
    symbol = symbol.upper()
    
    # Strike price should be positive
    if strike <= 0:
        return False
    
    # Check if strike is in proper increments
    if symbol == "NIFTY":
        # NIFTY strikes are in multiples of 50
        return strike % 50 == 0
    elif symbol == "BANKNIFTY":
        # BANKNIFTY strikes are in multiples of 100
        return strike % 100 == 0
    elif symbol == "FINNIFTY":
        # FINNIFTY strikes are in multiples of 50
        return strike % 50 == 0
    
    # For other symbols, accept any positive value
    return True


def generate_strategy_id() -> str:
    """Generate unique strategy ID.
    
    Returns:
        Unique strategy ID string
    """
    from datetime import datetime
    import random
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = random.randint(1000, 9999)
    return f"STR_{timestamp}_{random_suffix}"
