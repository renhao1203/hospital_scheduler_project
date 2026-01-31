from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # 🏥 護理長修正：讓 http://127.0.0.1:8000/ 直接變上傳頁
    path('', RedirectView.as_view(url='/upload/', permanent=True)),
    path('upload/', views.ScheduleUploadView.as_view(), name='upload'),
    path('optimize/<int:upload_id>/', views.ScheduleOptimizationView.as_view(), name='optimize'),
    path('result/<int:optimized_id>/', views.ResultView.as_view(), name='result'),
    path('export/<int:optimized_id>/', views.ExportPDFView.as_view(), name='export_pdf'),
    path('emergency/', views.EmergencySurgeryView.as_view(), name='emergency'),
]
