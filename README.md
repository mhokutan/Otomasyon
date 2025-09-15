# YouTube Auto Shorts (Crypto AM, Sports PM)

- **AM 07:00 New York (UTC 11:00)** → Crypto brief
- **PM 19:00 New York (UTC 23:00)** → Sports brief (Google News RSS)
- English scripts + OpenAI TTS (cheap: `gpt-4o-mini-tts`)
- 60 fps vertical video, dynamic changing backgrounds, optional presenter avatar & BREAKING banner
- YouTube upload sets **Not made for kids** automatically

## Required Secrets
- `OPENAI_API_KEY`
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`

Optional:
- `HF_TOKEN` (not required; images are pulled from picsum.photos instead)

## Tuning (via env in workflow)
- `TTS_ATEMPO` (e.g. `1.07`)  
- `BG_IMAGES_PER_SLIDE` (e.g. `5`)  
- `PRESENTER_URL`, `PRESENTER_INITIALS`, `PRESENTER_POS`, `PRESENTER_SIZE`  
- `BREAKING_ON`, `BREAKING_TEXT`  

## Run
- Push to `main` or trigger **Actions → yt-auto → Run workflow**.
- Outputs saved under `out/` and uploaded as artifacts.
- Optional: set `YT_PRIVACY` to `public`, `unlisted`, or `private` before running the
  workflow to control the uploaded video's visibility (defaults to `public`).
