import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import aiofiles
import aiohttp

from config import (
    AUTO_INSTALL_YTDLP,
    COOKIES_DIR,
    DOWNLOAD_DIR,
    LUFFY_API_KEY,
    LUFFY_API_URL,
    YTDLP_BINARY_DIR,
)

logger = logging.getLogger(__name__)

PLATFORMS = {
    "instagram": r"instagram\.com\/(p|reel|tv|stories)\/",
    "youtube": r"(youtube\.com\/watch|youtu\.be\/|youtube\.com\/shorts\/)",
    "tiktok": r"tiktok\.com\/@?.+\/video\/",
    "twitter": r"(twitter\.com|x\.com)\/.+\/status\/",
    "facebook": r"facebook\.com\/(watch|videos|reel|share\/v)",
    "spotify": r"open\.spotify\.com\/track\/",
    "soundcloud": r"soundcloud\.com\/",
    "pinterest": r"pinterest\.(com|co\.uk)\/pin\/",
    "reddit": r"reddit\.com\/r\/.+\/comments\/",
    "twitch": r"clips\.twitch\.tv\/",
    "bilibili": r"bilibili\.com\/video\/",
    "dailymotion": r"dailymotion\.com\/video\/",
    "vimeo": r"vimeo\.com\/\d+",
    "tumblr": r"tumblr\.com\/",
    "streamable": r"streamable\.com\/",
    "likee": r"likee\.video\/",
    "kwai": r"kwai\.com\/",
}

_YTDLP_BACKEND = None


def detect_platform(url):
    for name, pattern in PLATFORMS.items():
        if re.search(pattern, url, re.I):
            return name
    return "other"


def is_url(text):
    return bool(re.match(r"https?://", text.strip()))


def get_cookie_file(platform):
    cookie_path = Path(COOKIES_DIR) / f"{platform}.txt"
    if cookie_path.exists():
        return str(cookie_path)
    return None


def _binary_url():
    if sys.platform.startswith("win"):
        return "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    if sys.platform == "darwin":
        return "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
    return "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"


def _binary_path():
    binary_name = "yt-dlp.exe" if sys.platform.startswith("win") else "yt-dlp"
    return Path(YTDLP_BINARY_DIR) / binary_name


def ensure_ytdlp_available():
    global _YTDLP_BACKEND
    if _YTDLP_BACKEND:
        return _YTDLP_BACKEND

    try:
        import yt_dlp  # noqa: F401

        _YTDLP_BACKEND = ("module", None)
        return _YTDLP_BACKEND
    except Exception:
        pass

    binary = _binary_path()
    if binary.exists():
        if not sys.platform.startswith("win"):
            binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
        _YTDLP_BACKEND = ("binary", str(binary))
        return _YTDLP_BACKEND

    system_binary = shutil.which("yt-dlp")
    if system_binary:
        _YTDLP_BACKEND = ("binary", system_binary)
        return _YTDLP_BACKEND

    if not AUTO_INSTALL_YTDLP:
        raise RuntimeError("yt-dlp is not installed and auto install is disabled")

    binary.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(_binary_url(), binary)
    if not sys.platform.startswith("win"):
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    logger.info("✅ yt-dlp binary downloaded to %s", binary)
    _YTDLP_BACKEND = ("binary", str(binary))
    return _YTDLP_BACKEND


def _module_opts(base_opts, platform, cookie_file):
    opts = dict(base_opts)
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def _cli_base_cmd(binary_path, url, cookie_file):
    cmd = [binary_path, "--no-warnings", "--ignore-errors", "--socket-timeout", "30"]
    if cookie_file:
        cmd.extend(["--cookies", cookie_file])
    cmd.append(url)
    return cmd


def _extract_formats(info):
    formats = []
    seen_heights = set()
    for fmt in info.get("formats") or []:
        height = fmt.get("height")
        if height and height not in seen_heights and fmt.get("vcodec", "none") != "none":
            seen_heights.add(height)
            raw_size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
            formats.append(
                {
                    "format_id": fmt["format_id"],
                    "quality": f"{height}p",
                    "ext": fmt.get("ext", "mp4"),
                    "size": f"{raw_size / 1024 / 1024:.1f}MB" if raw_size else "?MB",
                    "height": height,
                }
            )
    formats.sort(key=lambda item: item["height"], reverse=True)
    return formats


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


def ytdlp_info(url, platform=None):
    platform = platform or detect_platform(url)
    cookie_file = get_cookie_file(platform)
    backend, binary_path = ensure_ytdlp_available()

    if backend == "module":
        try:
            import yt_dlp

            opts = _module_opts(
                {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "socket_timeout": 20,
                },
                platform,
                cookie_file,
            )
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info, _extract_formats(info)
        except Exception as e:
            logger.error(f"yt-dlp info error: {e}")
            return None, []

    try:
        cmd = _cli_base_cmd(binary_path, url, cookie_file)
        cmd[:0] = []
        cmd.insert(1, "--dump-single-json")
        cmd.insert(2, "--skip-download")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(result.stderr.strip() or "yt-dlp info command failed")
        info = json.loads(result.stdout)
        return info, _extract_formats(info)
    except Exception as e:
        logger.error(f"yt-dlp info error: {e}")
        return None, []


def ytdlp_download(url, fmt_id=None, audio_only=False, height_limit=None, platform=None):
    platform = platform or detect_platform(url)
    cookie_file = get_cookie_file(platform)
    backend, binary_path = ensure_ytdlp_available()
    ts = int(time.time())
    out = f"{DOWNLOAD_DIR}/{ts}_%(title).50s.%(ext)s"

    if backend == "module":
        try:
            import yt_dlp

            if audio_only:
                opts = {
                    "format": "bestaudio/best",
                    "outtmpl": out,
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                    "quiet": True,
                    "socket_timeout": 30,
                }
            elif fmt_id and fmt_id not in ("best", "audio"):
                opts = {
                    "format": f"{fmt_id}+bestaudio/{fmt_id}/best",
                    "outtmpl": out,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "socket_timeout": 30,
                }
            elif height_limit:
                opts = {
                    "format": f"bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}]",
                    "outtmpl": out,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "socket_timeout": 30,
                }
            else:
                opts = {
                    "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                    "outtmpl": out,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "socket_timeout": 30,
                }

            opts = _module_opts(opts, platform, cookie_file)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                if audio_only:
                    filepath = str(Path(filepath).with_suffix(".mp3"))
                if not Path(filepath).exists():
                    candidates = sorted(Path(DOWNLOAD_DIR).glob(f"{ts}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if candidates:
                        filepath = str(candidates[0])
                return filepath, info
        except Exception as e:
            logger.error(f"yt-dlp download error: {e}")
            return None, None

    try:
        cmd = _cli_base_cmd(binary_path, url, cookie_file)
        cmd.extend(["-o", out, "--print", "after_move:filepath"])
        if audio_only:
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "192K", "-f", "bestaudio/best"])
        elif fmt_id and fmt_id not in ("best", "audio"):
            cmd.extend(["-f", f"{fmt_id}+bestaudio/{fmt_id}/best", "--merge-output-format", "mp4"])
        elif height_limit:
            cmd.extend(
                [
                    "-f",
                    f"bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}]",
                    "--merge-output-format",
                    "mp4",
                ]
            )
        else:
            cmd.extend(["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]", "--merge-output-format", "mp4"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "yt-dlp download command failed")

        filepath = None
        for line in reversed([line.strip() for line in result.stdout.splitlines() if line.strip()]):
            if Path(line).exists():
                filepath = line
                break
        if not filepath:
            candidates = sorted(Path(DOWNLOAD_DIR).glob(f"{ts}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                filepath = str(candidates[0])

        info, _ = ytdlp_info(url, platform)
        return filepath, info
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        return None, None


async def download_file(url, save_path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    async with aiofiles.open(save_path, "wb") as file_handle:
                        async for chunk in resp.content.iter_chunked(1024 * 64):
                            await file_handle.write(chunk)
                    return save_path
    except Exception as e:
        logger.error(f"Direct download error: {e}")
    return None


def cleanup_old_files(max_age_seconds=3600):
    try:
        now = time.time()
        for file_path in Path(DOWNLOAD_DIR).glob("*"):
            if file_path.is_file() and (now - file_path.stat().st_mtime) > max_age_seconds:
                file_path.unlink()
    except Exception:
        pass


def file_size_mb(path):
    try:
        return Path(path).stat().st_size / 1024 / 1024
    except Exception:
        return 0
