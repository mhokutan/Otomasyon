# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, subprocess
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# ---------- env helpers ----------
def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _get_bool_env(name: str, default: bool = False) -> bool:
    v = _get_env(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

# ---------- ffprobe helpers (shorts detection) ----------
def _ffprobe(cmd_args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", *cmd_args],
            check=True, capture_output=True, text=True
        ).stdout.strip()
        return out
    except Exception:
        return ""

def _video_duration_s(path: str) -> float:
    s = _ffprobe(["-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path])
    try:
        d = float(s)
        return d if d > 0 else 0.0
    except Exception:
        return 0.0

def _video_is_vertical(path: str) -> bool:
    # returns True if height > width
    s = _ffprobe(["-select_streams", "v:0", "-show_entries", "stream=width,height",
                  "-of", "csv=p=0", path])
    try:
        w, h = [int(x) for x in s.split(",")]
        return h > w
    except Exception:
        return False

# ---------- auth ----------
def _get_creds() -> Credentials:
    client_id = _get_env("YT_CLIENT_ID")
    client_secret = _get_env("YT_CLIENT_SECRET")
    refresh_token = _get_env("YT_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("YouTube credentials missing (YT_CLIENT_ID/SECRET/REFRESH_TOKEN)")

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds

# ---------- main upload ----------
def try_upload_youtube(
    video_path: str,
    title: str,
    description: str,
    privacy_status: str = "public",
    made_for_kids: Optional[bool] = None,
) -> Optional[str]:
    """
    Uploads a video and returns its URL, or None.
    Audience (COPPA): uses `status.selfDeclaredMadeForKids`.
    Control via:
      - YT_MADE_FOR_KIDS=true|false   (default false)
      - YT_NOTIFY_SUBS=true|false     (default true)
      - YT_CATEGORY_ID=24             (default 24 - Entertainment)
    """
    privacy = (privacy_status or "public").lower()
    if privacy not in {"public", "private", "unlisted"}:
        privacy = "public"

    if made_for_kids is None:
        made_for_kids = _get_bool_env("YT_MADE_FOR_KIDS", False)

    notify_subs = _get_bool_env("YT_NOTIFY_SUBS", True)
    category_id = _get_env("YT_CATEGORY_ID", "24")  # 24=Entertainment, 25=News & Politics

    # Auto #shorts if vertical <= 60s and not already present
    try:
        dur = _video_duration_s(video_path)
        vertical = _video_is_vertical(video_path)
        is_shorts = vertical and (0.0 < dur <= 60.0)
    except Exception:
        dur, vertical, is_shorts = 0.0, False, False

    if is_shorts and "#shorts" not in title.lower():
        # keep under 100 chars
        add = " #shorts"
        title = (title + add) if len(title) + len(add) <= 95 else (title[:95 - len(add)] + add)
    if is_shorts and "#shorts" not in (description or "").lower():
        description = (description or "") + "\n\n#shorts"

    creds = _get_creds()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": (title or "")[:95],
            "description": (description or "")[:4900],
            "categoryId": str(category_id),
            # Optionally you can set defaultLanguage using env if needed
            # "defaultLanguage": _get_env("YT_DEFAULT_LANGUAGE", "en"),
        },
        "status": {
            "privacyStatus": privacy,
            # ✅ correct field to comply with COPPA:
            "selfDeclaredMadeForKids": bool(made_for_kids),
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=1024 * 1024,
        resumable=True,
        mimetype="video/mp4",
    )

    # YouTube API allows notifySubscribers as a query param:
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=notify_subs,
    )

    # basic retry loop for transient errors
    response = None
    attempts = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Upload {int(status.progress() * 100)}%")
        except HttpError as e:
            attempts += 1
            msg = getattr(e, "content", None) or str(e)
            print(f"[upload] HttpError attempt {attempts}: {msg}")
            if attempts >= 5:
                raise
            time.sleep(min(2 ** attempts, 30))
        except Exception as e:
            attempts += 1
            print(f"[upload] Error attempt {attempts}: {e}")
            if attempts >= 5:
                raise
            time.sleep(min(2 ** attempts, 30))

    video_id = (response or {}).get("id")
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else None
