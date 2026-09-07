import sys
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List

# إضافة المسار الحالي للمشروع
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# استيراد الدوال المطلوبة من worker
from worker import run_job, get_pending_job, update_job_status

app = FastAPI(title="YouTube AI Agent API")

# نموذج لبيانات الطلب
class JobRequest(BaseModel):
    id: str
    title: str
    feeds: Optional[List[str]] = []
    topic: Optional[dict] = None

@app.get("/")
def read_root():
    """مسار اختبار الجاهزية (Health Check)"""
    return {"status": "ok", "service": "YouTube AI Agent"}

@app.post("/start-job")
async def start_job_endpoint(job: JobRequest, background_tasks: BackgroundTasks):
    """
    استلام طلب إنشاء الفيديو وتشغيله في الخلفية فوراً
    """
    job_data = job.dict()
    
    # 1. إضافة المهمة إلى الخلفية فوراً دون الانتظار
    background_tasks.add_task(run_job, job_data)
    
    # 2. إرجاع استجابة فورية للعميل برقم المهمة
    return {
        "status": "processing",
        "job_id": job.id,
        "message": "تم بدء معالجة الفيديو في الخلفية بنجاح"
    }

@app.post("/process-pending")
async def process_pending_job(background_tasks: BackgroundTasks):
    """
    جلب المهمة القادمة من قاعدة البيانات وتشغيلها في الخلفية
    """
    job = get_pending_job()
    if not job:
        return {"status": "idle", "message": "لا توجد مهام قيد الانتظار حالياً"}

    # تشغيل المهمة في الخلفية
    background_tasks.add_task(run_job, job)
    
    job_id = job.get("id") or job.get("job_id")
    return {
        "status": "processing",
        "job_id": job_id,
        "message": "بدأت معالجة المهمة المنتظرة في الخلفية"
    }
    
