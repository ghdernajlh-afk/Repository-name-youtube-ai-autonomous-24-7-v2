import sys
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

# إضافة المسار الحالي للمشروع
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# استيراد الدوال المطلوبة من worker
from worker import run_job

app = FastAPI(
    title="YouTube AI Agent Controller",
    description="واجهة التحكم البسيطة في توليد فيديوهات يوتيوب",
    version="2.2.0"
)

# متغير عام بسيط لتخزين حالة المهمة الأخيرة
current_job_status = {
    "status": "جاهز للعمل",
    "title": "لا يوجد فيديو قيد الإنشاء حالياً",
    "progress": "في انتظار البدء..."
}

def tracked_run_job(job_data):
    """دالة وسيطة لتحديث الحالة أثناء عمل الفيديو في الخلفية"""
    global current_job_status
    try:
        current_job_status = {
            "status": "قيد المعالجة ⏳",
            "title": job_data.get("title"),
            "progress": "جاري توليد الصوت والصورة عبر FFmpeg..."
        }
        
        # تشغيل الوظيفة الأساسية
        run_job(job_data)
        
        current_job_status = {
            "status": "مكتمل بنجاح ✅",
            "title": job_data.get("title"),
            "progress": "تم الانتهاء من إنشاء الفيديو بنجاح!"
        }
    except Exception as e:
        current_job_status = {
            "status": "فشل ❌",
            "title": job_data.get("title"),
            "progress": f"حدث خطأ: {str(e)}"
        }

@app.get("/", response_class=HTMLResponse)
def read_root():
    """واجهة مرئية بسيطة تحتوي على مربع نص وزر لإنشاء الفيديو ومتابعة حالته"""
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>منصة إنشاء فيديوهات الذكاء الاصطناعي</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 100%; max-width: 420px; text-align: center; }
            input[type="text"] { width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #475569; border-radius: 6px; background: #0f172a; color: #fff; box-sizing: border-box; font-size: 16px; }
            button { background: #3b82f6; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; }
            button:hover { background: #2563eb; }
            .status-btn { background: #10b981; margin-top: 10px; display: inline-block; text-decoration: none; padding: 10px; border-radius: 6px; color: white; width: 100%; box-sizing: border-box; font-weight: bold; }
            .status-btn:hover { background: #059669; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>إنشاء فيديو جديد</h2>
            <form action="/web-create" method="post">
                <input type="text" name="title" placeholder="اكتب عنوان الفيديو هنا..." required>
                <button type="submit">إنشاء الفيديو 🚀</button>
            </form>
            <a href="/status" class="status-btn" target="_blank">🔍 متابعة حالة الفيديو الحالي</a>
        </div>
    </body>
    </html>
    """

@app.post("/web-create", response_class=HTMLResponse)
async def web_create(title: str = Form(...), background_tasks: BackgroundTasks = None):
    job_data = {
        "id": f"job_{abs(hash(title))}",
        "title": title,
        "feeds": []
    }
    
    if background_tasks:
        background_tasks.add_task(tracked_run_job, job_data)
        
    return f"""
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><style>body{{font-family:Tahoma,sans-serif;background:#0f172a;color:#fff;text-align:center;padding-top:100px;}}</style></head>
    <body>
        <h2>تم استلام طلبك وبدء العمل! 🚀</h2>
        <p>جاري الآن إنشاء الفيديو بالعنوان: <b>{title}</b></p>
        <br>
        <a href="/status" style="color:#34d399;font-size:18px;font-weight:bold;text-decoration:none;">📊 اضغط هنا لمتابعة حالة التقدم لحظة بلحظة</a>
        <br><br><br>
        <a href="/" style="color:#60a5fa;text-decoration:none;">← العودة للصفحة الرئيسية</a>
    </body>
    </html>
    """

@app.get("/status", response_class=HTMLResponse)
def get_status():
    """صفحة تعرض حالة الفيديو الحالي مباشرة في المتصفح مع تحديث تلقائي"""
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>حالة الفيديو الحالي</title>
        <meta http-equiv="refresh" content="5"> <!-- تحديث الصفحة تلقائياً كل 5 ثوانٍ -->
        <style>
            body {{ font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 100%; max-width: 450px; text-align: center; }}
            .box {{ background: #0f172a; padding: 15px; border-radius: 6px; margin: 15px 0; border: 1px solid #475569; text-align: right; }}
            a {{ color: #60a5fa; text-decoration: none; display: inline-block; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>حالة النظام والمهام</h2>
            <div class="box">
                <p><b>حالة المهمة:</b> {current_job_status['status']}</p>
                <p><b>عنوان الفيديو:</b> {current_job_status['title']}</p>
                <p><b>التفاصيل:</b> {current_job_status['progress']}</p>
            </div>
            <p style="font-size: 12px; color: #94a3b8;">(تتحدث هذه الصفحة تلقائياً كل 5 ثوانٍ)</p>
            <a href="/">← العودة للرئيسية</a>
        </div>
    </body>
    </html>
    """

@app.get("/quick-create")
async def quick_create(title: str, background_tasks: BackgroundTasks):
    job_data = {
        "id": f"job_{abs(hash(title))}",
        "title": title,
        "feeds": []
    }
    background_tasks.add_task(tracked_run_job, job_data)
    return {"status": "success", "message": f"جاري إنشاء الفيديو: '{title}'"}
    
