import os
import django
import click
from datetime import datetime, timedelta

# 1. 初始化 Django 環境
# 如果你的專案資料夾名稱不是 hospital_scheduler，請修改此處
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital_scheduler.settings')
django.setup()

from surgery_scheduler.models import Surgery, Doctor, OperatingRoom
from surgery_scheduler.llm_analyzer import SurgeryLLMAnalyzer

@click.command()
@click.option('--patient', prompt='病人姓名', help='輸入緊急病人姓名')
@click.option('--surgery_name', prompt='手術法 (例如: SPINAL FUSION)', help='手術法名稱')
@click.option('--room_no', prompt='手術室編號', type=int, help='欲插入的手術室號碼')
@click.option('--doctor_name', prompt='主刀醫師姓名', help='醫師名稱')
def run_emergency(patient, surgery_name, room_no, doctor_name):
    """【醫療系統】緊急插刀 CLI 工具：自動分析並順延排程"""
    
    analyzer = SurgeryLLMAnalyzer() 
    now = datetime.now()
    
    # 2. 驗證資料庫物件 [cite: 480, 482, 490]
    try:
        room = OperatingRoom.objects.get(number=room_no)
        doctor = Doctor.objects.filter(name__icontains=doctor_name).first()
        if not doctor:
            click.secho(f"❌ 找不到醫師: {doctor_name}", fg='red')
            return
    except OperatingRoom.DoesNotExist:
        click.secho(f"❌ 找不到手術室 {room_no}", fg='red')
        return

    # 3. 智慧分析手術資訊 [cite: 162, 193]
    analysis = analyzer.analyze_surgery({'surgery_type': surgery_name})
    duration = analysis['estimated_duration'] [cite: 202]
    
    click.echo(f"\n[系統分析] 手術法: {surgery_name}")
    click.echo(f"[結果] 預估時長: {duration} 分鐘 | 優先級: 1 (緊急)")

    # 4. 決定插入時間點 [cite: 501, 527]
    # 邏輯：檢查目前該房間排程，排在最後一個正在進行或已排程手術之後
    last_op = Surgery.objects.filter(
        operating_room=room, 
        status__in=['scheduled', 'in_progress']
    ).order_by('-scheduled_end').first()

    start_time = now if not last_op or last_op.scheduled_end < now else last_op.scheduled_end
    end_time = start_time + timedelta(minutes=duration)

    # 5. 建立緊急手術物件 [cite: 496, 507]
    emergency_case = Surgery.objects.create(
        patient_name=patient,
        doctor=doctor,
        operating_room=room,
        surgery_type='trauma',
        estimated_duration=duration,
        scheduled_start=start_time,
        scheduled_end=end_time,
        status='scheduled',
        notes=f"🚨 終端緊急插刀：{surgery_name}"
    )

    click.secho(f"\n✅ 成功插入緊急手術！", fg='green', bold=True)
    click.echo(f"時段: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")

    # 6. 自動順延衝突手術 [cite: 721, 730]
    # 找出所有在緊急刀之後且狀態為「已排程」的手術
    conflicts = Surgery.objects.filter(
        operating_room=room,
        scheduled_start__lt=end_time,
        status='scheduled'
    ).exclude(id=emergency_case.id).order_by('scheduled_start')

    if conflicts.exists():
        click.echo(f"⚠️ 偵測到時間衝突，正在自動順延 {conflicts.count()} 筆手術...")
        current_pointer = end_time
        for s in conflicts:
            # 計算該手術原本的時長
            s_dur = (s.scheduled_end - s.scheduled_start).total_seconds() / 60
            s.scheduled_start = current_pointer
            s.scheduled_end = current_pointer + timedelta(minutes=s_dur)
            s.save()
            current_pointer = s.scheduled_end
        click.echo("✅ 後續排程已完成順延調整。")

if __name__ == '__main__':
    run_emergency()
