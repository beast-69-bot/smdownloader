# ============================================================
#   ⚙️  CONFIG — Yahan apni values dalo
# ============================================================

BOT_TOKEN    = "YOUR_BOT_TOKEN_HERE"       # @BotFather se lo
ADMIN_IDS    = [123456789]                 # Tumhara Telegram User ID
LOG_CHANNEL  = ""                          # "-100xxxxxxxxxx" ya "" for disable
CHANNEL_ID   = ""                          # "@yourchannel" force subscribe, "" disable

# Bot Info
BOT_NAME     = "SM Downloader"
BOT_USERNAME = "your_bot"
SUPPORT_LINK = "https://t.me/your_support"
UPDATE_CHANNEL = "https://t.me/your_channel"
DEVELOPER    = "@YourUsername"

# Download Settings
MAX_FILE_MB  = 50                          # Telegram free limit 50MB
DOWNLOAD_DIR = "downloads"
DB_FILE      = "bot_data.db"
MAX_RETRIES  = 3

# Rate Limiting
MAX_DAILY_DOWNLOADS = 20                   # Per user daily limit (0 = unlimited)
COOLDOWN_SECONDS = 5                       # Between downloads

# Luffy API
LUFFY_API_KEY = "luffy"
LUFFY_API_URL = "https://luffy-api.is-dev.org/api/down"

# Supported Platforms (for display)
SUPPORTED_PLATFORMS = [
    ("📸", "Instagram",    "Reels, Posts, Stories"),
    ("▶️", "YouTube",      "Videos, Shorts, Playlists"),
    ("🎵", "TikTok",       "Videos (No Watermark)"),
    ("🐦", "Twitter/X",    "Videos, GIFs"),
    ("📘", "Facebook",     "Videos, Reels"),
    ("🎶", "Spotify",      "Tracks (via yt-dlp)"),
    ("🔊", "SoundCloud",   "Tracks, Playlists"),
    ("🎮", "Twitch",       "Clips"),
    ("📌", "Pinterest",    "Videos, Images"),
    ("🟠", "Reddit",       "Videos, GIFs"),
    ("📺", "Bilibili",     "Videos"),
    ("🎬", "Dailymotion",  "Videos"),
    ("🎞️", "Vimeo",        "Videos"),
    ("🐙", "Tumblr",       "Videos"),
    ("📹", "Streamable",   "Videos"),
    ("🌐", "Others",       "100+ Sites via yt-dlp"),
]
