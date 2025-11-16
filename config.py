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
