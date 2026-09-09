import asyncio
import os
import json
import logging
from datetime import datetime
from typing import List, Dict

# Scraper'lar
from scrapers.google_flights import GoogleFlightsScraper
from scrapers.turna import TurnaScraper

# Yardımcı modüller
from history import PriceHistory
from report import ReportGenerator
from telegram_sender import TelegramSender

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════
# KONFIGÜRASYON
# ════════════════════════════════════════════════════

HEADLESS = True  # False yaparsanız tarayıcı açılır (debug için)

# Aranan tarihler
DEPART_DATES = ["2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]
RETURN_DATES = ["2026-10-29", "2026-11-01", "2026-11-03"]

# Havalimanları
ORIGIN_AIRPORTS = ["ESB", "IST", "SAW"]
DESTINATION_AIRPORTS = ["CDG", "ORY", "BVA"]

# ════════════════════════════════════════════════════
# ANA SINIF
# ════════════════════════════════════════════════════

class FlightTracker:
    def __init__(self):
        self.history = PriceHistory()
        self.report = ReportGenerator()
        self.telegram = TelegramSender()
        self.all_flights = []
        self.best_options = []
        self.history_comparisons = {}
        self.run_time = datetime.now().strftime("%Y%m%d_%H%M%S")

    async def run_search(self):
        """Tüm aramaları başlat"""
        logger.info("🚀 Uçuş araması başlatılıyor...")
        logger.info(f"🕐 Çalışma zamanı: {self.run_time}")
        logger.info(f"📅 Aranan gidiş: {DEPART_DATES}")
        logger.info(f"📅 Aranan dönüş: {RETURN_DATES}")
        logger.info(f"✈️ Kalkış: {ORIGIN_AIRPORTS} → Varış: {DESTINATION_AIRPORTS}")
        logger.info("═" * 50)

        # Tüm kombinasyonları dene
        for origin in ORIGIN_AIRPORTS:
            for dest in DESTINATION_AIRPORTS:
                for depart in DEPART_DATES:
                    for return_date in RETURN_DATES:
                        logger.info(f"🔍 Aranıyor: {origin} → {dest}, {depart} → {return_date}")

                        # 1. Google Flights
                        try:
                            google_scraper = GoogleFlightsScraper(headless=HEADLESS)
                            google_results = await google_scraper.search(origin, dest, depart, return_date)
                            self._process_results(google_results, origin, dest, depart, return_date, "Google Flights")
                            logger.info(f"   ✅ Google: {len(google_results)} uçuş bulundu")
                        except Exception as e:
                            logger.error(f"   ❌ Google hatası: {e}")

                        # 2. Turna
                        try:
                            turna_scraper = TurnaScraper(headless=HEADLESS)
                            turna_results = await turna_scraper.search(origin, dest, depart, return_date)
                            self._process_results(turna_results, origin, dest, depart, return_date, "Turna")
                            logger.info(f"   ✅ Turna: {len(turna_results)} uçuş bulundu")
                        except Exception as e:
                            logger.error(f"   ❌ Turna hatası: {e}")

        # İstatistik
        logger.info("═" * 50)
        logger.info(f"📊 Toplam {len(self.all_flights)} uçuş bulundu")

        # Geçmişi güncelle
        self._update_history()

        # En iyi seçenekleri belirle
        self._find_best_options()

        # Rapor oluştur
        self._generate_report()

        return self.all_flights

    def _process_results(self, results: List[Dict], origin: str, dest: str,
                         depart: str, return_date: str, source: str):
        """Sonuçları işle ve ekle"""
        if not results:
            return

        for flight in results:
            flight.update({
                'origin': origin,
                'destination': dest,
                'depart_date': depart,
                'return_date': return_date,
                'source': source,
                'route_key': f"{origin}→{dest}_{depart}_{return_date}",
                'timestamp': self.run_time
            })
            self.all_flights.append(flight)

    def _update_history(self):
        """Fiyat geçmişini güncelle"""
        logger.info("📊 Fiyat geçmişi güncelleniyor...")

        for flight in self.all_flights:
            route_key = flight.get('route_key')
            if route_key and 'price' in flight and flight['price'] > 0:
                comp = self.history.compare_with_previous(route_key, flight['price'])
                self.history_comparisons[route_key] = comp

                self.history.update_price(route_key, {
                    'price': flight['price'],
                    'airline': flight.get('airline', 'BİLGİ ALINAMADI'),
                    'stops': flight.get('stops', 0),
                    'source': flight.get('source', 'BİLGİ ALINAMADI'),
                    'depart_date': flight.get('depart_date', ''),
                    'return_date': flight.get('return_date', ''),
                    'origin': flight.get('origin', ''),
                    'destination': flight.get('destination', '')
                })

        logger.info(f"✅ {len(self.history_comparisons)} rota güncellendi")

    def _find_best_options(self):
        """En iyi 3 seçeneği belirle"""
        logger.info("🏆 En iyi seçenekler belirleniyor...")

        # Fiyatı olan uçuşları filtrele
        valid_flights = [f for f in self.all_flights if f.get('price', 0) > 0]

        if not valid_flights:
            logger.warning("⚠️ Fiyatı olan uçuş bulunamadı!")
            self.best_options = [
                {'airline': 'BULUNAMADI', 'price': 0, 'stops': 0},
                {'airline': 'BULUNAMADI', 'price': 0, 'stops': 0},
                {'airline': 'BULUNAMADI', 'price': 0, 'stops': 0}
            ]
            return

        # Fiyata göre sırala
        sorted_by_price = sorted(valid_flights, key=lambda x: x['price'])

        # 1. En ucuz (direkt veya 1 aktarma)
        best_cheap = None
        for f in sorted_by_price:
            if f.get('stops', 10) <= 1:
                best_cheap = f
                break
        if not best_cheap:
            best_cheap = sorted_by_price[0] if sorted_by_price else None

        # 2. En dengeli (fiyat + süre + aktarma)
        def score(f):
            price_score = f.get('price', 999999) / 1000
            stops_score = f.get('stops', 10) * 2
            return price_score + stops_score

        best_balanced = min(valid_flights, key=score) if valid_flights else None

        # 3. En rahat (az aktarma, makul fiyat)
        def comfort_score(f):
            stops = f.get('stops', 10)
            price = f.get('price', 999999)
            return (stops * 3) + (price / 10000)

        best_comfort = min(valid_flights, key=comfort_score) if valid_flights else None

        # Seçenekleri topla
        self.best_options = []
        seen = set()

        for option in [best_cheap, best_balanced, best_comfort]:
            if option and id(option) not in seen:
                seen.add(id(option))
                self.best_options.append(option)

        # Eğer 3'ten azsa diğerlerini ekle
        for f in valid_flights:
            if len(self.best_options) >= 3:
                break
            if id(f) not in seen:
                seen.add(id(f))
                self.best_options.append(f)

        # Emoji etiketleri ekle
        labels = ['En Ucuz', 'En Dengeli', 'En Rahat']
        for i, option in enumerate(self.best_options[:3]):
            if option.get('airline') != 'BULUNAMADI':
                option['best_label'] = labels[i] if i < len(labels) else f"Seçenek {i+1}"

        logger.info(f"✅ En iyi 3 seçenek belirlendi")

    def _generate_report(self):
        """Rapor oluştur ve gönder"""
        logger.info("📄 Rapor oluşturuluyor...")

        # 1. Telegram mesajı
        message = self.telegram.format_report(
            self.all_flights,
            self.best_options,
            self.history_comparisons,
            DEPART_DATES,
            RETURN_DATES,
            self.run_time
        )

        # 2. PDF Rapor
        pdf_path = None
        try:
            pdf_path = self.report.generate_pdf(
                self.all_flights,
                self.history_comparisons,
                self.best_options,
                DEPART_DATES,
                RETURN_DATES,
                self.run_time
            )
            logger.info(f"✅ PDF oluşturuldu: {pdf_path}")
        except Exception as e:
            logger.error(f"❌ PDF oluşturulamadı: {e}")

        # 3. Telegram'a gönder
        try:
            asyncio.run(self.telegram.send_message(message))
            logger.info("✅ Telegram mesajı gönderildi")

            if pdf_path:
                asyncio.run(self.telegram.send_pdf(pdf_path))
                logger.info("✅ PDF gönderildi")
        except Exception as e:
            logger.error(f"❌ Telegram gönderme hatası: {e}")

        logger.info("═" * 50)
        logger.info("✅ İşlem tamamlandı!")

# ════════════════════════════════════════════════════
# ÇALIŞTIRMA
# ════════════════════════════════════════════════════

async def main():
    """Ana çalıştırma fonksiyonu"""
    tracker = FlightTracker()
    await tracker.run_search()

if __name__ == "__main__":
    asyncio.run(main())
