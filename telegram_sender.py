import os
import asyncio
from datetime import datetime
from telegram import Bot
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)

class TelegramSender:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_TOKEN ve TELEGRAM_CHAT_ID tanımlanmalı")
        
        self.bot = Bot(token=self.token)

    async def send_message(self, message: str):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            logging.info("Telegram mesajı gönderildi")
        except Exception as e:
            logging.error(f"Telegram hatası: {e}")

    async def send_pdf(self, pdf_path: str):
        if not pdf_path or not os.path.exists(pdf_path):
            return
        try:
            with open(pdf_path, 'rb') as pdf_file:
                await self.bot.send_document(chat_id=self.chat_id, document=pdf_file)
            logging.info("PDF gönderildi")
        except Exception as e:
            logging.error(f"PDF gönderme hatası: {e}")

    def format_report(self, results: List[Dict], best_options: List[Dict],
                     history_comparisons: Dict, depart_dates: List[str],
                     return_dates: List[str], run_time: str) -> str:
        now = datetime.now()
        hour = now.hour
        time_of_day = "🌅 Sabah" if 6 <= hour < 12 else "☀️ Öğle" if 12 <= hour < 17 else "🌆 Akşam" if 17 <= hour < 22 else "🌙 Gece"
        
        lines = []
        lines.append(f"✈️ <b>PARİS UÇAK BİLETİ RAPORU</b>")
        lines.append(f"🕐 {time_of_day} - {now.strftime('%d %B %Y %H:%M')}")
        lines.append(f"🔄 #{run_time}")
        lines.append("👨‍👩‍👧 1 yetişkin + 2 çocuk")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        
        lines.append("\n<b>🥇 EN İYİ 3 SEÇENEK</b>")
        medals = ['🥇', '🥈', '🥉']
        labels = ['En Ucuz', 'En Dengeli', 'En Rahat']
        
        for i, option in enumerate(best_options[:3]):
            if option.get('airline') == 'BULUNAMADI' or option.get('price', 0) == 0:
                lines.append(f"\n{medals[i]} {labels[i]} - UÇUŞ BULUNAMADI")
                continue
            lines.append(f"\n{medals[i]} <b>{labels[i]}</b>")
            lines.append(f"  ✈️ {option.get('airline', 'BİLGİ ALINAMADI')}")
            lines.append(f"  💰 {option.get('price', 'BİLGİ ALINAMADI')} TL")
        
        return "\n".join(lines)
