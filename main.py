import sys
import os
import asyncio
import html
from pathlib import Path
from urllib.parse import urlencode

from fastapi import (
    FastAPI,
    BackgroundTasks,
    Form,
    Request,
    HTTPException,
)

from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    RedirectResponse,
)

from pydantic import BaseModel
from typing import Optional, List


# ============================================================
# PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))


# ============================================================
# IMPORTS
# ============================================================

from worker import run_job

from youtube import (
    authorization_url,
    finish_authorization,
    is_connected,
    channel,
    upload_private,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="YouTube AI Agent Controller",
    description="واجهة التحكم في إنشاء ومعاينة ورفع فيديوهات YouTube",
    version="3.0.0",
)


# ============================================================
# JOB REQUEST MODEL
# ============================================================

class JobRequest(BaseModel):

    id: str

    title: str

    feeds: Optional[List[str]] = []

    topic: Optional[dict] = None


# ============================================================
# CURRENT JOB STATUS
# ============================================================

current_job_status = {

    "status": "جاهز للعمل",

    "title": "لا يوجد فيديو قيد الإنشاء حالياً",

    "progress": "في انتظار البدء...",

    "video_path": None,

    "youtube_video_id": None,

}


# ============================================================
# OAUTH STATE STORAGE
#
# IMPORTANT:
# This is kept in memory.
# It works while the Render service remains running.
# ============================================================

oauth_sessions = {}


# ============================================================
# SAFE TEXT
# ============================================================

def safe_text(value):

    if value is None:
        return ""

    return html.escape(
        str(value)
    )


# ============================================================
# GET LATEST VIDEO
# ============================================================

def get_latest_video():

    video_extensions = (
        "*.mp4",
        "*.mov",
        "*.mkv",
    )

    videos = []

    for pattern in video_extensions:

        videos.extend(
            BASE_DIR.glob(
                f"**/{pattern}"
            )
        )

    if not videos:
        return None

    # Avoid hidden virtual environment folders if any
    filtered = []

    for video in videos:

        text_path = str(
            video
        )

        if ".venv" in text_path:
            continue

        if "__pycache__" in text_path:
            continue

        filtered.append(
            video
        )

    if not filtered:
        return None

    return max(
        filtered,
        key=lambda item: item.stat().st_mtime,
    )


# ============================================================
# BUILD JOB DATA
# ============================================================

def build_job_data(title):

    title = (
        title or ""
    ).strip()

    if not title:

        raise ValueError(
            "موضوع الفيديو فارغ."
        )

    job_id = (
        f"job_{abs(hash(title))}_{int(__import__('time').time())}"
    )

    topic = {

        "title": title,

        "source": "manual",

        "description": title,

    }

    return {

        "id": job_id,

        "job_id": job_id,

        "title": title,

        "topic": topic,

        "feeds": [],

    }


# ============================================================
# TRACKED WORKER JOB
# ============================================================

async def tracked_run_job(job_data):

    global current_job_status

    title = (
        job_data.get("title")
        or "فيديو جديد"
    )

    try:

        current_job_status = {

            "status": "قيد المعالجة ⏳",

            "title": title,

            "progress": (
                "بدأ إنشاء الفيديو..."
            ),

            "video_path": None,

            "youtube_video_id": None,

        }


        print(
            f"[API] Starting job: {job_data.get('id')}",
            flush=True,
        )


        # ----------------------------------------------------
        # RUN THE ASYNC WORKER
        # ----------------------------------------------------

        result = await run_job(
            job_data
        )


        print(
            f"[API] Job result: {result}",
            flush=True,
        )


        # ----------------------------------------------------
        # LOOK FOR THE GENERATED VIDEO
        # ----------------------------------------------------

        latest_video = get_latest_video()


        # ----------------------------------------------------
        # WORKER FAILED
        # ----------------------------------------------------

        if result is False:

            current_job_status = {

                "status": "فشل ❌",

                "title": title,

                "progress": (
                    "فشلت عملية إنشاء الفيديو. "
                    "راجع Render Logs."
                ),

                "video_path": None,

                "youtube_video_id": None,

            }

            return


        # ----------------------------------------------------
        # WORKER FINISHED
        # ----------------------------------------------------

        current_job_status = {

            "status": "مكتمل بنجاح ✅",

            "title": title,

            "progress": (
                "انتهت معالجة الفيديو. "
                "يمكنك فتح صفحة المعاينة."
            ),

            "video_path": (
                str(latest_video)
                if latest_video
                else None
            ),

            "youtube_video_id": None,

        }


        print(
            "[API] Video job completed.",
            flush=True,
        )


    except Exception as exc:

        print(
            f"[API] JOB ERROR: {repr(exc)}",
            flush=True,
        )

        current_job_status = {

            "status": "فشل ❌",

            "title": title,

            "progress": (
                f"حدث خطأ أثناء إنشاء الفيديو: "
                f"{str(exc)}"
            ),

            "video_path": None,

            "youtube_video_id": None,

        }


# ============================================================
# ROOT PAGE
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def read_root():

    youtube_status = (
        "🟢 YouTube مربوط"
        if is_connected()
        else "🔴 YouTube غير مربوط"
    )

    return f"""

    <!DOCTYPE html>

    <html
        lang="ar"
        dir="rtl"
    >

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="
                width=device-width,
                initial-scale=1
            "
        >

        <title>
            YouTube AI Agent
        </title>


        <style>

            body {{

                font-family:
                    Tahoma,
                    sans-serif;

                background:
                    #0f172a;

                color:
                    #ffffff;

                margin:
                    0;

                padding:
                    25px;

            }}


            .card {{

                background:
                    #1e293b;

                padding:
                    25px;

                border-radius:
                    15px;

                max-width:
                    520px;

                margin:
                    auto;

                box-shadow:
                    0 4px 25px
                    rgba(
                        0,
                        0,
                        0,
                        0.4
                    );

                text-align:
                    center;

            }}


            input {{

                width:
                    100%;

                padding:
                    14px;

                margin:
                    15px 0;

                box-sizing:
                    border-box;

                border:
                    1px solid
                    #475569;

                border-radius:
                    8px;

                background:
                    #0f172a;

                color:
                    white;

                font-size:
                    16px;

            }}


            button,
            .button {{

                display:
                    block;

                width:
                    100%;

                box-sizing:
                    border-box;

                padding:
                    13px;

                border:
                    none;

                border-radius:
                    8px;

                font-size:
                    16px;

                font-weight:
                    bold;

                cursor:
                    pointer;

                text-decoration:
                    none;

                color:
                    white;

                margin-top:
                    10px;

            }}


            .create {{

                background:
                    #2563eb;

            }}


            .status {{

                background:
                    #10b981;

            }}


            .preview {{

                background:
                    #8b5cf6;

            }}


            .youtube {{

                background:
                    #dc2626;

            }}


            .channel {{

                background:
                    #ea580c;

            }}


            .info {{

                background:
                    #0f172a;

                padding:
                    12px;

                border-radius:
                    8px;

                margin:
                    15px 0;

            }}

        </style>

    </head>


    <body>


        <div
            class="card"
        >


            <h2>
                🎬 YouTube AI Agent
            </h2>


            <div
                class="info"
            >

                {youtube_status}

            </div>


            <form
                action="/web-create"
                method="post"
            >

                <input
                    type="text"
                    name="title"
                    placeholder="
                        اكتب موضوع الفيديو هنا...
                    "
                    required
                >

                <button
                    class="create"
                    type="submit"
                >

                    🚀 إنشاء الفيديو

                </button>

            </form>


            <a
                href="/status"
                class="
                    button
                    status
                "
            >

                📊 متابعة حالة الفيديو

            </a>


            <a
                href="/preview"
                class="
                    button
                    preview
                "
            >

                🎬 معاينة الفيديو

            </a>


            <a
                href="/auth"
                class="
                    button
                    youtube
                "
            >

                🔐 ربط YouTube

            </a>


            <a
                href="/channel"
                class="
                    button
                    channel
                "
            >

                📺 فحص القناة

            </a>


        </div>


    </body>


    </html>

    """


# ============================================================
# CREATE VIDEO FROM WEB FORM
# ============================================================

@app.post(
    "/web-create",
    response_class=HTMLResponse,
)
async def web_create(

    title: str = Form(...),

    background_tasks: BackgroundTasks = None,

):

    try:

        job_data = build_job_data(
            title
        )

    except ValueError as exc:

        raise HTTPException(

            status_code=400,

            detail=str(exc),

        )


    if background_tasks:

        background_tasks.add_task(

            tracked_run_job,

            job_data,

        )


    safe_title = safe_text(
        title
    )


    return f"""

    <!DOCTYPE html>

    <html
        lang="ar"
        dir="rtl"
    >

    <head>

        <meta charset="UTF-8">

        <title>
            جاري إنشاء الفيديو
        </title>


        <style>

            body {{

                font-family:
                    Tahoma,
                    sans-serif;

                background:
                    #0f172a;

                color:
                    white;

                text-align:
                    center;

                padding-top:
                    100px;

            }}


            a {{

                color:
                    #60a5fa;

                text-decoration:
                    none;

            }}

        </style>

    </head>


    <body>


        <h2>

            🚀 تم بدء إنشاء الفيديو

        </h2>


        <p>

            الموضوع:

            <b>

                {safe_title}

            </b>

        </p>


        <br>


        <a
            href="/status"
            style="
                color:#34d399;
                font-size:18px;
                font-weight:bold;
            "
        >

            📊 متابعة الحالة

        </a>


        <br>
        <br>


        <a
            href="/"
        >

            ← العودة للرئيسية

        </a>


    </body>


    </html>

    """


# ============================================================
# QUICK CREATE
# ============================================================

@app.get(
    "/quick-create",
)
async def quick_create(

    title: str,

    background_tasks: BackgroundTasks,

):

    try:

        job_data = build_job_data(
            title
        )

    except ValueError as exc:

        raise HTTPException(

            status_code=400,

            detail=str(exc),

        )


    background_tasks.add_task(

        tracked_run_job,

        job_data,

    )


    return {

        "status":
            "processing",

        "job_id":
            job_data["id"],

        "title":
            job_data["title"],

        "message":
            "تم بدء إنشاء الفيديو في الخلفية",

    }


# ============================================================
# JOB STATUS
# ============================================================

@app.get(
    "/status",
    response_class=HTMLResponse,
)
def get_status():

    status = safe_text(
        current_job_status.get(
            "status"
        )
    )

    title = safe_text(
        current_job_status.get(
            "title"
        )
    )

    progress = safe_text(
        current_job_status.get(
            "progress"
        )
    )

    video_path = (
        current_job_status.get(
            "video_path"
        )
    )

    youtube_video_id = (
        current_job_status.get(
            "youtube_video_id"
        )
    )


    video_html = ""

    if video_path:

        video_html = """

        <p>

            🎬 يوجد فيديو جاهز

        </p>

        <a
            href="/preview"
            style="
                color:#a78bfa;
                font-weight:bold;
            "
        >

            فتح المعاينة

        </a>

        """


    youtube_html = ""

    if youtube_video_id:

        youtube_html = f"""

        <p>

            🎥 YouTube Video ID:

            {safe_text(
                youtube_video_id
            )}

        </p>

        """


    return f"""

    <!DOCTYPE html>

    <html
        lang="ar"
        dir="rtl"
    >

    <head>

        <meta charset="UTF-8">

        <meta
            http-equiv="refresh"
            content="5"
        >

        <title>
            حالة الفيديو
        </title>


        <style>

            body {{

                font-family:
                    Tahoma,
                    sans-serif;

                background:
                    #0f172a;

                color:
                    white;

                display:
                    flex;

                justify-content:
                    center;

                align-items:
                    center;

                min-height:
                    100vh;

                margin:
                    0;

                padding:
                    20px;

            }}


            .card {{

                background:
                    #1e293b;

                padding:
                    30px;

                border-radius:
                    12px;

                width:
                    100%;

                max-width:
                    500px;

                text-align:
                    center;

            }}


            .box {{

                background:
                    #0f172a;

                padding:
                    15px;

                border-radius:
                    8px;

                margin:
                    15px 0;

                text-align:
                    right;

            }}

        </style>

    </head>


    <body>


        <div
            class="card"
        >


            <h2>

                📊 حالة الفيديو

            </h2>


            <div
                class="box"
            >

                <p>

                    <b>
                        الحالة:
                    </b>

                    {status}

                </p>


                <p>

                    <b>
                        الموضوع:
                    </b>

                    {title}

                </p>


                <p>

                    <b>
                        التفاصيل:
                    </b>

                    {progress}

                </p>


            </div>


            {video_html}


            {youtube_html}


            <br>


            <a
                href="/"
                style="
                    color:#60a5fa;
                "
            >

                ← العودة للرئيسية

            </a>


        </div>


    </body>


    </html>

    """


# ============================================================
# PREVIEW LATEST VIDEO
# ============================================================

@app.get(
    "/preview",
    response_class=HTMLResponse,
)
def preview_latest_video():

    latest_video = get_latest_video()


    if not latest_video:

        return """

        <html
            lang="ar"
            dir="rtl"
        >

        <body
            style="
                background:#0f172a;
                color:#fff;
                text-align:center;
                padding-top:100px;
                font-family:Tahoma;
            "
        >

            <h2>

                لا يوجد فيديو جاهز للمعاينة.

            </h2>


            <a
                href="/status"
                style="
                    color:#34d399;
                    display:block;
                    margin-top:15px;
                "
            >

                📊 متابعة الحالة

            </a>


            <a
                href="/"
                style="
                    color:#60a5fa;
                    display:block;
                    margin-top:15px;
                "
            >

                
            العودة للرئيسية

        </a>


    </body>


    </html>

    """


# ============================================================
# API HEALTH CHECK
# ============================================================

@app.get(
    "/health",
)
def health():

    return {

        "status":
            "ok",

        "service":
            "YouTube AI Agent",

        "youtube_connected":
            is_connected(),

    }
