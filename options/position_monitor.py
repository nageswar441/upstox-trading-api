"""Position Monitor Service for Automatic P&L Based Square-Off.

This module continuously monitors intraday positions and automatically
squares off all positions when profit/loss exceeds 2% of invested capital.
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
    
    def __init__(self, upstox_client=None):
        """Initialize position monitor.
        
        Args:
            upstox_client: Upstox API client instance
        """
        self.upstox_client = upstox_client
        self.status = MonitorStatus.STOPPED
        self.profit_threshold = Decimal("0.02")  # 2% profit
        self.loss_threshold = Decimal("0.02")    # 2% loss
        self.check_interval = 5  # Check every 5 seconds
        self.total_invested_capital = Decimal(0)
        self.monitoring_task = None
        self._stop_flag = False
        
        # Statistics
        self.stats = {
            "checks_performed": 0,
            "last_check_time": None,
            "current_pnl": Decimal(0),
            "current_pnl_percent": Decimal(0),
            "auto_squared_off": False,
            "square_off_reason": None
        }
    
    async def start_monitoring(self, check_interval: int = 5) -> Dict:
        """Start monitoring positions.
        
        Args:
            check_interval: Interval in seconds between checks
        
        Returns:
            Start confirmation dict
        """
        if self.status == MonitorStatus.RUNNING:
            return {
                "success": False,
                "message": "Monitor is already running"
            }
        
        self.check_interval = check_interval
        self._stop_flag = False
        self.status = MonitorStatus.RUNNING
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"Position monitor started with {check_interval}s interval")
        logger.info(f"Profit threshold: {self.profit_threshold * 100}%")
        logger.info(f"Loss threshold: {self.loss_threshold * 100}%")
        
        return {
            "success": True,
            "message": "Position monitoring started",
            "check_interval": check_interval,
            "profit_threshold": f"{self.profit_threshold * 100}%",
            "loss_threshold": f"{self.loss_threshold * 100}%"
        }
    
    async def stop_monitoring(self) -> Dict:
        """Stop monitoring positions.
        
        Returns:
            Stop confirmation dict
        """
        if self.status == MonitorStatus.STOPPED:
            return {
                "success": False,
                "message": "Monitor is not running"
            }
        
        self._stop_flag = True
        self.status = MonitorStatus.STOPPED
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Position monitor stopped")
        
        return {
            "success": True,
            "message": "Position monitoring stopped",
            "stats": self.get_stats()
        }
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Monitoring loop started")
        
        while not self._stop_flag:
            try:
                # Check positions and P&L
                await self._check_positions_and_pnl()
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_positions_and_pnl(self):
        """Check current positions and P&L against thresholds."""
        try:
            # Fetch today's positions
            positions = await self._get_todays_positions()
            
            if not positions:
                logger.debug("No positions to monitor")
                return
            
            # Calculate total invested capital and current P&L
            total_invested, current_pnl = self._calculate_pnl(positions)
            
            if total_invested == 0:
                logger.debug("No invested capital")
                return
            
            # Calculate P&L percentage
            pnl_percent = (current_pnl / total_invested) * 100
            
            # Update stats
            self.stats["checks_performed"] += 1
            self.stats["last_check_time"] = datetime.now().isoformat()
            self.stats["current_pnl"] = float(current_pnl)
            self.stats["current_pnl_percent"] = float(pnl_percent)
            self.total_invested_capital = total_invested
            
            logger.info(f"P&L Check: ₹{current_pnl:.2f} ({pnl_percent:.2f}%) | Capital: ₹{total_invested:.2f}")
            
            # Check if thresholds breached
            should_square_off = False
            reason = None
            
            if pnl_percent >= (self.profit_threshold * 100):
                should_square_off = True
                reason = f"Profit target reached: {pnl_percent:.2f}% (Target: {self.profit_threshold * 100}%)"
                logger.warning(f"🎯 {reason}")
            
            elif pnl_percent <= -(self.loss_threshold * 100):
                should_square_off = True
                reason = f"Stop loss hit: {pnl_percent:.2f}% (Threshold: {self.loss_threshold * 100}%)"
                logger.warning(f"🛑 {reason}")
            
            # Trigger square-off if threshold breached
            if should_square_off:
                logger.critical(f"Auto Square-Off Triggered! Reason: {reason}")
                await self._trigger_square_off(reason)
                self.stats["auto_squared_off"] = True
                self.stats["square_off_reason"] = reason
                # Stop monitoring after square-off
                await self.stop_monitoring()
        
        except Exception as e:
            logger.error(f"Error checking positions: {str(e)}")
            raise
    
    async def _get_todays_positions(self) -> List[Dict]:
        """Fetch today's positions.
        
        Returns:
            List of position dictionaries
        """
        # TODO: Replace with actual Upstox API call
        # positions = await self.upstox_client.get_positions()
        # Filter today's positions
        
        today = date.today()
        
        # Mock data for demonstration
        mock_positions = [
            {
                "symbol": "NIFTY",
                "strike": 19500,
                "option_type": "CE",
                "quantity": 50,
                "buy_price": 150.00,
                "current_price": 153.50,  # +2.33% profit
                "entry_date": today
            },
            {
                "symbol": "BANKNIFTY",
                "strike": 44000,
                "option_type": "PE",
                "quantity": 25,
                "buy_price": 200.00,
                "current_price": 201.00,  # +0.5% profit
                "entry_date": today
            }
        ]
        
        return [p for p in mock_positions if p.get("entry_date") == today]
    
    def _calculate_pnl(self, positions: List[Dict]) -> tuple:
        """Calculate total invested capital and current P&L.
        
        Args:
            positions: List of position dicts
        
        Returns:
            Tuple of (total_invested, current_pnl)
        """
        total_invested = Decimal(0)
        current_value = Decimal(0)
        
        for pos in positions:
            invested = Decimal(str(pos["buy_price"])) * pos["quantity"]
            current = Decimal(str(pos["current_price"])) * pos["quantity"]
            
            total_invested += invested
            current_value += current
        
        pnl = current_value - total_invested
        
        return (total_invested, pnl)
    
    async def _trigger_square_off(self, reason: str):
        """Trigger automatic square-off of all positions.
        
        Args:
            reason: Reason for square-off
        """
        try:
            logger.critical("="*60)
            logger.critical("AUTOMATIC SQUARE-OFF INITIATED")
            logger.critical(f"Reason: {reason}")
            logger.critical("="*60)
            
            # Import here to avoid circular dependency
            from .service import OptionsOrderService
            
            service = OptionsOrderService(self.upstox_client)
            result = await service.square_off_today_positions()
            
            logger.critical(f"Square-off completed: {result['positions_closed']} positions closed")
            logger.critical(f"Final P&L: ₹{result['total_pnl']:.2f}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error during auto square-off: {str(e)}")
            raise
    
    def get_stats(self) -> Dict:
        """Get monitoring statistics.
        
        Returns:
            Stats dictionary
        """
        return {
            "status": self.status.value,
            "profit_threshold": f"{self.profit_threshold * 100}%",
            "loss_threshold": f"{self.loss_threshold * 100}%",
            "check_interval": self.check_interval,
            "total_invested_capital": float(self.total_invested_capital),
            **self.stats
        }
    
    def set_thresholds(self, profit_percent: float = 2.0, loss_percent: float = 2.0):
        """Set custom profit/loss thresholds.
        
        Args:
            profit_percent: Profit threshold percentage (default 2%)
            loss_percent: Loss threshold percentage (default 2%)
        """
        self.profit_threshold = Decimal(str(profit_percent / 100))
        self.loss_threshold = Decimal(str(loss_percent / 100))
        
        logger.info(f"Thresholds updated: Profit={profit_percent}%, Loss={loss_percent}%")


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
