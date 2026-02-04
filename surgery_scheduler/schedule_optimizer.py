from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class OptimizationConfig:
    """優化配置參數 - 依臨床需求調優"""
    MIN_SLOT_DURATION = 60  
    DURATION_TOLERANCE = 0.15  
    CLEAN_TIME = 20  
    PRESERVE_FIRST_SURGERY = True
    
    # ML 分析設定
    USE_ML_ANALYSIS = True  # 啟用 ML 分析
    ML_PRIORITY = True  # ML 優先於知識庫
    
    # 緊急手術設定
    EMERGENCY_BUFFER = 30  # 緊急手術預留緩衝時間（分鐘）

class SurgeryAnalyzer:
    """整合式手術分析器：ML 模型 → 知識庫 → 預設值"""
    
    def __init__(self):
        self.config = OptimizationConfig
        
        # 嘗試載入 ML 模型
        self.ml_analyzer = None
        if self.config.USE_ML_ANALYSIS:
            try:
                from .ml_analyzer import MLSurgeryAnalyzer
                self.ml_analyzer = MLSurgeryAnalyzer()
                if self.ml_analyzer.is_ready():
                    print("✓ ML 模型已載入，將優先使用 ML 分析")
                else:
                    self.ml_analyzer = None
                    print("ℹ ML 模型未就緒，使用知識庫")
            except Exception as e:
                print(f"ℹ 無法載入 ML 模型: {e}，使用知識庫")
        
        # 知識庫（備用）
        self.surgery_knowledge = {
            'TRIGGER': {'duration': 30, 'priority': 5, 'category': '小型'},
            'RELEASE': {'duration': 30, 'priority': 5, 'category': '小型'},
            'PORT-A': {'duration': 45, 'priority': 4, 'category': '小型'},
            'REMOVAL': {'duration': 40, 'priority': 4, 'category': '小型'},
            'DJ': {'duration': 35, 'priority': 4, 'category': '小型'},
            'EXCISION': {'duration': 45, 'priority': 4, 'category': '小型'},
            'CONE': {'duration': 45, 'priority': 4, 'category': '小型'},
            'CTS': {'duration': 40, 'priority': 4, 'category': '小型'},
            'SPINAL': {'duration': 180, 'priority': 2, 'category': '大型'},
            'FUSION': {'duration': 180, 'priority': 2, 'category': '大型'},
            'FIXATION': {'duration': 120, 'priority': 2, 'category': '大型'},
            'DISKECTOMY': {'duration': 150, 'priority': 2, 'category': '大型'},
            'CRANIOTOMY': {'duration': 200, 'priority': 1, 'category': '大型'},
            'LAMINECTOMY': {'duration': 150, 'priority': 2, 'category': '大型'},
        }
    
    def estimate_duration(self, surgery_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        估算手術時長（整合 ML 和知識庫）
        優先級：ML 模型 > 知識庫 > 預設值
        """
        
        # 優先嘗試 ML 分析
        if self.ml_analyzer and self.config.ML_PRIORITY:
            ml_result = self.ml_analyzer.analyze_surgery(surgery_data)
            if ml_result:
                # ML 成功分析，加上容忍值
                base_duration = ml_result.get('estimated_duration', 90)
                return {
                    'duration': int(base_duration * (1 + self.config.DURATION_TOLERANCE)),
                    'base_duration': base_duration,
                    'priority': ml_result.get('priority', 3),
                    'category': ml_result.get('category', '中型'),
                    'method': 'ML',
                    'confidence': ml_result.get('confidence', 0.0)
                }
        
        # 使用知識庫
        surgery_type = surgery_data.get('surgery_type', '').upper()
        for keyword, info in self.surgery_knowledge.items():
            if keyword in surgery_type:
                base_duration = info['duration']
                return {
                    'duration': int(base_duration * (1 + self.config.DURATION_TOLERANCE)),
                    'base_duration': base_duration,
                    'priority': info['priority'],
                    'category': info.get('category', '中型'),
                    'method': '知識庫',
                    'confidence': 0.8
                }
        
        # 預設值
        return {
            'duration': 105,
            'base_duration': 90,
            'priority': 3,
            'category': '中型',
            'method': '預設',
            'confidence': 0.5
        }


class EmergencySurgeryInserter:
    """緊急手術插入器"""
    
    def __init__(self, analyzer: SurgeryAnalyzer):
        self.analyzer = analyzer
        self.config = OptimizationConfig
    
    def find_best_room(self, current_schedule: List[Dict]) -> Dict[str, Any]:
        """
        找出最適合插入緊急手術的房間
        
        策略：
        1. 優先選擇當前空閒的房間
        2. 其次選擇最快空出的房間
        3. 評估影響最小的房間
        """
        
        # 按房間分組
        by_room = {}
        for s in current_schedule:
            room = s['room']
            if room not in by_room:
                by_room[room] = []
            by_room[room].append(s)
        
        # 評估每個房間
        room_scores = []
        current_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        
        for room, surgeries in by_room.items():
            if not surgeries:
                # 空房間，最優選擇
                room_scores.append({
                    'room': room,
                    'score': 1000,
                    'insert_time': current_time,
                    'affected_surgeries': 0,
                    'reason': '空閒房間'
                })
                continue
            
            # 排序手術
            sorted_surgeries = sorted(surgeries, 
                key=lambda x: datetime.strptime(x.get('time', '08:00'), '%H:%M'))
            
            # 計算最後一台手術的結束時間
            last_surgery = sorted_surgeries[-1]
            last_time = datetime.strptime(last_surgery['time'], '%H:%M')
            last_end = last_time + timedelta(
                minutes=last_surgery.get('duration', 90) + self.config.CLEAN_TIME
            )
            
            # 影響的手術數量
            affected = len(sorted_surgeries)
            
            # 評分
            time_score = max(0, 100 - (last_end.hour - 8) * 10)
            impact_score = max(0, 100 - affected * 15)
            total_score = time_score + impact_score
            
            room_scores.append({
                'room': room,
                'score': total_score,
                'insert_time': last_end,
                'affected_surgeries': affected,
                'reason': f"於 {last_end.strftime('%H:%M')} 插入，影響 {affected} 台手術"
            })
        
        # 選擇最佳房間
        best = max(room_scores, key=lambda x: x['score'])
        return best
    
    def insert_emergency(self, current_schedule: List[Dict], 
                        emergency_surgery: Dict) -> Dict[str, Any]:
        """
        插入緊急手術並調整排程
        
        Args:
            current_schedule: 當前排程
            emergency_surgery: 緊急手術資料
                {
                    'patient': '病患姓名',
                    'doctor': '醫師姓名',
                    'surgery_type': '手術類型',
                    'urgency_level': 1-5
                }
        """
        
        print(f"\n{'='*60}")
        print(f"🚨 緊急手術插入處理")
        print(f"{'='*60}")
        
        # 1. 分析緊急手術（使用 ML 或知識庫）
        print(f"\n[1] 分析緊急手術...")
        analysis = self.analyzer.estimate_duration(emergency_surgery)
        emergency_surgery['duration'] = analysis['duration']
        emergency_surgery['base_duration'] = analysis.get('base_duration', analysis['duration'])
        emergency_surgery['priority'] = 1  # 最高優先級
        emergency_surgery['is_emergency'] = True
        emergency_surgery['category'] = analysis.get('category', '中型')
        emergency_surgery['analysis_method'] = analysis.get('method', '預設')
        
        print(f"  手術: {emergency_surgery['surgery_type']}")
        print(f"  時長: {analysis.get('base_duration', 90)}分 (含容忍值: {analysis['duration']}分)")
        print(f"  分析: {analysis.get('method', '預設')}")
        
        # 2. 尋找最佳房間
        print(f"\n[2] 尋找最適合的房間...")
        best_room = self.find_best_room(current_schedule)
        
        print(f"  選擇: 房間 {best_room['room']}")
        print(f"  理由: {best_room['reason']}")
        
        # 3. 插入緊急手術
        print(f"\n[3] 插入緊急手術並調整排程...")
        
        emergency_surgery['room'] = best_room['room']
        emergency_surgery['time'] = best_room['insert_time'].strftime('%H:%M')
        emergency_surgery['status'] = '🚨 緊急手術'
        emergency_surgery['is_scheduled'] = True
        emergency_surgery['original_room'] = best_room['room']
        emergency_surgery['original_time'] = emergency_surgery['time']
        
        # 4. 調整該房間其他手術（往後延）
        adjusted_schedule = []
        delay_minutes = emergency_surgery['duration'] + self.config.CLEAN_TIME + self.config.EMERGENCY_BUFFER
        
        for surgery in current_schedule:
            if surgery['room'] == best_room['room']:
                # 該房間的手術需要延後
                original_time = datetime.strptime(surgery['time'], '%H:%M')
                new_time = original_time + timedelta(minutes=delay_minutes)
                
                surgery['time'] = new_time.strftime('%H:%M')
                surgery['status'] = f"⏰ 因緊急手術延後 {delay_minutes} 分鐘"
                surgery['delayed_by_emergency'] = True
                
                print(f"  延後: {surgery['surgery_type']} → {surgery['time']}")
            
            adjusted_schedule.append(surgery)
        
        # 5. 將緊急手術加入排程
        adjusted_schedule.append(emergency_surgery)
        
        print(f"\n✓ 緊急手術已插入")
        
        return {
            'adjusted_schedule': adjusted_schedule,
            'emergency_surgery': emergency_surgery,
            'insertion_info': {
                'room': best_room['room'],
                'time': emergency_surgery['time'],
                'affected_surgeries': best_room['affected_surgeries'],
                'total_delay': delay_minutes
            }
        }


class ScheduleOptimizer:
    """手術排程優化器 - 整合 ML 分析 + 平均分配 + 緊急插入"""
    
    def __init__(self):
        self.config = OptimizationConfig
        self.analyzer = SurgeryAnalyzer()
        self.emergency_inserter = EmergencySurgeryInserter(self.analyzer)
    
    def optimize(self, extracted_data: List[Dict], hospital_id: str = None) -> Dict:
        """標準優化流程（整合 ML 分析）"""
        
        # 統計使用的分析方法
        ml_count = 0
        kb_count = 0
        default_count = 0
        
        # 1. 初始化並使用 ML/知識庫分析
        for s in extracted_data:
            analysis = self.analyzer.estimate_duration(s)
            s['duration'] = analysis['duration']
            s['base_duration'] = analysis.get('base_duration', analysis['duration'])
            s['priority'] = analysis['priority']
            s['category'] = analysis.get('category', '中型')
            s['analysis_method'] = analysis.get('method', '預設')
            s['is_scheduled'] = False
            s['is_tf'] = "TF" in str(s.get('time', '')).upper()
            s['original_room'] = s['room']
            s['original_time'] = s['time']
            
            # 統計
            if analysis.get('method') == 'ML':
                ml_count += 1
            elif analysis.get('method') == '知識庫':
                kb_count += 1
            else:
                default_count += 1

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
                first['is_first_surgery'] = True
                first['status'] = "📌 第一台-保留"
                t_str = "08:00" if first['is_tf'] else first['time']
                curr_t = datetime.strptime(t_str, "%H:%M")
                first['time'] = curr_t.strftime("%H:%M")
                room_busy_until[r] = curr_t + timedelta(minutes=first['duration'] + self.config.CLEAN_TIME)
                optimized_list.append(first)

        # 3. 平均分配其餘手術
        remaining = sorted([s for s in pool if not s['is_scheduled']], 
                           key=lambda x: (x['priority'], datetime.strptime("08:00" if x['is_tf'] else x['time'], "%H:%M")))
        
        total_saved = 0
        for surgery in remaining:
            best_room = min(room_busy_until.keys(), key=lambda r: room_busy_until[r])
            ready_t = room_busy_until[best_room]
            
            orig_t_str = "08:00" if surgery['is_tf'] else surgery['original_time']
            orig_t = datetime.strptime(orig_t_str, "%H:%M")
            
            if ready_t <= orig_t:
                surgery['is_scheduled'] = True
                surgery['room'] = best_room
                surgery['time'] = ready_t.strftime("%H:%M")
                surgery['status'] = f"🔄 重新分配(原房{surgery['original_room']})"
                total_saved += (orig_t - ready_t).total_seconds() / 60
                optimized_list.append(surgery)
                room_busy_until[best_room] = ready_t + timedelta(minutes=surgery['duration'] + self.config.CLEAN_TIME)
            else:
                r_orig = surgery['original_room']
                ready_orig = room_busy_until.get(r_orig, datetime.strptime("08:00", "%H:%M"))
                act_t = max(ready_orig, orig_t)
                if act_t > orig_t and not surgery['is_tf']: 
                    act_t = orig_t
                
                surgery['is_scheduled'] = True
                surgery['room'], surgery['time'] = r_orig, act_t.strftime("%H:%M")
                surgery['status'] = "✅ 保持原房"
                optimized_list.append(surgery)
                room_busy_until[r_orig] = act_t + timedelta(minutes=surgery['duration'] + self.config.CLEAN_TIME)

        return {
            'optimized_data': sorted(optimized_list, key=lambda x: (int(x['room']), x['time'])),
            'improvement': round((total_saved / 480) * 100, 1),
            'ml_analysis_count': ml_count,
            'kb_analysis_count': kb_count,
            'default_analysis_count': default_count
        }
    
    def insert_emergency_surgery(self, current_schedule: List[Dict], 
                                emergency_data: Dict) -> Dict:
        """
        插入緊急手術
        
        Args:
            current_schedule: 當前排程（optimized_data）
            emergency_data: 緊急手術資料
        """
        return self.emergency_inserter.insert_emergency(current_schedule, emergency_data)
