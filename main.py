import sys
import os
import html
import inspect
import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import (
    FastAPI,
    BackgroundTasks,
    Form,
    HTTPException,
)
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    RedirectResponse,
)
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ============================================================
# إعداد مسار المشروع
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))


# ============================================================
# استيراد Worker
# ============================================================

try:
    from worker import run_job
except Exception as exc:
    raise RuntimeError(
        f"فشل استيراد worker.py: {exc}"
    )


# ============================================================
# استيراد نظام YouTube
# ============================================================

youtube_import_error = None

try:
    import youtube as youtube_module
except Exception as exc:
    youtube_module = None
    youtube_import_error = str(exc)


# ============================================================
# إنشاء التطبيق
# ============================================================

app = FastAPI(
    title="YouTube AI Agent Controller",
    description=(
        "واجهة التحكم المتكاملة في توليد "
        "ومعاينة ونشر فيديوهات يوتيوب"
    ),
    version="3.0.0"
)


# ============================================================
# تخزين جلسات OAuth مؤقتاً
# ============================================================

oauth_sessions: Dict[str, Dict[str, Any]] = {}


# ============================================================
# حالة المهمة الحالية
# ============================================================

current_job_status = {
    "status": "جاهز للعمل",
    "title": "لا يوجد فيديو قيد الإنشاء حالياً",
    "progress": "في انتظار البدء..."
}


# ============================================================
# أدوات مساعدة
# ============================================================

def safe_text(value: Any) -> str:
    """
    حماية النصوص قبل عرضها داخل HTML.
    """
    if value is None:
        return ""

    return html.escape(str(value))


async def call_maybe_async(func, *args, **kwargs):
    """
    تشغيل الدالة سواء كانت عادية أو async.
    """
    result = func(*args, **kwargs)

    if inspect.isawaitable(result):
        result = await result

    return result


async def run_job_safely(job_data: Dict[str, Any]):
    """
    تشغيل run_job سواء كانت async أو دالة عادية.
    """
    result = run_job(job_data)

    if inspect.isawaitable(result):
        return await result

    return result


def get_youtube_function(*names):
    """
    البحث عن دالة داخل youtube.py بأكثر من اسم محتمل.
    """
    if youtube_module is None:
        return None

    for name in names:
        func = getattr(
            youtube_module,
            name,
            None,
        )

        if callable(func):
            return func

    return None


# ============================================================
# نموذج طلب API
# ============================================================

class JobRequest(BaseModel):
    id: str
    title: str
    feeds: Optional[List[str]] = []
    topic: Optional[dict] = None


# ============================================================
# تشغيل إنشاء الفيديو ومتابعة الحالة
# ============================================================

async def tracked_run_job(job_data: Dict[str, Any]):
    """
    تشغيل مهمة إنشاء الفيديو في الخلفية
    مع تحديث حالة المهمة.
    """

    global current_job_status

    title = job_data.get(
        "title",
        "فيديو جديد"
    )

    try:

        current_job_status = {
            "status": "قيد المعالجة ⏳",
            "title": title,
            "progress": (
                "بدأ النظام معالجة طلب إنشاء الفيديو..."
            )
        }

        result = await run_job_safely(
            job_data
        )

        if result is False:

            current_job_status = {
                "status": "فشل ❌",
                "title": title,
                "progress": (
                    "فشلت عملية إنشاء الفيديو "
                    "داخل worker.py."
                )
            }

        else:

            current_job_status = {
                "status": "مكتمل بنجاح ✅",
                "title": title,
                "progress": (
                    "تم الانتهاء من إنشاء الفيديو. "
                    "يمكنك فتح صفحة المعاينة."
                )
            }

    except Exception as exc:

        current_job_status = {
            "status": "فشل ❌",
            "title": title,
            "progress": (
                f"حدث خطأ أثناء إنشاء الفيديو: "
                f"{exc}"
            )
        }


# ============================================================
# الصفحة الرئيسية
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def read_root():

    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            منصة إنشاء فيديوهات الذكاء الاصطناعي
        </title>

        <style>

            body {
                font-family: Tahoma, sans-serif;
                background: #0f172a;
                color: #ffffff;

                display: flex;

                justify-content: center;

                align-items: center;

                min-height: 100vh;

                margin: 0;

                padding: 20px;

                box-sizing: border-box;
            }

            .card {

                background: #1e293b;

                padding: 30px;

                border-radius: 16px;

                box-shadow:
                    0 4px 25px
                    rgba(0,0,0,0.5);

                width: 100%;

                max-width: 460px;

                text-align: center;
            }

            h2 {

                margin-top: 0;

                color: #ffffff;
            }

            input[type="text"] {

                width: 100%;

                padding: 14px;

                margin:
                    15px
                    0;

                border:
                    1px
                    solid
                    #475569;

                border-radius: 8px;

                background: #0f172a;

                color: white;

                box-sizing:
                    border-box;

                font-size: 16px;
            }

            button {

                background:
                    #3b82f6;

                color: white;

                border: none;

                padding:
                    14px
                    20px;

                border-radius: 8px;

                cursor: pointer;

                width: 100%;

                font-size: 16px;

                font-weight: bold;
            }

            button:hover {

                background:
                    #2563eb;
            }

            .btn {

                display: block;

                margin-top: 12px;

                padding: 12px;

                border-radius: 8px;

                text-decoration: none;

                color: white;

                font-weight: bold;

                box-sizing:
                    border-box;
            }

            .status {

                background:
                    #10b981;
            }

            .preview {

                background:
                    #8b5cf6;
            }

            .youtube {

                background:
                    #dc2626;
            }

            .channel {

                background:
                    #f59e0b;
            }

            .small {

                color:
                    #94a3b8;

                font-size:
                    13px;

                margin-top:
                    20px;
            }

        </style>

    </head>


    <body>

        <div class="card">

            <h2>
                🎬 إنشاء فيديو جديد
            </h2>


            <form
                action="/web-create"
                method="post"
            >

                <input
                    type="text"
                    name="title"

                    placeholder="
                    اكتب موضوع أو عنوان الفيديو هنا...
                    "

                    required
                >


                <button
                    type="submit"
                >

                    🚀 إنشاء الفيديو

                </button>

            </form>


            <a
                href="/status"
                class="
                    btn
                    status
                "
            >

                📊 متابعة حالة الفيديو

            </a>


            <a
                href="/preview"
                class="
                    btn
                    preview
                "
            >

                🎬 معاينة الفيديو

            </a>


            <a
                href="/auth"
                class="
                    btn
                    youtube
                "
            >

                🔐 ربط قناة YouTube

            </a>


            <a
                href="/channel"
                class="
                    btn
                    channel
                "
            >

                📺 فحص القناة المرتبطة

            </a>


            <p
                class="small"
            >

                اكتب موضوع الفيديو ثم اضغط إنشاء.

            </p>

        </div>

    </body>

    </html>
    """


# ============================================================
# إنشاء فيديو من واجهة الموقع
# ============================================================

@app.post(
    "/web-create",
    response_class=HTMLResponse,
)
async def web_create(
    title: str = Form(...),
    background_tasks: BackgroundTasks = None,
):

    clean_title = title.strip()

    if not clean_title:

        raise HTTPException(
            status_code=400,
            detail="عنوان الفيديو مطلوب"
        )


    job_data = {

        "id":
            f"job_{uuid4().hex}",

        "title":
            clean_title,

        "feeds":
            []

    }


    if background_tasks is not None:

        background_tasks.add_task(
            tracked_run_job,
            job_data
        )


    safe_title = safe_text(
        clean_title
    )


    return f"""

    <!DOCTYPE html>

    <html
        lang="ar"
        dir="rtl"
    >

    <head>

        <meta charset="UTF-8">

        <style>

            body {{

                font-family:
                    Tahoma,
                    sans-serif;

                background:
                    #0f172a;

                color:
                    #ffffff;

                text-align:
                    center;

                padding:
                    100px
                    20px;
            }}

            a {{

                display:
                    inline-block;

                margin:
                    10px;

                color:
                    #60a5fa;

                font-size:
                    18px;

                text-decoration:
                    none;
            }}

        </style>

    </head>


    <body>

        <h2>

            🚀 تم استلام طلبك!

        </h2>


        <p>

            جاري الآن إنشاء الفيديو بعنوان:

            <b>

                {safe_title}

            </b>

        </p>


        <br>


        <a
            href="/status"
        >

            📊 متابعة حالة التقدم

        </a>


        <br>


        <a
            href="/preview"
        >

            🎬 معاينة الفيديو

        </a>


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
# حالة الفيديو
# ============================================================

@app.get(
    "/status",
    response_class=HTMLResponse,
)
def get_status():

    status = safe_text(
        current_job_status.get(
            "status",
            ""
        )
    )

    title = safe_text(
        current_job_status.get(
            "title",
            ""
        )
    )

    progress = safe_text(
        current_job_status.get(
            "progress",
            ""
        )
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
                    16px;

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
                    15px
                    0;

                border:
                    1px
                    solid
                    #475569;

                text-align:
                    right;
            }}


            a {{

                color:
                    #60a5fa;

                text-decoration:
                    none;

                display:
                    inline-block;

                margin:
                    10px;
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

                        حالة المهمة:

                    </b>

                    {status}

                </p>


                <p>

                    <b>

                        عنوان الفيديو:

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


            <p
                style="
                    font-size:12px;
                    color:#94a3b8;
                "
            >

                يتم تحديث الصفحة
                تلقائياً كل 5 ثوانٍ.

            </p>


            <a
                href="/preview"
            >

                🎬 معاينة الفيديو

            </a>


            <br>


            <a
                href="/"
            >

                ← العودة للرئيسية

            </a>

        </div>


    </body>

    </html>
    """


# ============================================================
# البحث عن أحدث فيديو
# ============================================================

def find_latest_video():

    search_locations = [

        BASE_DIR,

        BASE_DIR / "output",

        BASE_DIR / "outputs",

        BASE_DIR / "videos",

        BASE_DIR / "generated_videos",

    ]


    videos = []


    for location in search_locations:

        if not location.exists():

            continue


        try:

            videos.extend(
                list(
                    location.glob(
                        "**/*.mp4"
                    )
                )
            )

        except Exception:

            pass


    unique_videos = list(
        set(videos)
    )


    if not unique_videos:

        return None


    return max(
        unique_videos,
        key=lambda item:
            item.stat().st_mtime
    )


# ============================================================
# معاينة أحدث فيديو
# ============================================================

@app.get(
    "/preview",
    response_class=HTMLResponse,
)
def preview_latest_video():

    latest_video = find_latest_video()


    if latest_video is None:

        return """

        <html
            lang="ar"
            dir="rtl"
        >

        <head>

            <meta charset="UTF-8">

        </head>


        <body

            style="
                background:#0f172a;
                color:#ffffff;
                text-align:center;
                padding-top:100px;
                font-family:Tahoma;
            "

        >


            <h2>

                لا يوجد فيديو جاهز
                للمعاينة حتى الآن.

            </h2>


            <p>

                تأكد من حالة المهمة
                أولاً.

            </p>


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


    video_filename = latest_video.name


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
            content="width=device-width, initial-scale=1.0"
        >


        <title>

            معاينة الفيديو

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

                padding:
                    30px;

                margin:
                    0;
            }}


            .container {{

                background:
                    #1e293b;

                padding:
                    25px;

                border-radius:
                    16px;

                display:
                    inline-block;

                max-width:
                    800px;

                width:
                    100%;

                box-sizing:
                    border-box;
            }}


            video {{

                width:
                    100%;

                border-radius:
                    8px;

                margin:
                    20px
                    0;

                background:
                    black;
            }}


            button {{

                background:
                    #10b981;

                color:
                    white;

                border:
                    none;

                            border:
                    none;

                padding:
                    14px;

                border-radius:
                    8px;

                font-size:
                    16px;

                font-weight:
                    bold;

                cursor:
                    pointer;

                width:
                    100%;
            }}


            a {{

                color:
                    #60a5fa;

                text-decoration:
                    none;

                display:
                    inline-block;

                margin-top:
                    20px;
            }}

        </style>

    </head>


    <body>


        <div
            class="container"
        >

            <h2>

                🎬 معاينة الفيديو

            </h2>


            <p>

                اسم الملف:

                <b>

                    {safe_text(video_filename)}

                </b>

            </p>


            <video
                controls
            >

                <source

                    src="/stream-file/{video_filename}"

                    type="video/mp4"

                >

                متصفحك لا يدعم تشغيل الفيديو.

            </video>


            <form
                action="/publish-direct"
                method="post"
            >

                <input

                    type="hidden"

                    name="video_path"

                    value="{safe_text(str(latest_video))}"

                >


                <button
                    type="submit"
                >

                    🚀 رفع الفيديو إلى YouTube
                    كفيديو خاص

                </button>

            </form>


            <a
                href="/"
            >

                ← العودة للرئيسية

            </a>

        </div>


    </body>

    </html>
    """


# ============================================================
# بث الفيديو
# ============================================================

@app.get(
    "/stream-file/{filename}"
)
def stream_file(
    filename: str
):

    # منع الانتقال إلى مسارات أخرى

    filename = Path(
        filename
    ).name


    latest_video = find_latest_video()


    if (
        latest_video
        and
        latest_video.name
        ==
        filename
    ):

        return FileResponse(

            path=str(
                latest_video
            ),

            media_type=
                "video/mp4",

            filename=
                filename

        )


    videos = list(
        BASE_DIR.glob(
            f"**/{filename}"
        )
    )


    if not videos:

        raise HTTPException(

            status_code=404,

            detail=
                "ملف الفيديو غير موجود"

        )


    return FileResponse(

        path=str(
            videos[0]
        ),

        media_type=
            "video/mp4",

        filename=
            filename

    )


# ============================================================
# YouTube OAuth
# ============================================================

@app.get("/auth")
async def youtube_auth():

    if youtube_module is None:

        raise HTTPException(

            status_code=500,

            detail=(
                "تعذر تحميل youtube.py: "
                f"{youtube_import_error}"
            )

        )


    auth_function = get_youtube_function(

        "authorization_url",

        "get_authorization_url",

        "start_authorization",

        "get_auth_url"

    )


    if auth_function is None:

        raise HTTPException(

            status_code=500,

            detail=(
                "لم يتم العثور على دالة "
                "authorization_url داخل youtube.py"
            )

        )


    try:

        result = await call_maybe_async(
            auth_function
        )


        # الحالة الأولى:
        # (url, state, code_verifier)

        if (
            isinstance(
                result,
                tuple
            )
            and
            len(result)
            >= 3
        ):

            url = result[0]

            state = result[1]

            code_verifier = result[2]


        # الحالة الثانية:
        # dict

        elif isinstance(
            result,
            dict
        ):

            url = (
                result.get("url")
                or
                result.get(
                    "authorization_url"
                )
            )

            state = result.get(
                "state"
            )

            code_verifier = (
                result.get(
                    "code_verifier"
                )
            )


        else:

            raise RuntimeError(
                "شكل نتيجة authorization_url غير معروف"
            )


        if not url:

            raise RuntimeError(
                "لم يتم إنشاء رابط Google OAuth"
            )


        if not state:

            state = uuid4().hex


        oauth_sessions[state] = {

            "code_verifier":
                code_verifier

        }


        return RedirectResponse(

            url=str(url),

            status_code=302

        )


    except HTTPException:

        raise


    except Exception as exc:

        raise HTTPException(

            status_code=500,

            detail=(
                "تعذر بدء ربط YouTube: "
                f"{exc}"
            )

        )


# ============================================================
# Google OAuth Callback
# ============================================================

@app.get(
    "/oauth2callback",
    response_class=HTMLResponse,
)
async def oauth2callback(

    code: str = "",

    state: str = "",

    error: str = ""

):

    if error:

        return HTMLResponse(

            f"""

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ❌ تم إلغاء أو رفض ربط YouTube

                </h2>


                <p>

                    {safe_text(error)}

                </p>


                <a

                    href="/auth"

                    style="
                        color:#60a5fa;
                    "

                >

                    🔐 إعادة المحاولة

                </a>

            </body>

            </html>

            """,

            status_code=400

        )


    if not code:

        return HTMLResponse(

            """

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ❌ لم يتم استلام رمز Google

                </h2>


                <a
                    href="/auth"
                    style="color:#60a5fa;"
                >

                    إعادة المحاولة

                </a>

            </body>

            </html>

            """,

            status_code=400

        )


    finish_function = get_youtube_function(

        "finish_authorization",

        "complete_authorization",

        "exchange_code",

        "handle_callback"

    )


    if finish_function is None:

        return HTMLResponse(

            """

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ❌ دالة إكمال الربط غير موجودة

                </h2>


                <p>

                    تحقق من youtube.py

                </p>

            </body>

            </html>

            """,

            status_code=500

        )


    session = oauth_sessions.pop(
        state,
        {}
    )


    code_verifier = session.get(
        "code_verifier"
    )


    try:

        # نحاول استدعاء الدالة
        # وفق أكثر التواقيع احتمالاً

        try:

            result = await call_maybe_async(

                finish_function,

                code,

                state,

                code_verifier

            )

        except TypeError:

            try:

                result = await call_maybe_async(

                    finish_function,

                    code=code,

                    state=state,

                    code_verifier=code_verifier

                )

            except TypeError:

                result = await call_maybe_async(

                    finish_function,

                    code

                )


        return HTMLResponse(

            """

            <!DOCTYPE html>

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ✅ تم ربط حساب YouTube بنجاح

                </h2>


                <p>

                    يمكنك الآن فحص القناة
                    والعودة لإنشاء الفيديوهات.

                </p>


                <br>


                <a

                    href="/channel"

                    style="
                        color:#34d399;
                        font-size:18px;
                    "

                >

                    📺 فحص القناة المرتبطة

                </a>


                <br><br>


                <a

                    href="/"

                    style="
                        color:#60a5fa;
                    "

                >

                    ← العودة للرئيسية

                </a>


            </body>

            </html>

            """

        )


    except Exception as exc:

        return HTMLResponse(

            f"""

            <!DOCTYPE html>

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ❌ فشل إكمال ربط YouTube

                </h2>


                <p>

                    {safe_text(exc)}

                </p>


                <br>


                <a

                    href="/auth"

                    style="
                        color:#60a5fa;
                    "

                >

                    🔐 إعادة المحاولة

                </a>


            </body>

            </html>

            """,

            status_code=500

        )


# ============================================================
# فحص اتصال YouTube
# ============================================================

@app.get(
    "/channel",
    response_class=HTMLResponse,
)
async def channel_info():

    if youtube_module is None:

        return HTMLResponse(

            f"""

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ❌ تعذر تحميل نظام YouTube

                </h2>


                <p>

                    {safe_text(youtube_import_error)}

                </p>

            </body>

            </html>

            """,

            status_code=500

        )


    is_connected_function = get_youtube_function(

        "is_connected",

        "youtube_connected",

        "is_authenticated"

    )


    if is_connected_function:

        try:

            connected = await call_maybe_async(

                is_connected_function

            )

        except Exception:

            connected = False


        if not connected:

            return HTMLResponse(

                """

                <html
                    lang="ar"
                    dir="rtl"
                >

                <head>

                    <meta charset="UTF-8">

                </head>


                <body

                    style="
                        font-family:Tahoma;
                        background:#0f172a;
                        color:white;
                        text-align:center;
                        padding-top:100px;
                    "

                >

                    <h2>

                        🔴 لم يتم ربط YouTube بعد

                    </h2>


                    <br>


                    <a

                        href="/auth"

                        style="
                            color:#60a5fa;
                            font-size:20px;
                        "

                    >

                        🔐 اضغط هنا لربط القناة

                    </a>

                </body>

                </html>

                """

            )


    channel_function = get_youtube_function(

        "channel",

        "get_channel",

        "get_channel_info",

        "channel_info"

    )


    if channel_function is None:

        return HTMLResponse(

            """

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    🟢 تم العثور على نظام YouTube

                </h2>


                <p>

                    لكن لا توجد دالة
                    لقراءة بيانات القناة.

                </p>


                <a

                    href="/"

                    style="
                        color:#60a5fa;
                    "

                >

                    العودة للرئيسية

                </a>

            </body>

            </html>

            """

        )


    try:

        data = await call_maybe_async(

            channel_function

        )


        if not isinstance(
            data,
            dict
        ):

            data = {
                "data":
                    data
            }


        snippet = data.get(
            "snippet",
            {}
        )


        channel_title = safe_text(

            snippet.get(
                "title",

                data.get(
                    "title",
                    "قناة YouTube"
                )
            )

        )


        channel_id = safe_text(

            data.get(
                "id",
                data.get(
                    "channel_id",
                    ""
                )
            )

        )


        return HTMLResponse(

            f"""

            <!DOCTYPE html>

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    🟢 تم ربط YouTube بنجاح

                </h2>


                <p>

                    <b>

                        اسم القناة:

                    </b>

                    {channel_title}

                </p>


                <p>

                    <b>

                        معرف القناة:

                    </b>

                    {channel_id}

                </p>


                <br>


                <a

                    href="/"

                    style="
                        color:#60a5fa;
                    "

                >

                    ← العودة للرئيسية

                </a>

            </body>

            </html>

            """

        )


    except Exception as exc:

        return HTMLResponse(

            f"""

            <!DOCTYPE html>

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:white;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ⚠️ تعذر قراءة بيانات القناة

                </h2>


                <p>

                    {safe_text(exc)}

                </p>


                <br>


                <a

                    href="/auth"

                    style="
                        color:#60a5fa;
                    "

                >

                    🔐 إعادة ربط الحساب

                </a>

            </body>

            </html>

            """,

            status_code=500

        )


# ============================================================
# نشر الفيديو
# ============================================================

@app.post(
    "/publish-direct",
    response_class=HTMLResponse,
)
async def publish_direct(

    video_path: str = Form(...)

):

    if not os.path.exists(
        video_path
    ):

        return HTMLResponse(

            """

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    background:#0f172a;
                    color:#ffffff;
                    text-align:center;
                    padding-top:100px;
                    font-family:Tahoma;
                "

            >

                <h2>

                    ❌ ملف الفيديو غير موجود

                </h2>


                <a

                    href="/preview"

                    style="
                        color:#60a5fa;
                    "

                >

                    العودة للمعاينة

                </a>

            </body>

            </html>

            """,

            status_code=404

        )


    if youtube_module is None:

        return HTMLResponse(

            f"""

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    background:#0f172a;
                    color:#ffffff;
                    text-align:center;
                    padding-top:100px;
                    font-family:Tahoma;
                "

            >

                <h2>

                    ❌ تعذر تحميل youtube.py

                </h2>


                <p>

                    {safe_text(youtube_import_error)}

                </p>

            </body>

            </html>

            """,

            status_code=500

        )


    is_connected_function = get_youtube_function(

        "is_connected",

        "youtube_connected",

        "is_authenticated"

    )


    if is_connected_function:

        try:

            connected = await call_maybe_async(

                is_connected_function

            )

        except Exception:

            connected = False


        if not connected:

            return HTMLResponse(

                """

                <html
                    lang="ar"
                    dir="rtl"
                >

                <head>

                    <meta charset="UTF-8">

                </head>


                <body

                    style="
                        background:#0f172a;
                        color:#ffffff;
                        text-align:center;
                        padding-top:100px;
                        font-family:Tahoma;
                    "

                >

                    <h2>

                        🔴 يجب ربط قناة YouTube أولاً

                    </h2>


                    <br>


                    <a

                        href="/auth"

                        style="
                            color:#60a5fa;
                            font-size:20px;
                        "

                    >

                        🔐 ربط قناة YouTube

                    </a>

                </body>

                </html>

                """

            )


    upload_function = get_youtube_function(

        "upload_video",

        "upload",

        "publish_video",

        "upload_to_youtube"

    )


    if upload_function is None:

        return HTMLResponse(

            """

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    background:#0f172a;
                    color:#ffffff;
                    text-align:center;
                    padding-top:100px;
                    font-family:Tahoma;
                "

            >

                <h2>

                    ⚠️ تم ربط الواجهة

                    لكن دالة رفع الفيديو

                    غير موجودة في youtube.py

                </h2>


                <p>

                    يجب أن تكون هناك دالة مثل:

                    upload_video

                </p>


                <a

                    href="/"

                    style="
                        color:#60a5fa;
                    "

                >

                    العودة للرئيسية

                </a>

            </body>

            </html>

            """,

            status_code=500

        )


    try:

        try:

            result = await call_maybe_async(

                upload_function,

                video_path,

                privacy_status="private"

            )

        except TypeError:

            try:

                result = await call_maybe_async(

                    upload_function,

                    video_path,

                    privacy="private"

                )

            except TypeError:

                result = await call_maybe_async(

                    upload_function,

                    video_path

                )


        return HTMLResponse(

            """

            <!DOCTYPE html>

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:#ffffff;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    🚀 تم إرسال طلب رفع الفيديو

                </h2>


                <p>

                    تحقق من YouTube Studio.

                </p>


                <p>

                    إذا نجحت عملية الرفع

                    سيظهر الفيديو

                    وفق إعدادات الخصوصية

                    الموجودة في youtube.py.

                </p>


                <br>


                <a

                    href="/"

                    style="
                        color:#60a5fa;
                    "

                >

                    ← العودة للرئيسية

                </a>

            </body>

            </html>

            """

        )


    except Exception as exc:

        return HTMLResponse(

            f"""

            <!DOCTYPE html>

            <html
                lang="ar"
                dir="rtl"
            >

            <head>

                <meta charset="UTF-8">

            </head>


            <body

                style="
                    font-family:Tahoma;
                    background:#0f172a;
                    color:#ffffff;
                    text-align:center;
                    padding-top:100px;
                "

            >

                <h2>

                    ❌ فشل رفع الفيديو

                </h2>


                <p>

                    {safe_text(exc)}

                </p>


                <br>


                <a

                    href="/preview"

                    style="
                        color:#60a5fa;
                    "

                >

                    العودة للمعاينة

                </a>

            </body>

            </html>

            """,

            status_code=500

        )


# ============================================================
# API لإنشاء فيديو
# ============================================================

@app.post(
    "/start-job"
)
async def start_job_endpoint(

    job: JobRequest,

    background_tasks:
        BackgroundTasks

):

    job_data = job.model_dump()


    background_tasks.add_task(

        tracked_run_job,

        job_data

    )


    return {

        "status":
            "processing",

        "job_id":
            job.id,

        "message":
            "تم بدء إنشاء الفيديو"

    }


# ============================================================
# الرابط القديم لإنشاء الفيديو
# ============================================================

@app.get(
    "/quick-create"
)
async def quick_create(

    title: str,

    background_tasks:
        BackgroundTasks

):

    clean_title = title.strip()


    if not clean_title:

        raise HTTPException(

            status_code=400,

            detail=
                "يرجى كتابة عنوان الفيديو"

        )


    job_data = {

        "id":
            f"job_{uuid4().hex}",

        "title":
            clean_title,

        "feeds":
            []

    }


    background_tasks.add_task(

        tracked_run_job,

        job_data

    )


    return {

        "status":
            "success",

        "job_id":
            job_data["id"],

        "message":
            f"جاري إنشاء الفيديو: "
            f"'{clean_title}'"

    }


# ============================================================
# API Health Check
# ============================================================

@app.get(
    "/health"
)
def health_check():

    return {

        "status":
            "ok",

        "service":
            "YouTube AI Agent",

        "youtube_module_loaded":
            youtube_module
            is not None,

        "youtube_error":
            youtube_import_error

    }    
