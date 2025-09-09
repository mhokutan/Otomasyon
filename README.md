# YouTube Shorts Otomasyon (Ücretsiz, OpenAI yok)

- Orkestrasyon: **GitHub Actions** (ücretsiz)
- Metin: kural tabanlı
- TTS: **gTTS** (ücretsiz)
- Render: **FFmpeg** (1080×1920)
- YouTube yükleme: OAuth ile (opsiyonel)

## Hızlı Kurulum
1. Bu dosyaları repo’ya ekle.
2. GitHub → **Settings → Secrets and variables → Actions**:
   - (Otomatik upload için) `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
   - (Opsiyonel) `YT_PRIVACY` = `unlisted` / `public` / `private`  
     > Boş/hatalıysa otomatik **`unlisted`** kullanılır.
   - (Opsiyonel) `VIDEO_TITLE_PREFIX` = `Günün Özeti:`
3. **Actions → yt-auto → Run workflow**.  
   - Çıkışlar **Artifacts → output**’ta.
   - Secret’lar varsa otomatik YouTube’a yükler.

## YouTube OAuth (kısaca)
- Google Cloud Console → YouTube Data API v3 **Enable**
- OAuth consent screen: **External**, **Test users**’a Gmail’ini ekle.
- **OAuth client (Web)** oluştur, redirect URI:  
  `https://developers.google.com/oauthplayground`
- **OAuth Playground** (Use your own credentials) ile `youtube.upload` scope’tan **refresh_token** al → Secrets’a koy.

## Özelleştirme
- RSS kaynağı: `src/scriptgen.py → RSS_URL_TR`
- Senaryo kalıbı: `make_script_tr()` fonksiyonu
- Video üretimi: `src/video.py` (FFmpeg komutunu zenginleştirebilirsin)
