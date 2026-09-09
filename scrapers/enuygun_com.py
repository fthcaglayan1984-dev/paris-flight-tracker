import os
import re
import random
from datetime import datetime
from playwright.async_api import async_playwright
from typing import List, Dict

class EnuygunComScraper:
    """Enuygun.com - Türkiye'nin Ucuz Bilet Sitesi"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    async def search(self, origin: str, destination: str, 
                     depart_date: str, return_date: str) -> List[Dict]:
        """Enuygun.com'da uçuş ara"""
        
        try:
            # Enuygun tarih formatı: DD.MM.YYYY
            depart = datetime.strptime(depart_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            returns = datetime.strptime(return_date, "%Y-%m-%d").strftime("%d.%m.%Y")
        except:
            return []
        
        # Havalimanı dönüşümü
        airport_codes = {
            'ESB': 'ankara',
            'IST': 'istanbul',
            'SAW': 'istanbul-sabiha-gokcen',
            'CDG': 'paris',
            'ORY': 'paris-orly',
            'BVA': 'paris-beauvais'
        }
        
        origin_code = airport_codes.get(origin, origin.lower())
        dest_code = airport_codes.get(destination, destination.lower())
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            # Enuygun URL
            url = f"https://www.enuygun.com/ucak-bileti/{origin_code}-{dest_code}-{depart}-{returns}-1-2-0/"
            
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(random.randint(3000, 6000))
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/enuygun_{timestamp}.png")
                
                flights = []
                page_text = await page.inner_text("body")
                
                # Fiyatları bul
                prices = re.findall(r'(\d{1,3}(?:[.,]\d{3})*)\s*TL', page_text)
                airlines = re.findall(r'([A-Za-zğüşıöçİĞÜŞİÖÇ\s]{3,30})', page_text)
                
                for i, price_str in enumerate(prices[:10]):
                    try:
                        price = int(price_str.replace('.', '').replace(',', ''))
                        airline = airlines[i] if i < len(airlines) and len(airlines[i].strip()) > 2 else "BİLGİ ALINAMADI"
                        flights.append({
                            'airline': airline.strip()[:30],
                            'price': price,
                            'price_currency': 'TL',
                            'price_type': 'kişi başı',
                            'depart_time': 'BİLGİ ALINAMADI',
                            'arrive_time': 'BİLGİ ALINAMADI',
                            'stops': 0,
                            'source': 'Enuygun.com',
                            'link': page.url
                        })
                    except:
                        pass
                
                return flights
                
            except Exception as e:
                print(f"Enuygun hatası: {e}")
                return []
                
            finally:
                await browser.close()
