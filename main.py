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
    version="2.1.0"
)

@app.get("/", response_class=HTMLResponse)
def read_root():
    """واجهة مرئية بسيطة تحتوي على مربع نص وزر لإنشاء الفيديو بضغطة واحدة"""
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>منصة إنشاء فيديوهات الذكاء الاصطناعي</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 100%; max-width: 400px; text-align: center; }
            input[type="text"] { width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #475569; border-radius: 6px; background: #0f172a; color: #fff; box-sizing: border-box; font-size: 16px; }
            button { background: #3b82f6; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; }
            button:hover { background: #2563eb; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>إنشاء فيديو جديد</h2>
            <form action="/web-create" method="post">
                <input type="text" name="title" placeholder="اكتب عنوان الفيديو هنا..." required>
                <button type="submit">إنشاء الفيديو 🚀</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/web-create", response_class=HTMLResponse)
async def web_create(title: str = Form(...), background_tasks: BackgroundTasks = None):
    """استقبال العنوان من الواجهة وبدء العمل فوراً"""
    job_data = {
        "id": f"job_{abs(hash(title))}",
        "title": title,
        "feeds": []
    }
    
    if background_tasks:
        background_tasks.add_task(run_job, job_data)
        
    return f"""
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><style>body{{font-family:Tahoma,sans-serif;background:#0f172a;color:#fff;text-align:center;padding-top:100px;}}</style></head>
    <body>
        <h2>تم استلام طلبك بنجاح! 🚀</h2>
        <p>جاري الآن العمل على إنشاء الفيديو بالعنوان: <b>{title}</b> في الخلفية.</p>
        <a href="/" style="color:#60a5fa;text-decoration:none;font-size:18px;">← العودة للصفحة الرئيسية</a>
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
    background_tasks.add_task(run_job, job_data)
    return {"status": "success", "message": f"جاري إنشاء الفيديو: '{title}'"}
    
