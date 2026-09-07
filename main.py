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

app = FastAPI(
    title="YouTube AI Agent Controller",
    description="واجهة التحكم في إنشاء وتوليد فيديوهات يوتيوب بالذكاء الاصطناعي",
    version="1.0.0"
)

# نموذج لبيانات طلب إنشاء فيديو جديد
class JobRequest(BaseModel):
    id: str
    title: str
    feeds: Optional[List[str]] = []
    topic: Optional[dict] = None

@app.get("/", tags=["Status"])
def read_root():
    """مسار فحص الجاهزية التشغيلية (Health Check)"""
    return {"status": "ok", "service": "YouTube AI Agent", "docs": "/docs"}

@app.get("/trigger-process", tags=["Quick Actions"])
async def trigger_process_get(background_tasks: BackgroundTasks):
    """
    رابط سريع لفتح المتصفح المباشر: يجلب المهمة المنتظرة ويشغلها في الخلفية
    """
    job = get_pending_job()
    if not job:
        return {"status": "idle", "message": "لا توجد مهام قيد الانتظار حالياً في قاعدة البيانات"}

    background_tasks.add_task(run_job, job)
    job_id = job.get("id") or job.get("job_id")
    return {
        "status": "processing",
        "job_id": job_id,
        "message": f"بدأت معالجة المهمة {job_id} في الخلفية بنجاح"
    }

@app.post("/process-pending", tags=["Core API"])
async def process_pending_job(background_tasks: BackgroundTasks):
    """
    تشغيل المهمة القادمة من طابور الانتظار في الخلفية (POST)
    """
    job = get_pending_job()
    if not job:
        return {"status": "idle", "message": "لا توجد مهام قيد الانتظار حالياً"}

    background_tasks.add_task(run_job, job)
    job_id = job.get("id") or job.get("job_id")
    return {
        "status": "processing",
        "job_id": job_id,
        "message": "بدأت معالجة المهمة المنتظرة في الخلفية بنجاح"
    }

@app.post("/start-job", tags=["Core API"])
async def start_job_endpoint(job: JobRequest, background_tasks: BackgroundTasks):
    """
    إرسال بيانات مهمة جديدة مخصصة وتشغيلها في الخلفية
    """
    job_data = job.dict()
    background_tasks.add_task(run_job, job_data)
    return {
        "status": "processing",
        "job_id": job.id,
        "message": "تم استلام المهمة وبدأت معالجتها في الخلفية"
    }
    
