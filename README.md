# ✈️ Paris Uçak Bileti Takip Sistemi

Ankara'dan Paris'e 1 yetişkin + 2 çocuk için en uygun uçak biletlerini otomatik takip eden sistem.

## 🚀 Özellikler

- Günde 4 kez otomatik çalışma
- Google Flights + Turna entegrasyonu
- Fiyat geçmişi takibi
- En iyi 3 seçenek analizi
- Telegram bildirimi
- PDF rapor
- Otomatik dosya temizliği

## 📅 Aranan Tarihler

**Gidiş:** 15-18 Ekim 2026  
**Dönüş:** 29 Ekim, 1 Kasım, 3 Kasım 2026

## 🔧 Kurulum

1. Repository'yi klonlayın
2. `pip install -r requirements.txt`
3. `playwright install chromium`
4. GitHub Secrets'a TELEGRAM_TOKEN ve TELEGRAM_CHAT_ID ekleyin

## 📊 Rapor Formatı

- Telegram: Anlık özet
- PDF: Detaylı rapor
- Debug: Hata durumunda otomatik kayıt

## 🤖 GitHub Actions

Her gün 09:00, 15:00, 21:00 ve 03:00'te çalışır.

## 📝 Lisans

MIT
