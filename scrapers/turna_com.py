import os
import re
import json
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from typing import List, Dict
import asyncio

class TurnaComScraper:
    """Turna.com - Türkiye'nin En Büyük Uçak Bileti Sitesi"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    async def search(self, origin: str, destination: str, 
                     depart_date: str, return_date: str) -> List[Dict]:
        """Turna.com'da uçuş ara"""
        
        # Tarih formatını dönüştür
        try:
            depart_dt = datetime.strptime(depart_date, "%Y-%m-%d")
            return_dt = datetime.strptime(return_date, "%Y-%m-%d")
            depart_str = depart_dt.strftime("%d.%m.%Y")
            return_str = return_dt.strftime("%d.%m.%Y")
        except:
            return []
        
        # Havalimanı kodlarını dönüştür (Turna farklı kod kullanıyor)
        airport_map = {
            'ESB': 'Ankara',
            'IST': 'İstanbul',
            'SAW': 'İstanbul',
            'CDG': 'Paris',
            'ORY': 'Paris',
            'BVA': 'Paris'
        }
        
        origin_name = airport_map.get(origin, origin)
        dest_name = airport_map.get(destination, destination)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale='tr-TR'
            )
            
            page = await context.new_page()
            
            # Turna URL - Gidiş-Dönüş
            url = f"https://www.turna.com/ucak-bileti/{origin_name}-{dest_name}-{depart_str}-{return_str}-1-2-0"
            
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(random.randint(3000, 5000))
                
                # Rastgele scroll
                await page.mouse.wheel(delta_x=0, delta_y=random.randint(200, 500))
                await page.wait_for_timeout(random.randint(1000, 2000))
                
                # Debug
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/turna_{timestamp}.png")
                
                # Sayfa içeriğini al
                html = await page.content()
                with open(f"{self.debug_dir}/turna_{timestamp}.html", "w", encoding='utf-8') as f:
                    f.write(html)
                
                # 🔥 Uçuş sonuçlarını bul - Turna'nın özel yapısı
                flights = await self._extract_flights(page)
                
                return flights
                
            except Exception as e:
                print(f"Turna hatası: {e}")
                return []
                
            finally:
                await browser.close()
    
    async def _extract_flights(self, page) -> List[Dict]:
        """Turna'dan uçuş bilgilerini çıkar"""
        flights = []
        
        try:
            # Turna'nın sonuç kartları
            result_selectors = [
                '.flight-item',
                '.result-item',
                '.flight-card',
                '[data-testid="flight-card"]',
                '.offer-item'
            ]
            
            for selector in result_selectors:
                cards = await page.query_selector_all(selector)
                if cards:
                    print(f"✅ Turna: {len(cards)} kart bulundu")
                    for card in cards[:10]:
                        try:
                            text = await card.inner_text()
                            
                            # Fiyat bul
                            price_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s*TL', text)
                            if not price_match:
                                continue
                            
                            price = int(price_match.group(1).replace('.', '').replace(',', ''))
                            
                            # Havayolu bul
                            airline_match = re.search(r'([A-Za-zğüşıöçİĞÜŞİÖÇ\s]{2,30})', text)
                            airline = airline_match.group(1).strip() if airline_match else "BİLGİ ALINAMADI"
                            
                            # Saatler
                            times = re.findall(r'(\d{1,2}:\d{2})', text)
                            
                            # Aktarma
                            stop_match = re.search(r'(\d+)\s*aktarma', text, re.IGNORECASE)
                            stops = int(stop_match.group(1)) if stop_match else 0
                            
                            flights.append({
                                'airline': airline[:30],
                                'price': price,
                                'price_currency': 'TL',
                                'price_type': 'kişi başı',
                                'depart_time': times[0] if times else 'BİLGİ ALINAMADI',
                                'arrive_time': times[1] if len(times) > 1 else 'BİLGİ ALINAMADI',
                                'stops': stops,
                                'source': 'Turna.com',
                                'link': page.url,
                                'raw_text': text[:200]
                            })
                        except Exception as e:
                            print(f"Kart okuma hatası: {e}")
                    
                    if flights:
                        break
            
            # Eğer kart bulunamadıysa, sayfa metninden fiyatları çıkar
            if not flights:
                page_text = await page.inner_text("body")
                prices = re.findall(r'(\d{1,3}(?:[.,]\d{3})*)\s*TL', page_text)
                airlines = re.findall(r'([A-Za-zğüşıöçİĞÜŞİÖÇ\s]{3,20})\s+Havayolu', page_text)
                
                for i, price_str in enumerate(prices[:10]):
                    try:
                        price = int(price_str.replace('.', '').replace(',', ''))
                        airline = airlines[i] if i < len(airlines) else "BİLGİ ALINAMADI"
                        flights.append({
                            'airline': airline.strip()[:30],
                            'price': price,
                            'price_currency': 'TL',
                            'price_type': 'kişi başı',
                            'depart_time': 'BİLGİ ALINAMADI',
                            'arrive_time': 'BİLGİ ALINAMADI',
                            'stops': 0,
                            'source': 'Turna.com',
                            'link': page.url
                        })
                    except:
                        pass
        
        except Exception as e:
            print(f"Turna extract hatası: {e}")
        
        return flights
