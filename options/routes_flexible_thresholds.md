# Routes.py Updates for Flexible Threshold Monitoring

## How to Integrate position_monitor_v2.py with Flexible Thresholds

### Step 1: Update the import statement in routes.py

**Change this:**
```python
from .position_monitor import get_monitor
```

**To this:**
```python
from .position_monitor_v2 import PositionMonitor, get_monitor
```

---

### Step 2: Update the `/monitor/start` endpoint

**Replace the existing endpoint with this enhanced version:**

```python
@router.post(
    "/monitor/start",
    status_code=status.HTTP_200_OK,
    summary="Start Position Monitoring",
    description="Start continuous monitoring with flexible profit/loss thresholds"
)
async def start_position_monitor(
    check_interval: int = 5,
    profit_percent: Optional[float] = None,
    loss_percent: Optional[float] = None
):
    """Start the position monitor with optional thresholds.
    
    Args:
        check_interval: How often to check positions (seconds). Default: 5
        profit_percent: Profit target (e.g., 3.0 for 3%). None = no profit target
        loss_percent: Stop loss (e.g., 2.0 for 2%). None = no stop loss
    
    Examples:
        - Both thresholds: profit_percent=3.0, loss_percent=2.0
        - Only profit: profit_percent=5.0, loss_percent=None
        - Only loss: profit_percent=None, loss_percent=1.5
        - Monitor only: profit_percent=None, loss_percent=None
    
    Returns:
        Confirmation message and monitor status
    """
    try:
        # Create new monitor instance with specified thresholds
        monitor = PositionMonitor(
            upstox_client=options_service.upstox_client,
            profit_percent=profit_percent,
            loss_percent=loss_percent
        )
        
        # Check if already running
        if monitor.status.value == "RUNNING":
            return {
                "success": False,
                "message": "Monitor is already running",
                "status": monitor.status.value
            }
        
        await monitor.start_monitoring(check_interval)
        
        # Build threshold info for response
        threshold_info = {
            "profit": f"{profit_percent}%" if profit_percent is not None else "None (no limit)",
            "loss": f"{loss_percent}%" if loss_percent is not None else "None (no limit)"
        }
        
        logger.info(f"Position monitor started: check_interval={check_interval}s, thresholds={threshold_info}")
        
        return {
            "success": True,
            "message": "Position monitor started successfully",
            "status": monitor.status.value,
            "check_interval": check_interval,
            "thresholds": threshold_info,
            "configuration": {
                "profit_target": "Active" if profit_percent is not None else "Disabled",
                "stop_loss": "Active" if loss_percent is not None else "Disabled",
                "mode": (
                    "Full Protection" if profit_percent and loss_percent
                    else "Profit Only" if profit_percent
                    else "Loss Only" if loss_percent
                    else "Monitoring Only (No Auto Square-off)"
                )
            }
        }
    
    except Exception as e:
        logger.error(f"Error starting position monitor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start position monitor: {str(e)}"
        )
```

---

### Step 3: Update the `/monitor/status` endpoint response

**Enhance the status endpoint to show threshold configuration:**

```python
@router.get(
    "/monitor/status",
    status_code=status.HTTP_200_OK,
    summary="Get Monitor Status",
    description="Get current status and statistics of the position monitor"
)
async def get_monitor_status():
    """Get monitor status and statistics.
    
    Returns:
        Monitor status, thresholds, and statistics with configuration details
    """
    try:
        monitor = get_monitor()
        stats = monitor.get_stats()
        
        return {
            "success": True,
            "status": monitor.status.value,
            "thresholds": {
                "profit": stats.get("profit_threshold", "None"),
                "loss": stats.get("loss_threshold", "None")
            },
            "configuration": {
                "profit_target_active": monitor.profit_threshold is not None,
                "stop_loss_active": monitor.loss_threshold is not None,
            },
            "stats": stats.get("stats", {})
        }
    
    except Exception as e:
        logger.error(f"Error getting monitor status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitor status: {str(e)}"
        )
```

---

## API Usage Examples

### Example 1: Both Profit Target (3%) AND Stop Loss (2%)
**Traditional risk management - good for options with defined risk**

```bash
POST /api/v1/options/monitor/start
Content-Type: application/json

{
  "check_interval": 5,
  "profit_percent": 3.0,
  "loss_percent": 2.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Position monitor started successfully",
  "status": "RUNNING",
  "check_interval": 5,
  "thresholds": {
    "profit": "3.0%",
    "loss": "2.0%"
  },
  "configuration": {
    "profit_target": "Active",
    "stop_loss": "Active",
    "mode": "Full Protection"
  }
}
```

---

### Example 2: Only Profit Target (5%), NO Stop Loss
**Bullish strategy - let winners run, book at target**

```bash
POST /api/v1/options/monitor/start
Content-Type: application/json

{
  "check_interval": 5,
  "profit_percent": 5.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Position monitor started successfully",
  "status": "RUNNING",
  "thresholds": {
    "profit": "5.0%",
    "loss": "None (no limit)"
  },
  "configuration": {
    "profit_target": "Active",
    "stop_loss": "Disabled",
    "mode": "Profit Only"
  }
}
```

---

### Example 3: Only Stop Loss (1.5%), NO Profit Target
**Capital preservation - cut losses quickly, unlimited upside**

```bash
POST /api/v1/options/monitor/start
Content-Type: application/json

{
  "check_interval": 5,
  "loss_percent": 1.5
}
```

**Response:**
```json
{
  "success": true,
  "message": "Position monitor started successfully",
  "status": "RUNNING",
  "thresholds": {
    "profit": "None (no limit)",
    "loss": "1.5%"
  },
  "configuration": {
    "profit_target": "Disabled",
    "stop_loss": "Active",
    "mode": "Loss Only"
  }
}
```

---

### Example 4: Monitoring Only (No Auto Square-off)
**Pure tracking - monitor P&L without automatic actions**

```bash
POST /api/v1/options/monitor/start
Content-Type: application/json

{
  "check_interval": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Position monitor started successfully",
  "status": "RUNNING",
  "thresholds": {
    "profit": "None (no limit)",
    "loss": "None (no limit)"
  },
  "configuration": {
    "profit_target": "Disabled",
    "stop_loss": "Disabled",
    "mode": "Monitoring Only (No Auto Square-off)"
  }
}
```

---

## Trading Strategy Use Cases

### 1. **Conservative Straddle/Strangle (Both CE & PE)**
```json
{
  "profit_percent": 2.0,
  "loss_percent": 2.0
}
```
✅ Symmetric risk management  
✅ Quick exits on both sides  
✅ Good for high volatility days

### 2. **Bullish Call Buying (Let Winners Run)**
```json
{
  "profit_percent": 5.0,
  "loss_percent": null
}
```
✅ Capture large upside moves  
✅ No artificial profit cap  
✅ Use manual stop or let position expire

### 3. **Options Selling (Premium Decay)**
```json
{
  "profit_percent": 3.0,
  "loss_percent": 2.0
}
```
✅ Book profits at 60% of max  
✅ Tighter stop loss (options can move fast)  
✅ Typical for credit spreads

### 4. **Intraday Scalping**
```json
{
  "profit_percent": 1.0,
  "loss_percent": 0.5
}
```
✅ Quick profits, tight stops  
✅ High frequency trading  
✅ Good for range-bound markets

---

## Important Notes

⚠️ **Risk Warnings:**
- `loss_percent=None` means **UNLIMITED RISK** - use with caution!
- Options can move 50-100% quickly - tight stops recommended
- Monitor network connectivity - missed checks could be costly

✅ **Best Practices:**
- Start with both thresholds until comfortable
- Use tighter stops (1-2%) for options vs stocks
- Test in paper trading first
- Consider time decay when setting profit targets
- Check monitor status regularly with `/monitor/status`

---

## Complete Routes.py Integration Checklist

- [ ] Import `PositionMonitor` from `position_monitor_v2.py`
- [ ] Update `/monitor/start` endpoint with Optional threshold parameters
- [ ] Update response format to show threshold configuration
- [ ] Test all 4 scenarios (both, profit-only, loss-only, neither)
- [ ] Update API documentation/Swagger
- [ ] Add logging for threshold configurations
- [ ] Test with live positions (paper trading first!)

---

**File created:** November 16, 2025  
**Version:** 2.0 - Flexible Threshold Monitoring
