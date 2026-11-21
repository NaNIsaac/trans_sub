"""OAuth for the YouTube Data API: installed-app flow, token kept in the user's config directory."""

import os
import sys
from pathlib import Path
from typing import Any

# Captions need youtube.force-ssl (or youtubepartner, for content owners); it also covers
# videos.update, so it is the one scope requested.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRET_ENV = "TRANS_SUB_YOUTUBE_CLIENT_SECRET"
TOKEN_ENV = "TRANS_SUB_YOUTUBE_TOKEN"
EXTRA_HINT = (
    "the youtube command needs the 'youtube' extra: "
    "uv sync --extra youtube (or pip install 'trans-sub[youtube]')"
)


class AuthError(RuntimeError):
    """Missing credentials or the optional Google packages."""


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "trans-sub"


def client_secret_path(flag: Path | None) -> Path:
    return flag or Path(os.environ.get(CLIENT_SECRET_ENV) or config_dir() / "youtube-client.json")


def token_path(flag: Path | None) -> Path:
    return flag or Path(os.environ.get(TOKEN_ENV) or config_dir() / "youtube-token.json")


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def youtube_service(client_secret: Path | None = None, token: Path | None = None) -> Any:
    """A YouTube Data API v3 client. The first run opens the browser to log in."""
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise AuthError(EXTRA_HINT) from None

    token_file = token_path(token)
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None  # revoked or expired refresh token: log in again
    if not creds or not creds.valid:
        secret = client_secret_path(client_secret)
        if not secret.exists():
            raise AuthError(
                "no OAuth client file: pass --client-secret or set "
                f"{CLIENT_SECRET_ENV} (see the README, 'YouTube setup')"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
        creds = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)
    _write_private(token_file, creds.to_json())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def media_upload(path: Path) -> Any:
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise AuthError(EXTRA_HINT) from None
    return MediaFileUpload(str(path), mimetype="application/octet-stream", resumable=False)
