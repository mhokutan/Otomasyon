# Otomatik YouTube Shorts – Haber/Kripto

Tam otomatik: metin → TTS → dikey video (9:16) → (opsiyonel) YouTube’a yükleme.

## Kurulum
1. Bu repo’yu oluştur.
2. Actions sekmesinde workflow izinlerini aç.
3. Gerekirse `.github/workflows/auto.yml` içinde env değişkenlerini düzenle.

## Çalıştırma
- Elle: **Actions → yt-auto → Run workflow**
- Otomatik: cron (`0 6 * * *`) her gün TR 09:00 civarı.

## Temalar
- `THEME=news` → Google News TR RSS (üstte “BREAKING NEWS” etiketi + altta ticker)
- `THEME=crypto` → CoinGecko’dan BTC/ETH/SOL vb. fiyat + sparkline

## YouTube Yükleme (opsiyonel)
Repo ayarlarında env set et:
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
- `YT_PRIVACY`: `public|unlisted|private`

Boş bırakılırsa video sadece **artifact** olarak kaydolur.

## Hız ve Görsel
- `TTS_ATEMPO` ile konuşma hızını artır (örn. `1.35`)
- `BG_ZOOM_PER_SEC` ile arka plan hareketini ayarla (örn. `0.0010`)
- `XFADE_SEC` slayt geçiş yumuşaklığı
