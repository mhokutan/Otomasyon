# -*- coding: utf-8 -*-
import os, time
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def _get_bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

def _get_creds() -> Credentials:
    client_id = os.getenv("YT_CLIENT_ID")
    client_secret = os.getenv("YT_CLIENT_SECRET")
    refresh_token = os.getenv("YT_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("YouTube credentials missing")

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

def try_upload_youtube(video_path: str, title: str, description: str, privacy_status: str = "public") -> Optional[str]:
    # Privacy guard
    privacy = privacy_status if privacy_status in {"public","private","unlisted"} else "public"

    # Audience: default FALSE (not made for kids); can override via env if istenirse
    # Set YT_MADE_FOR_KIDS=true to switch.
    made_for_kids = _get_bool_env("YT_MADE_FOR_KIDS", False)

    creds = _get_creds()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:95],
            "description": description[:4900],
            "categoryId": "24"  # Entertainment (Shorts için uygun)
        },
        "status": {
            "privacyStatus": privacy,
            # 🔴 DOĞRU ALAN: selfDeclaredMadeForKids
            "selfDeclaredMadeForKids": made_for_kids
        }
    }

    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress()*100)}%")
    video_id = response.get("id")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return None
