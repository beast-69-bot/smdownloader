# 🤖 Social Media Downloader Bot v2.0

Telegram bot for downloading videos from 100+ social media platforms.

## ⚡ Features

### User Features
- 📥 Multi-quality video download (360p to 4K)
- 🎵 Audio/MP3 extraction
- 🖼️ Auto thumbnail display
- 🌐 100+ supported sites
- 📊 Personal download statistics
- 🔗 Referral system
- 💬 Feedback system
- 🔍 Inline mode support

### Admin Features
- 📊 Full dashboard with stats
- 📢 Broadcast to all users
- 🚫 Ban/Unban users
- 🔧 Maintenance mode on/off
- 🤖 Bot on/off toggle
- 📋 Platform download stats
- 👥 User management
- 🔍 User search
- 📝 View user feedbacks
- 📩 Send message to specific user
- ⚙️ Set daily download limits
- 🎨 Custom welcome message
- 🗑️ Clear download cache

## 📋 Commands

### User Commands
| Command | Description |
|---------|-------------|
| /start | Bot start karo |
| /help | Help guide |
| /stats | Tumhare download stats |
| /about | Bot ke baare mein |
| /ping | Bot online check |
| /myid | Apna Telegram ID |
| /refer | Referral link |
| /feedback | Feedback do |
| /cancel | Cancel karo |

### Admin Commands
| Command | Description |
|---------|-------------|
| /admin | Admin panel |
| /broadcast <msg> | Sab ko message bhejo |
| /ban <id> [reason] | User ban karo |
| /unban <id> | User unban karo |
| /adminstats | Detailed stats |
| /send <id> <msg> | Specific user ko message |
| /maintenance | Maintenance toggle |
| /setlimit <n> | Daily download limit |
| /setwelcome <msg> | Welcome message set |
| /users | Top users list |
| /searchuser <query> | User search |

## 🚀 Setup (Termux)

```bash
# 1. Setup run karo
bash setup.sh

# 2. Config edit karo
nano config.py
# BOT_TOKEN = "your_token"
# ADMIN_IDS = [your_id]

# 3. Bot chalao
python bot.py
```

## 🌐 Supported Platforms
- Instagram (Reels, Posts)
- YouTube (Videos, Shorts)
- TikTok (No Watermark)
- Twitter/X
- Facebook
- SoundCloud
- Spotify (via yt-dlp)
- Reddit, Pinterest, Twitch
- Bilibili, Dailymotion, Vimeo
- ...100+ more!

## 📁 File Structure
```
smbot/
├── bot.py          # Main bot file
├── config.py       # Configuration
├── database.py     # SQLite database
├── downloader.py   # Download logic
├── keyboards.py    # Telegram keyboards
├── messages.py     # Text messages
├── cache.py        # Session/cache management
├── requirements.txt
├── setup.sh        # Auto setup script
└── README.md
```
