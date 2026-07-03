"""Selectel S3 upload utility for ARTIFACT arcade.

Provides reliable file uploads to Selectel Object Storage with public URLs
for QR code generation. Used by photobooth, ai_prophet, roast, fortune,
zodiac, and rapgod modes.

Storage: vnvnc bucket on Selectel S3 (ru-7 region)
Path: artifact/{type}/{filename}
Public URL: https://e6aaa51f-863a-439e-9b6e-69991ff0ad6e.selstorage.ru/artifact/...
"""

import json
import logging
import subprocess
import uuid
import tempfile
import threading
import shutil
import os
import configparser
import hashlib
import hmac
from urllib.parse import quote, urlparse
from datetime import datetime, timezone
from typing import Optional, Callable, Any
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

S3_MAIN_UPLOAD_TIMEOUT = 180
S3_REDIRECT_UPLOAD_TIMEOUT = 45
S3_MANIFEST_TIMEOUT = 180
S3_UPLOAD_RETRIES = 3
AWS_COMMAND_LOCK = threading.Lock()

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent
UPLOAD_SPOOL_DIR = _PROJECT_ROOT / "data" / "upload_spool"

# Check AWS CLI availability - include common macOS paths
def _find_aws_cli() -> Optional[str]:
    """Find AWS CLI binary, checking common paths on macOS."""
    # First try standard PATH lookup
    aws_path = shutil.which('aws')
    if aws_path:
        return aws_path

    # Check common macOS paths not always in PATH when launched from GUI
    common_paths = [
        '/opt/homebrew/bin/aws',  # Apple Silicon Homebrew
        '/usr/local/bin/aws',      # Intel Homebrew
        '/usr/bin/aws',            # System
    ]
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None

AWS_CLI_PATH = _find_aws_cli()
AWS_CLI_AVAILABLE = AWS_CLI_PATH is not None
if not AWS_CLI_AVAILABLE:
    logger.warning("AWS CLI not found - S3 uploads will use direct HTTPS fallback")


def _prepare_aws_args(args: list[str]) -> list[str]:
    """Run AWS as the arcade user from the root hardware service."""
    if (
        os.getenv("ARTIFACT_ENV") == "hardware"
        and hasattr(os, "geteuid")
        and os.geteuid() == 0
        and os.path.isdir("/home/kirniy")
        and os.path.exists("/usr/bin/sudo")
    ):
        return [
            "/usr/bin/sudo",
            "-u",
            "kirniy",
            "-H",
            "env",
            "HOME=/home/kirniy",
            *args,
        ]

    return args


def _aws_home_dir() -> Path:
    if (
        os.getenv("ARTIFACT_ENV") == "hardware"
        and os.path.isdir("/home/kirniy")
    ):
        return Path("/home/kirniy")
    return Path(os.path.expanduser("~"))


def _load_selectel_credentials() -> Optional[dict[str, str]]:
    credentials_path = _aws_home_dir() / ".aws" / "credentials"
    if not credentials_path.exists():
        return None

    parser = configparser.RawConfigParser()
    parser.read(credentials_path)
    if not parser.has_section("selectel"):
        return None

    access_key = parser.get("selectel", "aws_access_key_id", fallback="").strip()
    secret_key = parser.get("selectel", "aws_secret_access_key", fallback="").strip()
    session_token = parser.get("selectel", "aws_session_token", fallback="").strip()
    if not access_key or not secret_key:
        return None

    return {
        "access_key": access_key,
        "secret_key": secret_key,
        "session_token": session_token,
    }


def _signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    def sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    date_key = sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    region_key = sign(date_key, region)
    service_key = sign(region_key, service)
    return sign(service_key, "aws4_request")


def _upload_local_path_to_s3_direct(
    local_path: str,
    s3_key: str,
    content_type: str,
    *,
    cache_control: Optional[str] = None,
) -> subprocess.CompletedProcess[bytes]:
    """Upload directly with SigV4 HTTPS PUT, bypassing AWS CLI transport issues."""
    if not HAS_REQUESTS:
        return subprocess.CompletedProcess([], 1, b"", b"requests is not installed")

    credentials = _load_selectel_credentials()
    if credentials is None:
        return subprocess.CompletedProcess([], 1, b"", b"Selectel credentials not found")

    parsed = urlparse(SELECTEL_ENDPOINT)
    host = parsed.netloc
    encoded_key = quote(s3_key, safe="/")
    canonical_uri = f"/{SELECTEL_BUCKET}/{encoded_key}"
    url = f"{SELECTEL_ENDPOINT}{canonical_uri}"
    payload = Path(local_path).read_bytes()
    payload_hash = hashlib.sha256(payload).hexdigest()
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers = {
        "content-type": content_type,
        "host": host,
        "x-amz-acl": "public-read",
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if cache_control:
        headers["cache-control"] = cache_control
    if credentials["session_token"]:
        headers["x-amz-security-token"] = credentials["session_token"]

    signed_header_names = sorted(headers)
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in signed_header_names)
    signed_headers = ";".join(signed_header_names)
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/ru-7/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(credentials["secret_key"], date_stamp, "ru-7", "s3"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={credentials['access_key']}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    try:
        with AWS_COMMAND_LOCK:
            response = requests.put(url, data=payload, headers=headers, timeout=S3_MAIN_UPLOAD_TIMEOUT)
        if 200 <= response.status_code < 300:
            return subprocess.CompletedProcess([], 0, response.content, b"")
        return subprocess.CompletedProcess(
            [],
            response.status_code,
            response.content,
            f"HTTP {response.status_code}: {response.text[:500]}".encode("utf-8", errors="replace"),
        )
    except Exception as e:
        return subprocess.CompletedProcess([], 1, b"", str(e).encode("utf-8", errors="replace"))


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(
        f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}"
        for key, value in sorted(params.items())
    )


def _signed_s3_get(params: dict[str, str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    """Run a direct signed S3 GET request, used when AWS CLI is unavailable."""
    if not HAS_REQUESTS:
        return subprocess.CompletedProcess([], 1, b"", b"requests is not installed")

    credentials = _load_selectel_credentials()
    if credentials is None:
        return subprocess.CompletedProcess([], 1, b"", b"Selectel credentials not found")

    parsed = urlparse(SELECTEL_ENDPOINT)
    host = parsed.netloc
    canonical_uri = f"/{SELECTEL_BUCKET}"
    canonical_query = _canonical_query(params)
    url = f"{SELECTEL_ENDPOINT}{canonical_uri}?{canonical_query}"
    payload_hash = hashlib.sha256(b"").hexdigest()
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if credentials["session_token"]:
        headers["x-amz-security-token"] = credentials["session_token"]

    signed_header_names = sorted(headers)
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in signed_header_names)
    signed_headers = ";".join(signed_header_names)
    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/ru-7/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(credentials["secret_key"], date_stamp, "ru-7", "s3"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={credentials['access_key']}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    try:
        with AWS_COMMAND_LOCK:
            response = requests.get(url, headers=headers, timeout=timeout)
        if 200 <= response.status_code < 300:
            return subprocess.CompletedProcess([], 0, response.content, b"")
        return subprocess.CompletedProcess(
            [],
            response.status_code,
            response.content,
            f"HTTP {response.status_code}: {response.text[:500]}".encode("utf-8", errors="replace"),
        )
    except Exception as e:
        return subprocess.CompletedProcess([], 1, b"", str(e).encode("utf-8", errors="replace"))


def _list_s3_objects_direct(prefix: str, max_items: int) -> subprocess.CompletedProcess[bytes]:
    """List S3 objects with direct SigV4 HTTPS requests and return AWS-CLI-like JSON."""
    contents: list[dict[str, Any]] = []
    continuation_token: Optional[str] = None

    while len(contents) < max_items:
        params = {
            "list-type": "2",
            "max-keys": str(min(1000, max_items - len(contents))),
            "prefix": prefix,
        }
        if continuation_token:
            params["continuation-token"] = continuation_token

        result = _signed_s3_get(params, timeout=S3_MANIFEST_TIMEOUT)
        if result.returncode != 0:
            return result

        root = ET.fromstring(result.stdout)
        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}", 1)[0] + "}"

        for item in root.findall(f"{namespace}Contents"):
            key = item.findtext(f"{namespace}Key") or ""
            last_modified = item.findtext(f"{namespace}LastModified") or ""
            size_text = item.findtext(f"{namespace}Size") or "0"
            contents.append(
                {
                    "Key": key,
                    "LastModified": last_modified,
                    "Size": int(size_text),
                }
            )
            if len(contents) >= max_items:
                break

        is_truncated = (root.findtext(f"{namespace}IsTruncated") or "").lower() == "true"
        continuation_token = root.findtext(f"{namespace}NextContinuationToken")
        if not is_truncated or not continuation_token:
            break

    payload = json.dumps({"Contents": contents}, ensure_ascii=False).encode("utf-8")
    return subprocess.CompletedProcess([], 0, payload, b"")

# Selectel S3 configuration
SELECTEL_ENDPOINT = "https://s3.ru-7.storage.selcloud.ru"
SELECTEL_BUCKET = "vnvnc"
SELECTEL_PREFIX = "artifact"
SELECTEL_PUBLIC_URL = "https://e6aaa51f-863a-439e-9b6e-69991ff0ad6e.selstorage.ru"

# Try importing QR code library
try:
    import qrcode
    from PIL import Image
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    logger.warning("qrcode library not available - QR codes will not be generated")


@dataclass
class UploadResult:
    """Result of an upload operation."""
    success: bool
    url: Optional[str] = None
    short_url: Optional[str] = None  # vnvnc.ru/p/{id} redirect URL
    short_id: Optional[str] = None   # Just the short ID part
    qr_image: Optional[np.ndarray] = None
    error: Optional[str] = None


def generate_filename(prefix: str, extension: str = "jpg") -> str:
    """Generate a unique filename with timestamp and UUID.

    Args:
        prefix: Type prefix (e.g., 'photo', 'caricature', 'roast', 'track')
        extension: File extension without dot

    Returns:
        Unique filename like 'caricature_20251227_123456_a1b2c3d4.jpg'
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{unique_id}.{extension}"


@dataclass
class PreUploadInfo:
    """Pre-generated upload information for rendering labels before upload.

    This allows rendering the label with the QR code/URL before uploading,
    so the uploaded image can be the complete rendered label.
    """
    filename: str
    short_id: str
    short_url: str
    s3_key: str
    full_url: str


@dataclass
class PendingUpload:
    """Persisted upload job kept on disk until S3 confirms success."""

    prefix: str
    filename: str
    extension: str
    content_type: str
    s3_key: str
    file_path: str
    meta_path: str
    short_id: Optional[str] = None
    metadata: dict[str, Any] | None = None


def _ensure_spool_dir(prefix: str) -> Path:
    path = UPLOAD_SPOOL_DIR / prefix
    path.mkdir(parents=True, exist_ok=True)
    for target in (UPLOAD_SPOOL_DIR, path):
        try:
            target.chmod(0o777)
        except OSError:
            logger.debug("Could not chmod spool dir %s", target, exc_info=True)
    return path


def _pending_paths(prefix: str, filename: str) -> tuple[Path, Path]:
    spool_dir = _ensure_spool_dir(prefix)
    return spool_dir / filename, spool_dir / f"{filename}.json"


def _create_pending_upload(
    data: bytes,
    *,
    prefix: str,
    filename: str,
    extension: str,
    content_type: str,
    s3_key: str,
    short_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> PendingUpload:
    file_path, meta_path = _pending_paths(prefix, filename)

    if not file_path.exists():
        file_path.write_bytes(data)

    meta = {
        "prefix": prefix,
        "filename": filename,
        "extension": extension,
        "content_type": content_type,
        "s3_key": s3_key,
        "short_id": short_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_path": str(file_path),
        "metadata": metadata or {},
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return PendingUpload(
        prefix=prefix,
        filename=filename,
        extension=extension,
        content_type=content_type,
        s3_key=s3_key,
        short_id=short_id,
        file_path=str(file_path),
        meta_path=str(meta_path),
        metadata=metadata or {},
    )


def _load_pending_upload(meta_path: Path) -> Optional[PendingUpload]:
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        file_path = Path(payload["file_path"])
        if not file_path.exists():
            logger.warning("Pending upload payload missing: %s", file_path)
            return None
        return PendingUpload(
            prefix=payload["prefix"],
            filename=payload["filename"],
            extension=payload["extension"],
            content_type=payload["content_type"],
            s3_key=payload["s3_key"],
            short_id=payload.get("short_id"),
            file_path=str(file_path),
            meta_path=str(meta_path),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except Exception as e:
        logger.warning("Failed to read pending upload %s: %s", meta_path, e)
        return None


def _delete_pending_upload(pending: PendingUpload) -> None:
    for path_str in (pending.file_path, pending.meta_path):
        try:
            Path(path_str).unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.warning("Failed to remove pending upload artifact %s: %s", path_str, e)


def pre_generate_upload_info(prefix: str, extension: str = "png") -> PreUploadInfo:
    """Pre-generate upload info including short URL before actual upload.

    Use this when you need to render a label with the QR code/URL
    before uploading the final image.

    Args:
        prefix: Type prefix (e.g., 'photobooth', 'roast')
        extension: File extension

    Returns:
        PreUploadInfo with filename, short_id, short_url, etc.
    """
    filename = generate_filename(prefix, extension)
    short_id = filename.rsplit('_', 1)[-1].rsplit('.', 1)[0]
    s3_key = f"{SELECTEL_PREFIX}/{prefix}/{filename}"
    full_url = f"{SELECTEL_PUBLIC_URL}/{s3_key}"
    short_url = f"https://vnvnc.ru/p/{short_id}"

    return PreUploadInfo(
        filename=filename,
        short_id=short_id,
        short_url=short_url,
        s3_key=s3_key,
        full_url=full_url,
    )


def _create_redirect_html(target_url: str, title: str = "VNVNC Arcade") -> str:
    """Create an HTML redirect page.

    Args:
        target_url: Full URL to redirect to
        title: Page title

    Returns:
        HTML content as string
    """
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            background: #0a0a0a;
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }}
        .loader {{
            text-align: center;
        }}
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid #333;
            border-top-color: #ff6b35;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        a {{
            color: #ff6b35;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="loader">
        <div class="spinner"></div>
        <p>ФОТО ГОТОВИТСЯ...</p>
        <p id="status">ПРОВЕРЯЕМ ФАЙЛ...</p>
        <p><a href="{target_url}">Нажмите, если не перенаправлено</a></p>
    </div>
    <script>
        const targetUrl = {json.dumps(target_url)};
        const statusEl = document.getElementById("status");
        const isImageTarget = /\\.(png|jpe?g|webp|gif)(\\?|$)/i.test(targetUrl);

        function redirectNow() {{
            window.location.replace(targetUrl);
        }}

        function pollForImage(delayMs) {{
            const probe = new Image();
            probe.onload = () => {{
                statusEl.textContent = "ПЕРЕХОДИМ К ФОТО...";
                redirectNow();
            }};
            probe.onerror = () => {{
                statusEl.textContent = "ФОТО ЕЩЕ ЗАГРУЖАЕТСЯ...";
                window.setTimeout(() => pollForImage(Math.min(delayMs + 500, 5000)), delayMs);
            }};
            probe.src = targetUrl + (targetUrl.includes("?") ? "&" : "?") + "wait=" + Date.now();
        }}

        if (isImageTarget) {{
            pollForImage(1000);
        }} else {{
            statusEl.textContent = "ПОДГОТАВЛИВАЕМ ССЫЛКУ...";
            window.setTimeout(redirectNow, 1200);
        }}
    </script>
</body>
</html>'''


def _run_aws_command(
    args: list[str],
    *,
    timeout: int,
    retries: int = 1,
    retry_delay_sec: float = 2.0,
) -> subprocess.CompletedProcess[bytes]:
    """Run an AWS CLI command with bounded retries for flaky network conditions."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with AWS_COMMAND_LOCK:
                return subprocess.run(_prepare_aws_args(args), capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            logger.warning(
                "AWS command timed out on attempt %s/%s after %ss: %s",
                attempt,
                retries,
                timeout,
                " ".join(args[0:6]),
            )
            if attempt < retries:
                threading.Event().wait(retry_delay_sec * attempt)
    assert last_error is not None
    raise last_error


def _upload_local_path_to_s3(
    local_path: str,
    s3_key: str,
    content_type: str,
    *,
    timeout: int = S3_MAIN_UPLOAD_TIMEOUT,
    cache_control: Optional[str] = None,
) -> subprocess.CompletedProcess[bytes]:
    """Upload an existing local file to the configured S3 key."""
    if not AWS_CLI_AVAILABLE:
        return _upload_local_path_to_s3_direct(
            local_path,
            s3_key,
            content_type,
            cache_control=cache_control,
        )

    args = [
        AWS_CLI_PATH,
        '--endpoint-url',
        SELECTEL_ENDPOINT,
        '--profile',
        'selectel',
        's3',
        'cp',
        local_path,
        f's3://{SELECTEL_BUCKET}/{s3_key}',
        '--acl',
        'public-read',
        '--content-type',
        content_type,
    ]
    if cache_control:
        args.extend(["--cache-control", cache_control])

    result = _run_aws_command(args, timeout=timeout, retries=S3_UPLOAD_RETRIES)
    if result.returncode == 0:
        return result

    stderr = result.stderr.decode(errors="replace") if result.stderr else ""
    logger.warning("AWS CLI upload failed for %s; trying direct HTTPS fallback: %s", s3_key, stderr[:500])
    return _upload_local_path_to_s3_direct(
        local_path,
        s3_key,
        content_type,
        cache_control=cache_control,
    )


def _upload_redirect_html(short_id: str, target_url: str) -> bool:
    """Upload a redirect HTML file to S3.

    Creates p/{short_id} (a file, not directory) that redirects to target_url.
    This enables short URLs like vnvnc.ru/p/{short_id}

    Note: We upload as a file (not index.html in a directory) because S3 doesn't
    auto-serve index.html for directory requests.

    Args:
        short_id: The short identifier (8 hex chars)
        target_url: Full URL to redirect to

    Returns:
        True if successful, False otherwise
    """
    try:
        html_content = _create_redirect_html(target_url)
        # Upload as a file directly (not index.html) so S3 serves it without directory handling
        s3_key = f"p/{short_id}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name
        os.chmod(tmp_path, 0o644)

        result = _upload_local_path_to_s3(
            tmp_path,
            s3_key,
            'text/html; charset=utf-8',
            timeout=S3_REDIRECT_UPLOAD_TIMEOUT,
        )

        try:
            os.unlink(tmp_path)
        except:
            pass

        if result.returncode == 0:
            logger.info(f"Redirect HTML uploaded: vnvnc.ru/p/{short_id}")
            return True
        else:
            logger.warning(f"Failed to upload redirect HTML: {result.stderr.decode()}")
            return False

    except Exception as e:
        logger.warning(f"Failed to create redirect: {e}")
        return False


def provision_short_url_redirect(pre_info: PreUploadInfo) -> bool:
    """Create/update the short redirect URL before or after the main upload."""
    return _upload_redirect_html(pre_info.short_id, pre_info.full_url)


def refresh_public_photo_manifest(prefix: str = "photobooth", max_items: int = 5000) -> bool:
    """Publish a public manifest for gallery consumers."""
    if _load_selectel_credentials() is None:
        logger.warning("Cannot refresh manifest: AWS credentials not configured")
        return False

    list_prefix = f"{SELECTEL_PREFIX}/{prefix}/"
    manifest_key = f"{list_prefix}manifest.json"

    try:
        if AWS_CLI_AVAILABLE:
            result = _run_aws_command(
                [
                    AWS_CLI_PATH,
                    "--endpoint-url",
                    SELECTEL_ENDPOINT,
                    "--profile",
                    "selectel",
                    "s3api",
                    "list-objects-v2",
                    "--bucket",
                    SELECTEL_BUCKET,
                    "--prefix",
                    list_prefix,
                    "--page-size",
                    "1000",
                    "--max-items",
                    str(max_items),
                    "--output",
                    "json",
                ],
                timeout=S3_MANIFEST_TIMEOUT,
                retries=2,
            )
        else:
            result = _list_s3_objects_direct(list_prefix, max_items)

        if result.returncode != 0:
            stderr = result.stderr.decode() if result.stderr else ""
            logger.warning("Failed to list S3 objects for manifest refresh: %s", stderr)
            return False

        payload = json.loads(result.stdout.decode() or "{}")
        contents = payload.get("Contents") or []
        photos = []

        for item in contents:
            key = item.get("Key") or ""
            size = int(item.get("Size") or 0)
            if not key or key == manifest_key or key.endswith("/") or size < 1000:
                continue
            if not key.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            photos.append(
                {
                    "key": key,
                    "url": f"{SELECTEL_PUBLIC_URL}/{key}",
                    "lastModified": item.get("LastModified") or "",
                    "size": size,
                }
            )

        photos.sort(key=lambda photo: photo["lastModified"], reverse=True)
        manifest = {
            "photos": photos[:max_items],
            "total": len(photos),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
            tmp_path = tmp.name
        os.chmod(tmp_path, 0o644)

        upload = _upload_local_path_to_s3(
            tmp_path,
            manifest_key,
            "application/json; charset=utf-8",
            timeout=S3_MANIFEST_TIMEOUT,
            cache_control="no-cache, no-store, must-revalidate",
        )

        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        if upload.returncode != 0:
            stderr = upload.stderr.decode() if upload.stderr else ""
            logger.warning("Failed to upload public manifest: %s", stderr)
            return False

        logger.info("Refreshed public %s manifest with %s photos", prefix, len(photos))
        return True
    except Exception as e:
        logger.warning("Manifest refresh failed: %s", e)
        return False


def retry_pending_uploads(prefix: Optional[str] = None, limit: int = 50) -> dict:
    """Retry persisted uploads left behind by earlier failures."""
    if not UPLOAD_SPOOL_DIR.exists():
        return {"retried": 0, "succeeded": 0, "failed": 0}

    meta_files: list[Path] = []
    if prefix:
        meta_files.extend(sorted((UPLOAD_SPOOL_DIR / prefix).glob("*.json")))
    else:
        meta_files.extend(sorted(UPLOAD_SPOOL_DIR.glob("*/*.json")))

    retried = 0
    succeeded = 0
    failed = 0
    manifest_prefixes: set[str] = set()

    for meta_path in meta_files[:limit]:
        pending = _load_pending_upload(meta_path)
        if pending is None:
            failed += 1
            continue

        retried += 1
        try:
            result = _upload_local_path_to_s3(pending.file_path, pending.s3_key, pending.content_type)
            if result.returncode != 0:
                failed += 1
                stderr = result.stderr.decode() if result.stderr else ""
                logger.warning("Pending upload failed for %s: %s", pending.filename, stderr)
                continue

            url = f"{SELECTEL_PUBLIC_URL}/{pending.s3_key}"
            short_url = f"https://vnvnc.ru/p/{pending.short_id}" if pending.short_id else None
            if pending.short_id:
                _upload_redirect_html(pending.short_id, url)
            if pending.prefix == "photobooth":
                manifest_prefixes.add(pending.prefix)
                try:
                    from artifact.telegram.events import append_bot_event

                    append_bot_event(
                        "photobooth_photo",
                        {
                            "success": True,
                            "mode": "photobooth",
                            "theme_id": "",
                            "theme_name": "Photobooth",
                            "url": url,
                            "short_url": short_url,
                            "short_id": pending.short_id,
                            "filename": pending.filename,
                            "result_bytes": Path(pending.file_path).stat().st_size,
                            "source_photo_bytes": 0,
                            "uploaded_by": "upload_spool_daemon",
                            **(pending.metadata or {}),
                        },
                    )
                except Exception:
                    logger.debug("Could not append Telegram success event for pending upload", exc_info=True)

            _delete_pending_upload(pending)
            succeeded += 1
            logger.info("Retried pending upload successfully: %s", pending.filename)
        except Exception as e:
            failed += 1
            logger.warning("Pending upload retry failed for %s: %s", pending.filename, e)

    for manifest_prefix in manifest_prefixes:
        refresh_public_photo_manifest(prefix=manifest_prefix)

    return {"retried": retried, "succeeded": succeeded, "failed": failed}


def generate_qr_image(url: str, size: int = 60) -> Optional[np.ndarray]:
    """Generate a QR code image for the given URL.

    Args:
        url: URL to encode in QR code
        size: Output image size in pixels (square)

    Returns:
        RGB numpy array of QR code image, or None if generation fails
    """
    if not HAS_QRCODE or not url:
        return None

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=2,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="white", back_color="black")
        img = img.convert('RGB')
        img = img.resize((size, size), Image.NEAREST)

        return np.array(img, dtype=np.uint8)
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return None


def _queued_upload_result(s3_key: str, short_id: str) -> UploadResult:
    """Return the already reserved public URL while the durable spool drains."""
    url = f"{SELECTEL_PUBLIC_URL}/{s3_key}"
    short_url = f"https://vnvnc.ru/p/{short_id}"
    qr_image = generate_qr_image(short_url)
    return UploadResult(success=True, url=url, short_url=short_url, short_id=short_id, qr_image=qr_image)


def upload_bytes_to_s3(
    data: bytes,
    prefix: str,
    extension: str = "jpg",
    content_type: str = "image/jpeg",
    pre_info: Optional[PreUploadInfo] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> UploadResult:
    """Upload bytes to Selectel S3 synchronously.

    Args:
        data: File content as bytes
        prefix: Type prefix for filename (e.g., 'caricature', 'photo')
        extension: File extension
        content_type: MIME type for the file
        pre_info: Optional pre-generated upload info (from pre_generate_upload_info)
                  Use this when you need to render a label with the URL before upload.

    Returns:
        UploadResult with success status, URL, and optional QR image
    """
    if _load_selectel_credentials() is None:
        error = "AWS credentials not configured. Run: ~/modular-arcade/scripts/setup-aws-s3.sh"
        logger.error(error)
        return UploadResult(success=False, error=error)

    try:
        # Use pre-generated info if provided, otherwise generate new
        if pre_info:
            filename = pre_info.filename
            s3_key = pre_info.s3_key
        else:
            filename = generate_filename(prefix, extension)
            s3_key = f"{SELECTEL_PREFIX}/{prefix}/{filename}"
        short_id = filename.rsplit('_', 1)[-1].rsplit('.', 1)[0]
        pending = _create_pending_upload(
            data,
            prefix=prefix,
            filename=filename,
            extension=extension,
            content_type=content_type,
            s3_key=s3_key,
            short_id=short_id,
            metadata=metadata,
        )

        logger.info(f"Uploading to Selectel S3: {s3_key} ({len(data)} bytes)")

        result = _upload_local_path_to_s3(pending.file_path, s3_key, content_type)

        if result.returncode == 0:
            url = f"{SELECTEL_PUBLIC_URL}/{s3_key}"
            short_url = f"https://vnvnc.ru/p/{short_id}"
            qr_image = generate_qr_image(short_url)
            if prefix == "photobooth":
                threading.Thread(
                    target=refresh_public_photo_manifest,
                    kwargs={"prefix": prefix},
                    daemon=True,
                ).start()
            if pre_info is not None:
                threading.Thread(
                    target=provision_short_url_redirect,
                    args=(pre_info,),
                    daemon=True,
                ).start()
            else:
                threading.Thread(
                    target=_upload_redirect_html,
                    args=(short_id, url),
                    daemon=True,
                ).start()
            _delete_pending_upload(pending)
            logger.info(f"Upload successful: {url} (short: {short_url})")
            return UploadResult(success=True, url=url, short_url=short_url, short_id=short_id, qr_image=qr_image)
        else:
            stderr = result.stderr.decode() if result.stderr else ""
            # Provide helpful error messages
            if "could not be found" in stderr or "NoCredentialProviders" in stderr:
                error = "AWS 'selectel' profile not configured. Run: ~/modular-arcade/scripts/setup-aws-s3.sh"
            elif "AccessDenied" in stderr:
                error = "S3 access denied - check your Selectel credentials"
            elif "NoSuchBucket" in stderr:
                error = f"S3 bucket '{SELECTEL_BUCKET}' not found"
            else:
                error = stderr or "Unknown error"
            logger.error(f"S3 upload failed: {error}")
            if pre_info is not None or (Path(pending.file_path).exists() and Path(pending.meta_path).exists()):
                logger.warning(
                    "Initial S3 upload failed for %s, but durable spool owns this upload; "
                    "returning reserved URL while upload_spool_daemon retries: %s",
                    s3_key,
                    error,
                )
                return _queued_upload_result(s3_key, short_id)
            return UploadResult(success=False, error=error)

    except subprocess.TimeoutExpired:
        logger.error("Upload timed out after %s seconds after %s attempts - check network connection", S3_MAIN_UPLOAD_TIMEOUT, S3_UPLOAD_RETRIES)
        return UploadResult(success=False, error="Upload timeout - check network")
    except FileNotFoundError:
        if "s3_key" in locals() and "short_id" in locals() and pre_info is not None:
            logger.warning(
                "Initial S3 upload helper could not access the pending file for %s; "
                "returning reserved URL because the durable spool will retry",
                s3_key,
            )
            return _queued_upload_result(s3_key, short_id)
        error = "AWS CLI not found. Run: sudo apt install awscli"
        logger.error(error)
        return UploadResult(success=False, error=error)
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        return UploadResult(success=False, error=str(e))


def upload_file_to_s3(
    file_path: str,
    prefix: str,
    extension: str = "jpg",
    content_type: str = "image/jpeg"
) -> UploadResult:
    """Upload a file to Selectel S3 synchronously.

    Args:
        file_path: Path to file to upload
        prefix: Type prefix for S3 key (e.g., 'photo', 'track')
        extension: File extension
        content_type: MIME type

    Returns:
        UploadResult with success status, URL, and optional QR image
    """
    if _load_selectel_credentials() is None:
        error = "AWS credentials not configured. Run: ~/modular-arcade/scripts/setup-aws-s3.sh"
        logger.error(error)
        return UploadResult(success=False, error=error)

    try:
        filename = generate_filename(prefix, extension)
        s3_key = f"{SELECTEL_PREFIX}/{prefix}/{filename}"

        # Get file size for logging
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading file to Selectel S3: {s3_key} ({file_size} bytes)")
        except:
            logger.info(f"Uploading file to Selectel S3: {s3_key}")

        result = _upload_local_path_to_s3(
            file_path,
            s3_key,
            content_type,
            timeout=90,
        )

        if result.returncode == 0:
            url = f"{SELECTEL_PUBLIC_URL}/{s3_key}"

            # Extract short_id from filename (the 8-char UUID portion)
            # Filename format: prefix_20251227_123456_a1b2c3d4.jpg
            short_id = filename.rsplit('_', 1)[-1].rsplit('.', 1)[0]
            short_url = None

            # Upload redirect HTML for short URL
            if _upload_redirect_html(short_id, url):
                short_url = f"https://vnvnc.ru/p/{short_id}"

            # Generate QR code for the short URL if available, otherwise full URL
            qr_image = generate_qr_image(short_url or url)
            logger.info(f"Upload successful: {url} (short: {short_url})")
            return UploadResult(success=True, url=url, short_url=short_url, short_id=short_id, qr_image=qr_image)
        else:
            stderr = result.stderr.decode() if result.stderr else ""
            # Provide helpful error messages
            if "could not be found" in stderr or "NoCredentialProviders" in stderr:
                error = "AWS 'selectel' profile not configured. Run: ~/modular-arcade/scripts/setup-aws-s3.sh"
            elif "AccessDenied" in stderr:
                error = "S3 access denied - check your Selectel credentials"
            elif "NoSuchBucket" in stderr:
                error = f"S3 bucket '{SELECTEL_BUCKET}' not found"
            else:
                error = stderr or "Unknown error"
            logger.error(f"S3 upload failed: {error}")
            return UploadResult(success=False, error=error)

    except subprocess.TimeoutExpired:
        logger.error("Upload timed out after 30 seconds - check network connection")
        return UploadResult(success=False, error="Upload timeout - check network")
    except FileNotFoundError:
        error = "AWS CLI not found. Run: sudo apt install awscli"
        logger.error(error)
        return UploadResult(success=False, error=error)
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        return UploadResult(success=False, error=str(e))


class AsyncUploader:
    """Background uploader for non-blocking uploads.

    Usage:
        uploader = AsyncUploader()
        uploader.upload_bytes(image_bytes, 'caricature', callback=on_complete)

        # Later check result:
        if uploader.is_complete:
            result = uploader.result
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[UploadResult] = None
        self._callback: Optional[Callable[[UploadResult], None]] = None

    @property
    def is_complete(self) -> bool:
        """Check if upload is complete."""
        return self._result is not None

    @property
    def is_uploading(self) -> bool:
        """Check if upload is in progress."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def result(self) -> Optional[UploadResult]:
        """Get upload result (None if not complete)."""
        return self._result

    def upload_bytes(
        self,
        data: bytes,
        prefix: str,
        extension: str = "jpg",
        content_type: str = "image/jpeg",
        callback: Optional[Callable[[UploadResult], None]] = None,
        pre_info: Optional[PreUploadInfo] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Start background upload of bytes.

        Args:
            data: File content
            prefix: Type prefix for filename
            extension: File extension
            content_type: MIME type
            callback: Optional callback when complete
            pre_info: Optional pre-generated upload info (for rendering labels with URL before upload)
        """
        self._result = None
        self._callback = callback

        def _upload():
            result = upload_bytes_to_s3(data, prefix, extension, content_type, pre_info=pre_info, metadata=metadata)
            if prefix != "photobooth":
                try:
                    retry_pending_uploads(prefix=prefix, limit=10)
                except Exception as e:
                    logger.warning(f"Pending upload retry pass failed: {e}")
            self._result = result
            if self._callback:
                try:
                    self._callback(result)
                except Exception as e:
                    logger.error(f"Upload callback failed: {e}")

        self._thread = threading.Thread(target=_upload, daemon=True)
        self._thread.start()

    def upload_file(
        self,
        file_path: str,
        prefix: str,
        extension: str = "jpg",
        content_type: str = "image/jpeg",
        callback: Optional[Callable[[UploadResult], None]] = None
    ) -> None:
        """Start background upload of file.

        Args:
            file_path: Path to file
            prefix: Type prefix for S3 key
            extension: File extension
            content_type: MIME type
            callback: Optional callback when complete
        """
        self._result = None
        self._callback = callback

        def _upload():
            result = upload_file_to_s3(file_path, prefix, extension, content_type)
            self._result = result
            if self._callback:
                try:
                    self._callback(result)
                except Exception as e:
                    logger.error(f"Upload callback failed: {e}")

        self._thread = threading.Thread(target=_upload, daemon=True)
        self._thread.start()

    def wait(self, timeout: float = 30.0) -> Optional[UploadResult]:
        """Wait for upload to complete.

        Args:
            timeout: Max seconds to wait

        Returns:
            UploadResult or None if timeout
        """
        if self._thread:
            self._thread.join(timeout=timeout)
        return self._result
