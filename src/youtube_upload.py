import os, time
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

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
    # Force refresh to get access token
    creds.refresh(Request())
    return creds

def try_upload_youtube(video_path: str, title: str, description: str, privacy_status: str = "public") -> Optional[str]:
    privacy = privacy_status or "public"
    if privacy not in {"public","private","unlisted"}:
        privacy = "public"

    creds = _get_creds()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:95],
            "description": description[:4900],
            "categoryId": "24"  # Entertainment (ok for shorts)
        },
        "status": {"privacyStatus": privacy}
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
        # Shorts: add #shorts tag in title/desc if vertical < 60s is preferred.
        return f"https://www.youtube.com/watch?v={video_id}"
    return None
