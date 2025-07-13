import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

# CoinGecko API Configuration
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Database Configuration
DATABASE_PATH = "bot_database.db"

# Monitoring Configuration
CHECK_INTERVAL = 60  # 1 minute in seconds
PRICE_CHECK_DELAY = 10  # seconds between API calls to avoid rate limiting

# Dark theme emojis and styling
DARK_EMOJIS = {
    "bot": "🕶️",
    "alert": "🚨",
    "coin": "💰",
    "up": "📈",
    "down": "📉",
    "add": "➕",
    "delete": "❌",
    "list": "📋",
    "skull": "💀",
    "bell": "🛎️",
    "shadow": "👻",
    "warning": "⚠️",
    "success": "✅",
    "error": "💥"
} 