from config import BOT_NAME, DEVELOPER, SUPPORT_LINK, SUPPORTED_PLATFORMS

# ─────────────────────────────────────────
def START_MSG(user_name, total_users):
    return f"""
╔══════════════════════════════╗
  🎬 **{BOT_NAME}**
╚══════════════════════════════╝

👋 Salam **{user_name}**!

Main aapka personal **Social Media Downloader** hoon!
Koi bhi video/audio link bhejo — main download kar dunga! ⚡

━━━━━━━━━━━━━━━━━━━━
**⚡ Features:**
✅ Multiple Video Qualities  
✅ Audio/MP3 Extract  
✅ Auto Thumbnail  
✅ No Watermark (TikTok)  
✅ Fast Download  
✅ 100+ Supported Sites  

━━━━━━━━━━━━━━━━━━━━
👇 **Bas koi link paste karo aur bhejo!**

👥 **{total_users:,}** users already use kar rahe hain!
"""

HELP_MSG = """
📖 **Help & Guide**

━━━━━━━━━━━━━━━━━━━━
**📥 Download kaise karein:**

1️⃣ Kisi bhi supported site ka link copy karo
2️⃣ Bot mein paste karke bhejo
3️⃣ Quality select karo (360p to 4K)
4️⃣ Wait karo — video aa jayegi!

━━━━━━━━━━━━━━━━━━━━
**🎵 Audio Download:**
→ Quality selection mein "Audio Only" button dabao
→ MP3 format mein milega

━━━━━━━━━━━━━━━━━━━━
**📌 Tips:**
• Private videos download nahi hote
• 50MB se badi files split ho sakti hain
• Best quality = highest available quality
• 720p = fast aur good quality

━━━━━━━━━━━━━━━━━━━━
**📋 Commands:**
/start — Bot start
/help — Yeh message
/stats — Tumhare download stats
/about — Bot ke baare mein
/feedback — Feedback do
/ping — Bot online hai?
/cancel — Current download cancel karo
"""

def STATS_MSG(user):
    from datetime import datetime
    joined = user["joined_at"][:10] if user["joined_at"] else "Unknown"
    last = user["last_used"][:10] if user["last_used"] else "Unknown"
    premium = "✅ Premium" if user["is_premium"] else "🆓 Free"
    return f"""
📊 **Your Statistics**

━━━━━━━━━━━━━━━━━━━━
👤 **Name:** {user['full_name']}
🆔 **ID:** `{user['user_id']}`
👤 **Username:** @{user['username'] or 'N/A'}
📅 **Joined:** {joined}
🕐 **Last Used:** {last}
━━━━━━━━━━━━━━━━━━━━
📥 **Total Downloads:** {user['total_downloads']}
📆 **Today's Downloads:** {user['today_downloads']}
⭐ **Account Type:** {premium}
━━━━━━━━━━━━━━━━━━━━
"""

ABOUT_MSG = f"""
ℹ️ **About {BOT_NAME}**

━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {BOT_NAME}
👨‍💻 **Developer:** {DEVELOPER}
📡 **API:** Luffy API + yt-dlp
🔧 **Version:** 2.0.0
📅 **Updated:** 2025

━━━━━━━━━━━━━━━━━━━━
**Tech Stack:**
• Python 3.11+
• python-telegram-bot 20.x
• yt-dlp
• SQLite Database
• Luffy Downloader API

━━━━━━━━━━━━━━━━━━━━
**💡 Features:**
• 100+ sites support
• Multiple quality options
• Audio extraction (MP3)
• Auto thumbnail
• Inline mode
• Admin panel
• Broadcast system
• User statistics

💬 Support: {SUPPORT_LINK}
"""

def SITES_MSG():
    msg = "🌐 **Supported Platforms**\n\n━━━━━━━━━━━━━━━━━━━━\n"
    for emoji, name, desc in SUPPORTED_PLATFORMS:
        msg += f"{emoji} **{name}** — {desc}\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━\n_...aur 100+ sites via yt-dlp!_"
    return msg

def VIDEO_INFO_MSG(title, uploader, duration, views, platform, thumb=False):
    dur_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "?"
    views_str = f"{int(views):,}" if views else "?"
    return f"""
🎬 **{title[:60]}{'...' if len(title)>60 else ''}**

━━━━━━━━━━━━━━━━━━━━
👤 **Uploader:** {uploader or 'Unknown'}
⏱️ **Duration:** {dur_str}
👁️ **Views:** {views_str}
🌐 **Platform:** {platform.title()}
{'🖼️ **Thumbnail:** ✅' if thumb else ''}
━━━━━━━━━━━━━━━━━━━━

👇 **Quality choose karo:**
"""

def DOWNLOAD_DONE_MSG(title, platform, quality, size_mb, bot_username):
    return f"""
✅ **Download Complete!**

━━━━━━━━━━━━━━━━━━━━
📹 **{title[:50]}{'...' if len(title)>50 else ''}**
🌐 **Platform:** {platform.title()}
🎬 **Quality:** {quality}
📦 **Size:** {size_mb:.1f} MB
━━━━━━━━━━━━━━━━━━━━
🤖 @{bot_username}
"""

MAINTENANCE_MSG = """
🔧 **Bot Maintenance Mode**

Bot abhi maintenance pe hai.
Thodi der baad wapas try karo! 🙏

Updates ke liye channel join karo.
"""

FORCE_SUB_MSG = """
⚠️ **Bot Use Karne Ke Liye**

Pehle hamara channel join karo,
phir bot use kar sakte ho! 🙏
"""

def ADMIN_STATS_MSG(stats):
    return f"""
🔧 **Admin Dashboard**

━━━━━━━━━━━━━━━━━━━━
👥 **Total Users:** `{stats['total_users']:,}`
🟢 **Active Today:** `{stats['active_today']:,}`
🚫 **Banned Users:** `{stats['banned_users']}`
━━━━━━━━━━━━━━━━━━━━
📥 **Total Downloads:** `{stats['total_downloads']:,}`
📆 **Today Downloads:** `{stats['today_downloads']:,}`
🏆 **Total Served:** `{stats['total_served']}`
━━━━━━━━━━━━━━━━━━━━
📊 **Top Platform:** {stats['top_platform'].title()} ({stats['top_platform_count']:,})
━━━━━━━━━━━━━━━━━━━━
"""
