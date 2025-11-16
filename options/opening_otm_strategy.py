"""Opening OTM Strategy - Auto-trade based on market opening conditions.

This module implements an automated trading strategy that:
1. Monitors market at 9:15:10 AM
2. Checks if open == high (bearish) or open == low (bullish) at 9:15:50 AM
3. Places orders between 9:15:50 - 9:16:10 AM
4. Selects highest OI OTM strikes
5. Auto-places 10% profit target orders
"""

import asyncio
import logging
from datetime import datetime, time
from decimal import Decimal
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Market opening signal types"""
    BEARISH = "BEARISH"  # open == high
    BULLISH = "BULLISH"  # open == low
    NONE = "NONE"        # no signal


class OpeningOTMStrategy:
    """Opening Range OTM Strategy with highest OI strike selection."""
    
    def __init__(self, upstox_client):
        """Initialize the opening strategy.
        
        Args:
            upstox_client: Upstox API client instance
        """
        self.upstox_client = upstox_client
        self.market_data = {
            "open": None,
            "high": None,
            "low": None,
            "spot": None,
            "timestamp": None
        }
        self.is_monitoring = False
        self.order_placed = False
        
        logger.info("OpeningOTMStrategy initialized")
    
    async def execute_strategy(self, 
                              symbol: str = "NIFTY",
                              quantity_lots: int = 1,
                              otm_range: int = 500,
                              target_profit_percent: float = 10.0,
                              price_tolerance: float = 2.0) -> Dict:
        """Execute the opening OTM strategy.
        
        Args:
            symbol: Trading symbol (NIFTY or BANKNIFTY)
            quantity_lots: Number of lots to trade (e.g., 2 lots = 50 qty for NIFTY)
            otm_range: Search range for OTM strikes (±points from spot)
            target_profit_percent: Profit target percentage (default 10%)
            price_tolerance: Tolerance for open==high/low check (±points)
        
        Returns:
            Strategy execution result with order details
        """
        try:
            logger.info(f"Starting opening OTM strategy for {symbol} with {quantity_lots} lot(s)")
            
            # Step 1: Start monitoring at 9:15:10 AM
            await self._wait_for_monitoring_time()
            
            # Step 2: Collect market data until 9:15:50 AM
            await self._monitor_market_data(symbol)
            
            # Step 3: Make decision at 9:15:50 AM
            signal = self._analyze_opening_signal(price_tolerance)
            
            if signal == SignalType.NONE:
                return {
                    "success": True,
                    "signal": "NONE",
                    "message": "No trading signal generated",
                    "market_data": self.market_data,
                    "action_taken": "NO_ACTION"
                }
            
            # Step 4: Place order between 9:15:50 - 9:16:10 AM
            order_result = await self._place_otm_order(
                symbol=symbol,
                signal=signal,
                quantity_lots=quantity_lots,
                otm_range=otm_range,
                target_profit_percent=target_profit_percent
            )
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error executing opening strategy: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "signal": "ERROR"
            }
    
    async def _wait_for_monitoring_time(self):
        """Wait until 9:15:10 AM to start monitoring."""
        now = datetime.now().time()
        target_time = time(9, 15, 10)
        
        # For testing, allow immediate execution outside market hours
        if now < target_time:
            wait_seconds = (datetime.combine(datetime.today(), target_time) - 
                          datetime.combine(datetime.today(), now)).total_seconds()
            logger.info(f"Waiting {wait_seconds} seconds until 9:15:10 AM")
            await asyncio.sleep(wait_seconds)
        
        logger.info("Monitoring started at 9:15:10 AM")
        self.is_monitoring = True
    
    async def _monitor_market_data(self, symbol: str):
        """Monitor market data from 9:15:10 to 9:15:50 AM."""
        logger.info("Collecting market data...")
        
        # Wait until 9:15:50 AM
        now = datetime.now().time()
        decision_time = time(9, 15, 50)
        
        if now < decision_time:
            wait_seconds = (datetime.combine(datetime.today(), decision_time) - 
                          datetime.combine(datetime.today(), now)).total_seconds()
            await asyncio.sleep(wait_seconds)
        
        # Fetch market data at 9:15:50 AM
        market_data = await self._fetch_market_data(symbol)
        self.market_data = market_data
        
        logger.info(f"Market data at 9:15:50: {market_data}")
    
    async def _fetch_market_data(self, symbol: str) -> Dict:
        """Fetch current market OHLC data."""
        try:
            # Fetch from Upstox API (implement actual API call)
            # This is a placeholder - replace with actual Upstox market data API
            response = await self.upstox_client.get_market_quote(symbol)
            
            return {
                "open": Decimal(str(response.get("ohlc", {}).get("open", 0))),
                "high": Decimal(str(response.get("ohlc", {}).get("high", 0))),
                "low": Decimal(str(response.get("ohlc", {}).get("low", 0))),
                "spot": Decimal(str(response.get("last_price", 0))),
                "timestamp": datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            raise
    
    def _analyze_opening_signal(self, tolerance: float) -> SignalType:
        """Analyze opening conditions to generate signal.
        
        Args:
            tolerance: Price tolerance for equality check
        
        Returns:
            SignalType: BEARISH, BULLISH, or NONE
        """
        open_price = self.market_data["open"]
        high_price = self.market_data["high"]
        low_price = self.market_data["low"]
        
        tolerance_decimal = Decimal(str(tolerance))
        
        # Check bearish signal: open == high (within tolerance)
        if abs(open_price - high_price) <= tolerance_decimal:
            logger.critical(f"BEARISH SIGNAL: Open ({open_price}) equals High ({high_price})")
            return SignalType.BEARISH
        
        # Check bullish signal: open == low (within tolerance)
        if abs(open_price - low_price) <= tolerance_decimal:
            logger.critical(f"BULLISH SIGNAL: Open ({open_price}) equals Low ({low_price})")
            return SignalType.BULLISH
        
        logger.info(f"No signal: Open={open_price}, High={high_price}, Low={low_price}")
        return SignalType.NONE
    
    async def _place_otm_order(self,
                              symbol: str,
                              signal: SignalType,
                              quantity_lots: int,
                              otm_range: int,
                              target_profit_percent: float) -> Dict:
        """Place OTM order with highest OI strike.
        
        Args:
            symbol: Trading symbol
            signal: BEARISH or BULLISH
            quantity_lots: Number of lots to trade
            otm_range: Range to search for OTM strikes
            target_profit_percent: Profit target percentage
        
        Returns:
            Order execution result
        """
        try:
            # Get lot size for the symbol
            lot_size = self._get_lot_size(symbol)
            total_quantity = quantity_lots * lot_size
            
            logger.info(f"Placing {quantity_lots} lot(s) = {total_quantity} quantity")
            
            # Determine option type based on signal
            option_type = "PE" if signal == SignalType.BEARISH else "CE"
            
            # Find highest OI OTM strike
            best_strike = await self._find_highest_oi_otm_strike(
                symbol=symbol,
                option_type=option_type,
                spot_price=float(self.market_data["spot"]),
                otm_range=otm_range
            )
            
            if not best_strike:
                raise ValueError(f"No suitable OTM {option_type} strike found")
            
            # Check if we're within execution window (9:15:50 - 9:16:10)
            now = datetime.now().time()
            execution_start = time(9, 15, 50)
            execution_end = time(9, 16, 10)
            
            in_window = execution_start <= now <= execution_end
            if not in_window:
                logger.warning(f"Outside execution window: {now}")
            
            # Place buy order
            buy_order = await self._place_buy_order(
                symbol=symbol,
                option_type=option_type,
                strike=best_strike["strike"],
                quantity=total_quantity
            )
            
            entry_price = Decimal(str(buy_order["price"]))
            target_price = entry_price * (Decimal("1") + Decimal(str(target_profit_percent)) / Decimal("100"))
            
            # Place target sell order at 10% profit
            target_order = await self._place_target_order(
                symbol=symbol,
                option_type=option_type,
                strike=best_strike["strike"],
                quantity=total_quantity,
                target_price=float(target_price)
            )
            
            logger.critical(f"Orders placed successfully: Buy {total_quantity} @ {entry_price}, Target @ {target_price}")
            
            return {
                "success": True,
                "signal": signal.value,
                "condition_met": "open_equals_high" if signal == SignalType.BEARISH else "open_equals_low",
                "data_snapshot": {
                    "spot_price": float(self.market_data["spot"]),
                    "open": float(self.market_data["open"]),
                    "high": float(self.market_data["high"]),
                    "low": float(self.market_data["low"]),
                    "timestamp": self.market_data["timestamp"].isoformat()
                },
                "action_taken": f"BUY_{option_type}_OTM",
                "strike_selected": best_strike["strike"],
                "option_type": option_type,
                "selection_reason": "Highest OI OTM strike",
                "open_interest": best_strike["oi"],
                "lot_size": lot_size,
                "quantity_lots": quantity_lots,
                "total_quantity": total_quantity,
                "entry_price": float(entry_price),
                "target_price": float(target_price),
                "target_profit_percent": target_profit_percent,
                "orders": {
                    "buy_order_id": buy_order["order_id"],
                    "target_order_id": target_order["order_id"]
                },
                "execution_time": datetime.now().isoformat(),
                "time_in_window": in_window
            }
            
        except Exception as e:
            logger.error(f"Error placing OTM order: {str(e)}")
            raise
    
    def _get_lot_size(self, symbol: str) -> int:
        """Get lot size for the symbol."""
        lot_sizes = {
            "NIFTY": 25,
            "BANKNIFTY": 15,
            "FINNIFTY": 40
        }
        return lot_sizes.get(symbol.upper(), 25)
    
    async def _find_highest_oi_otm_strike(self,
                                         symbol: str,
                                         option_type: str,
                                         spot_price: float,
                                         otm_range: int) -> Optional[Dict]:
        """Find OTM strike with highest open interest.
        
        Args:
            symbol: Trading symbol
            option_type: CE or PE
            spot_price: Current spot price
            otm_range: Range to search (±points)
        
        Returns:
            Dict with strike and OI details
        """
        try:
            # Fetch option chain data
            option_chain = await self._fetch_option_chain(symbol)
            
            # Filter OTM strikes
            if option_type == "PE":
                # For PE, OTM means strike < spot
                otm_strikes = [
                    strike for strike in option_chain
                    if strike["strike_price"] < spot_price and
                    strike["strike_price"] >= (spot_price - otm_range)
                ]
            else:  # CE
                # For CE, OTM means strike > spot
                otm_strikes = [
                    strike for strike in option_chain
                    if strike["strike_price"] > spot_price and
                    strike["strike_price"] <= (spot_price + otm_range)
                ]
            
            if not otm_strikes:
                logger.warning(f"No OTM {option_type} strikes found in range")
                return None
            
            # Find strike with highest OI
            best_strike = max(otm_strikes, key=lambda x: x.get("open_interest", 0))
            
            logger.info(f"Selected {option_type} strike: {best_strike['strike_price']} with OI: {best_strike['open_interest']}")
            
            return {
                "strike": best_strike["strike_price"],
                "oi": best_strike["open_interest"],
                "ltp": best_strike.get("last_price", 0)
            }
            
        except Exception as e:
            logger.error(f"Error finding OTM strike: {str(e)}")
            raise
    
    async def _fetch_option_chain(self, symbol: str) -> List[Dict]:
        """Fetch option chain data from Upstox."""
        # Placeholder - implement actual Upstox option chain API call
        # This should return list of strikes with OI, LTP, etc.
        try:
            response = await self.upstox_client.get_option_chain(symbol)
            return response.get("data", [])
        except Exception as e:
            logger.error(f"Error fetching option chain: {str(e)}")
            raise
    
    async def _place_buy_order(self,
                              symbol: str,
                              option_type: str,
                              strike: float,
                              quantity: int) -> Dict:
        """Place buy order for the option."""
        try:
            order_params = {
                "symbol": symbol,
                "option_type": option_type,
                "strike_price": strike,
                "quantity": quantity,
                "transaction_type": "BUY",
                "order_type": "MARKET",
                "validity": "DAY"
            }
            
            # Place order through service
            from .service import OptionsOrderService
            service = OptionsOrderService(self.upstox_client)
            result = await service.place_order(order_params)
            
            return {
                "order_id": result.get("order_id"),
                "price": result.get("price", 0)
            }
            
        except Exception as e:
            logger.error(f"Error placing buy order: {str(e)}")
            raise
    
    async def _place_target_order(self,
                                 symbol: str,
                                 option_type: str,
                                 strike: float,
                                 quantity: int,
                                 target_price: float) -> Dict:
        """Place target sell order at 10% profit."""
        try:
            order_params = {
                "symbol": symbol,
                "option_type": option_type,
                "strike_price": strike,
                "quantity": quantity,
                "transaction_type": "SELL",
                "order_type": "LIMIT",
                "price": target_price,
                "validity": "DAY"
            }
            
            from .service import OptionsOrderService
            service = OptionsOrderService(self.upstox_client)
            result = await service.place_order(order_params)
            
            return {
                "order_id": result.get("order_id"),
                "price": target_price
            }
            
        except Exception as e:
            logger.error(f"Error placing target order: {str(e)}")
            raise


# Global strategy instance
_strategy_instance: Optional[OpeningOTMStrategy] = None


def get_strategy(upstox_client) -> OpeningOTMStrategy:
    """Get or create strategy instance."""
    global _strategy_instance
    if _strategy_instance is None:
        _strategy_instance = OpeningOTMStrategy(upstox_client)
    return _strategy_instance
