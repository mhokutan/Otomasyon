# YouTube Auto Shorts (Crypto AM, Sports PM)

- **AM 07:00 New York** → Crypto brief
- **PM 19:00 New York** → Sports brief (via Google News RSS)
- English script + OpenAI TTS, 60 fps, optional AI images (HF), SFX/BGM with ducking.

## Secrets required
- `OPENAI_API_KEY` (for TTS)
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (YouTube upload, OAuth)
- `HF_TOKEN` (optional, HuggingFace Inference API for images)

## Optional assets
Put your audio files in `assets/sfx/`:
- `bgm.mp3` (background music)
- `whoosh.wav` (transition SFX)

If missing, pipeline skips them gracefully.

## Run
- Push to `main` and wait for cron, or run **Actions → yt-auto → Run workflow**.
- Outputs saved under `out/` and uploaded as build artifacts.
