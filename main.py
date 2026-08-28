import os, threading, time
from pathlib import Path
from fastapi import FastAPI,Form,BackgroundTasks
from fastapi.responses import HTMLResponse,RedirectResponse
from dotenv import load_dotenv
from .db import *
from .worker import run_job,upload_job,publish_job,autopilot_once

load_dotenv()
init()
app=FastAPI(title="YouTube AI Autonomous 24/7")

def autopilot_loop():
    while True:
        try: autopilot_once()
        except Exception: pass
        time.sleep(3600)

threading.Thread(target=autopilot_loop,daemon=True).start()

@app.get("/setup",response_class=HTMLResponse)
def setup():
    return """<html lang='ar' dir='rtl'><meta charset='utf-8'>
    <style>body{font-family:Arial;max-width:800px;margin:40px auto}input,button{padding:10px;margin:5px}</style>
    <h1>إعداد الوكيل</h1>
    <p>ضع OPENAI_API_KEY في ملف .env. ثم ضع client_secret.json داخل credentials/.</p>
    <p>بعد ذلك ارجع إلى Dashboard. عند أول رفع سيُفتح OAuth من Google.</p>
    <a href='/'>Dashboard</a></html>"""

@app.get("/",response_class=HTMLResponse)
def home():
    rows=jobs()
    tr=""
    for j in rows:
        act=""
        if j["status"]=="ready":
            act=f"<form method='post' action='/upload/{j['id']}'><button>رفع Private</button></form>"
        elif j["status"]=="uploaded_private":
            act=f"<form method='post' action='/publish/{j['id']}'><button>نشر Public</button></form>"
        tr+=f"<tr><td>{j['id']}</td><td>{j['topic']}</td><td>{j['status']}</td><td>{j['title'] or ''}</td><td>{act}</td></tr>"
    ap=os.getenv("AUTOPILOT","false")
    return f"""<!doctype html><html lang='ar' dir='rtl'><meta charset='utf-8'>
    <style>body{{font-family:Arial;max-width:1200px;margin:30px auto}}input,button{{padding:10px;margin:4px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #ddd}}</style>
    <h1>🤖 YouTube AI Autonomous 24/7</h1>
    <p>Autopilot: <b>{ap}</b> — الحد اليومي: {os.getenv("DAILY_JOB_LIMIT","2")}</p>
    <form method='post' action='/create'><input name='topic' required placeholder='اكتب موضوعاً أو اترك الوكيل يبحث بنفسه' style='width:60%'><button>إنشاء</button></form>
    <form method='post' action='/autopilot'><button>تفعيل Autopilot</button></form>
    <table><tr><th>ID</th><th>الموضوع</th><th>الحالة</th><th>العنوان</th><th>إجراء</th></tr>{tr}</table>
    <p><a href='/setup'>الإعداد</a></p></html>"""

@app.post("/create")
def create(background_tasks:BackgroundTasks,topic:str=Form(...)):
    jid=add_job(topic,os.getenv("DEFAULT_LANGUAGE","ar"))
    if jid: background_tasks.add_task(run_job,jid)
    return RedirectResponse("/",303)

@app.post("/autopilot")
def autopilot():
    # Persist runtime setting in .env is deliberately avoided; this process setting is for current run.
    os.environ["AUTOPILOT"]="true"
    return RedirectResponse("/",303)

@app.post("/upload/{jid}")
def upload(jid:int):
    upload_job(jid); return RedirectResponse("/",303)

@app.post("/publish/{jid}")
def publish(jid:int):
    if os.getenv("AUTO_PUBLISH","false").lower()=="true":
        publish_job(jid)
    else:
        publish_job(jid)
    return RedirectResponse("/",303)
