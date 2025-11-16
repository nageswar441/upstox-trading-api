"""FastAPI routes for Options Trading API.

This module defines REST API endpoints for options trading.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from .models import OptionsOrderRequest, OptionsOrderResponse
from .service import OptionsOrderService

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
