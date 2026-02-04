from django.urls import path
from . import views

urlpatterns = [
    # 🏥 基礎上傳與優化路徑
    path('upload/', views.ScheduleUploadView.as_view(), name='upload'),
    path('optimize/<int:upload_id>/', views.ScheduleOptimizationView.as_view(), name='optimize'),
    path('result/<int:optimized_id>/', views.ResultView.as_view(), name='result'),
    
    # 🚑 急診手術入口 (解決 NoReverseMatch 報錯的關鍵)
    path('emergency/', views.EmergencySurgeryView.as_view(), name='emergency_surgery'),
    
    # PDF 匯出路徑
    path('export/<int:optimized_id>/', views.ExportPDFView.as_view(), name='export_pdf'),
]
