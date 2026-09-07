import sys
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List

# إضافة المسار الحالي للمشروع
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# استيراد الدوال المطلوبة من worker
from worker import run_job, get_pending_job

app = FastAPI(
    title="YouTube AI Agent Controller",
    description="واجهة التحكم البسيطة في إنشاء وتوليد فيديوهات يوتيوب بالذكاء الاصطناعي",
    version="2.0.0"
)

# نموذج لبيانات طلب إنشاء فيديو بالطريقة التقليدية
class JobRequest(BaseModel):
    id: str
    title: str
    feeds: Optional[List[str]] = []
    topic: Optional[dict] = None

@app.get("/")
def read_root():
    """مسار فحص الجاهزية التشغيلية (Health Check)"""
    return {"status": "ok", "service": "YouTube AI Agent"}

@app.get("/quick-create")
async def quick_create(title: str, background_tasks: BackgroundTasks):
    """
    الطريقة الأبسط: إنشاء فيديو فوري بكتابة العنوان مباشرة في الرابط
    مثال: /quick-create?title=مستقبل_التقنية
    """
    job_data = {
        "id": f"job_{abs(hash(title))}",
        "title": title,
        "feeds": []
    }
    
    # تشغيل المهمة في الخلفية فوراً دون أي انتظار أو تعقيد
    background_tasks.add_task(run_job, job_data)
    
    return {
        "status": "success",
        "message": f"جاري الآن إنشاء الفيديو بالعنوان: '{title}' في الخلفية بنجاح 🚀"
    }

@app.post("/start-job")
async def start_job_endpoint(job: JobRequest, background_tasks: BackgroundTasks):
    """طريقة البدء المتقدمة عبر POST"""
    job_data = job.dict()
    background_tasks.add_task(run_job, job_data)
    return {
        "status": "processing", 
        "job_id": job.id, 
        "message": "تم استلام المهمة وبدأت معالجتها في الخلفية"
    }
    
