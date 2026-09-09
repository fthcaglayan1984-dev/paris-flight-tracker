import json
import os
from datetime import datetime
from typing import Dict

class PriceHistory:
    def __init__(self, history_file: str = "price_history.json"):
        self.history_file = history_file
        self.history = self.load_history()

    def load_history(self) -> Dict:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_history(self, data: Dict):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_previous_price(self, route_key: str) -> Dict:
        if route_key in self.history:
            return self.history[route_key]
        return None

    def update_price(self, route_key: str, price_data: Dict):
        today = datetime.now().strftime("%Y-%m-%d")
        price_data['last_checked'] = today
        self.history[route_key] = price_data
        self.save_history(self.history)

    def compare_with_previous(self, route_key: str, current_price: float) -> Dict:
        previous = self.get_previous_price(route_key)
        if previous:
            old_price = previous.get('price', current_price)
            difference = current_price - old_price
            
            if difference < -100:
                status = "📉 DÜŞTÜ"
            elif difference > 100:
                status = "📈 ARTTI"
            else:
                status = "➖ AYNI"
            
            return {
                'previous_price': old_price,
                'current_price': current_price,
                'difference': difference,
                'status': status,
                'previous_data': previous
            }
        else:
            return {
                'previous_price': None,
                'current_price': current_price,
                'difference': 0,
                'status': "🆕 İlk kayıt",
                'previous_data': None
            }
