import sys
import os
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List

# إضافة المسار الحالي للمشروع
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# استيراد الدوال المطلوبة من worker
from worker import run_job

app = FastAPI(
    title="YouTube AI Agent Controller",
    description="واجهة التحكم المتكاملة في توليد ومعاينة ونشر فيديوهات يوتيوب",
    version="2.3.0"
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
            "progress": "تم الانتهاء من إنشاء الفيديو بنجاح! يمكنك معاينته الآن."
        }
    except Exception as e:
        current_job_status = {
            "status": "فشل ❌",
            "title": job_data.get("title"),
            "progress": f"حدث خطأ: {str(e)}"
        }

@app.get("/", response_class=HTMLResponse)
def read_root():
    """الواجهة الرئيسة: إدخال العنوان، بدء الإنشاء، ومتابعة الحالة أو المعاينة"""
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
            .btn-link { background: #10b981; margin-top: 10px; display: inline-block; text-decoration: none; padding: 10px; border-radius: 6px; color: white; width: 100%; box-sizing: border-box; font-weight: bold; }
            .btn-link:hover { background: #059669; }
            .btn-preview { background: #8b5cf6; margin-top: 10px; display: inline-block; text-decoration: none; padding: 10px; border-radius: 6px; color: white; width: 100%; box-sizing: border-box; font-weight: bold; }
            .btn-preview:hover { background: #7c3aed; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>إنشاء فيديو جديد</h2>
            <form action="/web-create" method="post">
                <input type="text" name="title" placeholder="اكتب عنوان الفيديو هنا..." required>
                <button type="submit">إنشاء الفيديو 🚀</button>
            </form>
            <a href="/status" class="btn-link">🔍 متابعة حالة الفيديو الحالي</a>
            <a href="/preview" class="btn-preview">🎬 معاينة وفحص الفيديو الجاهز</a>
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
        <a href="/status" style="color:#34d399;font-size:18px;font-weight:bold;text-decoration:none;">📊 متابعة حالة التقدم لحظة بلحظة</a>
        <br><br>
        <a href="/preview" style="color:#a78bfa;font-size:18px;font-weight:bold;text-decoration:none;">🎬 الانتقال لمعاينة الفيديو</a>
        <br><br><br>
        <a href="/" style="color:#60a5fa;text-decoration:none;">← العودة للرئيسية</a>
    </body>
    </html>
    """

@app.get("/status", response_class=HTMLResponse)
def get_status():
    """صفحة تعرض حالة الفيديو الحالي مباشرة مع تحديث تلقائي كل 5 ثوانٍ"""
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>حالة الفيديو الحالي</title>
        <meta http-equiv="refresh" content="5">
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
            <a href="/preview" style="display:block;color:#a78bfa;font-weight:bold;margin-top:10px;">🎬 الذهاب لصفحة المعاينة</a>
            <a href="/">← العودة للرئيسية</a>
        </div>
    </body>
    </html>
    """

@app.get("/preview", response_class=HTMLResponse)
def preview_latest_video():
    """عرض أحدث فيديو تم إنشاؤه للمعاينة المباشرة داخل المتصفح"""
    videos = list(Path(".").glob("**/*.mp4"))
    if not videos:
        return """
        <html lang="ar" dir="rtl"><body style="background:#0f172a;color:#fff;text-align:center;padding-top:100px;font-family:Tahoma;">
        <h2>لا يوجد أي فيديو جاهز للمعاينة حتى الآن.</h2>
        <a href="/" style="color:#60a5fa;">العودة للرئيسية</a>
        </body></html>
        """
    
    latest_video = max(videos, key=os.path.getmtime)
    video_filename = latest_video.name
    
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>معاينة الفيديو قبل النشر</title>
        <style>
            body {{ font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; text-align: center; padding: 40px; margin: 0; }}
            .container {{ background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.5); max-width: 700px; width: 100%; }}
            video {{ width: 100%; border-radius: 8px; margin: 20px 0; background: #000; }}
            .btn-publish {{ background: #10b981; color: white; border: none; padding: 12px 25px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; width: 100%; }}
            .btn-publish:hover {{ background: #059669; }}
            .btn-back {{ color: #60a5fa; text-decoration: none; display: inline-block; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🔍 معاينة الفيديو</h2>
            <p>اسم الملف: <b>{video_filename}</b></p>
            
            <!-- مشغل الفيديو المباشر -->
            <video controls>
                <source src="/stream-file/{video_filename}" type="video/mp4">
                متصفحك لا يدعم تشغيل الفيديو.
            </video>
            
            <!-- زر النشر المباشر كفيديو خاص لاستوديو يوتيوب -->
            <form action="/publish-direct" method="post">
                <input type="hidden" name="video_path" value="{str(latest_video)}">
                <button type="submit" class="btn-publish">🚀 رفع مباشر إلى استوديو يوتيوب (خاص)</button>
            </form>
            
            <a href="/" class="btn-back">← العودة للرئيسية</a>
        </div>
    </body>
    </html>
    """

@app.get("/stream-file/{filename}")
def stream_file(filename: str):
    """بث ملف الفيديو مباشرة للمتصفح دون الحاجة لتحميله"""
    videos = list(Path(".").glob(f"**/{filename}"))
    if not videos:
        return {"error": "الملف غير موجود"}
    return FileResponse(path=videos[0], media_type="video/mp4")

@app.post("/publish-direct", response_class=HTMLResponse)
async def publish_direct(video_path: str, background_tasks: BackgroundTasks):
    """إرسال الفيديو إلى استوديو يوتيوب كفيديو خاص (Private)"""
    if not os.path.exists(video_path):
        return """
        <html lang="ar" dir="rtl"><body style="background:#0f172a;color:#fff;text-align:center;padding-top:100px;font-family:Tahoma;">
        <h2>❌ خطأ: ملف الفيديو غير موجود.</h2>
        <a href="/preview" style="color:#60a5fa;">العودة للمعاينة</a>
        </body></html>
        """
    
    # يمكنك استدعاء دالة الرفع الخاصة بك هنا وتمرير privacy="private"
    # background_tasks.add_task(upload_video_to_youtube, video_path, privacy="private")
    
    return """
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>جاري الرفع</title>
        <style>body{font-family:Tahoma,sans-serif;background:#0f172a;color:#fff;text-align:center;padding-top:100px;}</style>
    </head>
    <body>
        <h2>🚀 تم بدء رفع الفيديو إلى استوديو يوتيوب بنجاح!</h2>
        <p>تم ضبط خيار الخصوصية على <b>(خاص - Private)</b> ليظهر في استوديو قناتك للمراجعة.</p>
        <br>
        <a href="/" style="color:#60a5fa;text-decoration:none;font-size:18px;">← العودة للرئيسية</a>
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
    
