# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, mimetypes, pathlib, time, argparse
from typing import Optional, List, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

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

def _creds():
    cid=_env("YT_CLIENT_ID"); csec=_env("YT_CLIENT_SECRET"); rtok=_env("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("YT_CLIENT_ID/SECRET/REFRESH_TOKEN eksik.")
    c = Credentials(None, refresh_token=rtok, client_id=cid, client_secret=csec, token_uri="https://oauth2.googleapis.com/token")
    c.refresh(Request())
    return c

def _add_to_playlist(yt, video_id: str, playlist_id: str) -> None:
    if not playlist_id: return
    try:
        yt.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        ).execute()
        print(f"[playlist] added to {playlist_id}")
    except Exception as e:
        _dump_json("out/playlist_error.json", {"error": str(e), "playlistId": playlist_id, "videoId": video_id})

def upload_video(video_path: str, title: str, description: str,
                 privacy_status: str="public", category_id: str="22",
                 tags: Optional[List[str]]=None) -> str:
    p = pathlib.Path(video_path)
    if not p.exists() or p.stat().st_size <= 0:
        raise RuntimeError(f"Video yok/boş: {video_path}")

    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)

    body = {
        "snippet": {"title": (title or "")[:95],
                    "description": (description or "")[:4900],
                    "categoryId": category_id},
        "status": {"privacyStatus": privacy_status if privacy_status in {"public","private","unlisted"} else "unlisted",
                   "selfDeclaredMadeForKids": _get_bool_env("YT_MADE_FOR_KIDS", False)}
    }
    if tags: body["snippet"]["tags"] = tags[:500]

    mime,_ = mimetypes.guess_type(str(p))
    media = MediaFileUpload(str(p), mimetype=mime or "video/mp4", chunksize=1024*1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    resp=None; last=-1; start=time.monotonic()
    while resp is None:
        status, resp = req.next_chunk()
        if status and hasattr(status,"progress"):
            try:
                pct = int(float(status.progress())*100)
                if pct != last:
                    print(f"[upload] {pct}%"); last=pct
            except: pass
        if time.monotonic()-start > 1800: raise RuntimeError("Upload timed out (1800s)")
    _dump_json("out/youtube_response.json", resp or {})

    vid = (resp or {}).get("id")
    if not vid: raise RuntimeError("Video id dönmedi")
    print("[done]", f"https://youtu.be/{vid}")

    pl = _env("PLAYLIST_ID")
    if pl:
        _add_to_playlist(yt, vid, pl)

    return f"https://youtu.be/{vid}"

# CLI optional (local testing)
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--desc", default="")
    ap.add_argument("--privacy", default="public", choices=["public","unlisted","private"])
    ap.add_argument("--tags", default="")
    args = ap.parse_args()

    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    upload_video(args.video, args.title, args.desc, privacy_status=args.privacy, tags=tags)
