import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
from typing import List, Dict

class SkyscannerScraper:
    """SkyScanner - Alternatif kaynak"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    async def search(self, origin: str, destination: str, 
                     depart_date: str, return_date: str) -> List[Dict]:
        """SkyScanner'da ara"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            # SkyScanner URL
            url = f"https://www.skyscanner.com/transport/flights/{origin}/{destination}/{depart_date}/{return_date}/"
            
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(8000)
                
                page_text = await page.inner_text("body")
                
                flights = []
                prices = re.findall(r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:TL|₺|TRY)', page_text)
                
                for price_str in prices[:5]:
                    try:
                        price = int(price_str.replace('.', '').replace(',', ''))
                        flights.append({
                            'airline': 'BİLGİ ALINAMADI',
                            'price': price,
                            'price_currency': 'TL',
                            'price_type': 'kişi başı',
                            'stops': 0,
                            'source': 'SkyScanner',
                            'link': page.url
                        })
                    except:
                        pass
                
                return flights
                
            except Exception as e:
                print(f"SkyScanner hatası: {e}")
                return []
                
            finally:
                await browser.close()
