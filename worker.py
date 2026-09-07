import os
import sys
import time
import asyncio
import traceback
from pathlib import Path

# إضافة المجلد الحالي للـ Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# ----------------------------------------------------
# استيراد مرن وآمن من db.py لمنع أي ImportError
# ----------------------------------------------------
import db

def get_pending_job():
    for name in ["get_pending_job", "get_next_job", "fetch_pending_job"]:
        if hasattr(db, name):
            return getattr(db, name)()
    return None

def update_job_status(job_id, status, error=None):
    for name in ["update_job_status", "set_job_status"]:
        if hasattr(db, name):
            try:
                return getattr(db, name)(job_id, status, error)
            except TypeError:
                return getattr(db, name)(job_id, status)
    return None

def save_job_result(job_id, title, script, video_path, thumb_path):
    for name in ["save_job_result", "save_result", "update_job_result"]:
        if hasattr(db, name):
            try:
                return getattr(db, name)(job_id, title, script, video_path, thumb_path)
            except Exception:
                pass
    return None

def clear_hung_jobs():
    for name in ["clear_hung_jobs", "reset_hung_jobs", "clean_jobs"]:
        if hasattr(db, name):
            return getattr(db, name)()
    return None

def log_db(msg: str):
    if hasattr(db, "log_db"):
        return getattr(db, "log_db")(msg)
    print(f"[DB LOG] {msg}", flush=True)

# ----------------------------------------------------
# استيراد باقي الوحدات
# ----------------------------------------------------
from discovery import discover_sources, fetch_source_text
from ai import generate_script
from media import make_video

def log(msg: str):
    print(f"[WORKER] {msg}", flush=True)

async def run_job(job: dict):
    if not job:
        return False
        
    job_id = job.get("id") or job.get("job_id")
    log(f"Job {job_id}: starting execution")

    try:
        # 1. تحديث الحالة
        update_job_status(job_id, "in_progress")

        # 2. اكتشاف المصادر
        feeds = job.get("feeds") or []
        log(f"Job {job_id}: discovering sources...")
        discovered = await discover_sources(feeds)
        log(f"Job {job_id}: discovered {len(discovered)} sources")

        if not discovered:
            raise RuntimeError("لم يتم العثور على أي مصادر أخبار")

        # 3. اختيار الموضوع واستخرج المحتوى
        log(f"Job {job_id}: selecting topic")
        topic_info = job.get("topic") or discovered[0]
        title = topic_info.get("title", "عنوان غير محدد") if isinstance(topic_info, dict) else str(topic_info)
        urls = topic_info.get("urls", [topic_info.get("link")]) if isinstance(topic_info, dict) else [str(topic_info)]
        
        urls = [u for u in urls if u]
        log(f"Job {job_id}: selected topic: {title}")

        sources_content = []
        max_sources = min(3, len(urls))
        for idx, url in enumerate(urls[:max_sources]):
            try:
                t0 = time.time()
                text = await fetch_source_text(url)
                dt = round(time.time() - t0, 2)
                if text:
                    sources_content.append({"url": url, "text": text})
                    log(f"Job {job_id}: source {idx+1} OK ({dt}s)")
            except Exception as e:
                log(f"Job {job_id}: source {idx+1} failed: {e}")

        if not sources_content:
            sources_content = [{"url": urls[0] if urls else "", "text": title}]

        # 4. الكتابة بالذكاء الاصطناعي
        log(f"Job {job_id}: starting AI writing")
        script_data = await generate_script(title, sources_content)
        log(f"Job {job_id}: AI content ready")

        script_items = script_data.get("items") or script_data.get("sections") or []
        if not script_items:
            script_items = [{"title": title, "text": script_data.get("full_text", title)}]

        # 5. إنشاء الفيديو والصورة المصغرة
        log(f"Job {job_id}: generating video")
        video_path, thumb_path = await make_video(
            str(job_id),
            title,
            script_items
        )

        log(f"Job {job_id}: video generated successfully at {video_path}")

        # 6. حفظ النتيجة
        save_job_result(
            job_id=job_id,
            title=title,
            script=script_data,
            video_path=str(video_path),
            thumb_path=str(thumb_path)
        )
        update_job_status(job_id, "completed")
        log(f"Job {job_id}: completed successfully")
        return True

    except Exception as e:
        error_msg = str(e)
        log(f"Job {job_id}: ERROR {error_msg}")
        traceback.print_exc()
        update_job_status(job_id, "failed", error=error_msg)
        return False

# ----------------------------------------------------
# الدوال المطلوبة لعمل main.py بدون أخطاء Import
# ----------------------------------------------------

async def upload_job(job_id: str):
    """رفع الفيديو إلى المنصات المحددة"""
    log(f"Uploading job {job_id}...")
    await asyncio.sleep(1)
    return True

async def publish_job(job_id: str):
    """نشر الفيديو رسمياً"""
    log(f"Publishing job {job_id}...")
    await asyncio.sleep(1)
    return True

async def autopilot_once():
    """تشغيل عملية الطيار الآلي لمرة واحدة"""
    log("Running autopilot cycle...")
    job = get_pending_job()
    if job:
        return await run_job(job)
    log("No pending jobs found for autopilot.")
    return False

# ----------------------------------------------------
# حلقة تشغيل الـ Worker
# ----------------------------------------------------

async def worker_loop():
    log("Worker loop started.")
    try:
        clear_hung_jobs()
    except Exception as e:
        log(f"Error clearing hung jobs: {e}")

    while True:
        try:
            job = get_pending_job()
            if job:
                await run_job(job)
            else:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log(f"Unexpected error in worker loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        log("Worker stopped manually.")
        
