# -*- coding: utf-8 -*-
import os, json, mimetypes, pathlib, time, argparse
from typing import Optional, List, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

def _env(name: str) -> Optional[str]:
    v = os.getenv(name)
    return v if v and v.strip() else None

def _dump_json(path: str, obj: Any) -> None:
    os.makedirs("out", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def _creds() -> Credentials:
    cid = _env("YT_CLIENT_ID")
    csec = _env("YT_CLIENT_SECRET")
    rtok = _env("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("YouTube OAuth bilgileri eksik")

    cred = Credentials(
        None,
        refresh_token=rtok,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid,
        client_secret=csec
    )
    try:
        cred.refresh(Request())
    except RefreshError as e:
        _dump_json("out/youtube_error.json", {"error": str(e)})
        raise
    return cred

def try_upload(video_path: str, title: str, desc: str, privacy: str="public") -> Optional[str]:
    vp = pathlib.Path(video_path)
    if not vp.exists() or vp.stat().st_size == 0:
        raise RuntimeError(f"Video yok veya boş: {video_path}")

    creds = _creds()
    yt = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {"title": title[:95], "description": desc[:4900], "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(vp), mimetype="video/mp4", chunksize=1024*1024, resumable=True)

    try:
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        start = time.monotonic()
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                pct = int(status.progress() * 100) if callable(getattr(status, "progress", None)) else None
                if pct is not None:
                    print(f"Upload {pct}%")
            if time.monotonic() - start > 1800:
                raise RuntimeError("Upload timed out")

        vid = resp.get("id")
        if vid:
            url = f"https://youtu.be/{vid}"
            print("Upload tamamlandı:", url)
            return url
        return None
    except HttpError as e:
        _dump_json("out/youtube_error.json", {"http_error": str(e)})
        print("Upload hata:", e)
        return None

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--desc", default="")
    ap.add_argument("--privacy", default="public")
    a = ap.parse_args()

    url = try_upload(a.video, a.title, a.desc, a.privacy)
    if not url:
        raise SystemExit(1)