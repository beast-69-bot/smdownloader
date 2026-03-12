import sqlite3
import logging
from datetime import datetime, date
from config import DB_FILE

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id       INTEGER PRIMARY KEY,
        username      TEXT,
        full_name     TEXT,
        language_code TEXT DEFAULT 'en',
        joined_at     TEXT,
        last_used     TEXT,
        total_downloads INTEGER DEFAULT 0,
        today_downloads INTEGER DEFAULT 0,
        last_dl_date  TEXT DEFAULT '',
        is_banned     INTEGER DEFAULT 0,
        ban_reason    TEXT DEFAULT '',
        is_premium    INTEGER DEFAULT 0,
        premium_until TEXT DEFAULT '',
        referrer_id   INTEGER DEFAULT 0,
        referral_count INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS downloads (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        url        TEXT,
        platform   TEXT,
        quality    TEXT,
        file_size  TEXT,
        title      TEXT,
        status     TEXT DEFAULT 'success',
        timestamp  TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS banned_urls (
        url_hash TEXT PRIMARY KEY,
        reason   TEXT,
        added_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        message   TEXT,
        timestamp TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS stats_daily (
        date_str    TEXT PRIMARY KEY,
        new_users   INTEGER DEFAULT 0,
        downloads   INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0
    )""")

    defaults = [
        ("bot_active",    "1"),
        ("maintenance",   "0"),
        ("force_sub",     "0"),
        ("max_daily",     "20"),
        ("welcome_msg",   ""),
        ("total_served",  "0"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

# ─────────────────────────────────────────
def db_exec(query, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def db_fetch(query, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def db_fetchone(query, params=()):
    rows = db_fetch(query, params)
    return rows[0] if rows else None

# ─────────────────────────────────────────
def register_user(user):
    existing = db_fetchone("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    now = datetime.now().isoformat()
    today = date.today().isoformat()

    if not existing:
        db_exec(
            "INSERT INTO users (user_id,username,full_name,language_code,joined_at,last_used,last_dl_date) VALUES (?,?,?,?,?,?,?)",
            (user.id, user.username or "", user.full_name, user.language_code or "en", now, now, today)
        )
        # Update daily stats
        db_exec(
            "INSERT OR IGNORE INTO stats_daily (date_str) VALUES (?)", (today,)
        )
        db_exec(
            "UPDATE stats_daily SET new_users=new_users+1 WHERE date_str=?", (today,)
        )
        return True  # New user
    else:
        db_exec(
            "UPDATE users SET last_used=?, username=?, full_name=? WHERE user_id=?",
            (now, user.username or "", user.full_name, user.id)
        )
        return False

def get_user(user_id):
    return db_fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))

def is_banned(user_id):
    r = db_fetchone("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    return r and r["is_banned"] == 1

def ban_user(user_id, reason=""):
    db_exec("UPDATE users SET is_banned=1, ban_reason=? WHERE user_id=?", (reason, user_id))

def unban_user(user_id):
    db_exec("UPDATE users SET is_banned=0, ban_reason='' WHERE user_id=?", (user_id,))

def get_setting(key, default=""):
    r = db_fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default

def set_setting(key, value):
    db_exec("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))

def log_download(user_id, url, platform, quality, size, title, status="success"):
    today = date.today().isoformat()
    now = datetime.now().isoformat()
    db_exec(
        "INSERT INTO downloads (user_id,url,platform,quality,file_size,title,status,timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, url, platform, quality, size, title[:100] if title else "", status, now)
    )
    db_exec("UPDATE users SET total_downloads=total_downloads+1 WHERE user_id=?", (user_id,))
    # Reset daily count if new day
    db_exec(
        "UPDATE users SET today_downloads=0, last_dl_date=? WHERE user_id=? AND last_dl_date!=?",
        (today, user_id, today)
    )
    db_exec("UPDATE users SET today_downloads=today_downloads+1, last_dl_date=? WHERE user_id=?", (today, user_id))
    # Daily stats
    db_exec("INSERT OR IGNORE INTO stats_daily (date_str) VALUES (?)", (today,))
    db_exec("UPDATE stats_daily SET downloads=downloads+1 WHERE date_str=?", (today,))
    db_exec("UPDATE settings SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='total_served'")

def get_today_downloads(user_id):
    today = date.today().isoformat()
    r = db_fetchone("SELECT today_downloads, last_dl_date FROM users WHERE user_id=?", (user_id,))
    if r and r["last_dl_date"] == today:
        return r["today_downloads"]
    return 0

def get_stats():
    total_users   = db_fetchone("SELECT COUNT(*) as c FROM users")["c"]
    active_today  = db_fetchone(f"SELECT COUNT(*) as c FROM users WHERE last_used LIKE '{date.today().isoformat()}%'")["c"]
    total_dl      = db_fetchone("SELECT COUNT(*) as c FROM downloads")["c"]
    today_dl      = db_fetchone(f"SELECT COUNT(*) as c FROM downloads WHERE timestamp LIKE '{date.today().isoformat()}%'")["c"]
    banned_users  = db_fetchone("SELECT COUNT(*) as c FROM users WHERE is_banned=1")["c"]
    total_served  = get_setting("total_served", "0")
    top_platform  = db_fetchone("SELECT platform, COUNT(*) as c FROM downloads GROUP BY platform ORDER BY c DESC LIMIT 1")
    return {
        "total_users": total_users,
        "active_today": active_today,
        "total_downloads": total_dl,
        "today_downloads": today_dl,
        "banned_users": banned_users,
        "total_served": total_served,
        "top_platform": top_platform["platform"] if top_platform else "N/A",
        "top_platform_count": top_platform["c"] if top_platform else 0,
    }

def get_all_user_ids():
    rows = db_fetch("SELECT user_id FROM users WHERE is_banned=0")
    return [r["user_id"] for r in rows]

def add_feedback(user_id, message):
    db_exec(
        "INSERT INTO feedback (user_id,message,timestamp) VALUES (?,?,?)",
        (user_id, message, datetime.now().isoformat())
    )

def get_recent_feedbacks(limit=10):
    return db_fetch(
        "SELECT f.*, u.full_name, u.username FROM feedback f "
        "LEFT JOIN users u ON f.user_id=u.user_id "
        "ORDER BY f.id DESC LIMIT ?", (limit,)
    )

def get_top_users(limit=10):
    return db_fetch(
        "SELECT user_id, full_name, username, total_downloads FROM users "
        "ORDER BY total_downloads DESC LIMIT ?", (limit,)
    )

def get_platform_stats():
    return db_fetch(
        "SELECT platform, COUNT(*) as cnt FROM downloads GROUP BY platform ORDER BY cnt DESC"
    )

def search_user(query):
    try:
        uid = int(query)
        return db_fetch("SELECT * FROM users WHERE user_id=?", (uid,))
    except:
        return db_fetch(
            "SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ?",
            (f"%{query}%", f"%{query}%")
        )
