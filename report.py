from datetime import datetime
from typing import List, Dict
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import os

class ReportGenerator:
    def __init__(self):
        self.report_dir = "reports"
        os.makedirs(self.report_dir, exist_ok=True)

    def generate_pdf(self, results: List[Dict], history_comparisons: Dict, 
                     best_options: List[Dict], depart_dates: List[str], 
                     return_dates: List[str], run_time: str) -> str:
        filename = f"{self.report_dir}/uçak_bileti_raporu_{run_time}.pdf"
        
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30
        )
        story.append(Paragraph("✈️ PARİS UÇAK BİLETİ RAPORU", title_style))
        story.append(Spacer(1, 12))
        
        now = datetime.now()
        story.append(Paragraph(f"📅 {now.strftime('%d %B %Y %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"👨‍👩‍👧 1 yetişkin + 2 çocuk", styles['Normal']))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("🥇 EN İYİ 3 SEÇENEK", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        labels = ['En Ucuz', 'En Dengeli', 'En Rahat']
        medals = ['🥇', '🥈', '🥉']
        
        for i, option in enumerate(best_options[:3]):
            if option.get('airline') == 'BULUNAMADI' or option.get('price', 0) == 0:
                story.append(Paragraph(f"{medals[i]} {labels[i]} - UÇUŞ BULUNAMADI", styles['Heading3']))
                continue
                
            story.append(Paragraph(f"{medals[i]} {labels[i]}", styles['Heading3']))
            story.append(Paragraph(f"✈️ Havayolu: {option.get('airline', 'BİLGİ ALINAMADI')}", styles['Normal']))
            story.append(Paragraph(f"💰 Fiyat: {option.get('price', 'BİLGİ ALINAMADI')} TL", styles['Normal']))
            story.append(Spacer(1, 10))
        
        doc.build(story)
        return filename
