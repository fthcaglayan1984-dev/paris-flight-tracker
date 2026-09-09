import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
from typing import List, Dict

class TurnaScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.results = []
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    async def search(self, origin: str, destination: str, 
                     depart_date: str, return_date: str) -> List[Dict]:
        try:
            depart_dt = datetime.strptime(depart_date, "%Y-%m-%d")
            return_dt = datetime.strptime(return_date, "%Y-%m-%d")
            depart_str = depart_dt.strftime("%d.%m.%Y")
            return_str = return_dt.strftime("%d.%m.%Y")
        except:
            return []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            url = f"https://www.turna.com/ucak-bileti/{origin}-{destination}-{depart_str}-{return_str}-1-2-0"
            
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(5000)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/turna_{timestamp}.png")
                
                page_text = await page.inner_text("body")
                prices = re.findall(r'(\d{1,3}(?:\.\d{3})*)\s*TL', page_text)
                airlines = re.findall(r'([A-Za-zğüşıöçİĞÜŞİÖÇ\s]+)\s+Havayolu', page_text)
                
                flights = []
                if prices:
                    for i, price_str in enumerate(prices[:10]):
                        try:
                            price = int(price_str.replace('.', ''))
                            airline = airlines[i].strip() if i < len(airlines) and airlines[i].strip() else "BİLGİ ALINAMADI"
                            flights.append({
                                'airline': airline,
                                'price': price,
                                'price_currency': 'TL',
                                'price_type': 'kişi başı',
                                'depart_time': 'BİLGİ ALINAMADI',
                                'arrive_time': 'BİLGİ ALINAMADI',
                                'stops': 0,
                                'source': 'Turna',
                                'link': page.url
                            })
                        except:
                            pass
                
                return flights
                
            except Exception as e:
                print(f"Turna hatası: {e}")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/turna_error_{timestamp}.png")
                return []
                
            finally:
                await browser.close()
