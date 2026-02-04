from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta, datetime
from .models import ScheduleUpload, OptimizedSchedule, Surgery, Doctor, OperatingRoom

class ScheduleUploadView(View):
    def get(self, request):
        return render(request, 'surgery_scheduler/upload.html', {'upload': None})
    
    def post(self, request):
        from .ocr_processor import ScheduleOCRProcessor
        uploaded_file = request.FILES.get('uploaded_file')
        if not uploaded_file: 
            return redirect('upload')
        
        upload = ScheduleUpload.objects.create(
            uploaded_file=uploaded_file, 
            hospital_id=1
        )
        
        processor = ScheduleOCRProcessor()
        result = processor.process(upload.uploaded_file.path)
        
        upload.extracted_data = result.get('schedule_data', [])
        upload.raw_text = result.get('raw_text', "")
        upload.save()
        
        return render(request, 'surgery_scheduler/upload.html', {'upload': upload})


class ScheduleOptimizationView(View):
    def post(self, request, upload_id):
        upload = get_object_or_404(ScheduleUpload, id=upload_id)
        Surgery.objects.all().delete()
        
        from .schedule_optimizer import ScheduleOptimizer
        optimizer = ScheduleOptimizer()
        
        # 執行優化（會自動使用 ML 分析）
        result = optimizer.optimize(upload.extracted_data, upload.hospital_id)
        
        # 儲存優化結果
        for item in result.get('optimized_data', []):
            room, _ = OperatingRoom.objects.get_or_create(
                number=str(item['room']), 
                hospital_id=upload.hospital_id
            )
            doc, _ = Doctor.objects.get_or_create(
                name=item.get('doctor', '待核對'), 
                hospital_id=upload.hospital_id
            )
            
            start_t = timezone.make_aware(
                datetime.combine(
                    datetime.today(), 
                    datetime.strptime(item['time'], '%H:%M').time()
                )
            )
            
            # 儲存 ML 分析結果
            analysis_method = item.get('analysis_method', '未知')
            category = item.get('category', '中型')
            base_duration = item.get('base_duration', item.get('duration', 90))
            
            notes = f"{item.get('status', '智慧優化')} | {analysis_method} | {category}"
            
            Surgery.objects.create(
                operating_room=room,
                doctor=doc,
                scheduled_start=start_t,
                scheduled_end=start_t + timedelta(minutes=item.get('duration', 90)),
                original_start_time=item.get('original_time'),
                original_room=item.get('original_room'),
                patient_name=item.get('patient', '不明病患'),
                surgery_type=item.get('surgery_type', '一般手術'),
                estimated_duration=base_duration,
                notes=notes
            )
        
        optimized = OptimizedSchedule.objects.create(
            original_schedule=upload,
            optimized_data=result,
            utilization_improvement=result.get('improvement', 0)
        )
        
        return redirect('result', optimized_id=optimized.id)


class EmergencySurgeryView(View):
    """緊急手術插入視圖"""
    
    def get(self, request):
        """顯示緊急手術表單"""
        latest_optimized = OptimizedSchedule.objects.order_by('-created_at').first()
        rooms = OperatingRoom.objects.all()
        doctors = Doctor.objects.all()
        
        context = {
            'latest_optimized': latest_optimized,
            'rooms': rooms,
            'doctors': doctors
        }
        
        return render(request, 'surgery_scheduler/emergency_form.html', context)
    
    def post(self, request):
        """處理緊急手術插入"""
        
        # 1. 獲取表單資料
        patient_name = request.POST.get('patient_name')
        doctor_name = request.POST.get('doctor_name')
        surgery_type = request.POST.get('surgery_type')
        urgency_level = int(request.POST.get('urgency_level', 1))
        notes = request.POST.get('notes', '')
        
        # 驗證
        if not all([patient_name, doctor_name, surgery_type]):
            return JsonResponse({
                'success': False,
                'error': '請填寫所有必填欄位'
            }, status=400)
        
        # 2. 獲取當前排程
        latest_optimized = OptimizedSchedule.objects.order_by('-created_at').first()
        if not latest_optimized:
            return JsonResponse({
                'success': False,
                'error': '找不到當前排程，請先上傳並優化排程'
            }, status=404)
        
        # 3. 準備緊急手術資料
        emergency_surgery = {
            'patient': patient_name,
            'doctor': doctor_name,
            'surgery_type': surgery_type,
            'urgency_level': urgency_level,
            'notes': notes
        }
        
        # 4. 插入緊急手術
        from .schedule_optimizer import ScheduleOptimizer
        optimizer = ScheduleOptimizer()
        
        current_schedule = latest_optimized.optimized_data.get('optimized_data', [])
        
        try:
            result = optimizer.insert_emergency_surgery(current_schedule, emergency_surgery)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'插入失敗: {str(e)}'
            }, status=500)
        
        # 5. 清除舊的手術記錄
        Surgery.objects.all().delete()
        
        # 6. 儲存新的排程（包含緊急手術）
        for item in result['adjusted_schedule']:
            room, _ = OperatingRoom.objects.get_or_create(
                number=str(item['room']), 
                hospital_id=1
            )
            doc, _ = Doctor.objects.get_or_create(
                name=item.get('doctor', '待核對'), 
                hospital_id=1
            )
            
            start_t = timezone.make_aware(
                datetime.combine(
                    datetime.today(), 
                    datetime.strptime(item['time'], '%H:%M').time()
                )
            )
            
            # 標記是否為緊急手術
            is_emergency = item.get('is_emergency', False)
            analysis_method = item.get('analysis_method', '未知')
            
            notes_text = item.get('status', '排程中')
            if analysis_method != '未知':
                notes_text += f" | {analysis_method}"
            
            Surgery.objects.create(
                operating_room=room,
                doctor=doc,
                scheduled_start=start_t,
                scheduled_end=start_t + timedelta(minutes=item.get('duration', 90)),
                original_start_time=item.get('original_time'),
                original_room=item.get('original_room'),
                patient_name=item.get('patient', '不明病患'),
                surgery_type=item.get('surgery_type', '一般手術'),
                estimated_duration=item.get('base_duration', item.get('duration', 90)),
                notes=notes_text
            )
        
        # 7. 創建新的優化記錄
        new_optimized_data = {
            'optimized_data': result['adjusted_schedule'],
            'improvement': latest_optimized.optimized_data.get('improvement', 0),
            'emergency_insertion': result['insertion_info']
        }
        
        new_optimized = OptimizedSchedule.objects.create(
            original_schedule=latest_optimized.original_schedule,
            optimized_data=new_optimized_data,
            utilization_improvement=latest_optimized.utilization_improvement
        )
        
        # 8. 返回結果
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'optimized_id': new_optimized.id,
                'insertion_info': result['insertion_info'],
                'redirect_url': f'/result/{new_optimized.id}/'
            })
        else:
            return redirect('result', optimized_id=new_optimized.id)


class ResultView(View):
    def get(self, request, optimized_id):
        optimized = get_object_or_404(OptimizedSchedule, id=optimized_id)
        all_surgeries = Surgery.objects.all().order_by('scheduled_start')
        
        raw_rooms_data = {}
        for s in all_surgeries:
            r_no = s.operating_room.number
            if r_no not in raw_rooms_data:
                raw_rooms_data[r_no] = {
                    'surgeries': [], 
                    'total_saved': 0,
                    'has_emergency': False
                }
            
            raw_rooms_data[r_no]['surgeries'].append(s)
            
            # 檢查是否有緊急手術
            if '🚨' in s.notes:
                raw_rooms_data[r_no]['has_emergency'] = True
            
            # 計算節省時間
            if s.original_start_time:
                try:
                    orig = datetime.strptime(s.original_start_time, '%H:%M')
                    now = s.scheduled_start.replace(tzinfo=None)
                    diff = (orig.hour * 60 + orig.minute) - (now.hour * 60 + now.minute)
                    if diff > 0: 
                        raw_rooms_data[r_no]['total_saved'] += diff
                except Exception: 
                    pass
        
        # 數字排序
        sorted_keys = sorted(raw_rooms_data.keys(), 
                           key=lambda x: int(x) if x.isdigit() else 999)
        rooms_data = {k: raw_rooms_data[k] for k in sorted_keys}
        
        # 檢查緊急手術資訊
        emergency_info = optimized.optimized_data.get('emergency_insertion')
        
        # ML 分析統計
        ml_count = optimized.optimized_data.get('ml_analysis_count', 0)
        kb_count = optimized.optimized_data.get('kb_analysis_count', 0)
        default_count = optimized.optimized_data.get('default_analysis_count', 0)
        
        context = {
            'optimized': optimized,
            'rooms_data': rooms_data,
            'emergency_info': emergency_info,
            'ml_analysis_count': ml_count,
            'kb_analysis_count': kb_count,
            'default_analysis_count': default_count
        }
        
        return render(request, 'surgery_scheduler/result.html', context)


class ExportPDFView(View):
    def get(self, request, optimized_id):
        return redirect('result', optimized_id=optimized_id)
