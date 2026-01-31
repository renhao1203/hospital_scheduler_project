from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.utils import timezone
from datetime import timedelta, datetime
from .models import ScheduleUpload, OptimizedSchedule, Surgery, Doctor, OperatingRoom

class ScheduleUploadView(View):
    def get(self, request):
        return render(request, 'surgery_scheduler/upload.html', {'upload': None})
    def post(self, request):
        from .ocr_processor import ScheduleOCRProcessor
        uploaded_file = request.FILES.get('uploaded_file')
        if not uploaded_file: return redirect('upload')
        upload = ScheduleUpload.objects.create(uploaded_file=uploaded_file, hospital_id=1)
        processor = ScheduleOCRProcessor()
        # 🏥 OCR 處理，這裏會抓取 PDF 的 sort_key 確保順序
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
        # 🏥 執行您剛才提供的 AI 知識庫優化邏輯
        result = optimizer.optimize(upload.extracted_data, upload.hospital_id)
        
        for item in result.get('optimized_data', []):
            room, _ = OperatingRoom.objects.get_or_create(number=str(item['room']), hospital_id=upload.hospital_id)
            doc, _ = Doctor.objects.get_or_create(name=item.get('doctor', '待核對'), hospital_id=upload.hospital_id)
            start_t = timezone.make_aware(datetime.combine(datetime.today(), datetime.strptime(item['time'], '%H:%M').time()))
            
            # 🏥 關鍵：將優化器算出的 duration 存入資料庫，排程長度才會準
            Surgery.objects.create(
                operating_room=room, doctor=doc,
                scheduled_start=start_t,
                scheduled_end=start_t + timedelta(minutes=item.get('duration', 90)),
                original_start_time=item.get('original_time'),
                original_room=item.get('original_room'),
                patient_name=item.get('patient', '不明病患'),
                surgery_type=item.get('surgery_type', '一般手術'),
                notes='✅ ' + item.get('status', '智慧優化')
            )
        
        optimized = OptimizedSchedule.objects.create(
            original_schedule=upload, optimized_data=result,
            utilization_improvement=result.get('improvement', 0)
        )
        return redirect('result', optimized_id=optimized.id)

class ResultView(View):
    def get(self, request, optimized_id):
        optimized = get_object_or_404(OptimizedSchedule, id=optimized_id)
        all_surgeries = Surgery.objects.all().order_by('scheduled_start')
        
        raw_rooms_data = {}
        for s in all_surgeries:
            r_no = s.operating_room.number
            if r_no not in raw_rooms_data:
                raw_rooms_data[r_no] = {'surgeries': [], 'total_saved': 0}
            raw_rooms_data[r_no]['surgeries'].append(s)
            
            if s.original_start_time:
                try:
                    orig = datetime.strptime(s.original_start_time, '%H:%M')
                    now = s.scheduled_start.replace(tzinfo=None)
                    # 🏥 只有「提早」才會計入節省時間，避免變晚
                    diff = (orig.hour * 60 + orig.minute) - (now.hour * 60 + now.minute)
                    if diff > 0: raw_rooms_data[r_no]['total_saved'] += diff
                except Exception: pass
        
        # 🏥 數字排序邏輯：1 -> 3 -> 5 -> 10
        sorted_keys = sorted(raw_rooms_data.keys(), key=lambda x: int(x) if x.isdigit() else 999)
        rooms_data = {k: raw_rooms_data[k] for k in sorted_keys}
        
        return render(request, 'surgery_scheduler/result.html', {'optimized': optimized, 'rooms_data': rooms_data})

class ExportPDFView(View):
    def get(self, request, optimized_id):
        return redirect('result', optimized_id=optimized_id)

class EmergencySurgeryView(View):
    def post(self, request):
        return redirect('upload')
