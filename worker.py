import os, json, traceback, threading
from pathlib import Path
from db import *
from discovery import discover, source_text
from ai import choose, make_content
from media import make_video
from youtube import upload_private,publish

def run_job(job_id):
    try:
        j=get_job(job_id); update_job(job_id,status="researching")
        items=discover()
        if not items: raise RuntimeError("لم يتم العثور على مصادر حديثة.")
        pick=choose(items,recent_topics(30))
        topic=pick["topic"]
        # Use selected feed items + fetched text.
        sources=[]
        for x in items[:8]:
            txt=source_text(x["link"])
            if txt: sources.append({"title":x["title"],"url":x["link"],"text":txt[:2500]})
        if len(sources)<int(os.getenv("MIN_SOURCE_COUNT","2")):
            sources=[{"title":x["title"],"url":x["link"],"text":x["summary"]} for x in items[:4]]
        update_job(job_id,status="writing")
        c=make_content(topic,sources,j["language"])
        out=Path("data/output")/str(job_id)
        video,thumb=make_video(c["title"],c["script"],c["scenes"],out,os.getenv("VOICE","ar-SA-HamedNeural"))
        update_job(job_id,title=c["title"],description=c["description"],script=c["script"],
                   video_path=video,thumbnail_path=thumb,sources=json.dumps(sources,ensure_ascii=False),
                   status="ready")
        return True
    except Exception as e:
        update_job(job_id,status="error",error=str(e))
        traceback.print_exc()
        return False

def upload_job(job_id):
    j=get_job(job_id)
    vid=upload_private(j["video_path"],j["title"],j["description"],j["thumbnail_path"])
    update_job(job_id,youtube_id=vid,status="uploaded_private")
    return vid

def publish_job(job_id):
    j=get_job(job_id)
    publish(j["youtube_id"])
    from datetime import datetime, timezone
    update_job(job_id,status="published",published_at=datetime.now(timezone.utc).isoformat())

def autopilot_once():
    if os.getenv("AUTOPILOT","false").lower()!="true": return None
    if jobs_today()>=int(os.getenv("DAILY_JOB_LIMIT","2")): return None
    items=discover()
    if not items:return None
    pick=choose(items,recent_topics(30))
    jid=add_job(pick["topic"],os.getenv("DEFAULT_LANGUAGE","ar"))
    if jid:
        threading.Thread(target=run_job,args=(jid,),daemon=True).start()
    return jid
