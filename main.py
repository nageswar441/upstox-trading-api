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
