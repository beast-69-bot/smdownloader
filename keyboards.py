from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import SUPPORT_LINK, UPDATE_CHANNEL

# ─────────────────────────────────────────
#  🏠 MAIN MENUS
# ─────────────────────────────────────────
def main_menu_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 How to Use", callback_data="menu_howto"),
            InlineKeyboardButton("🌐 Supported Sites", callback_data="menu_sites"),
        ],
        [
            InlineKeyboardButton("📊 My Stats", callback_data="menu_mystats"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("💬 Support", url=SUPPORT_LINK),
            InlineKeyboardButton("📢 Updates", url=UPDATE_CHANNEL),
        ],
        [
            InlineKeyboardButton("ℹ️ About Bot", callback_data="menu_about"),
        ]
    ])

def back_kb(target="start"):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Back", callback_data=f"menu_{target}")
    ]])

# ─────────────────────────────────────────
#  📥 QUALITY SELECTION
# ─────────────────────────────────────────
def quality_kb(formats, url_hash, source_url=None):
    buttons = []

    if formats:
        row = []
        for i, fmt in enumerate(formats[:8]):
            label = f"🎬 {fmt['quality']}"
            if fmt.get("size") and fmt["size"] != "?MB":
                label += f" ({fmt['size']})"
            row.append(InlineKeyboardButton(
                label,
                callback_data=f"dl|{url_hash}|{fmt['format_id']}|video"
            ))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        buttons.append([
            InlineKeyboardButton("🔝 Best Quality", callback_data=f"dl|{url_hash}|best|video"),
            InlineKeyboardButton("📱 720p", callback_data=f"dl|{url_hash}|720p|video"),
        ])
        buttons.append([
            InlineKeyboardButton("📉 480p", callback_data=f"dl|{url_hash}|480p|video"),
            InlineKeyboardButton("📉 360p", callback_data=f"dl|{url_hash}|360p|video"),
        ])

    buttons.append([
        InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data=f"dl|{url_hash}|audio|audio")
    ])
    buttons.append([
        InlineKeyboardButton("🖼️ Thumbnail Only", callback_data=f"dl|{url_hash}|thumb|thumb"),
    ])
    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        InlineKeyboardButton("🔗 Open URL", url=source_url or SUPPORT_LINK),
    ])
    return InlineKeyboardMarkup(buttons)

# ─────────────────────────────────────────
#  🔧 ADMIN KEYBOARDS
# ─────────────────────────────────────────
def admin_main_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Full Stats", callback_data="adm_stats"),
            InlineKeyboardButton("👥 Users", callback_data="adm_users"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
            InlineKeyboardButton("📋 Platform Stats", callback_data="adm_platforms"),
        ],
        [
            InlineKeyboardButton("🔧 Maintenance", callback_data="adm_maintenance"),
            InlineKeyboardButton("🤖 Bot ON/OFF", callback_data="adm_toggle"),
        ],
        [
            InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban_prompt"),
            InlineKeyboardButton("✅ Unban User", callback_data="adm_unban_prompt"),
        ],
        [
            InlineKeyboardButton("🔍 Search User", callback_data="adm_search"),
            InlineKeyboardButton("🏆 Top Users", callback_data="adm_topusers"),
        ],
        [
            InlineKeyboardButton("📝 Feedbacks", callback_data="adm_feedbacks"),
            InlineKeyboardButton("🗑️ Clear Cache", callback_data="adm_clearcache"),
        ],
        [
            InlineKeyboardButton("📣 Pin Message", callback_data="adm_pin"),
            InlineKeyboardButton("🔗 Bot Link", callback_data="adm_botlink"),
        ],
    ])

def admin_back_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")
    ]])

# ─────────────────────────────────────────
#  ✅ FORCE SUBSCRIBE
# ─────────────────────────────────────────
def force_sub_kb(channel):
    ch = channel.lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{ch}")],
        [InlineKeyboardButton("✅ I've Joined!", callback_data="check_sub")]
    ])

# ─────────────────────────────────────────
#  ⭐ FEEDBACK & RATING
# ─────────────────────────────────────────
def feedback_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Rate Bot", callback_data="fb_rate"),
            InlineKeyboardButton("💬 Send Feedback", callback_data="fb_send"),
        ],
        [
            InlineKeyboardButton("🐛 Report Bug", callback_data="fb_bug"),
            InlineKeyboardButton("💡 Suggest Feature", callback_data="fb_suggest"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_start")]
    ])

def rating_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐", callback_data="rate_1"),
        InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
        InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
        InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5"),
    ]])

# ─────────────────────────────────────────
#  📱 REPLY KEYBOARD
# ─────────────────────────────────────────
def reply_main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📥 Download"), KeyboardButton("📊 Stats")],
        [KeyboardButton("❓ Help"), KeyboardButton("⚙️ Settings")],
    ], resize_keyboard=True, one_time_keyboard=False)
