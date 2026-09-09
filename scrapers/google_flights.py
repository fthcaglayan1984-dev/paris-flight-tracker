import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
from typing import List, Dict

class GoogleFlightsScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.results = []
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    async def search(self, origin: str, destination: str, 
                     depart_date: str, return_date: str) -> List[Dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            url = f"https://www.google.com/travel/flights?q={origin}%20-%20{destination}%20{depart_date}%20%20{return_date}"
            
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(8000)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/google_{timestamp}.png")
                
                page_text = await page.inner_text("body")
                html = await page.content()
                with open(f"{self.debug_dir}/google_{timestamp}.html", "w", encoding='utf-8') as f:
                    f.write(html)
                
                flights = []
                prices = re.findall(r'(\d{1,3}(?:\.\d{3})*)\s*TL', page_text)
                airlines = re.findall(r'([A-Za-zğüşıöçİĞÜŞİÖÇ\s]+)\s+(?:uçuşu|flights?)', page_text, re.IGNORECASE)
                
                if prices:
                    for i, price_str in enumerate(prices[:10]):
                        try:
                            price = int(price_str.replace('.', ''))
                            airline = airlines[i] if i < len(airlines) else "BİLGİ ALINAMADI"
                            flights.append({
                                'airline': airline.strip() or "BİLGİ ALINAMADI",
                                'price': price,
                                'price_currency': 'TL',
                                'price_type': 'kişi başı',
                                'depart_time': 'BİLGİ ALINAMADI',
                                'arrive_time': 'BİLGİ ALINAMADI',
                                'stops': 0,
                                'source': 'Google Flights',
                                'link': page.url
                            })
                        except:
                            pass
                
                return flights
                
            except Exception as e:
                print(f"Google Flights hatası: {e}")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/google_error_{timestamp}.png")
                return []
                
            finally:
                await browser.close()
