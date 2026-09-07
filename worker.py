import os
import sys
import time
import asyncio
import traceback
from pathlib import Path

# إضافة المجلد الحالي ومجلد src للـ Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from db import (
    get_pending_job,
    update_job_status,
    save_job_result,
    clear_hung_jobs,
    log_db
)
from discovery import discover_sources, fetch_source_text
from ai import generate_script
from media import make_video

def log(msg: str):
    print(f"[WORKER] {msg}", flush=True)

async def run_job(job: dict):
    job_id = job["id"]
    log(f"Job {job_id}: starting execution")

    try:
        # 1. تحديث الحالة إلى in_progress
        update_job_status(job_id, "in_progress")

        # 2. مرحلة اكتشاف المصادر (Discovery)
        feeds = job.get("feeds") or []
        log(f"Job {job_id}: discovering sources...")
        discovered = await discover_sources(feeds)
        log(f"Job {job_id}: discovered {len(discovered)} sources")

        if not discovered:
            raise RuntimeError("لم يتم العثور على أي مصادر أخبار من الخلاصات المحددة")

        # 3. اختيار الموضوع واستخراج المحتوى
        log(f"Job {job_id}: selecting topic")
        topic_info = job.get("topic") or discovered[0]
        title = topic_info.get("title", "عنوان غير محدد")
        urls = topic_info.get("urls", [topic_info.get("link")]) if isinstance(topic_info, dict) else [str(topic_info)]
        
        # تصفية الروابط الفارغة
        urls = [u for u in urls if u]
        log(f"Job {job_id}: selected topic: {title}")

        sources_content = []
        max_sources = min(3, len(urls))
        log(f"Job {job_id}: fetching up to {max_sources} sources")

        for idx, url in enumerate(urls[:max_sources]):
            log(f"Job {job_id}: source {idx+1}/{max_sources}")
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
            log(f"Job {job_id}: no text fetched, using title as content")
            sources_content = [{"url": urls[0] if urls else "", "text": title}]

        log(f"Job {job_id}: using {len(sources_content)} sources")

        # 4. مرحلة الكتابة بالذكاء الاصطناعي (AI Writing)
        log(f"Job {job_id}: starting AI writing")
        script_data = await generate_script(title, sources_content)
        log(f"Job {job_id}: AI content ready")

        script_items = script_data.get("items") or script_data.get("sections") or []
        if not script_items:
            script_items = [{"title": title, "text": script_data.get("full_text", title)}]

        # 5. مرحلة إنشاء الفيديو والصورة المصغرة (Media Generation)
        log(f"Job {job_id}: generating video")
        
        # التعديل الرئيسي: استدعاء make_video بالمعاملات الثلاثة المحددة فقط وتمريرها بأمان
        video_path, thumb_path = await make_video(
            str(job_id),
            title,
            script_items
        )

        log(f"Job {job_id}: video generated successfully at {video_path}")

        # 6. حفظ النتيجة وتحديث الحالة إلى completed
        save_job_result(
            job_id=job_id,
            title=title,
            script=script_data,
            video_path=str(video_path),
            thumb_path=str(thumb_path)
        )
        update_job_status(job_id, "completed")
        log(f"Job {job_id}: completed successfully")

    except Exception as e:
        error_msg = str(e)
        log(f"Job {job_id}: ERROR {error_msg}")
        traceback.print_exc()
        update_job_status(job_id, "failed", error=error_msg)

async def worker_loop():
    log("Worker loop started.")
    
    # تنظيف أي مهام عالقة عند بداية التشغيل
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
            log("Worker loop cancelled.")
            break
        except Exception as e:
            log(f"Unexpected error in worker loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        log("Worker stopped manually.")
        
