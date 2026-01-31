import re, pdfplumber

class ScheduleOCRProcessor:
    def process(self, file_path):
        all_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                all_text += (page.extract_text() or "") + "\n"
        
        schedule_data = []
        room_blocks = re.split(r'房間\s*[：:]\s*(\d+)', all_text)
        
        for i in range(1, len(room_blocks), 2):
            room_no = room_blocks[i]
            content = room_blocks[i+1]
            # 🏥 這裡改用更穩定的切割，確保 TF 不會遺失順序
            parts = re.split(r'(\n\s*\d{1,2}[:：]\d{2}|\n\s*TF)', content)
            
            for j in range(1, len(parts), 2):
                time_val = parts[j].strip()
                detail = parts[j+1]
                p_name, d_name, s_type = "待核對", "待核對", "一般手術"
                
                # 抓取病患與醫師
                p_m = re.search(r'^\s*([\u4e00-\u9fa5]{2,4})', detail.lstrip())
                if p_m: p_name = p_m.group(1)
                d_m = re.search(r'([\u4e00-\u9fa5]{2,3})\s*(?:推床|病床|接送)', detail)
                if d_m: d_name = d_m.group(1)
                
                # 抓取術式
                op_m = re.search(r'([A-Z0-9]{4,}[A-Z]*\s+[A-Za-z].*?)(?=\n|NOTE|手術部位|$)', detail, re.S)
                if op_m: s_type = op_m.group(1).strip().replace('\n', ' ')

                schedule_data.append({
                    'room': room_no, 'time': time_val, 'patient': p_name,
                    'doctor': d_name, 'surgery_type': s_type,
                    'original_time': time_val, 'original_room': room_no,
                    'sort_key': j # 🏥 關鍵：保留 PDF 中的原始出現順序
                })
        return {'schedule_data': schedule_data, 'raw_text': all_text}
