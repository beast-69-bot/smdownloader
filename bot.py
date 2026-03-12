#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║   🤖 Social Media Downloader Bot v2.0           ║
║   Powered by Luffy API + yt-dlp                 ║
║   Features: Multi-quality, Audio, Admin Panel   ║
╚══════════════════════════════════════════════════╝
"""

import os
import asyncio
import logging
import time
from pathlib import Path
from datetime import datetime

from telegram import (
    Update, BotCommand, InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, InlineQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

import config
from database import (
    init_db, register_user, get_user, is_banned, ban_user, unban_user,
    get_setting, set_setting, log_download, get_stats, get_all_user_ids,
    get_today_downloads, get_platform_stats, get_top_users,
    get_recent_feedbacks, add_feedback, search_user
)
from downloader import (
    detect_platform, is_url, luffy_fetch,
    ytdlp_info, ytdlp_download, download_file, get_cookie_file,
    file_size_mb, cleanup_old_files
)
from keyboards import (
    main_menu_kb, quality_kb, admin_main_kb, admin_back_kb,
    force_sub_kb, feedback_kb, rating_kb, back_kb, cookies_platform_kb
)
from messages import (
    START_MSG, HELP_MSG, STATS_MSG, ABOUT_MSG, SITES_MSG,
    VIDEO_INFO_MSG, DOWNLOAD_DONE_MSG, MAINTENANCE_MSG,
    FORCE_SUB_MSG, ADMIN_STATS_MSG, BOT_INACTIVE_MSG
)
from cache import (
    store_url, get_url, clear_cache, set_user_state, get_user_state,
    clear_user_state, check_cooldown, set_cooldown
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

Path(config.DOWNLOAD_DIR).mkdir(exist_ok=True)
Path(config.COOKIES_DIR).mkdir(exist_ok=True)

COOKIE_PLATFORM_NAMES = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "twitter": "Twitter/X",
    "facebook": "Facebook",
    "reddit": "Reddit",
}

# ══════════════════════════════════════════
#   MIDDLEWARE
# ══════════════════════════════════════════
async def middleware_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns True if user can proceed"""
    user = update.effective_user
    if not user:
        return False

    is_new = register_user(user)

    if is_new and config.LOG_CHANNEL:
        try:
            await context.bot.send_message(
                config.LOG_CHANNEL,
                f"👤 **New User!**\nName: {user.full_name}\nID: `{user.id}`\n@{user.username or 'N/A'}",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

    if is_banned(user.id):
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        if msg:
            u = get_user(user.id)
            reason = u["ban_reason"] if u else ""
            await msg.reply_text(
                f"🚫 **Tumhara account ban hai!**\n\nReason: {reason or 'N/A'}\n\nSupport: {config.SUPPORT_LINK}",
                parse_mode=ParseMode.MARKDOWN
            )
        return False

    if get_setting("bot_active") != "1" and user.id not in config.ADMIN_IDS:
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        if msg:
            await msg.reply_text(BOT_INACTIVE_MSG, parse_mode=ParseMode.MARKDOWN)
        return False

    if get_setting("maintenance") == "1" and user.id not in config.ADMIN_IDS:
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        if msg:
            await msg.reply_text(MAINTENANCE_MSG, parse_mode=ParseMode.MARKDOWN)
        return False

    if config.CHANNEL_ID and get_setting("force_sub") == "1":
        try:
            member = await context.bot.get_chat_member(config.CHANNEL_ID, user.id)
            if member.status in ["left", "kicked"]:
                msg = update.message or (update.callback_query.message if update.callback_query else None)
                if msg:
                    await msg.reply_text(
                        FORCE_SUB_MSG,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=force_sub_kb(config.CHANNEL_ID)
                    )
                return False
        except:
            pass

    return True

# ══════════════════════════════════════════
#   /start
# ══════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return

    user = update.effective_user
    db_user = get_user(user.id)
    stats = get_stats()

    # Check referral
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != user.id:
                from database import db_exec
                db_exec("UPDATE users SET referral_count=referral_count+1 WHERE user_id=?", (ref_id,))
        except:
            pass

    msg = START_MSG(user.first_name, stats["total_users"])
    custom_welcome = get_setting("welcome_msg")
    if custom_welcome:
        msg = custom_welcome.replace("{name}", user.first_name)

    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_kb()
    )

# ══════════════════════════════════════════
#   /help
# ══════════════════════════════════════════
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    await update.message.reply_text(HELP_MSG, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("start"))

# ══════════════════════════════════════════
#   /stats
# ══════════════════════════════════════════
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    user = update.effective_user
    db_user = get_user(user.id)
    if db_user:
        await update.message.reply_text(
            STATS_MSG(dict(db_user)),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("start")
        )

# ══════════════════════════════════════════
#   /about
# ══════════════════════════════════════════
async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    await update.message.reply_text(ABOUT_MSG, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("start"))

# ══════════════════════════════════════════
#   /ping
# ══════════════════════════════════════════
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    start_time = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    latency = (time.time() - start_time) * 1000
    await msg.edit_text(f"🏓 **Pong!**\n⚡ Latency: `{latency:.1f}ms`", parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════
#   /feedback
# ══════════════════════════════════════════
async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    await update.message.reply_text(
        "💬 **Feedback**\n\nKya improve karein? Koi bug hai? Batao!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=feedback_kb()
    )

# ══════════════════════════════════════════
#   /cancel
# ══════════════════════════════════════════
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    clear_user_state(update.effective_user.id)
    await update.message.reply_text("❌ Cancelled.", parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════
#   /myid
# ══════════════════════════════════════════
async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 **Your Info**\n\n"
        f"ID: `{user.id}`\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"Language: {user.language_code or 'N/A'}",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════
#   /refer
# ══════════════════════════════════════════
async def cmd_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return
    user = update.effective_user
    bot_user = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_user.username}?start={user.id}"
    db_user = get_user(user.id)
    count = db_user["referral_count"] if db_user else 0
    await update.message.reply_text(
        f"🔗 **Your Referral Link**\n\n"
        f"`{ref_link}`\n\n"
        f"👥 Total Referrals: **{count}**\n\n"
        f"Is link se jo log bot join karein, wo tumhare referrals honge!",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════
#   ADMIN COMMANDS
# ══════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ Admin only!")
        return
    stats = get_stats()
    await update.message.reply_text(
        ADMIN_STATS_MSG(stats),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_main_kb()
    )

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg_text = " ".join(context.args)
    await do_broadcast(update, context, msg_text)

async def do_broadcast(update, context, msg_text):
    users = get_all_user_ids()
    total = len(users)
    sent = failed = 0
    status = await update.message.reply_text(f"📢 Broadcasting to {total} users...")

    for i, uid in enumerate(users):
        try:
            await context.bot.send_message(
                uid,
                f"📢 **Announcement**\n\n{msg_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
        except TelegramError:
            failed += 1
        if i % 20 == 0:
            await asyncio.sleep(1)

    await status.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"✔️ Sent: {sent}\n❌ Failed: {failed}\n📊 Total: {total}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id> [reason]")
        return
    uid = int(context.args[0])
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    ban_user(uid, reason)
    await update.message.reply_text(f"🚫 User `{uid}` banned!\nReason: {reason or 'N/A'}", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(uid, f"🚫 Aapka account ban kar diya gaya hai.\nReason: {reason or 'N/A'}")
    except:
        pass

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    uid = int(context.args[0])
    unban_user(uid)
    await update.message.reply_text(f"✅ User `{uid}` unbanned!", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(uid, "✅ Aapka account unban kar diya gaya hai!")
    except:
        pass

async def cmd_stats_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    stats = get_stats()
    platforms = get_platform_stats()
    plat_str = "\n".join([f"  • {r['platform'].title()}: {r['cnt']}" for r in platforms[:8]])
    await update.message.reply_text(
        ADMIN_STATS_MSG(stats) + f"\n**Platform Breakdown:**\n{plat_str}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message to specific user: /send <user_id> <message>"""
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /send <user_id> <message>")
        return
    uid = int(context.args[0])
    msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(uid, f"📩 **Message from Admin:**\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text(f"✅ Sent to {uid}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def cmd_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    current = get_setting("maintenance")
    new = "0" if current == "1" else "1"
    set_setting("maintenance", new)
    status = "ON 🔧" if new == "1" else "OFF ✅"
    await update.message.reply_text(f"🔧 Maintenance mode: **{status}**", parse_mode=ParseMode.MARKDOWN)

async def cmd_setlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text(f"Current limit: {get_setting('max_daily', '20')}/day\nUsage: /setlimit <number>")
        return
    set_setting("max_daily", context.args[0])
    await update.message.reply_text(f"✅ Daily limit set to: {context.args[0]}")

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /setwelcome <message>\nUse {name} for user's name")
        return
    msg = " ".join(context.args)
    set_setting("welcome_msg", msg)
    await update.message.reply_text(f"✅ Welcome message updated!\n\nPreview:\n{msg.replace('{name}', 'User')}")

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    top = get_top_users(10)
    msg = "🏆 **Top 10 Users:**\n\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. {u['full_name']} (`{u['user_id']}`) — {u['total_downloads']} downloads\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /searchuser <id or username>")
        return
    results = search_user(" ".join(context.args))
    if not results:
        await update.message.reply_text("❌ User not found!")
        return
    await update.message.reply_text(format_user_search_results(results), parse_mode=ParseMode.MARKDOWN)


async def cmd_addcookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    await update.message.reply_text(
        "🍪 **Add Cookies**\n\nKis platform ki cookies add karni hain?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cookies_platform_kb()
    )


def format_user_search_results(results):
    msg = ""
    for u in results[:5]:
        msg += (
            f"👤 **{u['full_name']}**\n"
            f"🆔 ID: `{u['user_id']}`\n"
            f"👤 @{u['username'] or 'N/A'}\n"
            f"📥 Downloads: {u['total_downloads']}\n"
            f"🚫 Banned: {'Yes' if u['is_banned'] else 'No'}\n"
            f"📅 Joined: {str(u['joined_at'])[:10]}\n\n"
        )
    return msg.rstrip()

# ══════════════════════════════════════════
#   MAIN URL HANDLER
# ══════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return

    user = update.effective_user
    text = update.message.text.strip()

    # Check user state (waiting for feedback/broadcast text)
    state = get_user_state(user.id)
    if state:
        s = state["state"]
        if s == "waiting_feedback":
            add_feedback(user.id, text)
            clear_user_state(user.id)
            await update.message.reply_text("✅ **Feedback mila! Shukriya!** 🙏", parse_mode=ParseMode.MARKDOWN)
            if config.LOG_CHANNEL:
                try:
                    await context.bot.send_message(
                        config.LOG_CHANNEL,
                        f"💬 **New Feedback**\nFrom: {user.full_name} (`{user.id}`)\n\n{text}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            return
        elif s == "waiting_broadcast" and user.id in config.ADMIN_IDS:
            clear_user_state(user.id)
            await do_broadcast(update, context, text)
            return
        elif s == "waiting_ban" and user.id in config.ADMIN_IDS:
            clear_user_state(user.id)
            try:
                uid = int(text.strip())
                ban_user(uid)
                await update.message.reply_text(f"🚫 User `{uid}` banned!", parse_mode=ParseMode.MARKDOWN)
            except:
                await update.message.reply_text("❌ Invalid user ID!")
            return
        elif s == "waiting_unban" and user.id in config.ADMIN_IDS:
            clear_user_state(user.id)
            try:
                uid = int(text.strip())
                unban_user(uid)
                await update.message.reply_text(f"✅ User `{uid}` unbanned!", parse_mode=ParseMode.MARKDOWN)
            except:
                await update.message.reply_text("❌ Invalid user ID!")
            return
        elif s == "waiting_send" and user.id in config.ADMIN_IDS:
            data = state.get("data", {})
            uid = data.get("target_uid")
            clear_user_state(user.id)
            if uid:
                try:
                    await context.bot.send_message(uid, f"📩 **Message from Admin:**\n\n{text}", parse_mode=ParseMode.MARKDOWN)
                    await update.message.reply_text(f"✅ Sent to {uid}")
                except Exception as e:
                    await update.message.reply_text(f"❌ Failed: {e}")
            return
        elif s == "waiting_search_admin" and user.id in config.ADMIN_IDS:
            clear_user_state(user.id)
            results = search_user(text)
            if not results:
                await update.message.reply_text("❌ User not found!")
                return
            await update.message.reply_text(
                format_user_search_results(results),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif s == "waiting_cookie_file" and user.id in config.ADMIN_IDS:
            platform = state.get("data", {}).get("platform")
            platform_name = COOKIE_PLATFORM_NAMES.get(platform, platform or "Selected platform")
            await update.message.reply_text(
                f"📎 **{platform_name} cookies file bhejo.**\n\nDocument upload karo, text nahi.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    if not is_url(text):
        await update.message.reply_text(
            "❓ Yeh URL nahi lag raha.\n\nKoi social media video link bhejo!",
            reply_markup=main_menu_kb()
        )
        return

    # Cooldown check
    ok, remaining = check_cooldown(user.id, config.COOLDOWN_SECONDS)
    if not ok:
        await update.message.reply_text(f"⏳ Thoda ruko! `{remaining}s` baad try karo.", parse_mode=ParseMode.MARKDOWN)
        return

    # Daily limit check
    max_daily = int(get_setting("max_daily", "0"))
    if max_daily > 0 and user.id not in config.ADMIN_IDS:
        today_count = get_today_downloads(user.id)
        if today_count >= max_daily:
            await update.message.reply_text(
                f"⚠️ **Daily limit reached!**\nAaj ke liye {max_daily} downloads ho gaye.\nKal dobara try karo! 🙏",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    platform = detect_platform(text)

    status_msg = await update.message.reply_text(
        f"🔍 **Processing...**\n🌐 Platform: `{platform.title()}`\n⏳ Info fetch ho rahi hai...",
        parse_mode=ParseMode.MARKDOWN
    )
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    # Parallel: Luffy API + yt-dlp info
    luffy_task = asyncio.create_task(luffy_fetch(text))
    loop = asyncio.get_event_loop()
    info_task = loop.run_in_executor(None, ytdlp_info, text, platform)

    luffy_data = await luffy_task
    info, formats = await info_task

    if not info and not luffy_data:
        await status_msg.edit_text(
            "❌ **Kuch nahi mila!**\n\n"
            "Possible reasons:\n"
            "• Private account/video\n"
            "• Galat URL\n"
            "• Platform temporarily down\n\n"
            "Dobara try karo ya /help dekho.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    url_hash = store_url(text, info, formats)
    kb = quality_kb(formats, url_hash, text)

    title      = (info or {}).get("title", "Video") or "Video"
    uploader   = (info or {}).get("uploader", "Unknown") or "Unknown"
    duration   = (info or {}).get("duration", 0) or 0
    views      = (info or {}).get("view_count", 0) or 0
    thumb_url  = (info or {}).get("thumbnail")

    caption = VIDEO_INFO_MSG(title, uploader, duration, views, platform, bool(thumb_url))

    try:
        await status_msg.delete()
    except:
        pass

    if thumb_url:
        try:
            await update.message.reply_photo(
                photo=thumb_url,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb
            )
            return
        except Exception as e:
            logger.warning(f"Thumb send failed: {e}")

    await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await middleware_check(update, context):
        return

    user = update.effective_user
    state = get_user_state(user.id)
    document = update.message.document

    if not state or state["state"] != "waiting_cookie_file" or user.id not in config.ADMIN_IDS:
        return

    platform = state.get("data", {}).get("platform")
    if not platform:
        clear_user_state(user.id)
        await update.message.reply_text("❌ Cookie upload session expire ho gaya. /addcookies dobara use karo.")
        return

    status_msg = await update.message.reply_text(
        f"🍪 **{COOKIE_PLATFORM_NAMES.get(platform, platform.title())} cookies save ho rahi hain...**",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        cookie_path = Path(config.COOKIES_DIR) / f"{platform}.txt"
        tg_file = await context.bot.get_file(document.file_id)
        await tg_file.download_to_drive(custom_path=str(cookie_path))
        clear_user_state(user.id)
        await status_msg.edit_text(
            f"✅ **Cookies added!**\n\nPlatform: {COOKIE_PLATFORM_NAMES.get(platform, platform.title())}\nFile: `{cookie_path.name}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Cookie upload error: {e}")
        await status_msg.edit_text(
            f"❌ Cookies save nahi hui: `{str(e)[:120]}`",
            parse_mode=ParseMode.MARKDOWN
        )


# ══════════════════════════════════════════
#   CALLBACK HANDLER
# ══════════════════════════════════════════
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await middleware_check(update, context):
        return
    data = q.data
    user = update.effective_user

    # ── Menu navigation ──
    if data == "menu_start":
        stats = get_stats()
        await q.message.edit_text(
            START_MSG(user.first_name, stats["total_users"]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb()
        )
        return
    if data == "menu_howto":
        await q.message.edit_text(HELP_MSG, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("start"))
        return
    if data == "menu_sites":
        await q.message.edit_text(SITES_MSG(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("start"))
        return
    if data == "menu_about":
        await q.message.edit_text(ABOUT_MSG, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("start"))
        return
    if data == "menu_settings":
        db_user = get_user(user.id)
        u = dict(db_user) if db_user else {}
        await q.message.edit_text(
            f"⚙️ **Settings**\n\n"
            f"👤 Account: `{user.id}`\n"
            f"📥 Downloads today: {u.get('today_downloads', 0)}\n"
            f"📦 Total: {u.get('total_downloads', 0)}\n"
            f"⭐ Type: {'Premium' if u.get('is_premium') else 'Free'}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("start")
        )
        return
    if data == "menu_mystats":
        db_user = get_user(user.id)
        if db_user:
            await q.message.edit_text(
                STATS_MSG(dict(db_user)),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_kb("start")
            )
        return

    # ── Cancel ──
    if data == "cancel":
        try:
            await q.message.delete()
        except:
            await q.message.edit_text("❌ Cancelled.")
        return

    # ── Force subscribe check ──
    if data == "check_sub":
        if config.CHANNEL_ID:
            try:
                member = await context.bot.get_chat_member(config.CHANNEL_ID, user.id)
                if member.status not in ["left", "kicked"]:
                    await q.answer("✅ Verified! Ab link bhejo.", show_alert=True)
                    try:
                        await q.message.delete()
                    except:
                        pass
                else:
                    await q.answer("❌ Abhi join nahi kiya!", show_alert=True)
            except:
                await q.answer("✅ OK! Try karo.", show_alert=True)
        return

    # ── Feedback ──
    if data == "fb_send":
        set_user_state(user.id, "waiting_feedback")
        await q.message.edit_text(
            "💬 **Apna feedback type karo:**\nKoi bhi message bhejo!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    if data == "fb_bug":
        set_user_state(user.id, "waiting_feedback")
        await q.message.edit_text("🐛 **Bug describe karo:**", parse_mode=ParseMode.MARKDOWN)
        return
    if data == "fb_suggest":
        set_user_state(user.id, "waiting_feedback")
        await q.message.edit_text("💡 **Apna suggestion type karo:**", parse_mode=ParseMode.MARKDOWN)
        return
    if data == "fb_rate":
        await q.message.edit_text(
            "⭐ **Bot ko rate karo:**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=rating_kb()
        )
        return
    if data.startswith("rate_"):
        stars = int(data.split("_")[1])
        emoji = "⭐" * stars
        add_feedback(user.id, f"Rating: {stars}/5 {emoji}")
        await q.message.edit_text(f"🙏 **Shukriya!** {emoji}\nTumhara rating mila!", parse_mode=ParseMode.MARKDOWN)
        return

    # ── Admin callbacks ──
    if data.startswith("adm_"):
        if user.id not in config.ADMIN_IDS:
            await q.answer("❌ Admin only!", show_alert=True)
            return
        await handle_admin_callback(q, data, user, context)
        return

    # ── Download ──
    if data.startswith("dl|"):
        await handle_download_callback(q, data, user, context)
        return

async def handle_admin_callback(q, data, user, context):
    action = data[4:]  # remove "adm_"

    if action == "back":
        stats = get_stats()
        await q.message.edit_text(ADMIN_STATS_MSG(stats), parse_mode=ParseMode.MARKDOWN, reply_markup=admin_main_kb())
        return

    if action == "stats":
        stats = get_stats()
        platforms = get_platform_stats()
        plat_str = "\n".join([f"  • {r['platform'].title()}: {r['cnt']}" for r in platforms[:6]])
        await q.message.edit_text(
            ADMIN_STATS_MSG(stats) + f"\n📊 **Platforms:**\n{plat_str}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=admin_back_kb()
        )
        return

    if action == "maintenance":
        cur = get_setting("maintenance")
        new = "0" if cur == "1" else "1"
        set_setting("maintenance", new)
        status = "🔧 ON" if new == "1" else "✅ OFF"
        await q.answer(f"Maintenance: {status}", show_alert=True)
        stats = get_stats()
        await q.message.edit_text(ADMIN_STATS_MSG(stats), parse_mode=ParseMode.MARKDOWN, reply_markup=admin_main_kb())
        return

    if action == "toggle":
        cur = get_setting("bot_active")
        new = "0" if cur == "1" else "1"
        set_setting("bot_active", new)
        status = "✅ Active" if new == "1" else "❌ Inactive"
        await q.answer(f"Bot: {status}", show_alert=True)
        stats = get_stats()
        await q.message.edit_text(ADMIN_STATS_MSG(stats), parse_mode=ParseMode.MARKDOWN, reply_markup=admin_main_kb())
        return

    if action == "clearcache":
        count = clear_cache()
        cleanup_old_files(0)
        await q.answer(f"🗑️ Cache cleared! ({count} entries)", show_alert=True)
        return

    if action == "topusers":
        top = get_top_users(10)
        msg = "🏆 **Top 10 Users:**\n\n"
        for i, u in enumerate(top, 1):
            msg += f"{i}. {u['full_name']} — {u['total_downloads']} downloads\n"
        await q.message.edit_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_back_kb())
        return

    if action == "platforms":
        rows = get_platform_stats()
        msg = "📊 **Downloads by Platform:**\n\n"
        for r in rows:
            msg += f"• {r['platform'].title()}: **{r['cnt']}**\n"
        await q.message.edit_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_back_kb())
        return

    if action == "feedbacks":
        rows = get_recent_feedbacks(10)
        msg = "📝 **Recent Feedbacks:**\n\n"
        for r in rows:
            msg += f"👤 {r['full_name']} (`{r['user_id']}`):\n_{r['message'][:100]}_\n\n"
        await q.message.edit_text(msg or "No feedbacks yet!", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_back_kb())
        return

    if action == "users":
        stats = get_stats()
        msg = (
            f"👥 **User Stats:**\n\n"
            f"Total: {stats['total_users']}\n"
            f"Active Today: {stats['active_today']}\n"
            f"Banned: {stats['banned_users']}\n"
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_back_kb())
        return

    if action == "broadcast":
        set_user_state(user.id, "waiting_broadcast")
        await q.message.edit_text(
            "📢 **Broadcast Message**\n\nSend karne wala message type karo:",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if action == "addcookies":
        await q.message.edit_text(
            "🍪 **Add Cookies**\n\nKis platform ki cookies add karni hain?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cookies_platform_kb()
        )
        return

    if action == "ban_prompt":
        set_user_state(user.id, "waiting_ban")
        await q.message.edit_text("🚫 **Ban User**\nUser ID bhejo:", parse_mode=ParseMode.MARKDOWN)
        return

    if action == "unban_prompt":
        set_user_state(user.id, "waiting_unban")
        await q.message.edit_text("✅ **Unban User**\nUser ID bhejo:", parse_mode=ParseMode.MARKDOWN)
        return

    if action == "search":
        set_user_state(user.id, "waiting_search_admin")
        await q.message.edit_text("🔍 **User Search**\nUser ID ya username bhejo:", parse_mode=ParseMode.MARKDOWN)
        return

    if action.startswith("cookie_"):
        platform = action.split("_", 1)[1]
        platform_name = COOKIE_PLATFORM_NAMES.get(platform, platform.title())
        set_user_state(user.id, "waiting_cookie_file", {"platform": platform})
        cookie_exists = "Existing file will be replaced.\n\n" if get_cookie_file(platform) else ""
        await q.message.edit_text(
            f"🍪 **{platform_name} Cookies**\n\n"
            f"{cookie_exists}"
            f"Ab `{platform}.txt` type ka cookies file document ke form me bhejo.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_back_kb()
        )
        return

    if action == "pin":
        try:
            await context.bot.pin_chat_message(
                chat_id=q.message.chat_id,
                message_id=q.message.message_id,
                disable_notification=True
            )
            await q.answer("📌 Message pinned!", show_alert=True)
        except Exception as e:
            await q.answer(f"❌ Pin failed: {str(e)[:60]}", show_alert=True)
        return

    if action == "botlink":
        bot_info = await context.bot.get_me()
        await q.answer(f"@{bot_info.username}", show_alert=True)
        return

async def handle_download_callback(q, data, user, context):
    parts = data.split("|")
    if len(parts) < 4:
        return

    _, url_hash, fmt_id, dl_type = parts[:4]
    cached = get_url(url_hash)

    if not cached:
        await q.answer("⏰ Session expired! URL dobara bhejo.", show_alert=True)
        try:
            await q.message.delete()
        except:
            pass
        return

    url    = cached["url"]
    info   = cached.get("info") or {}
    formats = cached.get("formats") or []

    # Cooldown
    ok, remaining = check_cooldown(user.id, config.COOLDOWN_SECONDS)
    if not ok:
        await q.answer(f"⏳ {remaining}s baad try karo!", show_alert=True)
        return

    audio_only  = (dl_type == "audio")
    thumb_only  = (dl_type == "thumb")
    platform    = detect_platform(url)
    title       = info.get("title", "Video") or "Video"

    # Edit message
    processing_text = "🎵 Audio extract ho raha hai..." if audio_only else "🖼️ Thumbnail..." if thumb_only else "⬇️ Downloading..."
    try:
        if q.message.photo:
            await q.message.edit_caption(f"⏳ **{processing_text}**\nPlease wait...", parse_mode=ParseMode.MARKDOWN)
        else:
            await q.message.edit_text(f"⏳ **{processing_text}**\nPlease wait...", parse_mode=ParseMode.MARKDOWN)
    except:
        pass

    await context.bot.send_chat_action(
        q.message.chat_id,
        ChatAction.UPLOAD_AUDIO if audio_only else ChatAction.UPLOAD_DOCUMENT
    )

    # Thumbnail only
    if thumb_only:
        thumb_url = info.get("thumbnail")
        if thumb_url:
            try:
                await context.bot.send_photo(
                    q.message.chat_id,
                    photo=thumb_url,
                    caption=f"🖼️ **Thumbnail**\n{title[:50]}",
                    parse_mode=ParseMode.MARKDOWN
                )
                try:
                    await q.message.delete()
                except:
                    pass
                return
            except Exception as e:
                pass
        await context.bot.send_message(q.message.chat_id, "❌ Thumbnail nahi mila!")
        return

    # Height limit from format ID
    height_limit = None
    actual_fmt = None
    if fmt_id in ("best", "audio"):
        pass
    elif fmt_id.endswith("p"):
        height_limit = int(fmt_id[:-1])
    else:
        actual_fmt = fmt_id

    loop = asyncio.get_event_loop()
    filepath, dl_info = await loop.run_in_executor(
        None, ytdlp_download, url, actual_fmt, audio_only, height_limit, platform
    )

    if not filepath or not Path(filepath).exists():
        # Try Luffy API fallback for direct download
        luffy = await luffy_fetch(url)
        if luffy and luffy.get("download_url"):
            ts = int(time.time())
            save_path = f"{config.DOWNLOAD_DIR}/{ts}_video.mp4"
            filepath = await download_file(luffy["download_url"], save_path)

    if not filepath or not Path(filepath).exists():
        await context.bot.send_message(
            q.message.chat_id,
            "❌ **Download fail hua!**\n\nDobara try karo ya dusri quality choose karo.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    size_mb = file_size_mb(filepath)

    if size_mb > config.MAX_FILE_MB:
        Path(filepath).unlink(missing_ok=True)
        await context.bot.send_message(
            q.message.chat_id,
            f"⚠️ **File bahut badi hai!** ({size_mb:.1f}MB)\n"
            f"Telegram limit {config.MAX_FILE_MB}MB hai.\n"
            f"Chhoti quality try karo.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    quality_label = "Audio MP3" if audio_only else (fmt_id if fmt_id != "best" else "Best Quality")
    caption = DOWNLOAD_DONE_MSG(title, platform, quality_label, size_mb, (await context.bot.get_me()).username)

    thumb_url = (dl_info or info or {}).get("thumbnail")
    thumb_path = None
    if thumb_url and not audio_only:
        thumb_path = f"{config.DOWNLOAD_DIR}/thumb_{url_hash}.jpg"
        await download_file(thumb_url, thumb_path)

    set_cooldown(user.id)

    try:
        with open(filepath, "rb") as f:
            if audio_only:
                await context.bot.send_audio(
                    q.message.chat_id, audio=f, caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    title=title[:60],
                    performer=(dl_info or info or {}).get("uploader", "")
                )
            else:
                thumb_file = None
                if thumb_path and Path(thumb_path).exists():
                    thumb_file = open(thumb_path, "rb")
                await context.bot.send_video(
                    q.message.chat_id, video=f, caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    thumbnail=thumb_file,
                    supports_streaming=True,
                )
                if thumb_file:
                    thumb_file.close()

        log_download(user.id, url, platform, quality_label, f"{size_mb:.1f}MB", title)

        if config.LOG_CHANNEL:
            try:
                await context.bot.send_message(
                    config.LOG_CHANNEL,
                    f"📥 **Download**\n👤 {user.full_name} (`{user.id}`)\n🌐 {platform.title()}\n🎬 {quality_label}\n📦 {size_mb:.1f}MB",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

        try:
            await q.message.delete()
        except:
            pass

    except Exception as e:
        logger.error(f"Send error: {e}")
        await context.bot.send_message(q.message.chat_id, f"❌ File send nahi hui: {str(e)[:100]}")
    finally:
        Path(filepath).unlink(missing_ok=True)
        if thumb_path:
            Path(thumb_path).unlink(missing_ok=True)

# ══════════════════════════════════════════
#   INLINE QUERY
# ══════════════════════════════════════════
async def inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.inline_query.query.strip()
    bot = await context.bot.get_me()

    if not q:
        results = [InlineQueryResultArticle(
            id="help",
            title="📥 Social Media Downloader",
            description="Yahan URL paste karo ya bot mein bhejo",
            input_message_content=InputTextMessageContent(
                f"🤖 @{bot.username} — Social Media Downloader\n\nKoi bhi video link bhejo!"
            )
        )]
        await update.inline_query.answer(results, cache_time=60)
        return

    if is_url(q):
        platform = detect_platform(q)
        results = [InlineQueryResultArticle(
            id="dl",
            title=f"📥 Download from {platform.title()}",
            description=f"Bot mein bhejo: @{bot.username}",
            input_message_content=InputTextMessageContent(
                f"🔗 {q}\n\n👆 @{bot.username} pe bhejo download karne ke liye!"
            )
        )]
        await update.inline_query.answer(results, cache_time=5)

# ══════════════════════════════════════════
#   STARTUP & MAIN
# ══════════════════════════════════════════
async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start",       "🏠 Bot start karo"),
        BotCommand("help",        "📖 Help aur guide"),
        BotCommand("stats",       "📊 Download stats"),
        BotCommand("about",       "ℹ️ Bot ke baare mein"),
        BotCommand("feedback",    "💬 Feedback do"),
        BotCommand("ping",        "🏓 Bot check karo"),
        BotCommand("myid",        "🆔 Apna ID dekho"),
        BotCommand("refer",       "🔗 Referral link"),
        BotCommand("cancel",      "❌ Cancel karo"),
        BotCommand("addcookies",  "🍪 Admin cookies add karo"),
    ])
    logger.info("✅ Bot commands set!")

    # Cleanup old files on startup
    cleanup_old_files(3600)

    # Notify admins
    for admin_id in config.ADMIN_IDS:
        try:
            await app.bot.send_message(
                admin_id,
                f"🚀 **Bot Started!**\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

def main():
    init_db()
    logger.info("🚀 Bot starting...")

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # User commands
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("about",      cmd_about))
    app.add_handler(CommandHandler("ping",       cmd_ping))
    app.add_handler(CommandHandler("feedback",   cmd_feedback))
    app.add_handler(CommandHandler("cancel",     cmd_cancel))
    app.add_handler(CommandHandler("myid",       cmd_myid))
    app.add_handler(CommandHandler("refer",      cmd_refer))
    app.add_handler(CommandHandler("addcookies", cmd_addcookies))

    # Admin commands
    app.add_handler(CommandHandler("admin",       cmd_admin))
    app.add_handler(CommandHandler("broadcast",   cmd_broadcast))
    app.add_handler(CommandHandler("ban",         cmd_ban))
    app.add_handler(CommandHandler("unban",       cmd_unban))
    app.add_handler(CommandHandler("adminstats",  cmd_stats_admin))
    app.add_handler(CommandHandler("send",        cmd_send))
    app.add_handler(CommandHandler("maintenance", cmd_maintenance))
    app.add_handler(CommandHandler("setlimit",    cmd_setlimit))
    app.add_handler(CommandHandler("setwelcome",  cmd_setwelcome))
    app.add_handler(CommandHandler("users",       cmd_users))
    app.add_handler(CommandHandler("searchuser",  cmd_search_user))

    # Message & callbacks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(InlineQueryHandler(inline_handler))

    logger.info("✅ All handlers registered!")
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
