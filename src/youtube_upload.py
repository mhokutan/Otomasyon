# -*- coding: utf-8 -*-
import os
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def _get_bool_env(name: str, default: bool=False) -> bool:
    v=os.getenv(name)
    if v is None or str(v).strip()=="": return default
    return str(v).strip().lower() in ("1","true","yes","on")

def _get_creds():
    cid=os.getenv("YT_CLIENT_ID"); csecret=os.getenv("YT_CLIENT_SECRET"); rtok=os.getenv("YT_REFRESH_TOKEN")
    if not all([cid,csecret,rtok]): raise RuntimeError("YouTube credentials missing")
    cred=Credentials(None, refresh_token=rtok, token_uri="https://oauth2.googleapis.com/token",
                     client_id=cid, client_secret=csecret, scopes=SCOPES)
    cred.refresh(Request()); return cred

def try_upload_youtube(video_path: str, title: str, description: str, privacy_status: str="public") -> Optional[str]:
    privacy=privacy_status if privacy_status in {"public","private","unlisted"} else "public"
    made_for_kids=_get_bool_env("YT_MADE_FOR_KIDS", False)

    yt=build("youtube","v3", credentials=_get_creds())
    body={
        "snippet":{"title": title[:95], "description": description[:4900], "categoryId":"24"},
        "status":{"privacyStatus": privacy, "selfDeclaredMadeForKids": made_for_kids}
    }
    media=MediaFileUpload(video_path, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
    req=yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp=None
    while resp is None:
        status, resp = req.next_chunk()
        if status: print(f"Upload {int(status.progress()*100)}%")
    vid=resp.get("id"); return f"https://www.youtube.com/watch?v={vid}" if vid else None
