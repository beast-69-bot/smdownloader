import time
import logging

logger = logging.getLogger(__name__)

# In-memory stores
_url_cache = {}          # url_hash -> {url, info, formats, time}
_user_state = {}         # user_id -> {state, data}
_cooldowns = {}          # user_id -> last_download_time
_pending_broadcast = {}  # admin_id -> message_text

def store_url(url, info=None, formats=None):
    h = str(abs(hash(url + str(time.time()))) % 999999)
    _url_cache[h] = {
        "url": url,
        "info": info or {},
        "formats": formats or [],
        "time": time.time()
    }
    _cleanup_cache()
    return h

def get_url(h):
    return _url_cache.get(h)

def _cleanup_cache():
    now = time.time()
    expired = [k for k, v in _url_cache.items() if now - v["time"] > 3600]
    for k in expired:
        del _url_cache[k]

def clear_cache():
    count = len(_url_cache)
    _url_cache.clear()
    return count

def set_user_state(user_id, state, data=None):
    _user_state[user_id] = {"state": state, "data": data or {}, "time": time.time()}

def get_user_state(user_id):
    s = _user_state.get(user_id)
    if s and time.time() - s["time"] < 300:  # 5 min expiry
        return s
    return None

def clear_user_state(user_id):
    _user_state.pop(user_id, None)

def check_cooldown(user_id, seconds=5):
    last = _cooldowns.get(user_id, 0)
    remaining = seconds - (time.time() - last)
    if remaining > 0:
        return False, int(remaining)
    return True, 0

def set_cooldown(user_id):
    _cooldowns[user_id] = time.time()

def set_pending_broadcast(admin_id, msg):
    _pending_broadcast[admin_id] = msg

def get_pending_broadcast(admin_id):
    return _pending_broadcast.get(admin_id)

def clear_pending_broadcast(admin_id):
    _pending_broadcast.pop(admin_id, None)
