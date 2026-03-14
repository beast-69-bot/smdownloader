import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import aiofiles
import aiohttp

import config as app_config
from config import (
    AUTO_INSTALL_YTDLP,
    COOKIES_DIR,
    DOWNLOAD_DIR,
    YTDLP_BINARY_DIR,
)

logger = logging.getLogger(__name__)


class CookiesRequiredError(Exception):
    """Raised when yt-dlp fails due to missing/expired cookies."""

    pass

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
COOKIE_REQUIRED_KEYWORDS = [
    "sign in",
    "login required",
    "confirm your age",
    "members only",
    "private video",
    "this video is unavailable",
]
RAPIDAPI_SUPPORTED_PLATFORMS = {"youtube", "instagram", "facebook", "tiktok"}
RAPIDAPI_KEY = (getattr(app_config, "RAPIDAPI_KEY", "") or "").strip()
RAPIDAPI_HOST = (
    getattr(app_config, "RAPIDAPI_HOST", "social-media-video-downloader.p.rapidapi.com") or ""
).strip()
RAPIDAPI_BASE_URL = (
    getattr(app_config, "RAPIDAPI_BASE_URL", "") or (f"https://{RAPIDAPI_HOST}" if RAPIDAPI_HOST else "")
).rstrip("/")
RAPIDAPI_TIMEOUT_SECONDS = int(getattr(app_config, "RAPIDAPI_TIMEOUT_SECONDS", 45) or 45)
RAPIDAPI_URL_ACCESS = (getattr(app_config, "RAPIDAPI_URL_ACCESS", "normal") or "normal").strip().lower()
RAPIDAPI_RENDERABLE_FORMATS = (getattr(app_config, "RAPIDAPI_RENDERABLE_FORMATS", "") or "").strip()


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


def _is_cookie_required_error(error_text):
    text = (error_text or "").lower()
    return any(keyword in text for keyword in COOKIE_REQUIRED_KEYWORDS)


def rapidapi_enabled():
    return bool(RAPIDAPI_KEY and RAPIDAPI_HOST and RAPIDAPI_BASE_URL)


def rapidapi_download_headers(target_url=None):
    if not rapidapi_enabled():
        return None
    if target_url:
        host = urllib.parse.urlparse(target_url).netloc.lower()
        allowed_hosts = {
            RAPIDAPI_HOST.lower(),
            "api-v3.smdw.xyz",
            "api.smdw.xyz",
        }
        if host not in allowed_hosts and not host.endswith(f".{RAPIDAPI_HOST.lower()}"):
            return None
    return {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }


def _parse_duration_seconds(raw_duration):
    if raw_duration is None:
        return 0
    if isinstance(raw_duration, (int, float)):
        return int(raw_duration)
    text = str(raw_duration).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    if ":" not in text:
        return 0
    parts = [part.strip() for part in text.split(":") if part.strip()]
    if not parts or len(parts) > 3 or not all(part.isdigit() for part in parts):
        return 0
    seconds = 0
    for part in parts:
        seconds = (seconds * 60) + int(part)
    return seconds


def _parse_view_count(raw_views):
    if raw_views is None:
        return 0
    if isinstance(raw_views, (int, float)):
        return int(raw_views)
    digits = re.sub(r"[^\d]", "", str(raw_views))
    return int(digits) if digits else 0


def _ensure_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _extract_youtube_video_id(url):
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    if "youtu.be" in host and path_parts:
        candidate = path_parts[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate

    query_video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", query_video_id):
        return query_video_id

    for marker in ("shorts", "embed", "v"):
        if marker in path_parts:
            idx = path_parts.index(marker)
            if idx + 1 < len(path_parts):
                candidate = path_parts[idx + 1]
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
                    return candidate

    match = re.search(r"([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None


def _extract_instagram_shortcode(url):
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    for marker in ("p", "reel", "tv"):
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None


def _rapidapi_route_and_params(url, platform, url_access=None, renderable_formats=None):
    effective_url_access = (url_access or RAPIDAPI_URL_ACCESS or "").strip().lower()
    effective_renderable_formats = (renderable_formats if renderable_formats is not None else RAPIDAPI_RENDERABLE_FORMATS)
    effective_renderable_formats = str(effective_renderable_formats or "").strip()

    if platform == "youtube":
        video_id = _extract_youtube_video_id(url)
        if not video_id:
            return None, None
        params = {"videoId": video_id, "lang": "en-US"}
        if effective_url_access in {"normal", "proxied"}:
            params["urlAccess"] = effective_url_access
        if effective_renderable_formats:
            params["renderableFormats"] = effective_renderable_formats
        return "/youtube/v3/video/details", params

    if platform == "instagram":
        shortcode = _extract_instagram_shortcode(url)
        if not shortcode:
            return None, None
        params = {"shortcode": shortcode}
        if effective_renderable_formats:
            params["renderableFormats"] = effective_renderable_formats
        return "/instagram/v3/media/post/details", params

    if platform == "facebook":
        params = {"url": url}
        if effective_renderable_formats:
            params["renderableFormats"] = effective_renderable_formats
        return "/facebook/v3/post/details", params

    if platform == "tiktok":
        return "/tiktok/v3/post/details", {"url": url}

    return None, None


def _rapidapi_request(route, params):
    query = urllib.parse.urlencode(params, doseq=True, safe=":/,@")
    endpoint = f"{RAPIDAPI_BASE_URL}{route}"
    if query:
        endpoint = f"{endpoint}?{query}"
    request = urllib.request.Request(endpoint, headers=rapidapi_download_headers() or {}, method="GET")
    with urllib.request.urlopen(request, timeout=RAPIDAPI_TIMEOUT_SECONDS) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return json.loads(payload)


def _rapidapi_guess_ext(item, direct_url):
    metadata = item.get("metadata") or {}
    mime_type = (metadata.get("mime_type") or item.get("mimeType") or "").lower()
    if "webm" in mime_type:
        return "webm"
    if "mpegurl" in mime_type or "m3u8" in direct_url:
        return "mp4"
    suffix = Path(urllib.parse.urlparse(direct_url).path).suffix.lower().lstrip(".")
    if suffix in {"mp4", "webm", "mkv", "mov"}:
        return suffix
    return "mp4"


def _rapidapi_guess_height(item):
    metadata = item.get("metadata") or {}
    height = metadata.get("height") or item.get("height")
    if isinstance(height, int):
        return height
    label = str(item.get("label") or metadata.get("quality_label") or "")
    match = re.search(r"(\d{3,4})p", label.lower())
    return int(match.group(1)) if match else 0


def _rapidapi_extract_formats(payload):
    formats = []
    contents = payload.get("contents") if isinstance(payload, dict) else None
    for content in _ensure_list(contents):
        for video in _ensure_list(content.get("videos")):
            direct_url = str(video.get("url") or "").strip()
            if not direct_url:
                continue
            metadata = video.get("metadata") or {}
            quality = (
                video.get("label")
                or metadata.get("quality_label")
                or (f"{metadata.get('height')}p" if metadata.get("height") else "Best")
            )
            size_text = (
                metadata.get("content_length_text")
                or metadata.get("size")
                or video.get("size")
                or "?MB"
            )
            if not isinstance(size_text, str):
                size_text = str(size_text)
            format_id = f"ra{len(formats)}"
            formats.append(
                {
                    "format_id": format_id,
                    "quality": str(quality),
                    "ext": _rapidapi_guess_ext(video, direct_url),
                    "size": size_text if size_text else "?MB",
                    "height": _rapidapi_guess_height(video),
                    "source": "rapidapi",
                    "direct_url": direct_url,
                }
            )
            if len(formats) >= 8:
                return formats
    return formats


def rapidapi_info(url, platform=None, url_access=None, renderable_formats=None):
    platform = platform or detect_platform(url)
    if not rapidapi_enabled() or platform not in RAPIDAPI_SUPPORTED_PLATFORMS:
        return None, []

    route, params = _rapidapi_route_and_params(url, platform, url_access=url_access, renderable_formats=renderable_formats)
    if not route:
        return None, []

    try:
        payload = _rapidapi_request(route, params)
    except Exception as e:
        logger.error("RapidAPI info error: %s", e)
        return None, []

    if not isinstance(payload, dict):
        return None, []

    if payload.get("error"):
        logger.warning("RapidAPI returned error payload: %s", payload.get("error"))
        return None, []

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    additional = metadata.get("additionalData") if isinstance(metadata.get("additionalData"), dict) else {}
    author = metadata.get("author") if isinstance(metadata.get("author"), dict) else {}
    formats = _rapidapi_extract_formats(payload)

    title = (
        metadata.get("title")
        or metadata.get("videoTitle")
        or payload.get("title")
        or "Video"
    )
    uploader = (
        author.get("name")
        or metadata.get("uploader")
        or payload.get("uploader")
        or "Unknown"
    )
    thumbnail = (
        metadata.get("thumbnailUrl")
        or metadata.get("thumbnail")
        or payload.get("thumbnail")
    )
    duration = _parse_duration_seconds(
        additional.get("duration")
        or metadata.get("duration")
        or payload.get("duration")
    )
    view_count = _parse_view_count(
        additional.get("view_count")
        or metadata.get("view_count")
        or payload.get("view_count")
    )

    info = {
        "title": str(title),
        "uploader": str(uploader),
        "duration": duration,
        "view_count": view_count,
        "thumbnail": thumbnail,
        "webpage_url": url,
        "extractor": "rapidapi",
    }
    return info, formats


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
        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if not cookie_file and _is_cookie_required_error(err):
                raise CookiesRequiredError(platform) from e
            logger.error(f"yt-dlp info error: {e}")
            return None, []
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
            err = (result.stderr or result.stdout or "").strip()
            if not cookie_file and _is_cookie_required_error(err):
                raise CookiesRequiredError(platform)
            raise RuntimeError(err or "yt-dlp info command failed")
        info = json.loads(result.stdout)
        return info, _extract_formats(info)
    except CookiesRequiredError:
        raise
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
        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if not cookie_file and _is_cookie_required_error(err):
                raise CookiesRequiredError(platform) from e
            logger.error(f"yt-dlp download error: {e}")
            return None, None
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
            err = (result.stderr or result.stdout or "").strip()
            if not cookie_file and _is_cookie_required_error(err):
                raise CookiesRequiredError(platform)
            raise RuntimeError(err or "yt-dlp download command failed")

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
    except CookiesRequiredError:
        raise
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        return None, None


async def download_file(url, save_path, headers=None, timeout_seconds=60):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers or {},
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as resp:
                if 200 <= resp.status < 300:
                    async with aiofiles.open(save_path, "wb") as file_handle:
                        async for chunk in resp.content.iter_chunked(1024 * 64):
                            await file_handle.write(chunk)
                    return save_path
                logger.warning("Direct download got HTTP %s for %s", resp.status, url)
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
