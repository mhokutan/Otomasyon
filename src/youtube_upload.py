# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, mimetypes, pathlib
from typing import Optional, List
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES: List[str] = ["https://www.googleapis.com/auth/youtube.upload"]

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _get_bool_env(name: str, default: bool=False) -> bool:
    v=_env(name)
    return default if v is None else str(v).strip().lower() in ("1","true","yes","on")

def _creds() -> Credentials:
    cid=_env("YT_CLIENT_ID"); csec=_env("YT_CLIENT_SECRET"); rtok=_env("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("YouTube OAuth bilgileri eksik (ID/SECRET/REFRESH_TOKEN).")
    cred = Credentials(
        None, refresh_token=rtok, token_uri="https://oauth2.googleapis.com/token",
        client_id=cid, client_secret=csec, scopes=SCOPES
    )
    cred.refresh(Request())
    return cred

def try_upload_youtube(
    video_path: str,
    title: str,
    description: str,
    privacy_status: str = "unlisted",
    category_id: str = "22",  # People & Blogs
    tags: Optional[List[str]] = None,
) -> Optional[str]:
    vp = pathlib.Path(video_path)
    if not vp.exists() or vp.stat().st_size <= 0:
        raise RuntimeError(f"Video yok ya da boş: {video_path}")

    yt = build("youtube", "v3", credentials=_creds())

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
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                print(f"[upload] {int(status.progress()*100)}%", flush=True)

        # Yanıtı sakla (kanıt)
        os.makedirs("out", exist_ok=True)
        with open("out/youtube_response.json", "w", encoding="utf-8") as f:
            json.dump(resp, f, ensure_ascii=False, indent=2)

        vid = (resp or {}).get("id")
        if not vid:
            print("[upload] response içinde video id yok.", flush=True)
            return None
        url = f"https://youtu.be/{vid}"
        print("[upload] tamamlandı:", url, flush=True)
        return url

    except HttpError as e:
        os.makedirs("out", exist_ok=True)
        with open("out/youtube_error.json", "w", encoding="utf-8") as f:
            f.write(str(e))
        print(f"[upload error] {e}", flush=True)
        return None
    except Exception as e:
        os.makedirs("out", exist_ok=True)
        with open("out/youtube_error.json", "w", encoding="utf-8") as f:
            f.write(str(e))
        print(f"[upload error] {e}", flush=True)
        return None
