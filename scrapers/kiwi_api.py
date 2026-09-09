import requests
import json
from datetime import datetime
from typing import List, Dict

class KiwiAPIScraper:
    """Kiwi.com API - Ücretsiz ve Güvenilir"""
    
    def __init__(self):
        self.base_url = "https://api.skypicker.com/flights"
    
    def search(self, origin: str, destination: str, 
               depart_date: str, return_date: str) -> List[Dict]:
        """Kiwi API ile uçuş ara - ÜCRETSİZ"""
        
        try:
            # API parametreleri
            params = {
                "flyFrom": origin,
                "to": destination,
                "dateFrom": depart_date,
                "dateTo": depart_date,
                "returnFrom": return_date,
                "returnTo": return_date,
                "adults": 1,
                "children": 2,
                "limit": 20,
                "curr": "TRY",
                "sort": "price",
                "asc": 1,
                "partner": "picky"
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            
            flights = []
            for flight in data.get('data', []):
                try:
                    # Havayolu bilgisi
                    airlines = []
                    for segment in flight.get('route', []):
                        if segment.get('airline'):
                            airlines.append(segment['airline'])
                    
                    # Fiyat
                    price = flight.get('price', 0)
                    
                    # Aktarma sayısı
                    stops = len(flight.get('route', [])) - 1
                    
                    flights.append({
                        'airline': ', '.join(list(set(airlines))[:2]) or "BİLGİ ALINAMADI",
                        'price': int(price),
                        'price_currency': 'TL',
                        'price_type': 'toplam',
                        'depart_time': flight.get('dTime', 'BİLGİ ALINAMADI'),
                        'arrive_time': flight.get('aTime', 'BİLGİ ALINAMADI'),
                        'stops': max(0, stops),
                        'source': 'Kiwi.com API',
                        'link': flight.get('deep_link', '')
                    })
                except:
                    continue
            
            return flights
            
        except Exception as e:
            print(f"Kiwi API hatası: {e}")
            return []
