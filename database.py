import json
import logging
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from config import (
    API_KEY_PREFIX,
    DB_FILE,
    DEFAULT_API_RATE_LIMIT,
    DEFAULT_MAX_DURATION,
    FILE_RETENTION_HOURS,
)

logger = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _table_has_column(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _ensure_column(cursor, table, column, definition):
    if not _table_has_column(cursor, table, column):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _generate_api_key():
    return f"{API_KEY_PREFIX}_{secrets.token_hex(32)}"


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
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
    )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS downloads (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        url        TEXT,
        platform   TEXT,
        quality    TEXT,
        file_size  TEXT,
        title      TEXT,
        status     TEXT DEFAULT 'success',
        timestamp  TEXT
    )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS banned_urls (
        url_hash TEXT PRIMARY KEY,
        reason   TEXT,
        added_at TEXT
    )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS feedback (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        message   TEXT,
        timestamp TEXT
    )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS stats_daily (
        date_str    TEXT PRIMARY KEY,
        new_users   INTEGER DEFAULT 0,
        downloads   INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0
    )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS api_keys (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id           INTEGER UNIQUE,
        api_key           TEXT UNIQUE,
        name              TEXT DEFAULT '',
        expires_at        TEXT DEFAULT '',
        is_blocked        INTEGER DEFAULT 0,
        block_reason      TEXT DEFAULT '',
        last_used_at      TEXT DEFAULT '',
        rate_limit        INTEGER DEFAULT 0,
        max_duration      INTEGER DEFAULT 0,
        ip_whitelist_json TEXT DEFAULT '[]',
        usage_count       INTEGER DEFAULT 0,
        rate_limit_hits   INTEGER DEFAULT 0,
        created_at        TEXT
    )"""
    )

    _ensure_column(c, "downloads", "file_path", "TEXT DEFAULT ''")
    _ensure_column(c, "downloads", "expires_at", "TEXT DEFAULT ''")
    _ensure_column(c, "downloads", "error_message", "TEXT DEFAULT ''")
    _ensure_column(c, "downloads", "duration_seconds", "INTEGER DEFAULT 0")
    _ensure_column(c, "downloads", "api_key_id", "INTEGER DEFAULT 0")

    defaults = [
        ("bot_active", "1"),
        ("maintenance", "0"),
        ("force_sub", "0"),
        ("max_daily", "20"),
        ("welcome_msg", ""),
        ("total_served", "0"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")


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


def ensure_api_key_for_user(user_id, name=""):
    row = db_fetchone("SELECT * FROM api_keys WHERE user_id=?", (user_id,))
    if row:
        if name and row["name"] != name:
            db_exec("UPDATE api_keys SET name=? WHERE user_id=?", (name, user_id))
            row = db_fetchone("SELECT * FROM api_keys WHERE user_id=?", (user_id,))
        return row

    now = datetime.now().isoformat()
    api_key = _generate_api_key()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO api_keys
        (user_id, api_key, name, expires_at, is_blocked, block_reason, last_used_at,
         rate_limit, max_duration, ip_whitelist_json, usage_count, rate_limit_hits, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            user_id,
            api_key,
            name or f"User {user_id}",
            "",
            0,
            "",
            "",
            DEFAULT_API_RATE_LIMIT,
            DEFAULT_MAX_DURATION,
            "[]",
            0,
            0,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return db_fetchone("SELECT * FROM api_keys WHERE user_id=?", (user_id,))


def register_user(user):
    existing = db_fetchone("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    now = datetime.now().isoformat()
    today = date.today().isoformat()

    if not existing:
        db_exec(
            "INSERT INTO users (user_id,username,full_name,language_code,joined_at,last_used,last_dl_date) VALUES (?,?,?,?,?,?,?)",
            (user.id, user.username or "", user.full_name, user.language_code or "en", now, now, today),
        )
        db_exec("INSERT OR IGNORE INTO stats_daily (date_str) VALUES (?)", (today,))
        db_exec("UPDATE stats_daily SET new_users=new_users+1 WHERE date_str=?", (today,))
        ensure_api_key_for_user(user.id, user.full_name)
        return True

    db_exec(
        "UPDATE users SET last_used=?, username=?, full_name=? WHERE user_id=?",
        (now, user.username or "", user.full_name, user.id),
    )
    ensure_api_key_for_user(user.id, user.full_name)
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


def get_api_key_for_user(user_id):
    return db_fetchone("SELECT * FROM api_keys WHERE user_id=?", (user_id,))


def get_api_key_by_value(api_key):
    return db_fetchone("SELECT * FROM api_keys WHERE api_key=?", (api_key,))


def touch_api_key(api_key_id):
    now = datetime.now().isoformat()
    db_exec(
        "UPDATE api_keys SET last_used_at=?, usage_count=usage_count+1 WHERE id=?",
        (now, api_key_id),
    )


def increment_rate_limit_hit(api_key_id):
    db_exec(
        "UPDATE api_keys SET rate_limit_hits=rate_limit_hits+1 WHERE id=?",
        (api_key_id,),
    )


def set_api_rate_limit(user_id, rate_limit):
    db_exec("UPDATE api_keys SET rate_limit=? WHERE user_id=?", (rate_limit, user_id))


def set_api_max_duration(user_id, max_duration):
    db_exec("UPDATE api_keys SET max_duration=? WHERE user_id=?", (max_duration, user_id))


def block_api_key(user_id, reason=""):
    db_exec(
        "UPDATE api_keys SET is_blocked=1, block_reason=? WHERE user_id=?",
        (reason, user_id),
    )


def unblock_api_key(user_id):
    db_exec(
        "UPDATE api_keys SET is_blocked=0, block_reason='' WHERE user_id=?",
        (user_id,),
    )


def set_api_whitelist(user_id, ip_list):
    payload = json.dumps(ip_list)
    db_exec("UPDATE api_keys SET ip_whitelist_json=? WHERE user_id=?", (payload, user_id))


def set_api_expiry(user_id, expires_at):
    db_exec("UPDATE api_keys SET expires_at=? WHERE user_id=?", (expires_at, user_id))


def _record_success_metrics(user_id, when=None):
    when = when or datetime.now()
    today = when.date().isoformat()
    db_exec("UPDATE users SET total_downloads=total_downloads+1 WHERE user_id=?", (user_id,))
    db_exec(
        "UPDATE users SET today_downloads=0, last_dl_date=? WHERE user_id=? AND last_dl_date!=?",
        (today, user_id, today),
    )
    db_exec("UPDATE users SET today_downloads=today_downloads+1, last_dl_date=? WHERE user_id=?", (today, user_id))
    db_exec("INSERT OR IGNORE INTO stats_daily (date_str) VALUES (?)", (today,))
    db_exec("UPDATE stats_daily SET downloads=downloads+1 WHERE date_str=?", (today,))
    db_exec("UPDATE settings SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='total_served'")


def create_download_record(user_id, url, platform, quality, title="", api_key_id=0, duration_seconds=0):
    now = datetime.now()
    expires_at = (now + timedelta(hours=FILE_RETENTION_HOURS)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO downloads
        (user_id, url, platform, quality, file_size, title, status, timestamp, file_path,
         expires_at, error_message, duration_seconds, api_key_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            user_id,
            url,
            platform,
            quality,
            "",
            title[:100] if title else "",
            "pending",
            now.isoformat(),
            "",
            expires_at,
            "",
            duration_seconds or 0,
            api_key_id or 0,
        ),
    )
    download_id = c.lastrowid
    conn.commit()
    conn.close()
    return download_id


def update_download_status(
    download_id,
    status,
    *,
    file_path=None,
    file_size=None,
    error_message=None,
    title=None,
    duration_seconds=None,
    quality=None,
):
    current = db_fetchone("SELECT * FROM downloads WHERE id=?", (download_id,))
    if not current:
        return

    fields = ["status=?"]
    params = [status]

    if file_path is not None:
        fields.append("file_path=?")
        params.append(file_path)
    if file_size is not None:
        fields.append("file_size=?")
        params.append(file_size)
    if error_message is not None:
        fields.append("error_message=?")
        params.append((error_message or "")[:250])
    if title is not None:
        fields.append("title=?")
        params.append((title or "")[:100])
    if duration_seconds is not None:
        fields.append("duration_seconds=?")
        params.append(duration_seconds)
    if quality is not None:
        fields.append("quality=?")
        params.append(quality)

    params.append(download_id)
    db_exec(f"UPDATE downloads SET {', '.join(fields)} WHERE id=?", tuple(params))

    if status == "success" and current["status"] != "success":
        _record_success_metrics(current["user_id"])


def log_download(user_id, url, platform, quality, size, title, status="success"):
    download_id = create_download_record(user_id, url, platform, quality, title=title)
    update_download_status(download_id, status, file_size=size, title=title, quality=quality)
    return download_id


def expire_old_downloads(max_age_hours=12):
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    rows = db_fetch(
        "SELECT id, file_path FROM downloads WHERE status IN ('pending','processing','failed') AND timestamp < ?",
        (cutoff.isoformat(),),
    )

    expired = 0
    for row in rows:
        file_path = (row["file_path"] or "").strip()
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass
        update_download_status(row["id"], "expired", file_path="", error_message="Expired by hourly cleanup")
        expired += 1
    return expired


def get_today_downloads(user_id):
    today = date.today().isoformat()
    r = db_fetchone("SELECT today_downloads, last_dl_date FROM users WHERE user_id=?", (user_id,))
    if r and r["last_dl_date"] == today:
        return r["today_downloads"]
    return 0


def get_stats():
    today = date.today().isoformat()
    total_users = db_fetchone("SELECT COUNT(*) as c FROM users")["c"]
    active_today = db_fetchone(f"SELECT COUNT(*) as c FROM users WHERE last_used LIKE '{today}%'")["c"]
    total_dl = db_fetchone("SELECT COUNT(*) as c FROM downloads WHERE status='success'")["c"]
    today_dl = db_fetchone(
        f"SELECT COUNT(*) as c FROM downloads WHERE status='success' AND timestamp LIKE '{today}%'"
    )["c"]
    banned_users = db_fetchone("SELECT COUNT(*) as c FROM users WHERE is_banned=1")["c"]
    total_served = get_setting("total_served", "0")
    top_platform = db_fetchone(
        "SELECT platform, COUNT(*) as c FROM downloads WHERE status='success' GROUP BY platform ORDER BY c DESC LIMIT 1"
    )
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
        (user_id, message, datetime.now().isoformat()),
    )


def get_recent_feedbacks(limit=10):
    return db_fetch(
        "SELECT f.*, u.full_name, u.username FROM feedback f "
        "LEFT JOIN users u ON f.user_id=u.user_id "
        "ORDER BY f.id DESC LIMIT ?",
        (limit,),
    )


def get_top_users(limit=10):
    return db_fetch(
        "SELECT user_id, full_name, username, total_downloads FROM users "
        "ORDER BY total_downloads DESC LIMIT ?",
        (limit,),
    )


def get_platform_stats():
    return db_fetch(
        "SELECT platform, COUNT(*) as cnt FROM downloads WHERE status='success' GROUP BY platform ORDER BY cnt DESC"
    )


def get_api_stats(limit=20, user_id=None):
    base_query = """
        SELECT
            k.*,
            u.full_name,
            u.username,
            u.total_downloads
        FROM api_keys k
        LEFT JOIN users u ON k.user_id = u.user_id
    """
    params = ()
    if user_id is not None:
        base_query += " WHERE k.user_id=? ORDER BY k.created_at DESC LIMIT ?"
        params = (user_id, limit)
    else:
        base_query += " ORDER BY k.usage_count DESC, k.created_at DESC LIMIT ?"
        params = (limit,)
    return db_fetch(base_query, params)


def search_user(query):
    try:
        uid = int(query)
        return db_fetch("SELECT * FROM users WHERE user_id=?", (uid,))
    except Exception:
        return db_fetch(
            "SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ?",
            (f"%{query}%", f"%{query}%"),
        )
