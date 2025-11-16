"""Position Monitor Service for Automatic P&L Based Square-Off with Flexible Thresholds.

This module continuously monitors intraday positions and automatically
squares off all positions when profit/loss exceeds specified thresholds.
Supports flexible configuration: both thresholds, only profit, only loss, or neither.
"""

import asyncio
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MonitorStatus(str, Enum):
    """Monitor status enum"""
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class PositionMonitor:
    """Monitors positions and triggers auto square-off based on P&L thresholds."""
    
    def __init__(self, upstox_client, profit_percent: Optional[float] = None, loss_percent: Optional[float] = None):
        """Initialize position monitor with flexible thresholds.
        
        Args:
            upstox_client: Upstox API client instance
            profit_percent: Profit threshold percentage (e.g., 2.0 for 2%). None = no profit target
            loss_percent: Loss threshold percentage (e.g., 2.0 for 2%). None = no stop loss
        """
        self.upstox_client = upstox_client
        self.status = MonitorStatus.STOPPED
        
        # Set thresholds based on input (None means no threshold)
        self.profit_threshold = Decimal(str(profit_percent / 100)) if profit_percent is not None else None
        self.loss_threshold = Decimal(str(loss_percent / 100)) if loss_percent is not None else None
        
        self.check_interval = 5  # Check every 5 seconds
        self.total_invested_capital = Decimal(0)
        self.monitoring_task = None
        self._stop_flag = False
        
        # Statistics
        self.stats = {
            "checks_performed": 0,
            "last_check_time": None,
            "current_pnl": Decimal(0),
            "pnl_percent": Decimal(0),
            "threshold_breaches": 0
        }
        
        logger.info(f"PositionMonitor initialized: profit_threshold={'None' if self.profit_threshold is None else f'{self.profit_threshold * 100}%'}, loss_threshold={'None' if self.loss_threshold is None else f'{self.loss_threshold * 100}%'}")
    
    async def start_monitoring(self, check_interval: int = 5):
        """Start continuous position monitoring.
        
        Args:
            check_interval: How often to check positions in seconds
        """
        if self.status == MonitorStatus.RUNNING:
            logger.warning("Monitor is already running")
            return
        
        self.check_interval = check_interval
        self.status = MonitorStatus.RUNNING
        self._stop_flag = False
        
        logger.info(f"Starting position monitor with {check_interval}s interval")
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self) -> Dict:
        """Stop the position monitor and return final stats."""
        if self.status != MonitorStatus.RUNNING:
            logger.warning("Monitor is not running")
            return self.stats
        
        logger.info("Stopping position monitor")
        self._stop_flag = True
        self.status = MonitorStatus.STOPPED
        
        # Wait for monitoring task to complete
        if self.monitoring_task:
            try:
                await asyncio.wait_for(self.monitoring_task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("Monitoring task did not stop gracefully")
                self.monitoring_task.cancel()
        
        return self.stats
    
    async def _monitor_loop(self):
        """Main monitoring loop that continuously checks positions."""
        logger.info("Monitor loop started")
        
        while not self._stop_flag:
            try:
                # Check positions and P&L
                breach = await self._check_positions_and_pnl()
                
                self.stats["checks_performed"] += 1
                self.stats["last_check_time"] = datetime.now()
                
                # If threshold breached, stop monitoring
                if breach:
                    logger.info("Threshold breached - stopping monitor")
                    break
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {str(e)}")
                await asyncio.sleep(self.check_interval)
        
        self.status = MonitorStatus.STOPPED
        logger.info("Monitor loop stopped")
    
    async def _check_positions_and_pnl(self) -> bool:
        """Check positions and P&L, trigger square-off if thresholds breached.
        
        Returns:
            bool: True if threshold breached and square-off triggered, False otherwise
        """
        try:
            positions = await self._get_todays_positions()
            
            if not positions:
                logger.debug("No positions to monitor")
                return False
            
            total_invested, current_pnl = self._calculate_pnl(positions)
            
            if total_invested == 0:
                return False
            
            pnl_percent = (current_pnl / total_invested) * Decimal("100")
            
            self.stats["current_pnl"] = current_pnl
            self.stats["pnl_percent"] = pnl_percent
            
            logger.info(f"P&L Check: Invested={total_invested}, P&L={current_pnl}, P&L%={pnl_percent:.2f}%")
            
            # Check profit threshold (only if specified)
            if self.profit_threshold is not None:
                target_percent = self.profit_threshold * Decimal("100")
                if pnl_percent >= target_percent:
                    logger.critical(f"PROFIT TARGET REACHED: P&L={pnl_percent:.2f}% >= {target_percent}%")
                    self.stats["threshold_breaches"] += 1
                    await self._trigger_square_off("Profit target reached")
                    return True
            
            # Check loss threshold (only if specified)
            if self.loss_threshold is not None:
                stop_loss_percent = self.loss_threshold * Decimal("100")
                if pnl_percent <= -stop_loss_percent:
                    logger.critical(f"STOP LOSS HIT: P&L={pnl_percent:.2f}% <= -{stop_loss_percent}%")
                    self.stats["threshold_breaches"] += 1
                    await self._trigger_square_off("Stop loss hit")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking P&L: {str(e)}")
            return False
    
    async def _get_todays_positions(self) -> List[Dict]:
        """Get all positions opened today."""
        try:
            # Import service to use square off method
            from .service import OptionsOrderService
            service = OptionsOrderService(self.upstox_client)
            
            # Get all positions
            response = await service.upstox_client.get_positions()
            
            if not response or "data" not in response:
                return []
            
            positions = response["data"]
            today = date.today()
            
            # Filter only today's positions
            todays_positions = [
                pos for pos in positions
                if pos.get("created_at") and
                datetime.fromisoformat(pos["created_at"].replace("Z", "+00:00")).date() == today
            ]
            
            return todays_positions
            
        except Exception as e:
            logger.error(f"Error fetching today's positions: {str(e)}")
            return []
    
    def _calculate_pnl(self, positions: List[Dict]) -> tuple:
        """Calculate total invested capital and current P&L.
        
        Returns:
            tuple: (total_invested_capital, current_pnl)
        """
        total_invested = Decimal(0)
        current_pnl = Decimal(0)
        
        for position in positions:
            try:
                quantity = Decimal(str(position.get("quantity", 0)))
                buy_price = Decimal(str(position.get("buy_price", 0)))
                current_price = Decimal(str(position.get("last_price", buy_price)))
                
                # Calculate invested capital for this position
                invested = buy_price * quantity
                total_invested += invested
                
                # Calculate P&L for this position
                pnl = (current_price - buy_price) * quantity
                current_pnl += pnl
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error calculating P&L for position: {str(e)}")
                continue
        
        return total_invested, current_pnl
    
    async def _trigger_square_off(self, reason: str):
        """Trigger automatic square-off of all today's positions.
        
        Args:
            reason: Reason for square-off (e.g., 'Profit target reached')
        """
        try:
            logger.critical(f"TRIGGERING AUTO SQUARE-OFF: {reason}")
            
            # Import service to use square off method
            from .service import OptionsOrderService
            service = OptionsOrderService(self.upstox_client)
            
            # Square off all today's positions
            result = await service.square_off_today_positions()
            
            logger.critical(f"Square-off completed: {result}")
            
        except Exception as e:
            logger.error(f"Error triggering square-off: {str(e)}")
    
    def get_stats(self) -> Dict:
        """Get current monitoring statistics."""
        return {
            "status": self.status.value,
            "profit_threshold": f"{self.profit_threshold * 100:.2f}%" if self.profit_threshold else "None",
            "loss_threshold": f"{self.loss_threshold * 100:.2f}%" if self.loss_threshold else "None",
            "check_interval": self.check_interval,
            "stats": self.stats
        }
    
    def set_thresholds(self, profit_percent: Optional[float] = None, loss_percent: Optional[float] = None):
        """Set custom profit/loss thresholds.
        
        Args:
            profit_percent: Profit threshold percentage (e.g., 3.0 for 3%). None = no limit
            loss_percent: Loss threshold percentage (e.g., 1.5 for 1.5%). None = no limit
        """
        self.profit_threshold = Decimal(str(profit_percent / 100)) if profit_percent is not None else None
        self.loss_threshold = Decimal(str(loss_percent / 100)) if loss_percent is not None else None
        
        logger.info(f"Thresholds updated: Profit={'None' if self.profit_threshold is None else f'{self.profit_threshold * 100}%'}, Loss={'None' if self.loss_threshold is None else f'{self.loss_threshold * 100}%'}")


# Global monitor instance
_monitor_instance: Optional[PositionMonitor] = None


def get_monitor() -> PositionMonitor:
    """Get or create monitor instance.
    
    Returns:
        PositionMonitor instance
    """
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PositionMonitor()
    return _monitor_instance
