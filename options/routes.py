"""FastAPI routes for Options Trading API.

This module defines REST API endpoints for options trading.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from .models import OptionsOrderRequest, OptionsOrderResponse
from .service import OptionsOrderService
from .position_monitor import get_monitor

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/options",
    tags=["Options Trading"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# Initialize service
options_service = OptionsOrderService()


@router.post(
    "/place-order",
    response_model=OptionsOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place Options Order",
    description="Place options order(s) for CE, PE, or BOTH (straddle/strangle)"
)
async def place_options_order(request: OptionsOrderRequest) -> OptionsOrderResponse:
    """
    Place options order with the following features:
    
    - **strike_price**: Required strike price (must be valid for symbol)
    - **option_type**: CE, PE, or BOTH (required)
    - **validity**: DAY or IOC (required)
    - **ce_price_config**: Price config for CE (defaults to MARKET)
    - **pe_price_config**: Price config for PE (defaults to MARKET)
    
    For BOTH type orders:
    - Automatically places both CE and PE orders
    - Calculates breakeven points
    - Returns combined order details
    
    Example Request:
    ```json
    {
        "symbol": "NIFTY",
        "strike_price": 19500,
        "option_type": "CE",
        "expiry_date": "2025-11-28",
        "quantity": 50,
        "transaction_type": "BUY",
        "validity": "DAY",
        "ce_price_config": {
            "order_type": "MARKET"
        }
    }
    ```
    """
    try:
        logger.info(f"Received options order request: {request.symbol} {request.strike_price} {request.option_type.value}")
        
        # Place order through service
        response = await options_service.place_order(request)
        
        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.message
            )
        
        logger.info(f"Order placed successfully: Strategy ID {response.strategy_id}")
        return response
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error placing options order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to place order. Please try again."
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check if options trading service is running"
)
async def health_check():
    """Health check endpoint for options trading service."""
    return {
        "status": "healthy",
        "service": "options-trading",
        "version": "1.0.0"
    }


@router.get(
    "/supported-symbols",
    status_code=status.HTTP_200_OK,
    summary="Get Supported Symbols",
    description="Get list of supported underlying symbols with lot sizes"
)
async def get_supported_symbols():
    """Get list of supported symbols for options trading."""
    from .utils import LOT_SIZES
    
    return {
        "symbols": [
            {"symbol": symbol, "lot_size": lot_size}
            for symbol, lot_size in LOT_SIZES.items()
        ]
    }



@router.post(
    "/square-off/all",
    status_code=status.HTTP_200_OK,
    summary="Square Off All Options Positions",
    description="Close all open options positions"
)
async def square_off_all_positions():
    """Square off all open options positions.
    
    This endpoint will:
    - Fetch all open options positions
    - Place opposite orders to close each position
    - Return summary of closed positions
    
    Returns:
        Summary of squared off positions
    """
    try:
        logger.info("Squaring off all options positions")
        
        result = await options_service.square_off_all_positions()
        
        return {
            "success": True,
            "message": "Successfully squared off all positions",
            "positions_closed": result.get("positions_closed", 0),
            "total_pnl": result.get("total_pnl", 0),
            "details": result.get("details", [])
        }
    
    except Exception as e:
        logger.error(f"Error squaring off all positions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to square off positions: {str(e)}"
        )


@router.post(
    "/square-off/today",
    status_code=status.HTTP_200_OK,
    summary="Square Off Today's Options Positions",
    description="Close all options positions opened today"
)
async def square_off_today_positions():
    """Square off all options positions opened today.
    
    This endpoint will:
    - Filter positions opened today
    - Place opposite orders to close each position
    - Return summary of closed positions
    
    Perfect for EOD (End of Day) square-off scenarios.
    
    Returns:
        Summary of squared off positions
    """
    try:
        logger.info("Squaring off today's options positions")
        
        result = await options_service.square_off_today_positions()
        
        if result.get("positions_closed", 0) == 0:
            return {
                "success": True,
                "message": "No positions opened today to square off",
                "positions_closed": 0,
                "total_pnl": 0,
                "details": []
            }
        
        return {
            "success": True,
            "message": f"Successfully squared off {result.get('positions_closed', 0)} position(s) opened today",
            "positions_closed": result.get("positions_closed", 0),
            "total_pnl": result.get("total_pnl", 0),
            "details": result.get("details", [])
        }
    
    except Exception as e:
        logger.error(f"Error squaring off today's positions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to square off positions: {str(e)}"
        )



# ==================== Position Monitor Endpoints ====================

@router.post(
    "/monitor/start",
    status_code=status.HTTP_200_OK,
    summary="Start Position Monitoring",
    description="Start continuous monitoring of intraday positions with auto square-off at 2% P&L threshold"
)
async def start_position_monitor(check_interval: int = 5):
    """Start the position monitor.
    
    Args:
        check_interval: How often to check positions (seconds). Default: 5
    
    Returns:
        Confirmation message and monitor status
    """
    try:
        monitor = get_monitor()
        
        if monitor.status.value == "RUNNING":
            return {
                "success": False,
                "message": "Monitor is already running",
                "status": monitor.status.value
            }
        
        await monitor.start_monitoring(check_interval)
        
        logger.info(f"Position monitor started with {check_interval}s check interval")
        
        return {
            "success": True,
            "message": f"Position monitor started successfully",
            "status": monitor.status.value,
            "check_interval": check_interval,
            "thresholds": {
                "profit": f"{monitor.profit_threshold}%",
                "loss": f"{monitor.loss_threshold}%"
            }
        }
    
    except Exception as e:
        logger.error(f"Error starting position monitor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start position monitor: {str(e)}"
        )


@router.post(
    "/monitor/stop",
    status_code=status.HTTP_200_OK,
    summary="Stop Position Monitoring",
    description="Stop the position monitor and get final statistics"
)
async def stop_position_monitor():
    """Stop the position monitor.
    
    Returns:
        Final monitor statistics
    """
    try:
        monitor = get_monitor()
        
        if monitor.status.value == "STOPPED":
            return {
                "success": False,
                "message": "Monitor is not running",
                "status": monitor.status.value
            }
        
        stats = await monitor.stop_monitoring()
        
        logger.info("Position monitor stopped")
        
        return {
            "success": True,
            "message": "Position monitor stopped successfully",
            "status": monitor.status.value,
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"Error stopping position monitor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop position monitor: {str(e)}"
        )


@router.get(
    "/monitor/status",
    status_code=status.HTTP_200_OK,
    summary="Get Monitor Status",
    description="Get current status and statistics of the position monitor"
)
async def get_monitor_status():
    """Get monitor status and statistics.
    
    Returns:
        Monitor status, thresholds, and statistics
    """
    try:
        monitor = get_monitor()
        stats = monitor.get_stats()
        
        return {
            "success": True,
            "status": monitor.status.value,
            "thresholds": {
                "profit": f"{monitor.profit_threshold}%",
                "loss": f"{monitor.loss_threshold}%"
            },
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"Error getting monitor status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitor status: {str(e)}"
        )


@router.post(
    "/monitor/set-threshold",
    status_code=status.HTTP_200_OK,
    summary="Set Monitor Thresholds",
    description="Update profit and loss thresholds for auto square-off"
)
async def set_monitor_thresholds(profit_percent: float = 2.0, loss_percent: float = 2.0):
    """Set custom thresholds for the monitor.
    
    Args:
        profit_percent: Profit threshold percentage (default 2%)
        loss_percent: Loss threshold percentage (default 2%)
    
    Returns:
        Confirmation message with new thresholds
    """
    try:
        if profit_percent <= 0 or loss_percent <= 0:
            raise ValueError("Thresholds must be positive numbers")
        
        monitor = get_monitor()
        monitor.set_thresholds(profit_percent, loss_percent)
        
        logger.info(f"Monitor thresholds updated: Profit={profit_percent}%, Loss={loss_percent}%")
        
        return {
            "success": True,
            "message": "Thresholds updated successfully",
            "thresholds": {
                "profit": f"{profit_percent}%",
                "loss": f"{loss_percent}%"
            }
        }
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error setting monitor thresholds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set monitor thresholds: {str(e)}"
        )


@router.post(
    "/auto-trade/opening-otm-strategy",
    status_code=status.HTTP_200_OK,
    summary="Execute Opening OTM Strategy",
    description="Automated trading based on market opening conditions with configurable lot quantity"
)
async def execute_opening_otm_strategy(
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    otm_range: int = 500,
    target_profit_percent: float = 10.0,
    price_tolerance: float = 2.0
):
    """Execute opening OTM strategy with configurable parameters.
    
    This strategy:
    - Triggers at 9:15:10 AM and monitors market until 9:15:50 AM
    - BEARISH signal: open price == high price → buys PE option
    - BULLISH signal: open price == low price → buys CE option
    - Selects highest OI among OTM strikes within ±otm_range points
    - Automatically places 10% profit target order
    - Executes orders between 9:15:50 - 9:16:10 AM
    
    Args:
        symbol: Trading symbol (NIFTY, BANKNIFTY, FINNIFTY)
        quantity_lots: Number of lots to execute (multiplies lot size)
        otm_range: OTM strike search range in points (default: 500)
        target_profit_percent: Profit target percentage (default: 10%)
        price_tolerance: Price equality tolerance in points (default: 2)
        
    Returns:
        Strategy execution result with order details
    """
    try:
        from .opening_otm_strategy import get_strategy
        from auth.dependencies import get_upstox_client
        
        logger.info(f"Executing opening OTM strategy: {symbol}, lots={quantity_lots}")
        
        upstox_client = get_upstox_client()
        strategy = get_strategy(upstox_client)
        
        result = await strategy.execute_strategy(
            symbol=symbol,
            quantity_lots=quantity_lots,
            otm_range=otm_range,
            target_profit_percent=target_profit_percent,
            price_tolerance=price_tolerance
        )
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error executing opening strategy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute strategy: {str(e)}"
        )


@router.post(
    "/auto-trade/option-chain-strategy",
    status_code=status.HTTP_200_OK,
    summary="Execute Option Chain Pattern Strategy",
    description="Automated trading based on option chain patterns with priority execution"
)
async def execute_option_chain_strategy(
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    target_profit_percent: float = 5.0,
    price_tolerance: float = 0.5
):
    """Execute option chain pattern strategy.
    
    Pattern Priority (executes ONLY ONE):
    1. CE Bullish: 4 OTM CEs with open==low → Buy 4th OTM CE
    2. PE Bullish: 4 OTM PEs with open==low → Buy 4th OTM PE  
    3. CE Bearish: 4 nearest CEs with open==high → Buy PE at 4th strike
    4. PE Bearish: 4 nearest PEs with open==high → Buy CE at 4th strike
    
    Timing:
    - Monitors: 9:15:00 - 9:16:00 AM (60 seconds)
    - Executes: 9:16:10 - 9:16:20 AM (10 seconds)
    
    Args:
        symbol: Trading symbol (NIFTY, BANKNIFTY, FINNIFTY)
        quantity_lots: Number of lots to execute
        target_profit_percent: Profit target percentage (default 5%)
        price_tolerance: Tolerance for open==low/high checks (default 0.5)
    
    Returns:
        Strategy execution result
    """
    try:
        from .option_chain_strategy import get_strategy
        from auth.dependencies import get_upstox_client
        
        logger.info(f"Executing option chain strategy: {symbol}, lots={quantity_lots}")
        
        upstox_client = get_upstox_client()
        strategy = get_strategy(upstox_client)
        
        result = await strategy.execute_strategy(
            symbol=symbol,
            quantity_lots=quantity_lots,
            target_profit_percent=target_profit_percent,
            price_tolerance=price_tolerance
        )
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error executing option chain strategy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute strategy: {str(e)}"
        )
