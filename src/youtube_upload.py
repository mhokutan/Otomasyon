# -*- coding: utf-8 -*-
"""
YouTube'a video yükleme scripti.
Refresh sırasında scope belirtmez; invalid_scope hatası engellenir.
"""

from __future__ import annotations
import os, sys, json, mimetypes, pathlib, time, argparse
from typing import Optional, List, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- Yardımcılar -----------------------------------------------------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _get_bool_env(name: str, default: bool=False) -> bool:
    v=_env(name)
    return default if v is None else str(v).strip().lower() in ("1","true","yes","on")

def _dump_json(path: str, obj: Any) -> None:
    os.makedirs("out", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

YT_DEBUG = _get_bool_env("YT_DEBUG", False)

# --- Kimlik doğrulama ------------------------------------------------------

def _creds() -> Credentials:
    cid = _env("YT_CLIENT_ID")
    csec = _env("YT_CLIENT_SECRET")
    rtok = _env("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN eksik!")

    creds = Credentials(
        None,
        refresh_token=rtok,
        client_id=cid,
        client_secret=csec,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return creds

def _check_video_status(youtube, vid: str) -> Dict[str, Any]:
    info = youtube.videos().list(part="status,snippet", id=vid).execute()
    if YT_DEBUG:
        _dump_json("out/youtube_status.json", info)
    return info

# --- Yükleme ---------------------------------------------------------------

def upload_video(
    video_path: str,
    title: str,
    description: str,
    privacy_status: str = "public",
    category_id: str = "22",
    tags: Optional[List[str]] = None,
) -> str:
    p = pathlib.Path(video_path)
    if not p.exists() or p.stat().st_size <= 0:
        raise RuntimeError(f"Video bulunamadı veya boş: {video_path}")

    creds = _creds()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    body = {
        "snippet": {
            "title": (title or "")[:95],
            "description": (description or "")[:4900],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status if privacy_status in {"public","private","unlisted"} else "unlisted",
            "selfDeclaredMadeForKids": _get_bool_env("YT_MADE_FOR_KIDS", False),
        },
    }
    if tags:
        body["snippet"]["tags"] = tags

    mimetype, _ = mimetypes.guess_type(str(p))
    media = MediaFileUpload(str(p), mimetype=mimetype or "video/mp4", chunksize=1024*1024, resumable=True)

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    start = time.monotonic()
    last_log = -1
    while response is None:
        status, response = request.next_chunk()
        if status and hasattr(status, "progress"):
            try:
                pct = int(float(status.progress()) * 100)
            except Exception:
                pct = None
            if pct is not None and pct != last_log:
                print(f"[upload] {pct}%")
                last_log = pct
        if time.monotonic() - start > 1800:
            raise RuntimeError("Upload timed out (1800s).")

    _dump_json("out/youtube_response.json", response or {})
    vid = (response or {}).get("id")
    if not vid:
        raise RuntimeError("Video id dönmedi!")

    # Kısa durum kontrolü
    try:
        for _ in range(5):
            st = _check_video_status(youtube, vid)
            s = ((st.get("items") or [{}])[0].get("status") or {})
            us = s.get("uploadStatus")
            ps = s.get("privacyStatus")
            print(f"[status] uploadStatus={us}, privacy={ps}")
            if us in {"processed", "uploaded"}:
                break
            time.sleep(8)
    except Exception as e:
        _dump_json("out/youtube_status_error.json", {"error": str(e), "videoId": vid})

    url = f"https://youtu.be/{vid}"
    print("[done]", url)
    return url

# --- CLI -------------------------------------------------------------------

def _parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Upload video to YouTube.")
    ap.add_argument("--video", required=True, help="Yüklenecek dosya yolu (.mp4)")
    ap.add_argument("--title", required=True, help="Video başlığı")
    ap.add_argument("--desc", default="", help="Video açıklaması")
    ap.add_argument("--privacy", default="public", choices=["public","unlisted","private"], help="Gizlilik")
    ap.add_argument("--category-id", default="22", help="Kategori ID")
    ap.add_argument("--tags", default="", help="Virgüllü etiketler")
    return ap.parse_args(argv)

def main(argv: List[str]) -> int:
    try:
        args = _parse_args(argv)
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        upload_video(
            video_path=args.video,
            title=args.title,
            description=args.desc,
            privacy_status=args.privacy,
            category_id=args.category_id,
            tags=[t for t in (tags or []) if t],
        )
        return 0
    except HttpError as e:
        _dump_json("out/youtube_error.json", {"http_error": str(e)})
        print(f"[upload error] {e}", file=sys.stderr)
        return 2
    except Exception as e:
        _dump_json("out/youtube_error.json", {"error": str(e)})
        print(f"[upload error] {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))