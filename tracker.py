import asyncio
import os
from datetime import datetime
import logging

from scrapers.google_flights import GoogleFlightsScraper
from scrapers.turna import TurnaScraper
from history import PriceHistory
from report import ReportGenerator
from telegram_sender import TelegramSender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HEADLESS = True
DEPART_DATES = ["2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]
RETURN_DATES = ["2026-10-29", "2026-11-01", "2026-11-03"]
ORIGIN_AIRPORTS = ["ESB", "IST", "SAW"]
DESTINATION_AIRPORTS = ["CDG", "ORY", "BVA"]

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
        logging.info(f"🚀 Uçuş araması başlatılıyor...")
        logging.info(f"🕐 Çalışma zamanı: {self.run_time}")
        
        for origin in ORIGIN_AIRPORTS:
            for dest in DESTINATION_AIRPORTS:
                for depart in DEPART_DATES:
                    for return_date in RETURN_DATES:
                        logging.info(f"🔍 Aranıyor: {origin} → {dest}, {depart} → {return_date}")
                        
                        google_scraper = GoogleFlightsScraper(headless=HEADLESS)
                        google_results = await google_scraper.search(origin, dest, depart, return_date)
                        self.process_results(google_results, origin, dest, depart, return_date)
                        
                        turna_scraper = TurnaScraper(headless=HEADLESS)
                        turna_results = await turna_scraper.search(origin, dest, depart, return_date)
                        self.process_results(turna_results, origin, dest, depart, return_date)
        
        self.update_history()
        self.find_best_options()
        self.generate_report()
        
        return self.all_flights

    def process_results(self, results, origin, dest, depart, return_date):
        for flight in results:
            flight.update({
                'origin': origin,
                'destination': dest,
                'depart_date': depart,
                'return_date': return_date,
                'route_key': f"{origin}→{dest}_{depart}_{return_date}"
            })
            self.all_flights.append(flight)

    def update_history(self):
        for flight in self.all_flights:
            route_key = flight.get('route_key')
            if route_key and 'price' in flight:
                comp = self.history.compare_with_previous(route_key, flight['price'])
                self.history_comparisons[route_key] = comp
                self.history.update_price(route_key, {
                    'price': flight['price'],
                    'airline': flight.get('airline', 'BİLGİ ALINAMADI'),
                    'stops': flight.get('stops', 0),
                    'source': flight.get('source', 'BİLGİ ALINAMADI')
                })

    def find_best_options(self):
        if not self.all_flights:
            self.best_options = [
                {'airline': 'BULUNAMADI', 'price': 0},
                {'airline': 'BULUNAMADI', 'price': 0},
                {'airline': 'BULUNAMADI', 'price': 0}
            ]
            return
        
        sorted_flights = sorted([f for f in self.all_flights if 'price' in f], key=lambda x: x['price'])
        
        self.best_options = [
            sorted_flights[0] if sorted_flights else {'airline': 'BULUNAMADI', 'price': 0},
            sorted_flights[1] if len(sorted_flights) > 1 else {'airline': 'BULUNAMADI', 'price': 0},
            sorted_flights[2] if len(sorted_flights) > 2 else {'airline': 'BULUNAMADI', 'price': 0}
        ]

    def generate_report(self):
        logging.info("📄 Rapor oluşturuluyor...")
        
        message = self.telegram.format_report(
            self.all_flights,
            self.best_options,
            self.history_comparisons,
            DEPART_DATES,
            RETURN_DATES,
            self.run_time
        )
        
        pdf_path = self.report.generate_pdf(
            self.all_flights,
            self.history_comparisons,
            self.best_options,
            DEPART_DATES,
            RETURN_DATES,
            self.run_time
        )
        
        asyncio.run(self.telegram.send_message(message))
        if pdf_path:
            asyncio.run(self.telegram.send_pdf(pdf_path))
        
        logging.info(f"✅ Rapor oluşturuldu: {pdf_path}")

async def main():
    tracker = FlightTracker()
    await tracker.run_search()

if __name__ == "__main__":
    asyncio.run(main())
