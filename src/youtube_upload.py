import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def try_upload_youtube(mp4_path: str, title: str, description: str, privacy_status: str = "unlisted"):
    client_id = os.getenv("YT_CLIENT_ID") or ""
    client_secret = os.getenv("YT_CLIENT_SECRET") or ""
    refresh_token = os.getenv("YT_REFRESH_TOKEN") or ""

    if not (client_id and client_secret and refresh_token):
        print("[INFO] YouTube creds not set — skipping upload.")
        return None

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "24"  # entertainment
        },
        "status": {
            "privacyStatus": privacy_status
        }
        # "notifySubscribers": False  # istersen aç/kapa
    }

    media = MediaFileUpload(mp4_path, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while True:
        status, response = request.next_chunk()
        if response is not None:
            break

    vid_id = response.get("id")
    if vid_id:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        return url
    return None
