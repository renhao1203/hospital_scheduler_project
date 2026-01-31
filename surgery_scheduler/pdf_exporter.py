from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from datetime import datetime
import os

class SchedulePDFExporter:
    """排程 PDF 匯出器"""
    
    def __init__(self):
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            self.font = 'STSong-Light'
        except:
            self.font = 'Helvetica'
    
    def export(self, optimized_data, output_path='media/exports/optimized_schedule.pdf'):
        """匯出優化後的排程為 PDF"""
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        y = height - 50
        
        # 標題
        c.setFont(self.font, 14)
        title = f"優化後排程 - {datetime.now().strftime('%Y/%m/%d %H:%M')}"
        c.drawString(50, y, title)
        y -= 30
        
        # 按房間分組
        by_room = {}
        for surgery in optimized_data.get('optimized_data', []):
            room = surgery.get('room', 0)
            if room not in by_room:
                by_room[room] = []
            by_room[room].append(surgery)
        
        # 逐房間輸出
        for room, surgeries in sorted(by_room.items()):
            if y < 100:
                c.showPage()
                y = height - 50
            
            # 房間標題
            c.setFont(self.font, 11)
            c.drawString(50, y, f"房間：{room}")
            y -= 20
            
            # 表頭
            c.setFont(self.font, 8)
            c.drawString(50, y, "時間")
            c.drawString(100, y, "醫師")
            c.drawString(160, y, "手術類型")
            c.drawString(380, y, "優先級")
            c.drawString(440, y, "預估時長")
            y -= 15
            
            # 手術列表
            for s in surgeries:
                analysis = s.get('analysis', {})
                
                c.setFont(self.font, 8)
                c.drawString(50, y, s.get('time', ''))
                c.drawString(100, y, s.get('doctor', '未知'))
                
                surgery_type = s.get('surgery_type', '一般手術')[:30]
                c.drawString(160, y, surgery_type)
                
                priority = analysis.get('priority', 3)
                c.drawString(380, y, f"P{priority}")
                
                duration = analysis.get('estimated_duration', 90)
                c.drawString(440, y, f"{duration}分")
                
                y -= 12
                
                if y < 80:
                    c.showPage()
                    y = height - 50
            
            y -= 10
        
        c.save()
        return output_path
