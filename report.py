from datetime import datetime
from typing import List, Dict
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
import os

class ReportGenerator:
    def __init__(self):
        self.report_dir = "reports"
        os.makedirs(self.report_dir, exist_ok=True)

    def generate_pdf(self, results: List[Dict], history_comparisons: Dict, 
                     best_options: List[Dict], depart_dates: List[str], 
                     return_dates: List[str], run_time: str) -> str:
        """PDF raporu oluştur - Google'sız!"""
        
        filename = f"{self.report_dir}/uçak_bileti_raporu_{run_time}.pdf"
        
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # ═══════════════════════════════════════════
        # BAŞLIK
        # ═══════════════════════════════════════════
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
        time_of_day = "🌅 Sabah" if 6 <= now.hour < 12 else "☀️ Öğle" if 12 <= now.hour < 17 else "🌆 Akşam" if 17 <= now.hour < 22 else "🌙 Gece"
        
        story.append(Paragraph(f"📅 {now.strftime('%d %B %Y %H:%M')} - {time_of_day}", styles['Normal']))
        story.append(Paragraph(f"🔄 #{run_time}", styles['Normal']))
        story.append(Paragraph(f"👨‍👩‍👧 1 yetişkin + 2 çocuk", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # ═══════════════════════════════════════════
        # İSTATİSTİK
        # ═══════════════════════════════════════════
        story.append(Paragraph("📊 ARAMA SONUÇLARI", styles['Heading2']))
        story.append(Paragraph(f"Toplam bulunan uçuş: {len(results)}", styles['Normal']))
        story.append(Paragraph(f"Gidiş tarihleri: {', '.join(depart_dates)}", styles['Normal']))
        story.append(Paragraph(f"Dönüş tarihleri: {', '.join(return_dates)}", styles['Normal']))
        
        # Kaynak dağılımı
        sources = {}
        for flight in results:
            src = flight.get('source', 'BİLGİ ALINAMADI')
            sources[src] = sources.get(src, 0) + 1
        
        if sources:
            story.append(Paragraph("Kaynaklar:", styles['Normal']))
            for src, count in sources.items():
                story.append(Paragraph(f"  • {src}: {count} uçuş", styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # ═══════════════════════════════════════════
        # EN İYİ 3 SEÇENEK
        # ═══════════════════════════════════════════
        story.append(Paragraph("🥇 EN İYİ 3 SEÇENEK", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        medals = ['🥇', '🥈', '🥉']
        labels = ['En Ucuz', 'En Dengeli', 'En Rahat']
        
        for i, option in enumerate(best_options[:3]):
            if option.get('airline') == 'BULUNAMADI' or option.get('price', 0) == 0:
                story.append(Paragraph(f"{medals[i]} {labels[i]} - UÇUŞ BULUNAMADI", styles['Heading3']))
                continue
                
            story.append(Paragraph(f"{medals[i]} <b>{labels[i]}</b>", styles['Heading3']))
            story.append(Paragraph(f"✈️ Havayolu: {option.get('airline', 'BİLGİ ALINAMADI')}", styles['Normal']))
            story.append(Paragraph(f"💰 Fiyat: {option.get('price', 'BİLGİ ALINAMADI')} TL", styles['Normal']))
            
            # Kaynak
            source = option.get('source', 'BİLGİ ALINAMADI')
            story.append(Paragraph(f"📡 Kaynak: {source}", styles['Normal']))
            
            if option.get('stops', 0) > 0:
                story.append(Paragraph(f"🔄 {option.get('stops')} aktarma", styles['Normal']))
            else:
                story.append(Paragraph("✈️ Direkt uçuş", styles['Normal']))
            
            if option.get('depart_time') and option.get('depart_time') != 'BİLGİ ALINAMADI':
                story.append(Paragraph(f"🕐 Kalkış: {option.get('depart_time')}", styles['Normal']))
            
            if option.get('link'):
                story.append(Paragraph(f"🔗 <link href='{option['link']}'>Uçuşu görüntüle</link>", styles['Normal']))
            
            story.append(Spacer(1, 10))
        
        # ═══════════════════════════════════════════
        # FİYAT DEĞİŞİMLERİ
        # ═══════════════════════════════════════════
        story.append(PageBreak())
        story.append(Paragraph("📈 FİYAT DEĞİŞİMLERİ", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        changes_found = False
        for key, comp in history_comparisons.items():
            if comp.get('previous_price'):
                changes_found = True
                diff = comp['difference']
                arrow = "📉 DÜŞTÜ" if diff < 0 else "📈 ARTTI" if diff > 0 else "➖ AYNI"
                
                story.append(Paragraph(f"<b>{key}</b>", styles['Normal']))
                story.append(Paragraph(f"  Dün: {comp['previous_price']} TL", styles['Normal']))
                story.append(Paragraph(f"  Bugün: {comp['current_price']} TL", styles['Normal']))
                story.append(Paragraph(f"  {arrow}: {abs(diff)} TL", styles['Normal']))
                story.append(Spacer(1, 5))
        
        if not changes_found:
            story.append(Paragraph("🆕 Henüz geçmiş veri yok", styles['Normal']))
        
        # ═══════════════════════════════════════════
        # TÜM UÇUŞLAR TABLOSU
        # ═══════════════════════════════════════════
        story.append(PageBreak())
        story.append(Paragraph("📋 TÜM UÇUŞLAR", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        if results:
            # Tablo başlıkları
            table_data = [['#', 'Kaynak', 'Havayolu', 'Fiyat (TL)', 'Aktarma']]
            
            for i, flight in enumerate(results[:30], 1):
                table_data.append([
                    str(i),
                    flight.get('source', 'BİLGİ ALINAMADI')[:15],
                    flight.get('airline', 'BİLGİ ALINAMADI')[:25],
                    str(flight.get('price', 'BİLGİ ALINAMADI')),
                    str(flight.get('stops', 0))
                ])
            
            if len(results) > 30:
                table_data.append([f"... ve {len(results)-30} daha fazla", "", "", "", ""])
            
            table = Table(table_data, colWidths=[1.5*cm, 3*cm, 5*cm, 2.5*cm, 2*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            story.append(table)
        else:
            story.append(Paragraph("❌ Uçuş bulunamadı", styles['Normal']))
        
        # ═══════════════════════════════════════════
        # FOOTER
        # ═══════════════════════════════════════════
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"<i>Bu rapor otomatik oluşturulmuştur. {now.strftime('%Y-%m-%d %H:%M:%S')}</i>", styles['Normal']))
        story.append(Paragraph(f"<i>Kaynaklar: Turna.com, Enuygun.com, Kiwi API</i>", styles['Normal']))
        story.append(Paragraph(f"<i>❌ Google Flights kullanılmamıştır</i>", styles['Normal']))
        
        # Raporu oluştur
        doc.build(story)
        return filename
