# YouTube Auto Shorts (Crypto AM, Sports PM)

- **AM 07:00 New York (UTC 11:00)** → Crypto brief
- **PM 19:00 New York (UTC 23:00)** → Sports brief (Google News RSS)
- English scripts + OpenAI TTS (cheap: `gpt-4o-mini-tts`)
- 60 fps vertical video, dynamic changing backgrounds, optional presenter avatar & BREAKING banner
- YouTube upload sets **Not made for kids** automatically

## Required Secrets
- `OPENAI_API_KEY`
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
  1. Sign in to the [Google Cloud Console](https://console.cloud.google.com/), click the project picker in the header, and create a new project (or reuse an existing one dedicated to your channel).
  2. With that project selected, go to **APIs & Services → Library**, search for **YouTube Data API v3**, and press **Enable**.
  3. Open **APIs & Services → Credentials → Create Credentials → OAuth client ID**. If prompted, configure the OAuth consent screen (external, add the YouTube scopes below). Choose **Desktop App** as the application type and finish the wizard.
  4. Download the OAuth client JSON and copy the `client_id`/`client_secret` values into the repository/workflow secrets `YT_CLIENT_ID` and `YT_CLIENT_SECRET`.
  5. Generate a refresh token using exactly the same scopes as the app uses. The required scopes (`YT_SCOPES` in the code) are:
     - `https://www.googleapis.com/auth/youtube.upload`
     - `https://www.googleapis.com/auth/youtube.readonly`

     Install `google-auth-oauthlib` locally (`pip install google-auth-oauthlib`) and run once to create credentials with those scopes:

     ```bash
     python -m google_auth_oauthlib.tool \
       --client-secrets=client_secret.json \
       --scopes="https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
     ```

     The tool stores a `refresh_token` in the generated credentials file; copy that value into the `YT_REFRESH_TOKEN` secret. The refresh token must be issued for the exact scopes listed above—if you change `YT_SCOPES`, you must reauthorize and store a new refresh token.

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

## Tests

Install dependencies (including pytest) and run the suite:

```bash
pip install -r requirements.txt
pytest
```
