import os
from dotenv import load_dotenv
from typing import List

# Load environment variables
load_dotenv()


def get_required_env(key: str) -> str:
    """
    Get required environment variable with validation
    
    Args:
        key: Environment variable name
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If environment variable is not set
    """
    value = os.getenv(key)
    if not value:
        raise ValueError(f"❌ Missing required environment variable: {key}")
    return value


def get_optional_env(key: str, default: str = "") -> str:
    """Get optional environment variable with default value"""
    return os.getenv(key, default)


def get_list_env(key: str, default: List[str] = None) -> List[str]:
    """
    Get environment variable as list (comma-separated)
    
    Args:
        key: Environment variable name
        default: Default list if not set
        
    Returns:
        List of values
    """
    if default is None:
        default = []
    value = os.getenv(key)
    if not value:
        return default
    return [item.strip() for item in value.split(',') if item.strip()]


# Upstox API Configuration (Required)
try:
    UPSTOX_API_KEY = get_required_env("UPSTOX_API_KEY")
    UPSTOX_API_SECRET = get_required_env("UPSTOX_API_SECRET")
    UPSTOX_API_TOKEN = get_required_env("UPSTOX_API_TOKEN")
    print("✅ Upstox credentials loaded successfully")
except ValueError as e:
    print(f"⚠️  {str(e)}")
    print("Please ensure all required environment variables are set in .env file")
    print("Run: python profile_manager.py dev")
    raise

# API URLs
UPSTOX_BASE_URL = get_optional_env("UPSTOX_BASE_URL", "https://api.upstox.com/v2")
UPSTOX_WEBSOCKET_URL = get_optional_env(
    "UPSTOX_WEBSOCKET_URL",
    "wss://api.upstox.com/v2/feed/market-data-feed"
)

# Internal API Configuration (Required)
try:
    INTERNAL_API_KEY = get_required_env("INTERNAL_API_KEY")
    print("✅ Internal API key loaded")
except ValueError:
    print("⚠️  INTERNAL_API_KEY not set. Generating a random key...")
    import secrets
    INTERNAL_API_KEY = secrets.token_urlsafe(32)
    print(f"🔑 Generated INTERNAL_API_KEY: {INTERNAL_API_KEY}")
    print("⚠️  Save this key in your .env file for production use!")

# Webhook Configuration (Optional)
WEBHOOK_SECRET = get_optional_env("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    print("⚠️  WEBHOOK_SECRET not set. Webhook signature verification will be disabled.")

# CORS Configuration
ALLOWED_ORIGINS = get_list_env(
    "ALLOWED_ORIGINS",
    ["http://localhost:3000", "http://localhost:8000"]
)

# Validate CORS configuration
if "*" in ALLOWED_ORIGINS:
    print("⚠️  WARNING: CORS is set to allow all origins (*). This is a security risk!")
    print("   For production, specify exact origins in ALLOWED_ORIGINS environment variable")

# JWT Configuration (Required for Auth)
try:
    JWT_SECRET_KEY = get_required_env("JWT_SECRET_KEY")
    JWT_ALGORITHM = get_optional_env("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(get_optional_env("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    print("✅ JWT configuration loaded")
except ValueError:
    print("⚠️  JWT_SECRET_KEY not set. Generating a random key...")
    import secrets
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    print(f"🔑 Generated JWT_SECRET_KEY: {JWT_SECRET_KEY}")
    print("⚠️  Save this key in your .env file for production use!")

# OAuth Configuration
UPSTOX_REDIRECT_URI = get_optional_env("UPSTOX_REDIRECT_URI", "http://localhost:8000/api/v1/auth/callback")

# Environment
ENVIRONMENT = get_optional_env("APP_ENV", "development")

class Settings:
    """
    Application Settings Class
    Aggregates all configuration variables for easy access
    """
    # Upstox API
    UPSTOX_API_KEY = UPSTOX_API_KEY
    UPSTOX_API_SECRET = UPSTOX_API_SECRET
    UPSTOX_API_TOKEN = UPSTOX_API_TOKEN
    UPSTOX_BASE_URL = UPSTOX_BASE_URL
    UPSTOX_WEBSOCKET_URL = UPSTOX_WEBSOCKET_URL
    UPSTOX_REDIRECT_URI = UPSTOX_REDIRECT_URI
    
    # Internal Security
    INTERNAL_API_KEY = INTERNAL_API_KEY
    WEBHOOK_SECRET = WEBHOOK_SECRET
    ALLOWED_ORIGINS = ALLOWED_ORIGINS
    
    # JWT Auth
    JWT_SECRET_KEY = JWT_SECRET_KEY
    JWT_ALGORITHM = JWT_ALGORITHM
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    
    # App Info
    ENVIRONMENT = ENVIRONMENT
    PROJECT_NAME = "Upstox Trading API"
    VERSION = "2.1.0"

# Instantiate settings
settings = Settings()

print(f"✅ Configuration loaded. CORS allowed origins: {ALLOWED_ORIGINS}")
print(f"✅ Environment: {ENVIRONMENT}")
