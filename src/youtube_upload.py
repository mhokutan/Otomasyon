import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def have_creds():
    return all(os.getenv(k) for k in ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"])

def get_youtube():
    creds = Credentials(
        None,
        refresh_token=os.getenv("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YT_CLIENT_ID"),
        client_secret=os.getenv("YT_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, static_discovery=False)

def try_upload_youtube(video_path, title, description="", privacy_status="unlisted"):
    if not have_creds():
        print("YouTube creds missing; skipping upload.")
        return None

    # privacy_status sağlamlaştır
    p = (privacy_status or "unlisted").strip().lower()
    if p not in {"public", "unlisted", "private"}:
        print(f"Invalid privacy '{privacy_status}', falling back to 'unlisted'")
        p = "unlisted"

    try:
        yt = get_youtube()
        body = {
            "snippet": {
                "title": (title or "Video").strip()[:95],
                "description": description or "",
                "categoryId": "25",  # News & Politics
            },
            "status": {"privacyStatus": p},
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        if video_id:
            return f"https://youtu.be/{video_id}"
        print("[WARN] Upload finished but no video id returned.")
        return None

    except HttpError as e:
        try:
            print("[ERROR] HttpError:", e.reason, e.error_details)
        except Exception:
            print("[ERROR] HttpError:", str(e))
        return None
    except Exception as e:
        print("[ERROR] Unexpected upload error:", e)
        return None
