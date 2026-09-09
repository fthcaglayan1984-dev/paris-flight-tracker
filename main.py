import os
import re
import json
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright
from telegram import Bot


# ============================================================
# AYARLAR
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DATA_FILE = Path("flight_price_history.json")

# Ana seyahat
MAIN_DEPARTURE = "17-10-2026"
MAIN_RETURN = "01-11-2026"

# Alternatif tarihler
DEPARTURE_DATES = [
    "15-10-2026",
    "16-10-2026",
    "17-10-2026",
    "18-10-2026",
]

RETURN_DATES = [
    "29-10-2026",
    "01-11-2026",
    "03-11-2026",
]

# Kalkış şehirleri
ROUTES = {
    "Ankara": ("ESB", "Ankara"),
    "İstanbul": ("IST", "İstanbul"),
    "Antalya": ("AYT", "Antalya"),
    "İzmir": ("ADB", "İzmir"),
    "Denizli": ("DNZ", "Denizli"),
}

PARIS_AIRPORTS = {
    "CDG": "Paris Charles de Gaulle",
    "ORY": "Paris Orly",
    "BVA": "Paris Beauvais",
}

# Çocuklarla seyahat edildiği için
MAX_IDEAL_CONNECTION_MINUTES = 240
MAX_ACCEPTABLE_CONNECTION_MINUTES = 480


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def load_history():
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def normalize_price(text):
    """
    Turna'daki farklı fiyat gösterimlerini TL sayısına çevirmeye çalışır.
    """

    if not text:
        return None

    text = text.upper()
    text = text.replace("TL", "")
    text = text.replace("TRY", "")
    text = text.replace("₺", "")
    text = text.replace(" ", "")

    # 8.950
    m = re.search(r"\d{1,3}(?:\.\d{3})+", text)
    if m:
        try:
            return int(m.group(0).replace(".", ""))
        except:
            pass

    # 8950
    m = re.search(r"\d{4,7}", text)
    if m:
        try:
            return int(m.group(0))
        except:
            pass

    return None


def parse_duration(text):
    """
    2s 45dk / 2sa 45dk / 2h 45m gibi değerleri dakikaya çevirmeye çalışır.
    """

    if not text:
        return None

    text = text.lower()

    hours = 0
    minutes = 0

    h = re.search(r"(\d+)\s*(?:sa|s|saat|h)", text)
    m = re.search(r"(\d+)\s*(?:dk|dakika|m)", text)

    if h:
        hours = int(h.group(1))

    if m:
        minutes = int(m.group(1))

    total = hours * 60 + minutes

    return total if total > 0 else None


def format_minutes(minutes):
    if minutes is None:
        return "Bilinmiyor"

    h = minutes // 60
    m = minutes % 60

    if h:
        return f"{h}s {m}dk"

    return f"{m}dk"


def price_change(previous, current):
    if previous is None or current is None:
        return None

    difference = current - previous

    if previous:
        percentage = (difference / previous) * 100
    else:
        percentage = 0

    return difference, percentage


def connection_comment(minutes):
    if minutes is None:
        return "⚪ Aktarma süresi tespit edilemedi"

    if minutes <= MAX_IDEAL_CONNECTION_MINUTES:
        return "🟢 Çocuklarla seyahat için makul aktarma"

    if minutes <= MAX_ACCEPTABLE_CONNECTION_MINUTES:
        return "🟡 Uzun aktarma"

    return "🔴 Çok uzun aktarma"


# ============================================================
# TURNA URL
# ============================================================

def create_turna_url(origin_code, departure, return_date):
    """
    Turna'nın klasik URL yapısı.
    """

    return (
        f"https://www.turna.com/ucak-bileti/"
        f"{origin_code.lower()}-paris-{origin_code.lower()}-cdg"
        f"?departureDate={departure}"
        f"&returnDate={return_date}"
    )


# ============================================================
# SAYFADAN UÇUŞ BİLGİSİ ÇEKME
# ============================================================

async def extract_flight_information(page, url, origin_name):
    flights = []

    try:
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        # Dinamik içerik için bekle
        await asyncio.sleep(7)

        # Sayfayı biraz aşağı kaydır
        for _ in range(5):
            await page.mouse.wheel(0, 1200)
            await asyncio.sleep(1)

        body_text = await page.locator("body").inner_text()

        # ----------------------------------------------------
        # FİYATLARI BUL
        # ----------------------------------------------------

        price_candidates = []

        # TL / ₺ içeren bütün metinleri tara
        elements = await page.locator(
            "body span, body div, body strong, body p"
        ).all_inner_texts()

        for text in elements:

            if not text:
                continue

            upper = text.upper()

            if (
                "TL" in upper
                or "₺" in upper
                or "TRY" in upper
            ):
                price = normalize_price(text)

                if price and 1000 <= price <= 200000:
                    price_candidates.append(price)

        # Tekrarlayan fiyatları temizle
        price_candidates = sorted(set(price_candidates))

        # ----------------------------------------------------
        # UÇUŞ KARTLARINI BULMAYA ÇALIŞ
        # ----------------------------------------------------

        selectors = [
            '[class*="flight"]',
            '[class*="Flight"]',
            '[class*="result"]',
            '[class*="Result"]',
            '[class*="ticket"]',
            '[class*="Ticket"]',
        ]

        cards = []

        for selector in selectors:

            try:
                found = await page.locator(selector).all()

                if found:
                    cards.extend(found)

            except:
                pass

        # Çok fazla tekrar varsa sınırla
        unique_cards = []

        seen_text = set()

        for card in cards:

            try:
                text = await card.inner_text()

                if not text:
                    continue

                text = text.strip()

                if len(text) < 30:
                    continue

                if text in seen_text:
                    continue

                seen_text.add(text)
                unique_cards.append(text)

            except:
                continue

        # ----------------------------------------------------
        # KARTLARDAN BİLGİ ÇIKAR
        # ----------------------------------------------------

        for index, card_text in enumerate(unique_cards[:30]):

            price = normalize_price(card_text)

            if not price:

                # Kart fiyat içermiyorsa global fiyat listesinden
                # sırayla kullanmayı dene
                if index < len(price_candidates):
                    price = price_candidates[index]

            if not price:
                continue

            lower = card_text.lower()

            # Aktarma
            stop_count = 0

            if "direkt" in lower:
                stop_count = 0
            else:
                stop_matches = re.findall(
                    r"(\d+)\s*(?:aktarma|stop)",
                    lower
                )

                if stop_matches:
                    stop_count = int(stop_matches[0])
                elif "1 aktarma" in lower:
                    stop_count = 1
                elif "2 aktarma" in lower:
                    stop_count = 2
                elif "3 aktarma" in lower:
                    stop_count = 3

            # Havayolu
            airline = "Bilinmiyor"

            airlines = [
                "Pegasus",
                "AJet",
                "Turkish Airlines",
                "Türk Hava Yolları",
                "Lufthansa",
                "Air France",
                "KLM",
                "LOT",
                "Eurowings",
                "SunExpress",
                "Ryanair",
                "Wizz Air",
                "easyJet",
                "Aegean",
                "Austrian",
                "Swiss",
                "ITA Airways",
                "Air Serbia",
            ]

            for name in airlines:
                if name.lower() in lower:
                    airline = name
                    break

            # Süre
            duration = None

            duration_match = re.search(
                r"(\d+\s*(?:sa|saat|h)"
                r"(?:\s*\d+\s*(?:dk|dakika|m))?)",
                lower
            )

            if duration_match:
                duration = parse_duration(
                    duration_match.group(1)
                )

            # Aktarma havalimanı / şehir tahmini
            connection = "Belirtilmemiş"

            airports = [
                "İstanbul",
                "Berlin",
                "Frankfurt",
                "Münih",
                "Düsseldorf",
                "Viyana",
                "Zürih",
                "Amsterdam",
                "Varşova",
                "Belgrad",
                "Atina",
                "Milano",
                "Roma",
                "Kopenhag",
                "Prag",
            ]

            for airport in airports:
                if airport.lower() in lower:
                    connection = airport
                    break

            # Bagaj
            baggage = "Bilgi yok"

            if "bagaj dahil" in lower:
                baggage = "Bagaj dahil"
            elif "15 kg" in lower:
                baggage = "15 kg"
            elif "20 kg" in lower:
                baggage = "20 kg"
            elif "25 kg" in lower:
                baggage = "25 kg"
            elif "30 kg" in lower:
                baggage = "30 kg"
            elif "bagajsız" in lower or "bagaj yok" in lower:
                baggage = "Bagajsız"

            flights.append({
                "origin": origin_name,
                "price": price,
                "airline": airline,
                "stops": stop_count,
                "duration": duration,
                "connection": connection,
                "baggage": baggage,
                "raw": card_text[:1000],
                "url": url
            })

        # ----------------------------------------------------
        # KARTLAR YAKALANAMADIYSA EN AZINDAN EN UCUZ FİYATI AL
        # ----------------------------------------------------

        if not flights and price_candidates:

            flights.append({
                "origin": origin_name,
                "price": min(price_candidates),
                "airline": "Bilgi alınamadı",
                "stops": None,
                "duration": None,
                "connection": "Bilgi alınamadı",
                "baggage": "Bilgi alınamadı",
                "raw": "",
                "url": url
            })

        return flights

    except Exception as e:

        print(
            f"{origin_name} için hata: {e}"
        )

        return []


# ============================================================
# FİYAT GEÇMİŞİ
# ============================================================

def update_price_history(flight):

    history = load_history()

    key = (
        f"{flight['origin']}_"
        f"{flight['url']}"
    )

    today = datetime.now().strftime("%Y-%m-%d")

    if key not in history:
        history[key] = {
            "origin": flight["origin"],
            "url": flight["url"],
            "prices": {}
        }

    old_prices = history[key]["prices"]

    previous_date = None
    previous_price = None

    dates = sorted(old_prices.keys())

    if dates:
        previous_date = dates[-1]
        previous_price = old_prices[previous_date]

    current_price = flight["price"]

    old_prices[today] = current_price

    # Son 60 günü tut
    if len(old_prices) > 60:
        old_prices = dict(
            sorted(old_prices.items())[-60:]
        )

    history[key]["prices"] = old_prices

    save_history(history)

    return previous_date, previous_price


# ============================================================
# RAPOR OLUŞTURMA
# ============================================================

def build_flight_report(flights):

    if not flights:
        return "❌ Uçuş fiyatı bulunamadı."

    # En ucuzdan pahalıya
    flights = sorted(
        flights,
        key=lambda x: x["price"]
    )

    lines = []

    lines.append(
        "✈️ *PARİS UÇUŞ FİYAT RAPORU*"
    )

    lines.append("")
    lines.append(
        "📅 *Ana tarih:* 17 Ekim 2026 → 1 Kasım 2026"
    )

    lines.append(
        "🔎 Alternatif tarihler de kontrol edildi."
    )

    lines.append("")
    lines.append(
        f"📊 *Toplam bulunan seçenek:* {len(flights)}"
    )

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, flight in enumerate(flights[:15], 1):

        previous_date, previous_price = (
            update_price_history(flight)
        )

        current_price = flight["price"]

        lines.append("")
        lines.append(
            f"*{i}. {flight['origin']} → Paris*"
        )

        lines.append(
            f"💰 *Fiyat:* {current_price:,} TL"
            .replace(",", ".")
        )

        lines.append(
            f"✈️ Havayolu: {flight['airline']}"
        )

        # Aktarma
        if flight["stops"] == 0:

            lines.append(
                "🛫 Uçuş: *Direkt*"
            )

        elif flight["stops"]:

            lines.append(
                f"🔄 Aktarma: *{flight['stops']}*"
            )

            lines.append(
                f"📍 Aktarma noktası: "
                f"{flight['connection']}"
            )

        else:

            lines.append(
                "🔄 Aktarma: Bilinmiyor"
            )

        # Süre
        lines.append(
            "⏱ Toplam süre: "
            + format_minutes(
                flight["duration"]
            )
        )

        # Bagaj
        lines.append(
            f"🧳 Bagaj: {flight['baggage']}"
        )

        # Fiyat geçmişi
        if previous_price:

            difference, percentage = price_change(
                previous_price,
                current_price
            )

            if difference < 0:

                lines.append(
                    f"📉 *Fiyat düştü:* "
                    f"{abs(difference):,} TL "
                    f"(%{abs(percentage):.1f})"
                    .replace(",", ".")
                )

            elif difference > 0:

                lines.append(
                    f"📈 *Fiyat arttı:* "
                    f"{difference:,} TL "
                    f"(%{percentage:.1f})"
                    .replace(",", ".")
                )

            else:

                lines.append(
                    "➡️ Fiyat değişmedi."
                )

        else:

            lines.append(
                "🆕 İlk fiyat kaydı."
            )

        # Çocuklarla seyahat değerlendirmesi
        if flight["duration"]:

            if flight["duration"] <= 300:
                lines.append(
                    "👨‍👩‍👧‍👦 *Süre:* Çocuklarla seyahat için iyi"
                )
            elif flight["duration"] <= 600:
                lines.append(
                    "👨‍👩‍👧‍👦 *Süre:* Orta uzunlukta"
                )
            else:
                lines.append(
                    "👨‍👩‍👧‍👦 *Süre:* Uzun yolculuk"
                )

        lines.append(
            f"🔗 [Uçuşları görüntüle]({flight['url']})"
        )

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# ============================================================
# ÖZEL AKTARMALI RAPOR
# ============================================================

def build_connection_report(flights):

    connection_flights = [
        f for f in flights
        if f.get("stops") and f["stops"] > 0
    ]

    if not connection_flights:
        return (
            "\n\n🔄 *AKTARMALI UÇUŞLAR*\n\n"
            "Bu taramada ayrıntılı aktarmalı "
            "uçuş bilgisi okunamadı."
        )

    connection_flights = sorted(
        connection_flights,
        key=lambda x: x["price"]
    )

    lines = [
        "",
        "",
        "🔄 *AKTARMALI UÇUŞLAR*",
        "",
        "Özellikle çocuklarla seyahat "
        "açısından değerlendirildi:",
        ""
    ]

    for flight in connection_flights[:10]:

        lines.append(
            f"✈️ {flight['origin']} → Paris"
        )

        lines.append(
            f"💰 {flight['price']:,} TL"
            .replace(",", ".")
        )

        lines.append(
            f"🏷 {flight['airline']}"
        )

        lines.append(
            f"🔄 {flight['stops']} aktarma"
        )

        lines.append(
            f"📍 {flight['connection']}"
        )

        lines.append(
            f"⏱ {format_minutes(flight['duration'])}"
        )

        lines.append(
            connection_comment(
                flight.get("connection_minutes")
            )
        )

        lines.append(
            f"🔗 [Detay]({flight['url']})"
        )

        lines.append("")

    return "\n".join(lines)


# ============================================================
# ANA PROGRAM
# ============================================================

async def main():

    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "TELEGRAM_TOKEN tanımlanmamış."
        )

    if not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID tanımlanmamış."
        )

    all_flights = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1366,
                "height": 900
            },
            locale="tr-TR"
        )

        page = await context.new_page()

        # ====================================================
        # TÜM TARİH KOMBINASYONLARI
        # ====================================================

        for departure_date in DEPARTURE_DATES:

            for return_date in RETURN_DATES:

                for city, (airport, _) in ROUTES.items():

                    print(
                        f"🔎 {city} "
                        f"{departure_date} → {return_date}"
                    )

                    url = create_turna_url(
                        airport,
                        departure_date,
                        return_date
                    )

                    flights = await extract_flight_information(
                        page,
                        url,
                        city
                    )

                    for flight in flights:

                        flight["departure_date"] = (
                            departure_date
                        )

                        flight["return_date"] = (
                            return_date
                        )

                    all_flights.extend(flights)

        await browser.close()

    # ========================================================
    # TEKRARLARI TEMİZLE
    # ========================================================

    unique = {}

    for flight in all_flights:

        key = (
            flight["origin"],
            flight["departure_date"],
            flight["return_date"],
            flight["price"],
            flight["airline"],
            flight["stops"]
        )

        unique[key] = flight

    all_flights = list(unique.values())

    # ========================================================
    # EN UCUZLAR
    # ========================================================

    all_flights.sort(
        key=lambda x: x["price"]
    )

    # ========================================================
    # TELEGRAM
    # ========================================================

    bot = Bot(
        token=TELEGRAM_TOKEN
    )

    # Telegram mesaj limiti nedeniyle
    # ana raporu parçalara böl
    report = build_flight_report(
        all_flights
    )

    connection_report = build_connection_report(
        all_flights
    )

    final_report = report + connection_report

    # 4096 karakter sınırı
    chunks = []

    while len(final_report) > 3900:

        cut = final_report.rfind(
            "\n",
            0,
            3900
        )

        if cut == -1:
            cut = 3900

        chunks.append(
            final_report[:cut]
        )

        final_report = final_report[cut:]

    if final_report:
        chunks.append(final_report)

    for chunk in chunks:

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=chunk,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

        await asyncio.sleep(1)

    print(
        f"✅ Rapor gönderildi. "
        f"{len(all_flights)} seçenek bulundu."
    )


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())
