# -*- coding: utf-8 -*-
"""
YouTube'a video yükleme yardımcı aracı (refresh sırasında scope GÖNDERMEZ).
Kullanım (workflow veya lokal):
  python youtube_upload.py --video out/video.mp4 --title "Başlık" --desc "Açıklama" --privacy public

Gerekli ortam değişkenleri (Secrets/Vars):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
İsteğe bağlı:
  YT_PRIVACY (public|unlisted|private), YT_MADE_FOR_KIDS (true/false), YT_DEBUG (1/0), YT_TAGS (virgüllü)
"""

from __future__ import annotations
import os, json, mimetypes, pathlib, time, argparse
from typing import Optional, List, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ---------- yardımcılar ----------

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

def _dump_json(path: str, obj: Any) -> None:
    os.makedirs("out", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

YT_DEBUG: bool = _get_bool_env("YT_DEBUG", False)

# ---------- kimlik doğrulama ----------

def _creds() -> Credentials:
    """
    ÖNEMLİ: refresh sırasında scopes GÖNDERME — invalid_scope hatasını engeller.
    """
    cid=_env("YT_CLIENT_ID"); csec=_env("YT_CLIENT_SECRET"); rtok=_env("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("YouTube OAuth bilgileri eksik (YT_CLIENT_ID/SECRET/REFRESH_TOKEN).")

    cred = Credentials(
        None,
        refresh_token=rtok,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid,
        client_secret=csec,
        # scopes YOK!
    )
    try:
        cred.refresh(Request())
    except RefreshError as exc:
        payload: Dict[str, Any] = {"error": str(exc)}
        resp = getattr(exc, "response", None)
        if resp is not None:
            payload["status_code"] = getattr(resp, "status", None) or getattr(resp, "status_code", None)
            try:
                payload["response"] = resp.json()
            except Exception:
                payload["response_text"] = getattr(resp, "text", None)
        _dump_json("out/youtube_error.json", payload)
        raise RuntimeError("YouTube OAuth token refresh failed; ayrıntı: out/youtube_error.json") from exc
    return cred

def _who_am_i(youtube) -> Dict[str, Any]:
    ch = youtube.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()
    if YT_DEBUG:
        _dump_json("out/youtube_me.json", ch)
    return ch

def _check_video_status(youtube, video_id: str) -> Dict[str, Any]:
    info = youtube.videos().list(part="status,snippet", id=video_id).execute()
    _dump_json("out/youtube_status.json", info)
    return info

# ---------- yükleme ----------

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
            print("[upload] channel info -> out/youtube_me.json", flush=True)
        except Exception as e:
            _dump_json("out/youtube_me_error.json", {"error": str(e)})

    # snippet / status gövdesi
    body: Dict[str, Any] = {
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

            if status is not None:
                # yüzde
                progress_fn = getattr(status, "progress", None)
                if callable(progress_fn):
                    try:
                        raw_fraction = progress_fn()
                        if raw_fraction is not None:
                            frac = float(raw_fraction)
                            frac = max(0.0, min(1.0, frac))
                            if frac > last_progress_fraction + 1e-6:
                                last_progress_fraction = frac
                                made_progress = True
                            pct = int(frac * 100)
                            if pct != last_logged_percent:
                                print(f"[upload] progress: {pct}%", flush=True)
                                last_logged_percent = pct
                    except Exception:
                        pass
                # bayt
                bytes_progress = getattr(status, "resumable_progress", None)
                if isinstance(bytes_progress, (int, float)) and bytes_progress > last_progress_bytes + 0.5:
                    last_progress_bytes = float(bytes_progress)
                    made_progress = True

            if made_progress:
                last_progress_time = now
            elif response is None:
                idle = now - last_progress_time
                if idle >= max_idle_seconds:
                    last_pct = 0 if last_progress_fraction < 0 else int(last_progress_fraction * 100)
                    last_bytes = None if last_progress_bytes < 0 else int(last_progress_bytes)
                    detail = f"last progress {last_pct}%"
                    if last_bytes is not None:
                        detail += f" (~{last_bytes} bytes)"
                    raise RuntimeError(
                        f"Upload stalled: no progress for {int(max_idle_seconds)}s ({detail})."
                    )

            if (now - start_time) >= max_total_seconds:
                raise RuntimeError(f"Upload timed out after {int(max_total_seconds)}s.")

        _dump_json("out/youtube_response.json", response or {})
        vid = (response or {}).get("id")
        if not vid:
            print("[upload] response içinde video id yok.", flush=True)
            return None

        # kısa durum kontrolü
        try:
            for _ in range(5):
                st = _check_video_status(youtube, vid)
                s = ((st.get("items") or [{}])[0].get("status") or {})
                us = s.get("uploadStatus"); ps = s.get("privacyStatus")
                print(f"[upload] status: uploadStatus={us}, privacy={ps}", flush=True)
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

# ---------- CLI ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="YouTube video uploader")
    p.add_argument("--video", required=True, help="Yüklenecek video yolu (mp4)")
    p.add_argument("--title", required=True, help="Başlık")
    p.add_argument("--desc", default="", help="Açıklama")
    p.add_argument("--privacy", default=_env("YT_PRIVACY","public"),
                   choices=["public","unlisted","private"], help="Gizlilik")
    p.add_argument("--category", default="22", help="YouTube categoryId (default 22)")
    return p.parse_args()

def main() -> int:
    args = parse_args()
    tags_env = _env("YT_TAGS")
    tags: Optional[List[str]] = None
    if tags_env:
        tags = [t.strip() for t in tags_env.split(",") if t.strip()]

    url = try_upload_youtube(
        video_path=args.video,
        title=args.title,
        description=args.desc,
        privacy_status=args.privacy,
        category_id=args.category,
        tags=tags,
    )
    print(url or "")
    return 0 if url else 2

if __name__ == "__main__":
    raise SystemExit(main())