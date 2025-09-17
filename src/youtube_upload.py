# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, mimetypes, pathlib, time
import re
from typing import Optional, List, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _get_bool_env(name: str, default: bool=False) -> bool:
    v=_env(name)
    return default if v is None else str(v).strip().lower() in ("1","true","yes","on")

def _get_float_env(name: str, default: float) -> float:
    v = _env(name)
    if v is None:
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default

# Default scopes allow uploads and basic read access so we can fetch
# channel metadata/status during debug checks.
SCOPES: List[str] = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

YT_DEBUG: bool = _get_bool_env("YT_DEBUG", False)

def _configured_scopes() -> List[str]:
    raw = _env("YT_SCOPES")
    if raw is None:
        return SCOPES
    tokens = re.split(r"[,\s]+", raw)
    scopes = [part.strip() for part in tokens if part.strip()]
    return scopes or SCOPES

def _dump_json(path: str, obj: Any) -> None:
    os.makedirs("out", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _creds() -> Credentials:
    cid=_env("YT_CLIENT_ID"); csec=_env("YT_CLIENT_SECRET"); rtok=_env("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("YouTube OAuth bilgileri eksik (YT_CLIENT_ID/SECRET/REFRESH_TOKEN).")
    scopes = _configured_scopes()
    cred = Credentials(
        None, refresh_token=rtok, token_uri="https://oauth2.googleapis.com/token",
        client_id=cid, client_secret=csec, scopes=scopes
    )
    try:
        cred.refresh(Request())
    except RefreshError as exc:
        error_payload: Dict[str, Any] = {"error": str(exc)}
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = getattr(response, "status", None)
            if status_code is None:
                status_code = getattr(response, "status_code", None)
            if status_code is not None:
                error_payload["status_code"] = status_code
            body: Optional[Any] = None
            try:
                body = response.json()
            except Exception:
                text = getattr(response, "text", None)
                if text is None:
                    content = getattr(response, "content", None)
                    if isinstance(content, bytes):
                        text = content.decode("utf-8", errors="replace")
                if text is not None:
                    error_payload["response_text"] = text
            else:
                error_payload["response"] = body
        _dump_json("out/youtube_error.json", error_payload)
        raise RuntimeError("YouTube OAuth token refresh failed; see out/youtube_error.json") from exc
    return cred

def validate_refresh_token() -> bool:
    """Refresh the stored credentials and confirm the refresh token is usable."""
    creds = _creds()
    if not creds.valid:
        raise RuntimeError("YouTube OAuth credentials are not valid after refresh.")
    return True

def _who_am_i(youtube) -> Dict[str, Any]:
    ch = youtube.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()
    if YT_DEBUG:
        _dump_json("out/youtube_me.json", ch)
    return ch

def _check_video_status(youtube, video_id: str) -> Dict[str, Any]:
    # uploadStatus / privacyStatus vs. kontrol
    info = youtube.videos().list(part="status,snippet", id=video_id).execute()
    _dump_json("out/youtube_status.json", info)
    return info

def try_upload_youtube(
    video_path: str,
    title: str,
    description: str,
    privacy_status: str = "public",
    category_id: str = "22",  # People & Blogs (22) / Entertainment (24)
    tags: Optional[List[str]] = None,
) -> Optional[str]:
    vp = pathlib.Path(video_path)
    if not vp.exists() or vp.stat().st_size <= 0:
        raise RuntimeError(f"Video yok ya da boş: {video_path}")

    creds = _creds()
    youtube = build("youtube", "v3", credentials=creds)

    if YT_DEBUG:
        try:
            _who_am_i(youtube)
            print("[upload] channel info written to out/youtube_me.json", flush=True)
        except Exception as e:
            _dump_json("out/youtube_me_error.json", {"error": str(e)})

    body = {
        "snippet": {
            "title": (title or "")[:95],
            "description": (description or "")[:4900],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status if privacy_status in {"public","private","unlisted"} else "unlisted",
            "selfDeclaredMadeForKids": _get_bool_env("YT_MADE_FOR_KIDS", False),
        }
    }
    if tags:
        body["snippet"]["tags"] = tags

    mimetype, _ = mimetypes.guess_type(str(vp))
    media = MediaFileUpload(str(vp), mimetype=mimetype or "video/mp4", chunksize=1024*1024, resumable=True)

    try:
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        max_idle_seconds = max(5.0, _get_float_env("YT_UPLOAD_MAX_IDLE_SECONDS", 180.0))
        configured_total = _get_float_env("YT_UPLOAD_MAX_TOTAL_SECONDS", 1800.0)
        max_total_seconds = max(configured_total, max_idle_seconds + 1.0)

        response = None
        start_time = time.monotonic()
        last_progress_time = start_time
        last_progress_bytes = -1.0
        last_progress_fraction = -1.0
        last_logged_percent = -1

        while response is None:
            status, response = request.next_chunk()
            now = time.monotonic()
            made_progress = False
            current_fraction = None

            if status is not None:
                progress_fn = getattr(status, "progress", None)
                if callable(progress_fn):
                    try:
                        raw_fraction = progress_fn()
                    except Exception:
                        raw_fraction = None
                    if raw_fraction is not None:
                        try:
                            current_fraction = float(raw_fraction)
                        except Exception:
                            current_fraction = None
                        else:
                            current_fraction = max(0.0, min(1.0, current_fraction))
                            if current_fraction > last_progress_fraction + 1e-6:
                                last_progress_fraction = current_fraction
                                made_progress = True
                            percent_int = int(current_fraction * 100)
                            if percent_int != last_logged_percent:
                                print(f"[upload] progress: {percent_int}%", flush=True)
                                last_logged_percent = percent_int

                bytes_progress = getattr(status, "resumable_progress", None)
                if isinstance(bytes_progress, (int, float)):
                    if bytes_progress > last_progress_bytes + 0.5:
                        last_progress_bytes = float(bytes_progress)
                        made_progress = True

            if made_progress:
                last_progress_time = now
            elif response is None:
                idle_seconds = now - last_progress_time
                if idle_seconds >= max_idle_seconds:
                    last_pct = 0 if last_progress_fraction < 0 else int(last_progress_fraction * 100)
                    last_bytes = None if last_progress_bytes < 0 else int(last_progress_bytes)
                    detail = f"last progress {last_pct}%"
                    if last_bytes is not None:
                        detail += f" (~{last_bytes} bytes)"
                    raise RuntimeError(
                        f"Upload stalled: no progress for {int(max_idle_seconds)} seconds ({detail})."
                    )

            elapsed = now - start_time
            if elapsed >= max_total_seconds:
                raise RuntimeError(
                    f"Upload timed out after {int(max_total_seconds)} seconds (no response from API)."
                )

        _dump_json("out/youtube_response.json", response or {})
        vid = (response or {}).get("id")
        if not vid:
            print("[upload] response içinde video id yok.", flush=True)
            return None

        try:
            for _ in range(5):  # ~1 dakikada birkaç kez kontrol
                st = _check_video_status(youtube, vid)
                s = ((st.get("items") or [{}])[0].get("status") or {})
                us = s.get("uploadStatus")
                ps = s.get("privacyStatus")
                print(f"[upload] status check: uploadStatus={us}, privacy={ps}", flush=True)
                if us in {"processed", "uploaded"}:
                    break
                time.sleep(10)
        except Exception as e:
            _dump_json("out/youtube_status_error.json", {"error": str(e), "videoId": vid})

        url = f"https://youtu.be/{vid}"
        print("[upload] tamamlandı:", url, flush=True)
        return url

    except HttpError as e:
        _dump_json("out/youtube_error.json", {"http_error": str(e)})
        print(f"[upload error] {e}", flush=True)
        return None
    except Exception as e:
        _dump_json("out/youtube_error.json", {"error": str(e)})
        print(f"[upload error] {e}", flush=True)
        return None

# ---- CLI ----
if __name__ == "__main__":
    import sys, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Yüklenecek video yolu (mp4)")
    ap.add_argument("--title", required=True, help="Başlık")
    ap.add_argument("--desc", default="", help="Açıklama")
    ap.add_argument("--privacy", default=os.getenv("YT_PRIVACY", "public"),
                    choices=["public","unlisted","private"])
    ap.add_argument("--category", default=os.getenv("YT_CATEGORY_ID", "22"))
    ap.add_argument("--tags", default=os.getenv("YT_TAGS", ""))  # "tag1,tag2"
    ap.add_argument("--fail-on-error", action="store_true",
                    default=_get_bool_env("YT_FAIL_ON_ERROR", True))
    args = ap.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    url = try_upload_youtube(
        video_path=args.video,
        title=args.title,
        description=args.desc,
        privacy_status=args.privacy,
        category_id=args.category,
        tags=tags,
    )
    if not url:
        msg = "YouTube upload başarısız. Ayrıntılar: out/youtube_error.json"
        if args.fail_on_error:
            print(msg, file=sys.stderr)
            sys.exit(1)
        else:
            print(msg)
    else:
        print(url)
