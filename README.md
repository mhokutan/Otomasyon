# YouTube Shorts Otomasyon (Ücretsiz Orkestrasyon)

Tamamen **GitHub Actions** ile çalışır (ücretsiz). LLM yok; metin üretimi kural tabanlı; TTS **gTTS**; render **FFmpeg**. İstersen YouTube’a otomatik yükler.

## Hızlı Kurulum
1. Bu repo dosyalarını aynen oluştur / kopyala.
2. GitHub → Settings → Secrets → Actions:
   - (Opsiyonel otomatik upload) `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
   - (Opsiyonel) `VIDEO_TITLE_PREFIX` (örn: `Günün Özeti:`)
   - (Opsiyonel) `YT_PRIVACY` (`private`/`unlisted`/`public`, varsayılan `unlisted`)
3. Actions tabında `yt-auto` workflow’u **Run workflow** ile tetikle. Bittiğinde **Artifacts → output** içinde `video-*.mp4` var.

## YouTube Refresh Token nasıl alınır? (bir kere)
Yerelde Python çalıştır:
```bash
pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
