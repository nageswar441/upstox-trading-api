# 🚀 Upstox Trading API - Complete Setup Guide

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 📋 Overview

Production-ready FastAPI application for automated trading with Upstox featuring:
- ✅ **REST APIs** - Order management, account info, market data
- 📊 **WebSocket Streaming** - Real-time market data
- 🔔 **Webhook Support** - Order and trade updates
- 🔐 **API Key Authentication** - Secure endpoints
- 📖 **Swagger Docs** - Interactive API documentation
- 🐳 **Docker Ready** - Easy deployment

## 🎯 Perfect For

- Algorithmic trading strategies
- Options trading automation (PCR analysis, Greeks)
- VWAP-based trading strategies  
- Real-time market monitoring
- Portfolio management
- Trading bots for NSE/BSE

---

## 📦 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/nageswar441/upstox-trading-api.git
cd upstox-trading-api
```

### 2. Create Project Files

Create the following files in your project directory:

---

## 📄 **requirements.txt** (Already Created ✅)

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
httpx==0.25.1
python-dotenv==1.0.0
websockets==12.0
pydantic==2.5.0
```

---

## 📄 **.env.example**

Create this file and copy your Upstox credentials:

```env
UPSTOX_API_KEY=your_api_key_here
UPSTOX_API_SECRET=your_api_secret_here  
UPSTOX_API_TOKEN=your_token_here
INTERNAL_API_KEY=your_strong_random_key_here
WEBHOOK_SECRET=your_webhook_secret_here
```

Then copy to `.env`:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

---

## 📄 **config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
UPSTOX_API_TOKEN = os.getenv("UPSTOX_API_TOKEN")
UPSTOX_BASE_URL = "https://api.upstox.com/v2"
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
UPSTOX_WEBSOCKET_URL = "wss://api.upstox.com/v2/feed/market-data-feed"
```

---

## 📄 **models.py**

Create Pydantic models for validation:

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class OrderRequest(BaseModel):
    symbol: str = Field(..., example="NSE_EQ|INE155A01022")
    quantity: int = Field(..., example=1)
    order_type: str = Field(..., example="MARKET")
    side: str = Field(..., example="BUY")
    product: str = Field("D", example="D")
    validity: str = Field("DAY", example="DAY")
    price: Optional[float] = Field(0)
    transaction_type: str = Field(..., example="BUY")

class OrderResponse(BaseModel):
    status: str
    data: Optional[Dict[str, Any]] = None

class AccountInfo(BaseModel):
    status: str
    data: Dict[str, Any]

class MarketFeedResponse(BaseModel):
    status: str
    data: Dict[str, Any]

class WebhookPayload(BaseModel):
    event: str = Field(..., example="order.placed")
    data: Dict[str, Any]

class WebSocketSubscription(BaseModel):
    instrument_keys: List[str]
    mode: str = Field("full", example="full")
```

---

## 📄 **main.py**

Core FastAPI application with all REST endpoints:

<details>
<summary>Click to expand main.py (FULL CODE)</summary>

```python
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging
from config import UPSTOX_API_KEY, UPSTOX_API_TOKEN, UPSTOX_BASE_URL, INTERNAL_API_KEY
from models import OrderRequest, OrderResponse, AccountInfo, MarketFeedResponse

app = FastAPI(
    title="Upstox Trading API",
    description="Production-ready API for Upstox trading with WebSocket and Webhook support",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)

def upstox_headers():
    return {
        "Authorization": f"Bearer {UPSTOX_API_TOKEN}",
        "Api-Version": "2.0",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@app.get("/")
async def root():
    return {
        "status": "active",
        "message": "Upstox Trading API",
        "docs": "/docs"
    }

@app.get("/api/v1/account/profile", response_model=AccountInfo, dependencies=[Depends(verify_api_key)])
async def get_account_profile():
    url = f"{UPSTOX_BASE_URL}/user/profile"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=upstox_headers())
        if r.status_code == 200:
            return r.json()
        raise HTTPException(status_code=r.status_code, detail=r.text)

@app.post("/api/v1/orders/place", response_model=OrderResponse, dependencies=[Depends(verify_api_key)])
async def place_order(order: OrderRequest):
    url = f"{UPSTOX_BASE_URL}/order/place"
    payload = {
        "quantity": order.quantity,
        "product": order.product,
        "validity": order.validity,
        "price": order.price,
        "instrument_token": order.symbol,
        "order_type": order.order_type,
        "transaction_type": order.transaction_type
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, headers=upstox_headers(), json=payload)
        if r.status_code in (200, 201):
            return r.json()
        raise HTTPException(status_code=r.status_code, detail=r.text)

@app.get("/api/v1/market/quote", response_model=MarketFeedResponse, dependencies=[Depends(verify_api_key)])
async def get_market_quote(symbol: str = Query(..., example="NSE_EQ|INE155A01022")):
    url = f"{UPSTOX_BASE_URL}/market-quote/quotes"
    params = {"symbols": symbol}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=upstox_headers(), params=params)
        if r.status_code == 200:
            return r.json()
        raise HTTPException(status_code=r.status_code, detail=r.text)
```
</details>

---

## 📄 **Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📄 **docker-compose.yml**

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

---

## 🚀 Run the Application

### Local Development
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

### Docker
```bash
docker-compose up -d
```

### Access Swagger UI
```
http://localhost:8000/docs
```

---

## 📊 Usage Examples

### Place an Order
```python
import requests

url = "http://localhost:8000/api/v1/orders/place"
headers = {"x-api-key": "your_internal_api_key"}
data = {
    "symbol": "NSE_EQ|INE155A01022",
    "quantity": 1,
    "order_type": "MARKET",
    "side": "BUY",
    "product": "D",
    "transaction_type": "BUY"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Get Account Info
```bash
curl -H "x-api-key: your_key" http://localhost:8000/api/v1/account/profile
```

---

## 📝 Additional Files Needed

For full functionality, download complete files from:

**Repository:** https://github.com/nageswar441/upstox-trading-api

### Full File List:
1. ✅ `requirements.txt` (created)
2. ⬜ `config.py`  
3. ⬜ `models.py`
4. ⬜ `main.py` (full version with all endpoints)
5. ⬜ `websocket_handler.py` (for real-time data)
6. ⬜ `webhook_handler.py` (for order updates)
7. ⬜ `.env.example`
8. ⬜ `.gitignore` (created by GitHub)
9. ⬜ `Dockerfile`
10. ⬜ `docker-compose.yml`

---

## 🔐 Security Notes

- Never commit `.env` file
- Use strong random keys for INTERNAL_API_KEY
- Enable HTTPS in production  
- Rotate API tokens regularly

---

## 📧 Support

- **Repository:** https://github.com/nageswar441/upstox-trading-api
- **Issues:** https://github.com/nageswar441/upstox-trading-api/issues
- **Upstox API Docs:** https://upstox.com/developer/api-documentation

---

## ⚠️ Disclaimer

**This software is for educational purposes only. Trading involves substantial risk. Use at your own risk.**

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file

---

**Made with ❤️ for Indian Traders | ⭐ Star this repo if helpful!**
