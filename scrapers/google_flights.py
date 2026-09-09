import os
import re
import time
import random
from datetime import datetime
from playwright.async_api import async_playwright
from typing import List, Dict

class GoogleFlightsScraper:
    def __init__(self, headless: bool = False):  # ← HEADLESS False!
        self.headless = headless
        self.results = []
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # Gerçek kullanıcı gibi görünmek için
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ]
        
        self.viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900}
        ]

    async def search(self, origin: str, destination: str, 
                     depart_date: str, return_date: str) -> List[Dict]:
        """Google Flights'ta uçuş ara - GERÇEK TARAYICI TAKLİDİ"""
        
        async with async_playwright() as p:
            # Rastgele user-agent ve viewport
            user_agent = random.choice(self.user_agents)
            viewport = random.choice(self.viewports)
            
            # Tarayıcı başlat - GERÇEK KULLANICI GİBİ
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-infobars',
                    '--disable-gpu',
                    '--no-first-run',
                    '--disable-extensions',
                    '--disable-default-apps'
                ]
            )
            
            # Context - GERÇEK KULLANICI
            context = await browser.new_context(
                user_agent=user_agent,
                viewport=viewport,
                locale='tr-TR',
                timezone_id='Europe/Istanbul',
                permissions=['geolocation'],
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False
            )
            
            page = await context.new_page()
            
            # JavaScript engellemelerini aş
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['tr-TR', 'tr', 'en-US', 'en']
                });
                window.chrome = {
                    runtime: {}
                };
            """)
            
            # Google Flights URL - Daha doğal URL
            url = f"https://www.google.com/travel/flights?q={origin}%20-%20{destination}%20{depart_date}%20%20{return_date}"
            
            try:
                # Rastgele bekleme (insan gibi)
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(random.randint(3000, 6000))
                
                # Rastgele scroll (insan gibi)
                await page.mouse.wheel(delta_x=0, delta_y=random.randint(100, 300))
                await page.wait_for_timeout(random.randint(1000, 2000))
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                # Debug için ekran görüntüsü
                await page.screenshot(path=f"{self.debug_dir}/google_{timestamp}.png", full_page=True)
                
                # Sayfa metnini al
                page_text = await page.inner_text("body")
                html = await page.content()
                with open(f"{self.debug_dir}/google_{timestamp}.html", "w", encoding='utf-8') as f:
                    f.write(html)
                
                # 🔥 YENİ: Dinamik içerik bekle
                await page.wait_for_selector('[role="main"]', timeout=10000, state='visible')
                await page.wait_for_timeout(random.randint(2000, 4000))
                
                # Fiyatları bul - Daha kapsamlı regex
                flights = self._extract_flights_from_text(page_text, page.url)
                
                # Eğer hiç uçuş bulunamadıysa, selector'larla dene
                if not flights:
                    flights = await self._extract_flights_with_selectors(page)
                
                self.results = flights
                return flights
                
            except Exception as e:
                print(f"Google Flights hatası: {e}")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                await page.screenshot(path=f"{self.debug_dir}/google_error_{timestamp}.png", full_page=True)
                with open(f"{self.debug_dir}/google_error_{timestamp}.html", "w", encoding='utf-8') as f:
                    f.write(await page.content())
                return []
                
            finally:
                await browser.close()

    def _extract_flights_from_text(self, text: str, url: str) -> List[Dict]:
        """Metinden uçuş bilgilerini çıkar - GELİŞMİŞ"""
        flights = []
        
        # Tüm fiyatları bul
        price_patterns = [
            r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:TL|₺|TRY)',
            r'(?:TL|₺|TRY)\s*(\d{1,3}(?:[.,]\d{3})*)',
            r'(\d{1,3}(?:[.,]\d{3})*)\s*₺',
            r'₺\s*(\d{1,3}(?:[.,]\d{3})*)'
        ]
        
        all_prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    price_str = str(match).replace('.', '').replace(',', '')
                    if price_str.isdigit() and int(price_str) > 100:
                        all_prices.append(int(price_str))
                except:
                    pass
        
        # Benzersiz fiyatlar (ilk 10)
        unique_prices = list(set(all_prices))[:10]
        
        for price in unique_prices:
            # Fiyatın yanındaki havayolunu bul
            airline = self._find_airline_near_price(text, str(price))
            
            # Aktarma bilgisi
            stops = 0
            if "aktarma" in text.lower() or "stop" in text.lower():
                stop_match = re.search(r'(\d+)\s*(?:aktarma|stop)', text, re.IGNORECASE)
                if stop_match:
                    stops = int(stop_match.group(1))
            
            flights.append({
                'airline': airline or "BİLGİ ALINAMADI",
                'price': price,
                'price_currency': 'TL',
                'price_type': 'kişi başı',
                'depart_time': 'BİLGİ ALINAMADI',
                'arrive_time': 'BİLGİ ALINAMADI',
                'stops': stops,
                'source': 'Google Flights',
                'link': url,
                'raw_price': price
            })
        
        return flights

    def _find_airline_near_price(self, text: str, price_str: str) -> str:
        """Fiyatın yanındaki havayolunu bul"""
        # Havayolu listesi
        airlines = [
            'Pegasus', 'AJet', 'Turkish Airlines', 'THY', 'Türk Hava Yolları',
            'Lufthansa', 'Air France', 'KLM', 'Eurowings', 'SunExpress',
            'Wizz Air', 'Ryanair', 'easyJet', 'British Airways', 'Emirates',
            'Qatar Airways', 'Iberia', 'SAS', 'Swiss', 'Austrian'
        ]
        
        # Fiyatın etrafındaki metni bul
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if price_str in line:
                # Önceki ve sonraki satırları kontrol et
                context = line
                if i > 0:
                    context += " " + lines[i-1]
                if i < len(lines) - 1:
                    context += " " + lines[i+1]
                
                for airline in airlines:
                    if airline.lower() in context.lower():
                        return airline
        
        return None

    async def _extract_flights_with_selectors(self, page) -> List[Dict]:
        """Selector'larla uçuşları bul"""
        flights = []
        
        # Farklı kart selector'ları
        card_selectors = [
            '.pIav2d', '.Y4z8G', '.yR1f2c', '.V88i3', 
            '[jsname="N5U9db"]', '[role="button"]',
            '.kQkAob', '.YMlIz', '.FExwuc'
        ]
        
        for selector in card_selectors:
            try:
                cards = await page.query_selector_all(selector)
                if cards:
                    for card in cards[:5]:
                        try:
                            text = await card.inner_text()
                            price_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:TL|₺)', text)
                            if price_match:
                                price = int(price_match.group(1).replace('.', '').replace(',', ''))
                                airline_match = re.search(r'([A-Za-zğüşıöçİĞÜŞİÖÇ\s]+)', text)
                                airline = airline_match.group(1).strip()[:30] if airline_match else "BİLGİ ALINAMADI"
                                
                                flights.append({
                                    'airline': airline,
                                    'price': price,
                                    'price_currency': 'TL',
                                    'price_type': 'kişi başı',
                                    'depart_time': 'BİLGİ ALINAMADI',
                                    'arrive_time': 'BİLGİ ALINAMADI',
                                    'stops': 0,
                                    'source': 'Google Flights (selector)',
                                    'link': page.url
                                })
                        except:
                            pass
                    if flights:
                        break
            except:
                continue
        
        return flights
