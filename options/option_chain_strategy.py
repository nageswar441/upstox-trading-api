"""Option Chain Pattern-Based Trading Strategy.

This module implements a sophisticated pattern detection strategy that monitors
option chain data and executes trades based on specific open/high/low patterns.
"""

import asyncio
import logging
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Pattern types for option chain analysis."""
    CE_BULLISH = "ce_open_equals_low"  # Priority 1: Buy 4th OTM CE
    PE_BULLISH = "pe_open_equals_low"  # Priority 2: Buy 4th OTM PE
    CE_BEARISH_BUY_PE = "ce_open_equals_high_buy_pe"  # Priority 3: Buy PE at 4th CE strike
    PE_BEARISH_BUY_CE = "pe_open_equals_high_buy_ce"  # Priority 4: Buy CE at 4th PE strike
    NONE = "no_pattern"


class OptionChainStrategy:
    """Option chain pattern detection and execution strategy.
    
    Monitors option chain from 9:15:00 to 9:16:00 AM, analyzes patterns,
    and executes single trade based on priority between 9:16:10-9:16:20 AM.
    """
    
    # Timing constants
    MONITOR_START_TIME = time(9, 15, 0)
    MONITOR_END_TIME = time(9, 16, 0)
    EXECUTION_START_TIME = time(9, 16, 10)
    EXECUTION_END_TIME = time(9, 16, 20)
    
    # Lot sizes
    LOT_SIZES = {
        "NIFTY": 25,
        "BANKNIFTY": 15,
        "FINNIFTY": 40
    }
    
    def __init__(self, upstox_client):
        self.upstox_client = upstox_client
        self.market_data: Dict[str, Dict] = {}
        self.spot_price: Optional[Decimal] = None
        
    async def execute_strategy(
        self,
        symbol: str = "NIFTY",
        quantity_lots: int = 1,
        target_profit_percent: float = 5.0,
        price_tolerance: float = 0.5
    ) -> Dict:
        """Execute option chain pattern strategy.
        
        Args:
            symbol: Trading symbol (NIFTY, BANKNIFTY, FINNIFTY)
            quantity_lots: Number of lots to execute
            target_profit_percent: Profit target percentage (default 5%)
            price_tolerance: Tolerance for price equality checks (default 0.5)
            
        Returns:
            Dict with execution results
        """
        try:
            logger.info(f"Starting option chain strategy for {symbol}")
            
            # Wait until monitoring start time
            await self._wait_for_monitoring_time()
            
            # Collect market data for 60 seconds
            await self._monitor_market_data(symbol)
            
            # Analyze patterns and determine trade
            pattern_result = self._analyze_patterns(symbol, price_tolerance)
            
            if pattern_result["pattern"] == PatternType.NONE:
                logger.info("No valid pattern detected")
                return {
                    "success": False,
                    "message": "No pattern matched",
                    "pattern": None
                }
            
            # Wait for execution window
            await self._wait_for_execution_time()
            
            # Execute the trade
            order_result = await self._place_order(
                symbol=symbol,
                pattern_result=pattern_result,
                quantity_lots=quantity_lots,
                target_profit_percent=target_profit_percent
            )
            
            return order_result
            
        except Exception as e:
            logger.error(f"Strategy execution failed: {str(e)}")
            raise
    
    async def _wait_for_monitoring_time(self):
        """Wait until 9:15:00 AM to start monitoring."""
        while True:
            now = datetime.now().time()
            if now >= self.MONITOR_START_TIME:
                logger.info("Monitoring time reached - starting data collection")
                break
            await asyncio.sleep(1)
    
    async def _monitor_market_data(self, symbol: str):
        """Monitor market data from 9:15:00 to 9:16:00."""
        logger.info(f"Monitoring market data for {symbol} until 9:16:00 AM")
        
        end_time = datetime.now().replace(
            hour=9, minute=16, second=0, microsecond=0
        )
        
        while datetime.now() < end_time:
            try:
                # Fetch spot price
                # TODO: Replace with actual Upstox API call
                # self.spot_price = await self._fetch_spot_price(symbol)
                
                # Fetch option chain data
                # TODO: Replace with actual Upstox API call
                # chain_data = await self._fetch_option_chain(symbol)
                # self._update_market_data(chain_data)
                
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Error monitoring market: {str(e)}")
                await asyncio.sleep(1)
        
        logger.info("Market monitoring completed")
    
    def _analyze_patterns(
        self,
        symbol: str,
        price_tolerance: float
    ) -> Dict:
        """Analyze patterns in priority order.
        
        Returns:
            Dict with pattern type, strike, and option type
        """
        logger.info("Analyzing option chain patterns")
        
        tolerance = Decimal(str(price_tolerance))
        
        # Priority 1: CE Bullish Pattern (open == low for 4 OTM CEs)
        ce_pattern = self._check_ce_bullish_pattern(tolerance)
        if ce_pattern:
            logger.critical("PRIORITY 1: CE Bullish pattern detected")
            return ce_pattern
        
        # Priority 2: PE Bullish Pattern (open == low for 4 OTM PEs)
        pe_pattern = self._check_pe_bullish_pattern(tolerance)
        if pe_pattern:
            logger.critical("PRIORITY 2: PE Bullish pattern detected")
            return pe_pattern
        
        # Priority 3: CE Bearish Pattern (open == high for 4 CEs, buy opposite PE)
        ce_bearish = self._check_ce_bearish_pattern(tolerance)
        if ce_bearish:
            logger.critical("PRIORITY 3: CE Bearish pattern detected")
            return ce_bearish
        
        # Priority 4: PE Bearish Pattern (open == high for 4 PEs, buy opposite CE)
        pe_bearish = self._check_pe_bearish_pattern(tolerance)
        if pe_bearish:
            logger.critical("PRIORITY 4: PE Bearish pattern detected")
            return pe_bearish
        
        return {"pattern": PatternType.NONE}
    
    def _check_ce_bullish_pattern(self, tolerance: Decimal) -> Optional[Dict]:
        """Check for CE bullish pattern: 4 OTM CEs with open == low.
        
        Returns dict if pattern found, None otherwise.
        """
        if not self.spot_price:
            return None
        
        # Get 4 OTM CE strikes (above spot)
        otm_ces = self._get_otm_strikes("CE", count=4)
        
        if len(otm_ces) < 4:
            return None
        
        # Check if all 4 have open == low
        pattern_matches = []
        for strike in otm_ces:
            strike_data = self.market_data.get(f"{strike}_CE")
            if not strike_data:
                return None
            
            open_price = Decimal(str(strike_data.get("open", 0)))
            low_price = Decimal(str(strike_data.get("low", 0)))
            
            if abs(open_price - low_price) <= tolerance:
                pattern_matches.append(strike)
        
        if len(pattern_matches) >= 4:
            fourth_strike = pattern_matches[3]
            logger.info(f"CE Bullish: Buy 4th OTM CE at strike {fourth_strike}")
            return {
                "pattern": PatternType.CE_BULLISH,
                "strike": fourth_strike,
                "option_type": "CE",
                "action": "BUY"
            }
        
        return None
    
    def _check_pe_bullish_pattern(self, tolerance: Decimal) -> Optional[Dict]:
        """Check for PE bullish pattern: 4 OTM PEs with open == low."""
        if not self.spot_price:
            return None
        
        # Get 4 OTM PE strikes (below spot)
        otm_pes = self._get_otm_strikes("PE", count=4)
        
        if len(otm_pes) < 4:
            return None
        
        # Check if all 4 have open == low
        pattern_matches = []
        for strike in otm_pes:
            strike_data = self.market_data.get(f"{strike}_PE")
            if not strike_data:
                return None
            
            open_price = Decimal(str(strike_data.get("open", 0)))
            low_price = Decimal(str(strike_data.get("low", 0)))
            
            if abs(open_price - low_price) <= tolerance:
                pattern_matches.append(strike)
        
        if len(pattern_matches) >= 4:
            fourth_strike = pattern_matches[3]
            logger.info(f"PE Bullish: Buy 4th OTM PE at strike {fourth_strike}")
            return {
                "pattern": PatternType.PE_BULLISH,
                "strike": fourth_strike,
                "option_type": "PE",
                "action": "BUY"
            }
        
        return None
    
    def _check_ce_bearish_pattern(self, tolerance: Decimal) -> Optional[Dict]:
        """Check for CE bearish pattern: 4 nearest CEs with open == high.
        
        Buy opposite PE at the 4th CE's strike.
        """
        if not self.spot_price:
            return None
        
        # Get 4 nearest CE strikes from ATM
        nearest_ces = self._get_nearest_strikes("CE", count=4)
        
        if len(nearest_ces) < 4:
            return None
        
        # Check if all 4 have open == high
        pattern_matches = []
        for strike in nearest_ces:
            strike_data = self.market_data.get(f"{strike}_CE")
            if not strike_data:
                return None
            
            open_price = Decimal(str(strike_data.get("open", 0)))
            high_price = Decimal(str(strike_data.get("high", 0)))
            
            if abs(open_price - high_price) <= tolerance:
                pattern_matches.append(strike)
        
        if len(pattern_matches) >= 4:
            fourth_strike = pattern_matches[3]
            logger.info(f"CE Bearish: Buy PE at strike {fourth_strike}")
            return {
                "pattern": PatternType.CE_BEARISH_BUY_PE,
                "strike": fourth_strike,
                "option_type": "PE",  # Buy opposite
                "action": "BUY"
            }
        
        return None
    
    def _check_pe_bearish_pattern(self, tolerance: Decimal) -> Optional[Dict]:
        """Check for PE bearish pattern: 4 nearest PEs with open == high.
        
        Buy opposite CE at the 4th PE's strike.
        """
        if not self.spot_price:
            return None
        
        # Get 4 nearest PE strikes from ATM
        nearest_pes = self._get_nearest_strikes("PE", count=4)
        
        if len(nearest_pes) < 4:
            return None
        
        # Check if all 4 have open == high
        pattern_matches = []
        for strike in nearest_pes:
            strike_data = self.market_data.get(f"{strike}_PE")
            if not strike_data:
                return None
            
            open_price = Decimal(str(strike_data.get("open", 0)))
            high_price = Decimal(str(strike_data.get("high", 0)))
            
            if abs(open_price - high_price) <= tolerance:
                pattern_matches.append(strike)
        
        if len(pattern_matches) >= 4:
            fourth_strike = pattern_matches[3]
            logger.info(f"PE Bearish: Buy CE at strike {fourth_strike}")
            return {
                "pattern": PatternType.PE_BEARISH_BUY_CE,
                "strike": fourth_strike,
                "option_type": "CE",  # Buy opposite
                "action": "BUY"
            }
        
        return None
    
    def _get_otm_strikes(self, option_type: str, count: int = 4) -> List[int]:
        """Get OTM strikes from spot price.
        
        Args:
            option_type: "CE" or "PE"
            count: Number of strikes to return
            
        Returns:
            List of strike prices
        """
        if not self.spot_price:
            return []
        
        spot = int(self.spot_price)
        all_strikes = sorted([int(k.split("_")[0]) for k in self.market_data.keys() 
                             if k.endswith(f"_{option_type}")])
        
        if option_type == "CE":
            # OTM CEs are above spot
            otm_strikes = [s for s in all_strikes if s > spot]
        else:  # PE
            # OTM PEs are below spot
            otm_strikes = [s for s in all_strikes if s < spot]
            otm_strikes.reverse()  # Nearest first
        
        return otm_strikes[:count]
    
    def _get_nearest_strikes(self, option_type: str, count: int = 4) -> List[int]:
        """Get nearest strikes from ATM (for reversal patterns).
        
        Args:
            option_type: "CE" or "PE"
            count: Number of strikes to return
            
        Returns:
            List of strike prices
        """
        if not self.spot_price:
            return []
        
        spot = int(self.spot_price)
        all_strikes = sorted([int(k.split("_")[0]) for k in self.market_data.keys() 
                             if k.endswith(f"_{option_type}")])
        
        # Find ATM strike
        atm_strike = min(all_strikes, key=lambda x: abs(x - spot))
        atm_index = all_strikes.index(atm_strike)
        
        # Get 4 strikes starting from ATM
        if option_type == "CE":
            # For CE, go upward from ATM
            nearest = all_strikes[atm_index:atm_index + count]
        else:  # PE
            # For PE, go downward from ATM
            nearest = all_strikes[max(0, atm_index - count + 1):atm_index + 1]
            nearest.reverse()
        
        return nearest[:count]
    
    async def _wait_for_execution_time(self):
        """Wait until execution window (9:16:10 AM)."""
        logger.info("Waiting for execution window (9:16:10 AM)")
        
        while True:
            now = datetime.now().time()
            if now >= self.EXECUTION_START_TIME:
                logger.info("Execution window opened - placing order")
                break
            await asyncio.sleep(0.5)
    
    async def _place_order(
        self,
        symbol: str,
        pattern_result: Dict,
        quantity_lots: int,
        target_profit_percent: float
    ) -> Dict:
        """Place the order based on pattern result.
        
        Args:
            symbol: Trading symbol
            pattern_result: Pattern analysis result
            quantity_lots: Number of lots
            target_profit_percent: Profit target percentage
            
        Returns:
            Order execution result
        """
        try:
            strike = pattern_result["strike"]
            option_type = pattern_result["option_type"]
            
            # Calculate quantity
            lot_size = self.LOT_SIZES.get(symbol, 25)
            total_quantity = quantity_lots * lot_size
            
            logger.critical(
                f"Placing order: {symbol} {strike} {option_type} "
                f"Qty={total_quantity} ({quantity_lots} lots)"
            )
            
            # Place buy order
            buy_result = await self._place_buy_order(
                symbol=symbol,
                strike=strike,
                option_type=option_type,
                quantity=total_quantity
            )
            
            if not buy_result.get("success"):
                return buy_result
            
            buy_price = Decimal(str(buy_result.get("price", 0)))
            target_price = buy_price * (Decimal("1") + Decimal(str(target_profit_percent)) / Decimal("100"))
            
            # Place target order
            target_result = await self._place_target_order(
                symbol=symbol,
                strike=strike,
                option_type=option_type,
                quantity=total_quantity,
                target_price=float(target_price)
            )
            
            return {
                "success": True,
                "pattern": pattern_result["pattern"].value,
                "symbol": symbol,
                "strike": strike,
                "option_type": option_type,
                "quantity": total_quantity,
                "lots": quantity_lots,
                "buy_order_id": buy_result.get("order_id"),
                "buy_price": float(buy_price),
                "target_order_id": target_result.get("order_id"),
                "target_price": float(target_price),
                "target_percent": target_profit_percent
            }
            
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            raise
    
    async def _place_buy_order(
        self,
        symbol: str,
        strike: int,
        option_type: str,
        quantity: int
    ) -> Dict:
        """Place buy order (MARKET).
        
        Args:
            symbol: Trading symbol
            strike: Strike price
            option_type: CE or PE
            quantity: Order quantity
            
        Returns:
            Order result with order_id and execution price
        """
        try:
            # TODO: Replace with actual Upstox order placement
            logger.info(f"BUY {symbol} {strike}{option_type} Qty={quantity} @ MARKET")
            
            # Placeholder for actual API call
            # order_params = {
            #     "symbol": f"{symbol}{strike}{option_type}",
            #     "quantity": quantity,
            #     "transaction_type": "BUY",
            #     "order_type": "MARKET",
            #     "product": "INTRADAY",
            #     "validity": "DAY"
            # }
            # 
            # from .service import OptionsOrderService
            # service = OptionsOrderService(self.upstox_client)
            # result = await service.place_order(order_params)
            
            return {
                "success": True,
                "order_id": "BUY_12345",
                "price": 100.50  # Placeholder
            }
            
        except Exception as e:
            logger.error(f"Error placing buy order: {str(e)}")
            raise
    
    async def _place_target_order(
        self,
        symbol: str,
        strike: int,
        option_type: str,
        quantity: int,
        target_price: float
    ) -> Dict:
        """Place target sell order (LIMIT).
        
        Args:
            symbol: Trading symbol
            strike: Strike price
            option_type: CE or PE
            quantity: Order quantity
            target_price: Target limit price
            
        Returns:
            Order result with order_id
        """
        try:
            # TODO: Replace with actual Upstox order placement
            logger.info(
                f"TARGET SELL {symbol} {strike}{option_type} "
                f"Qty={quantity} @ LIMIT {target_price:.2f}"
            )
            
            # Placeholder for actual API call
            # order_params = {
            #     "symbol": f"{symbol}{strike}{option_type}",
            #     "quantity": quantity,
            #     "transaction_type": "SELL",
            #     "order_type": "LIMIT",
            #     "price": target_price,
            #     "product": "INTRADAY",
            #     "validity": "DAY"
            # }
            # 
            # from .service import OptionsOrderService
            # service = OptionsOrderService(self.upstox_client)
            # result = await service.place_order(order_params)
            
            return {
                "success": True,
                "order_id": "SELL_12346"
            }
            
        except Exception as e:
            logger.error(f"Error placing target order: {str(e)}")
            raise
    
    def _get_lot_size(self, symbol: str) -> int:
        """Get lot size for symbol."""
        return self.LOT_SIZES.get(symbol, 25)


# Global strategy instance
_strategy_instance: Optional[OptionChainStrategy] = None


def get_strategy(upstox_client) -> OptionChainStrategy:
    """Get or create strategy instance."""
    global _strategy_instance
    if _strategy_instance is None:
        _strategy_instance = OptionChainStrategy(upstox_client)
          return _strategy_instance
    return _strategy_instance
