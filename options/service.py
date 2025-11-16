"""Business logic for Options Trading API.

This module handles order placement logic, validations, and interactions with Upstox API.
"""

from decimal import Decimal
from typing import List, Optional
from datetime import datetime
import logging

from .models import (
    OptionsOrderRequest,
    OptionsOrderResponse,
    OrderLeg,
    OptionType,
    TransactionType
)
from .utils import (
    generate_strategy_id,
    calculate_total_quantity,
    is_trading_hours,
    validate_strike_price,
    calculate_breakeven_straddle,
    calculate_max_profit_loss
)

logger = logging.getLogger(__name__)


class OptionsOrderService:
    """Service class for handling options order operations."""
    
    def __init__(self, upstox_client=None):
        """Initialize service with Upstox client.
        
        Args:
            upstox_client: Upstox API client instance
        """
        self.upstox_client = upstox_client
    
    async def place_order(self, request: OptionsOrderRequest) -> OptionsOrderResponse:
        """Place options order(s) based on request.
        
        Args:
            request: OptionsOrderRequest with order details
        
        Returns:
            OptionsOrderResponse with order results
        """
        try:
            # Validate request
            self._validate_order_request(request)
            
            # Generate strategy ID for multi-leg orders
            strategy_id = request.strategy_id or generate_strategy_id()
            
            # Place order(s) based on option type
            orders = []
            
            if request.option_type == OptionType.CE:
                # Place CE order
                ce_order = await self._place_single_order(
                    request, OptionType.CE, request.ce_price_config
                )
                orders.append(ce_order)
            
            elif request.option_type == OptionType.PE:
                # Place PE order
                pe_order = await self._place_single_order(
                    request, OptionType.PE, request.pe_price_config
                )
                orders.append(pe_order)
            
            elif request.option_type == OptionType.BOTH:
                # Place both CE and PE orders (straddle/strangle)
                ce_order = await self._place_single_order(
                    request, OptionType.CE, request.ce_price_config
                )
                pe_order = await self._place_single_order(
                    request, OptionType.PE, request.pe_price_config
                )
                orders.extend([ce_order, pe_order])
            
            # Calculate totals
            total_premium = self._calculate_total_premium(orders)
            breakeven = self._calculate_breakeven(request, orders)
            max_profit, max_loss = self._calculate_risk_metrics(request, orders)
            
            return OptionsOrderResponse(
                success=True,
                message="Order(s) placed successfully",
                strategy_id=strategy_id,
                orders=orders,
                total_premium=total_premium,
                breakeven_price=breakeven,
                max_profit=max_profit,
                max_loss=max_loss
            )
        
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return OptionsOrderResponse(
                success=False,
                message=f"Failed to place order: {str(e)}",
                orders=[]
            )
    
    def _validate_order_request(self, request: OptionsOrderRequest) -> None:
        """Validate order request.
        
        Args:
            request: Order request to validate
        
        Raises:
            ValueError: If validation fails
        """
        # Check trading hours unless AMO
        if not request.is_amo and not is_trading_hours():
            raise ValueError("Orders can only be placed during market hours (9:15 AM - 3:30 PM) unless marked as AMO")
        
        # Validate strike price
        if not validate_strike_price(request.strike_price, request.symbol):
            raise ValueError(f"Invalid strike price {request.strike_price} for {request.symbol}")
        
        # Validate expiry date
        if request.expiry_date < datetime.now().date():
            raise ValueError("Expiry date cannot be in the past")
    
    async def _place_single_order(self, request: OptionsOrderRequest, 
                                  option_type: OptionType, price_config) -> OrderLeg:
        """Place a single option order leg.
        
        Args:
            request: Original order request
            option_type: CE or PE
            price_config: Price configuration for this leg
        
        Returns:
            OrderLeg with order details
        """
        # Calculate total quantity
        total_qty = calculate_total_quantity(request.quantity, request.symbol)
        
        # Simulate order placement (replace with actual Upstox API call)
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{option_type.value}"
        
        # Mock price for simulation
        mock_price = Decimal("150.50") if option_type == OptionType.CE else Decimal("145.25")
        
        return OrderLeg(
            option_type=option_type,
            strike_price=request.strike_price,
            order_id=order_id,
            status="COMPLETE",
            price=mock_price if price_config.order_type.value == "MARKET" else price_config.price,
            quantity=total_qty
        )
    
    def _calculate_total_premium(self, orders: List[OrderLeg]) -> Optional[Decimal]:
        """Calculate total premium for all orders.
        
        Args:
            orders: List of order legs
        
        Returns:
            Total premium or None
        """
        if not orders or not all(o.price for o in orders):
            return None
        
        return sum(o.price * Decimal(o.quantity) for o in orders)
    
    def _calculate_breakeven(self, request: OptionsOrderRequest, 
                            orders: List[OrderLeg]) -> Optional[Decimal]:
        """Calculate breakeven price.
        
        Args:
            request: Original order request
            orders: List of order legs
        
        Returns:
            Breakeven price or None
        """
        if request.option_type == OptionType.BOTH and len(orders) == 2:
            ce_price = next((o.price for o in orders if o.option_type == OptionType.CE), Decimal(0))
            pe_price = next((o.price for o in orders if o.option_type == OptionType.PE), Decimal(0))
            upper_be, lower_be = calculate_breakeven_straddle(
                request.strike_price, ce_price, pe_price
            )
            return upper_be  # Return upper breakeven for simplicity
        
        return None
    
    def _calculate_risk_metrics(self, request: OptionsOrderRequest, 
                                orders: List[OrderLeg]) -> tuple:
        """Calculate maximum profit and loss.
        
        Args:
            request: Original order request
            orders: List of order legs
        
        Returns:
            Tuple of (max_profit, max_loss)
        """
        if not orders or not orders[0].price:
            return (None, None)
        
        # Simplified calculation for first leg
        max_profit, max_loss = calculate_max_profit_loss(
            orders[0].option_type.value,
            request.strike_price,
            orders[0].price,
            request.transaction_type.value,
            orders[0].quantity
        )
        
        return (max_profit, max_loss)
