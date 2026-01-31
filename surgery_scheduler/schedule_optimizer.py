from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json

class OptimizationConfig:
    """優化配置參數（已根據您的需求調優）"""
    # 🏥 關鍵修正：將最小時間槽降為 60 分鐘，否則吸不到刀
    MIN_SLOT_DURATION = 60  
    DURATION_TOLERANCE = 0.15 
    CLEAN_TIME = 20  
    USE_AI_ESTIMATION = False
    PRESERVE_FIRST_SURGERY = True

class SurgeryAnalyzer:
    """手術分析器 - 使用知識庫判斷手術時長"""
    def __init__(self):
        self.config = OptimizationConfig
        # 手術知識庫：對應您的 PDF 手術類型
        self.surgery_knowledge = {
            'TRIGGER': {'duration': 30, 'category': '小型'},
            'RELEASE': {'duration': 30, 'category': '小型'},
            'PORT-A': {'duration': 45, 'category': '小型'},
            'REMOVAL': {'duration': 40, 'category': '小型'},
            'DJ': {'duration': 35, 'category': '小型'},
            'EXCISION': {'duration': 45, 'category': '小型'},
            'CONE': {'duration': 45, 'category': '小型'},
            'CTS': {'duration': 40, 'category': '小型'},
            'SPINAL': {'duration': 180, 'category': '大型'},
            'FUSION': {'duration': 180, 'category': '大型'},
            'FIXATION': {'duration': 120, 'category': '大型'},
        }
    
    def estimate_duration(self, surgery_type: str) -> Dict[str, Any]:
        s_upper = surgery_type.upper()
        for keyword, info in self.surgery_knowledge.items():
            if keyword in s_upper:
                base = info['duration']
                return {
                    'base_duration': base,
                    'duration_with_tolerance': int(base * (1 + self.config.DURATION_TOLERANCE)),
                    'category': info['category']
                }
        return {'base_duration': 90, 'duration_with_tolerance': 105, 'category': '中型'}

class ScheduleOptimizer:
    def __init__(self):
        self.config = OptimizationConfig
        self.analyzer = SurgeryAnalyzer()
    
    def optimize(self, extracted_data: List[Dict], hospital_id: str = None) -> Dict:
        # 1. 初始化手術數據
        for s in extracted_data:
            analysis = self.analyzer.estimate_duration(s['surgery_type'])
            s['duration'] = analysis['duration_with_tolerance']
            s['is_scheduled'] = False
            # 處理 TF 時間：繼承前序或設為 08:00
            if "TF" in str(s['time']).upper():
                s['is_tf'] = True
            else:
                s['is_tf'] = False

        # 2. 排序：房號 -> PDF 原始順序 (sort_key)
        pool = sorted(extracted_data, key=lambda x: (int(x['room']), x.get('sort_key', 0)))
        
        optimized_list = []
        room_busy_until = {}
        all_rooms = sorted(list(set(int(s['room']) for s in pool)))

        for r_int in all_rooms:
            r = str(r_int)
            room_ops = [s for s in pool if s['room'] == r]
            if not room_ops: continue
            
            # 鎖定第一台 (📌 錨點)
            first = room_ops[0]
            first['is_scheduled'] = True
            first['status'] = "📌 第一台-保留"
            time_str = "08:00" if first['is_tf'] else first['time']
            curr_t = datetime.strptime(time_str, "%H:%M")
            first['time'] = curr_t.strftime("%H:%M")
            room_busy_until[r] = curr_t + timedelta(minutes=first['duration'] + self.config.CLEAN_TIME)
            optimized_list.append(first)

            # 處理後續手術
            for op in room_ops[1:]:
                # 計算空檔是否足以填補 (核心邏輯 3)
                orig_t_str = "08:00" if op['is_tf'] else op['time']
                next_orig_t = datetime.strptime(orig_t_str, "%H:%M")
                gap = int((next_orig_t - room_busy_until[r]).total_seconds() / 60)

                # 跨房填補嘗試
                if gap >= self.config.MIN_SLOT_DURATION:
                    candidates = [s for s in pool if not s['is_scheduled'] and s['room'] != r and s['duration'] <= 60]
                    for cand in sorted(candidates, key=lambda x: x['time'], reverse=True):
                        cand_orig = datetime.strptime(cand['time'], "%H:%M")
                        if room_busy_until[r] + timedelta(minutes=cand['duration'] + self.config.CLEAN_TIME) <= next_orig_t:
                            cand['is_scheduled'] = True
                            cand['original_room'], cand['original_time'] = cand['room'], cand['time']
                            cand['room'], cand['time'] = r, room_busy_until[r].strftime("%H:%M")
                            cand['status'] = f"🚀 跨房填補(房{cand['original_room']})"
                            optimized_list.append(cand)
                            room_busy_until[r] += timedelta(minutes=cand['duration'] + self.config.CLEAN_TIME)
                            break

                # 排入原房手術 (核心保護：不准變晚)
                op['is_scheduled'] = True
                act_t = max(room_busy_until[r], next_orig_t)
                if act_t > next_orig_t and not op['is_tf']:
                    act_t = next_orig_t # 鐵律：不變晚
                
                op['time'], op['status'] = act_t.strftime("%H:%M"), "✅ 智慧遞補"
                optimized_list.append(op)
                room_busy_until[r] = act_t + timedelta(minutes=op['duration'] + self.config.CLEAN_TIME)

        return {'optimized_data': optimized_list, 'improvement': len([s for s in optimized_list if '跨房' in s['status']]) * 10}
