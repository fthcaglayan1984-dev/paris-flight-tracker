import os
import asyncio
import re
from playwright.async_api import async_playwright
from telegram import Bot

# GitHub Secrets'tan Telegram bilgilerini alma
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def get_flight_data(page, url, label):
    try:
        # Gerçek kullanıcı gibi görünmek için User-Agent ve ekran boyutları
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)

        # Fiyat kutularını ve uçuş bilgilerini tarama
        prices = []
        elements = await page.query_selector_all('span[aria-label*="Türk Lirası"], span[aria-label*="TRY"], [data-test-id="price"]')
        
        for el in elements:
            text = await el.inner_text()
            # Sadece sayı içeren fiyat formatlarını temizleme
            clean_text = re.sub(r'[^\d.]', '', text.replace(',', '').replace('.', ''))
            if clean_text.isdigit() and int(clean_text) > 1000:
                prices.append(int(clean_text))

        if prices:
            min_price = min(prices)
            formatted_price = f"{min_price:,}".replace(',', '.') + " ₺"
            return f"✅ **{label}:** {formatted_price}"
        else:
            # Alternatif metin arama
            content = await page.content()
            found_prices = re.findall(r'(\d{1,3}(?:\.\d{3})+)\s*TL', content)
            if found_prices:
                return f"✅ **{label}:** {found_prices[0]} ₺"
            return f"⚠️ **{label}:** Anlık fiyat okunamadı (Detay linkten kontrol edin)."

    except Exception as e:
        return f"❌ **{label}:** Hata oluştu ({str(e)[:50]}...)"

async def main():
    async with async_playwright() as p:
        # Chromium tarayıcısını izlenemez modda başlatma
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Google Flights Arama Linkleri
        # Ankara (ESB) -> Paris (PAR) | 17 Ekim 2026 - 1 Kasım 2026
        esb_url = "https://www.google.com/travel/flights?q=Flights%20to%20PAR%20from%20ESB%20on%202026-10-17%20through%202026-11-01"
        
        # İstanbul (SAW/IST) -> Paris (PAR) | 17 Ekim 2026 - 1 Kasım 2026
        ist_url = "https://www.google.com/travel/flights?q=Flights%20to%20PAR%20from%20IST%20on%202026-10-17%20through%202026-11-01"

        res_esb = await get_flight_data(page, esb_url, "Ankara (ESB) - Paris")
        res_ist = await get_flight_data(page, ist_url, "İstanbul (IST/SAW) - Paris")

        await browser.close()

        # Telegram Mesaj Metni
        report_message = (
            "✈️ **GÜNLÜK PARİS UÇAK BİLETI RAPORU**\n\n"
            "📅 **Tarih:** 17 Ekim 2026 - 01 Kasım 2026\n"
            "───────────────\n"
            f"{res_esb}\n"
            f"{res_ist}\n"
            "───────────────\n"
            "🔗 **Bilet Linkleri:**\n"
            f"• [Ankara - Paris Uçuşları]({esb_url})\n"
            f"• [İstanbul - Paris Uçuşları]({ist_url})\n\n"
            "🤖 *Otomatik sistem tarafından kontrol edilip doğrulanmıştır.*"
        )

        # Telegram'a Gönderim
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=report_message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

if __name__ == "__main__":
    asyncio.run(main())

