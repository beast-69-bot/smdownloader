import re
import time
import asyncio
import aiohttp
import aiofiles
import logging
from pathlib import Path
from config import LUFFY_API_URL, LUFFY_API_KEY, DOWNLOAD_DIR, COOKIES_DIR, MAX_FILE_MB

logger = logging.getLogger(__name__)

PLATFORMS = {
    "instagram":   r"instagram\.com\/(p|reel|tv|stories)\/",
    "youtube":     r"(youtube\.com\/watch|youtu\.be\/|youtube\.com\/shorts\/)",
    "tiktok":      r"tiktok\.com\/@?.+\/video\/",
    "twitter":     r"(twitter\.com|x\.com)\/.+\/status\/",
    "facebook":    r"facebook\.com\/(watch|videos|reel|share\/v)",
    "spotify":     r"open\.spotify\.com\/track\/",
    "soundcloud":  r"soundcloud\.com\/",
    "pinterest":   r"pinterest\.(com|co\.uk)\/pin\/",
    "reddit":      r"reddit\.com\/r\/.+\/comments\/",
    "twitch":      r"clips\.twitch\.tv\/",
    "bilibili":    r"bilibili\.com\/video\/",
    "dailymotion": r"dailymotion\.com\/video\/",
    "vimeo":       r"vimeo\.com\/\d+",
    "tumblr":      r"tumblr\.com\/",
    "streamable":  r"streamable\.com\/",
    "likee":       r"likee\.video\/",
    "kwai":        r"kwai\.com\/",
}

def detect_platform(url):
    for name, pattern in PLATFORMS.items():
        if re.search(pattern, url, re.I):
            return name
    return "other"

def is_url(text):
    return bool(re.match(r'https?://', text.strip()))


def get_cookie_file(platform):
    cookie_path = Path(COOKIES_DIR) / f"{platform}.txt"
    if cookie_path.exists():
        return str(cookie_path)
    return None

# ─────────────────────────────────────────
async def luffy_fetch(url):
    try:
        import urllib.parse
        encoded = urllib.parse.quote(url, safe="")
        api_url = f"{LUFFY_API_URL}?key={LUFFY_API_KEY}&url={encoded}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json(content_type=None)
                if not data:
                    return None
                # Check for video URL in common keys
                for key in ["url", "download", "video", "link", "media", "data", "result"]:
                    val = data.get(key)
                    if isinstance(val, str) and val.startswith("http"):
                        return {"download_url": val, "data": data}
                    if isinstance(val, list) and val:
                        for item in val:
                            if isinstance(item, dict):
                                for subkey in ["url", "download_url", "link"]:
                                    if isinstance(item.get(subkey), str) and item[subkey].startswith("http"):
                                        return {"download_url": item[subkey], "data": data, "formats": val}
    except Exception as e:
        logger.warning(f"Luffy API error: {e}")
    return None

# ─────────────────────────────────────────
def ytdlp_info(url, platform=None):
    try:
        import yt_dlp
        platform = platform or detect_platform(url)
        opts = {
            "quiet": True, "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 20,
        }
        cookie_file = get_cookie_file(platform)
        if cookie_file:
            opts["cookiefile"] = cookie_file
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            seen_heights = set()
            for f in (info.get("formats") or []):
                h = f.get("height")
                if h and h not in seen_heights and f.get("vcodec", "none") != "none":
                    seen_heights.add(h)
                    raw_size = f.get("filesize") or f.get("filesize_approx") or 0
                    formats.append({
                        "format_id": f["format_id"],
                        "quality": f"{h}p",
                        "ext": f.get("ext", "mp4"),
                        "size": f"{raw_size/1024/1024:.1f}MB" if raw_size else "?MB",
                        "height": h,
                    })
            formats.sort(key=lambda x: x["height"], reverse=True)
            return info, formats
    except Exception as e:
        logger.error(f"yt-dlp info error: {e}")
        return None, []

def ytdlp_download(url, fmt_id=None, audio_only=False, height_limit=None, platform=None):
    try:
        import yt_dlp
        ts = int(time.time())
        out = f"{DOWNLOAD_DIR}/{ts}_%(title).50s.%(ext)s"
        platform = platform or detect_platform(url)

        if audio_only:
            opts = {
                "format": "bestaudio/best",
                "outtmpl": out,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                "quiet": True, "socket_timeout": 30,
            }
        elif fmt_id and fmt_id not in ("best", "audio"):
            # Specific format
            opts = {
                "format": f"{fmt_id}+bestaudio/{fmt_id}/best",
                "outtmpl": out, "merge_output_format": "mp4",
                "quiet": True, "socket_timeout": 30,
            }
        elif height_limit:
            opts = {
                "format": f"bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}]",
                "outtmpl": out, "merge_output_format": "mp4",
                "quiet": True, "socket_timeout": 30,
            }
        else:
            opts = {
                "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "outtmpl": out, "merge_output_format": "mp4",
                "quiet": True, "socket_timeout": 30,
            }

        cookie_file = get_cookie_file(platform)
        if cookie_file:
            opts["cookiefile"] = cookie_file

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if audio_only:
                filepath = str(Path(filepath).with_suffix(".mp3"))
            # Sometimes yt-dlp merges and changes filename
            if not Path(filepath).exists():
                # Try finding the file
                base = Path(DOWNLOAD_DIR)
                candidates = sorted(base.glob(f"{ts}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    filepath = str(candidates[0])
            return filepath, info
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        return None, None

async def download_file(url, save_path):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    async with aiofiles.open(save_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024*64):
                            await f.write(chunk)
                    return save_path
    except Exception as e:
        logger.error(f"Direct download error: {e}")
    return None

def cleanup_old_files(max_age_seconds=3600):
    try:
        now = time.time()
        for f in Path(DOWNLOAD_DIR).glob("*"):
            if f.is_file() and (now - f.stat().st_mtime) > max_age_seconds:
                f.unlink()
    except:
        pass

def file_size_mb(path):
    try:
        return Path(path).stat().st_size / 1024 / 1024
    except:
        return 0
