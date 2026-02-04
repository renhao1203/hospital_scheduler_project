from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class OptimizationConfig:
    """優化配置參數 - 依臨床需求調優"""
    MIN_SLOT_DURATION = 60  
    DURATION_TOLERANCE = 0.15  
    CLEAN_TIME = 20  
    PRESERVE_FIRST_SURGERY = True

class SurgeryAnalyzer:
    """手術分析器 - 知識庫判定時長"""
    def __init__(self):
        self.config = OptimizationConfig
        self.surgery_knowledge = {
            'TRIGGER': {'duration': 30, 'priority': 5},
            'RELEASE': {'duration': 30, 'priority': 5},
            'PORT-A': {'duration': 45, 'priority': 4},
            'REMOVAL': {'duration': 40, 'priority': 4},
            'DJ': {'duration': 35, 'priority': 4},
            'EXCISION': {'duration': 45, 'priority': 4},
            'CONE': {'duration': 45, 'priority': 4},
            'CTS': {'duration': 40, 'priority': 4},
            'SPINAL': {'duration': 180, 'priority': 2},
            'FUSION': {'duration': 180, 'priority': 2},
            'FIXATION': {'duration': 120, 'priority': 2},
        }
    
    def estimate_duration(self, surgery_type: str) -> Dict[str, Any]:
        s_upper = surgery_type.upper()
        for keyword, info in self.surgery_knowledge.items():
            if keyword in s_upper:
                return {'duration': int(info['duration'] * (1 + self.config.DURATION_TOLERANCE)), 'priority': info['priority']}
        return {'duration': 105, 'priority': 3}

class ScheduleOptimizer:
    """手術排程優化器 - 平均分配負載策略"""
    def __init__(self):
        self.config = OptimizationConfig
        self.analyzer = SurgeryAnalyzer()
    
    def optimize(self, extracted_data: List[Dict], hospital_id: str = None) -> Dict:
        # 1. 初始化資源池
        for s in extracted_data:
            analysis = self.analyzer.estimate_duration(s['surgery_type'])
            s['duration'] = analysis['duration']
            s['priority'] = analysis['priority']
            s['is_scheduled'] = False
            s['is_tf'] = "TF" in str(s.get('time', '')).upper()
            s['original_room'] = s['room']
            s['original_time'] = s['time']

        # 2. 鎖定第一台 (📌 錨點絕對不動)
        pool = sorted(extracted_data, key=lambda x: (int(x['room']), x.get('sort_key', 0)))
        room_busy_until = {}
        optimized_list = []
        all_rooms = sorted(list(set(int(s['room']) for s in pool)))
        
        for r_int in all_rooms:
            r = str(r_int)
            room_ops = [s for s in pool if s['room'] == r]
            if room_ops:
                first = room_ops[0]
                first['is_scheduled'] = True
                first['status'] = "📌 第一台-保留"
                t_str = "08:00" if first['is_tf'] else first['time']
                curr_t = datetime.strptime(t_str, "%H:%M")
                first['time'] = curr_t.strftime("%H:%M")
                room_busy_until[r] = curr_t + timedelta(minutes=first['duration'] + self.config.CLEAN_TIME)
                optimized_list.append(first)

        # 3. 平均分配其餘手術 (打破房號牆壁)
        remaining = sorted([s for s in pool if not s['is_scheduled']], 
                           key=lambda x: (x['priority'], datetime.strptime("08:00" if x['is_tf'] else x['time'], "%H:%M")))
        
        total_saved = 0
        for surgery in remaining:
            # 🏥 關鍵邏輯：找出當前最早空出來的房間 (平均分配)
            best_room = min(room_busy_until.keys(), key=lambda r: room_busy_until[r])
            ready_t = room_busy_until[best_room]
            
            orig_t_str = "08:00" if surgery['is_tf'] else surgery['original_time']
            orig_t = datetime.strptime(orig_t_str, "%H:%M")
            
            # 🏥 鐵律：搬移後的時間絕對不准比原始時間晚
            if ready_t <= orig_t:
                surgery['is_scheduled'] = True
                surgery['room'] = best_room
                surgery['time'] = ready_t.strftime("%H:%M")
                surgery['status'] = f"🔄 重新分配(原房{surgery['original_room']})"
                total_saved += (orig_t - ready_t).total_seconds() / 60
                optimized_list.append(surgery)
                room_busy_until[best_room] = ready_t + timedelta(minutes=surgery['duration'] + self.config.CLEAN_TIME)
            else:
                # 若最早房也塞不下且不延後，則試圖排回原房或等待
                r_orig = surgery['original_room']
                ready_orig = room_busy_until.get(r_orig, datetime.strptime("08:00", "%H:%M"))
                act_t = max(ready_orig, orig_t)
                if act_t > orig_t and not surgery['is_tf']: act_t = orig_t
                
                surgery['is_scheduled'] = True
                surgery['room'], surgery['time'] = r_orig, act_t.strftime("%H:%M")
                surgery['status'] = "✅ 保持原房"
                optimized_list.append(surgery)
                room_busy_until[r_orig] = act_t + timedelta(minutes=surgery['duration'] + self.config.CLEAN_TIME)

        return {
            'optimized_data': sorted(optimized_list, key=lambda x: (int(x['room']), x['time'])),
            'improvement': round((total_saved / 480) * 100, 1)
        }
