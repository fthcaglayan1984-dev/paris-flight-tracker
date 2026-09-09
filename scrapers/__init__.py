import asyncio
import os
import json
import logging
from datetime import datetime
from typing import List, Dict

# 🔥 YENİ: Google'sız scraper'lar
from scrapers.turna_com import TurnaComScraper
from scrapers.enuygun_com import EnuygunComScraper
from scrapers.kiwi_api import KiwiAPIScraper

# Yardımcı modüller
from history import PriceHistory
from report import ReportGenerator
from telegram_sender import TelegramSender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════
# KONFIGÜRASYON - Google YOK!
# ════════════════════════════════════════════════════

HEADLESS = True  # True olabilir, Google yok!

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
        """Tüm aramaları başlat - GOOGLE YOK!"""
        logger.info("🚀 Uçuş araması başlatılıyor...")
        logger.info("❌ Google Flights KULLANILMIYOR!")
        logger.info("✅ Kaynaklar: Turna.com, Enuygun.com, Kiwi API")
        logger.info(f"🕐 Çalışma zamanı: {self.run_time}")
        logger.info("═" * 50)

        # Tüm kombinasyonları dene
        for origin in ORIGIN_AIRPORTS:
            for dest in DESTINATION_AIRPORTS:
                for depart in DEPART_DATES:
                    for return_date in RETURN_DATES:
                        logger.info(f"🔍 Aranıyor: {origin} → {dest}, {depart} → {return_date}")

                        # 1. Turna.com
                        try:
                            scraper = TurnaComScraper(headless=HEADLESS)
                            results = await scraper.search(origin, dest, depart, return_date)
                            self._process_results(results, origin, dest, depart, return_date, "Turna.com")
                            logger.info(f"   ✅ Turna: {len(results)} uçuş")
                        except Exception as e:
                            logger.error(f"   ❌ Turna hatası: {e}")

                        # 2. Enuygun.com
                        try:
                            scraper = EnuygunComScraper(headless=HEADLESS)
                            results = await scraper.search(origin, dest, depart, return_date)
                            self._process_results(results, origin, dest, depart, return_date, "Enuygun.com")
                            logger.info(f"   ✅ Enuygun: {len(results)} uçuş")
                        except Exception as e:
                            logger.error(f"   ❌ Enuygun hatası: {e}")

                        # 3. Kiwi API (Senkron, ayrıca çalıştır)
                        try:
                            scraper = KiwiAPIScraper()
                            results = scraper.search(origin, dest, depart, return_date)
                            self._process_results(results, origin, dest, depart, return_date, "Kiwi API")
                            logger.info(f"   ✅ Kiwi: {len(results)} uçuş")
                        except Exception as e:
                            logger.error(f"   ❌ Kiwi hatası: {e}")

        logger.info("═" * 50)
        logger.info(f"📊 Toplam {len(self.all_flights)} uçuş bulundu")

        if not self.all_flights:
            logger.warning("⚠️ Hiç uçuş bulunamadı!")
            self._send_no_flights_report()
            return

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
                    'return_date': flight.get('return_date', '')
                })

    def _find_best_options(self):
        """En iyi 3 seçeneği belirle"""
        logger.info("🏆 En iyi seçenekler belirleniyor...")

        valid_flights = [f for f in self.all_flights if f.get('price', 0) > 0]

        if not valid_flights:
            self.best_options = [
                {'airline': 'BULUNAMADI', 'price': 0},
                {'airline': 'BULUNAMADI', 'price': 0},
                {'airline': 'BULUNAMADI', 'price': 0}
            ]
            return

        # Fiyata göre sırala
        sorted_by_price = sorted(valid_flights, key=lambda x: x['price'])

        # 1. En ucuz
        best_cheap = sorted_by_price[0] if sorted_by_price else None

        # 2. En dengeli
        def score(f):
            return f.get('price', 999999) / 1000 + f.get('stops', 10) * 2
        best_balanced = min(valid_flights, key=score) if valid_flights else None

        # 3. En rahat
        def comfort_score(f):
            return f.get('stops', 10) * 3 + f.get('price', 999999) / 10000
        best_comfort = min(valid_flights, key=comfort_score) if valid_flights else None

        self.best_options = []
        seen = set()
        for option in [best_cheap, best_balanced, best_comfort]:
            if option and id(option) not in seen:
                seen.add(id(option))
                self.best_options.append(option)

    def _generate_report(self):
        """Rapor oluştur ve gönder"""
        logger.info("📄 Rapor oluşturuluyor...")

        message = self.telegram.format_report(
            self.all_flights,
            self.best_options,
            self.history_comparisons,
            DEPART_DATES,
            RETURN_DATES,
            self.run_time
        )

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
        except Exception as e:
            logger.error(f"PDF hatası: {e}")

        try:
            asyncio.run(self.telegram.send_message(message))
            if pdf_path:
                asyncio.run(self.telegram.send_pdf(pdf_path))
        except Exception as e:
            logger.error(f"Telegram hatası: {e}")

        logger.info("✅ İşlem tamamlandı!")

    def _send_no_flights_report(self):
        """Hiç uçuş bulunamadı raporu"""
        message = """
✈️ PARİS UÇAK BİLETİ RAPORU

❌ UÇUŞ BULUNAMADI

Aranan Kaynaklar:
- Turna.com
- Enuygun.com
- Kiwi API

Aranan Tarihler:
- Gidiş: 15-18 Ekim 2026
- Dönüş: 29 Ekim, 1 Kasım, 3 Kasım 2026

⚠️ Sistem otomatik çalışmaya devam edecek.
        """
        asyncio.run(self.telegram.send_message(message))

async def main():
    tracker = FlightTracker()
    await tracker.run_search()

if __name__ == "__main__":
    asyncio.run(main())
