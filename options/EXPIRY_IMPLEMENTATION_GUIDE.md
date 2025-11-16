# Expiry Parameter Implementation Guide

## Overview
This guide provides step-by-step instructions to add `monitor_expiry` and `order_expiry` parameters to all trading strategies.

## Status
✅ **utils.py** - Expiry utility functions COMMITTED  
⏳ **Remaining:** 3 files need manual updates

---

## File 1: opening_otm_strategy.py

### Step 1: Add Import (Line ~16)
**Location:** After existing imports, add:
```python
from .utils import get_expiry_date, format_option_symbol, validate_expiry_date
```

### Step 2: Update execute_strategy() Parameters (Line ~48)
**Location:** In `async def execute_strategy()`, ADD these two parameters:
```python
async def execute_strategy(
    self,
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    otm_range: int = 500,
    target_profit_percent: float = 10.0,
    price_tolerance: float = 2.0,
    monitor_expiry: str = "current_week",     # ADD THIS
    order_expiry: str = "current_week"        # ADD THIS
) -> Dict:
```

### Step 3: Add Expiry Conversion Logic (Line ~62)
**Location:** Inside `execute_strategy()`, after parameter validation, ADD:
```python
# Convert expiry types to actual dates
self.monitor_expiry_date = get_expiry_date(monitor_expiry)
self.order_expiry_date = get_expiry_date(order_expiry)
validate_expiry_date(self.monitor_expiry_date)
validate_expiry_date(self.order_expiry_date)

logger.info(
    f"Using monitor_expiry: {self.monitor_expiry_date}, "
    f"order_expiry: {self.order_expiry_date}"
)
```

### Step 4: Update Order Placement (Line ~400+)
**Location:** In `_place_buy_order()` method, REPLACE strike symbol creation with:
```python
# OLD: option_symbol = f"{symbol}{strike}{option_type}"
# NEW:
option_symbol = format_option_symbol(
    symbol,
    self.order_expiry_date,
    strike,
    option_type
)
logger.info(f"Placing order: {option_symbol}")
```

### Step 5: Update Target Order (Line ~420+)
**Location:** In `_place_target_order()` method, use same format:
```python
option_symbol = format_option_symbol(
    symbol,
    self.order_expiry_date,
    strike,
    option_type
)
```

---

## File 2: option_chain_strategy.py

### Step 1: Add Import (Line ~16)
**Same as opening_otm_strategy.py:**
```python
from .utils import get_expiry_date, format_option_symbol, validate_expiry_date
```

### Step 2: Update execute_strategy() Parameters (Line ~48)
**ADD two parameters:**
```python
async def execute_strategy(
    self,
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    target_profit_percent: float = 5.0,
    price_tolerance: float = 0.5,
    monitor_expiry: str = "current_week",     # ADD THIS
    order_expiry: str = "current_week"        # ADD THIS
) -> Dict:
```

### Step 3: Add Expiry Conversion (Line ~62)
**Same logic as opening_otm_strategy:**
```python
# Convert expiry types to actual dates
self.monitor_expiry_date = get_expiry_date(monitor_expiry)
self.order_expiry_date = get_expiry_date(order_expiry)
validate_expiry_date(self.monitor_expiry_date)
validate_expiry_date(self.order_expiry_date)

logger.info(
    f"Using monitor_expiry: {self.monitor_expiry_date}, "
    f"order_expiry: {self.order_expiry_date}"
)
```

### Step 4: Update Order Methods
**In both `_place_buy_order()` and `_place_target_order()`:**
```python
option_symbol = format_option_symbol(
    symbol,
    self.order_expiry_date,
    strike,
    option_type
)
```

---

## File 3: routes.py

### Change 1: Update opening_otm_strategy endpoint (Line ~393)

**BEFORE:**
```python
async def execute_opening_otm_strategy(
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    otm_range: int = 500,
    target_profit_percent: float = 10.0,
    price_tolerance: float = 2.0
):
```

**AFTER:**
```python
async def execute_opening_otm_strategy(
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    otm_range: int = 500,
    target_profit_percent: float = 10.0,
    price_tolerance: float = 2.0,
    monitor_expiry: str = "current_week",     # ADD
    order_expiry: str = "current_week"        # ADD
):
```

**Update docstring (add these lines):**
```python
"""Execute opening OTM strategy with configurable parameters.

Args:
    ...
    monitor_expiry: Expiry to monitor ("current_week", "next_week", "current_month", "next_month", or "YYYY-MM-DD")
    order_expiry: Expiry for order placement (same options as monitor_expiry)
"""
```

**Update strategy call (Line ~430+):**
```python
result = await strategy.execute_strategy(
    symbol=symbol,
    quantity_lots=quantity_lots,
    otm_range=otm_range,
    target_profit_percent=target_profit_percent,
    price_tolerance=price_tolerance,
    monitor_expiry=monitor_expiry,              # ADD
    order_expiry=order_expiry                   # ADD
)
```

### Change 2: Update option_chain_strategy endpoint (Line ~459)

**BEFORE:**
```python
async def execute_option_chain_strategy(
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    target_profit_percent: float = 5.0,
    price_tolerance: float = 0.5
):
```

**AFTER:**
```python
async def execute_option_chain_strategy(
    symbol: str = "NIFTY",
    quantity_lots: int = 1,
    target_profit_percent: float = 5.0,
    price_tolerance: float = 0.5,
    monitor_expiry: str = "current_week",     # ADD
    order_expiry: str = "current_week"        # ADD
):
```

**Update docstring (add expiry parameter docs)**

**Update strategy call (Line ~495+):**
```python
result = await strategy.execute_strategy(
    symbol=symbol,
    quantity_lots=quantity_lots,
    target_profit_percent=target_profit_percent,
    price_tolerance=price_tolerance,
    monitor_expiry=monitor_expiry,              # ADD
    order_expiry=order_expiry                   # ADD
)
```

---

## Testing After Implementation

### Test 1: Default Behavior (Current Week)
```bash
curl -X POST "http://localhost:8000/api/v1/options/auto-trade/opening-otm-strategy" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NIFTY",
    "quantity_lots": 1
  }'
```

### Test 2: Monitor Current, Trade Next Week
```bash
curl -X POST "http://localhost:8000/api/v1/options/auto-trade/opening-otm-strategy" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NIFTY",
    "quantity_lots": 2,
    "monitor_expiry": "current_week",
    "order_expiry": "next_week"
  }'
```

### Test 3: Specific Dates
```bash
curl -X POST "http://localhost:8000/api/v1/options/auto-trade/option-chain-strategy" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BANKNIFTY",
    "quantity_lots": 3,
    "monitor_expiry": "2025-11-21",
    "order_expiry": "2025-11-28"
  }'
```

---

## Expected Behavior

### Scenario 1: Same Expiry (Default)
- `monitor_expiry="current_week"`, `order_expiry="current_week"`
- Analyzes current week options
- Places orders in current week options
- **Use Case:** Standard weekly trading

### Scenario 2: Monitor Near, Trade Far
- `monitor_expiry="current_week"`, `order_expiry="next_week"`
- Analyzes current week data for signals
- Places orders in next week (more liquid, safer)
- **Use Case:** Avoiding expiry week risks

### Scenario 3: Monitor Monthly, Trade Weekly
- `monitor_expiry="current_month"`, `order_expiry="current_week"`
- Analyzes monthly expiry for broader signals
- Executes in weekly expiry for flexibility
- **Use Case:** Macro trend with tactical execution

---

## Validation

The `validate_expiry_date()` function will:
1. ✅ Check date format (YYYY-MM-DD)
2. ✅ Ensure date is not in past
3. ⚠️ Warn if not Thursday (but allow it)
4. ❌ Raise error for invalid formats

---

## Benefits

✅ **Flexibility** - Trade any expiry combination  
✅ **Risk Management** - Avoid near-expiry gamma risks  
✅ **Liquidity** - Choose most liquid expiry  
✅ **Testing** - Easy backtest different expiries  
✅ **Scalping** - Monitor monthly, trade intraday weekly  

---

## Summary Checklist

- [ ] Update opening_otm_strategy.py (5 changes)
- [ ] Update option_chain_strategy.py (5 changes)
- [ ] Update routes.py (4 changes)
- [ ] Test default behavior
- [ ] Test mixed expiries
- [ ] Test specific dates
- [ ] Verify symbol formatting (NIFTY25NOV24500CE)

---

## Notes

1. **Symbol Format:** The `format_option_symbol()` creates symbols like `NIFTY25NOV24500CE`
2. **Upstox Format:** You may need to adjust based on Upstox's exact format requirements
3. **Market Data:** Ensure your data feed supports the expiry dates you're monitoring
4. **Logging:** All expiry conversions are logged for debugging

---

## Support

If you encounter issues:
1. Check logs for expiry date conversions
2. Verify option symbol format with Upstox docs
3. Test with current_week first before trying other expiries
4. Ensure market data includes the expiry you're monitoring

---

**End of Implementation Guide**
