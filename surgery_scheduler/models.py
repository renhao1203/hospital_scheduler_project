from django.db import models

class Hospital(models.Model):
    name = models.CharField(max_length=100)

class OperatingRoom(models.Model):
    number = models.CharField(max_length=10)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

class Doctor(models.Model):
    name = models.CharField(max_length=50)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

class ScheduleUpload(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    uploaded_file = models.FileField(upload_to='schedules/')
    extracted_data = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

class Surgery(models.Model):
    operating_room = models.ForeignKey(OperatingRoom, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient_name = models.CharField(max_length=100)
    surgery_type = models.TextField()
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    # 🏥 關鍵：紀錄原始資訊以便對照
    original_start_time = models.CharField(max_length=20, null=True)
    original_room = models.CharField(max_length=10, null=True)
    estimated_duration = models.IntegerField(default=90)
    notes = models.TextField(null=True)
    nurse_assigned = models.CharField(max_length=50, null=True)

class OptimizedSchedule(models.Model):
    original_schedule = models.ForeignKey(ScheduleUpload, on_delete=models.CASCADE)
    optimized_data = models.JSONField()
    utilization_improvement = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
