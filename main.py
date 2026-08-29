import os
import threading
import time

from fastapi import FastAPI, Form, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from dotenv import load_dotenv
from db import *
from worker import run_job, upload_job, publish_job, autopilot_once

from youtube import authorization_url, finish_authorization


load_dotenv()

init()

app = FastAPI(title="YouTube AI Autonomous 24/7")


# =========================
# Secure OAuth Session
# =========================

SESSION_SECRET = os.getenv(
    "OAUTH_SESSION_SECRET",
    "change-this-secret"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=True,
    same_site="lax",
)


# =========================
# YouTube OAuth
# =========================

@app.get("/auth")
def auth(request: Request):

    url, state, code_verifier = authorization_url()

    request.session["oauth_state"] = state
    request.session["code_verifier"] = code_verifier

    return RedirectResponse(url)


@app.get("/oauth2callback")
def oauth2callback(
    request: Request,
    code: str,
    state: str = ""
):

    saved_state = request.session.get("oauth_state")
    code_verifier = request.session.get("code_verifier")

    if not saved_state or not code_verifier:
        return HTMLResponse(
            """
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ انتهت جلسة OAuth</h2>

            <p>
            افتح /auth وابدأ عملية الربط من جديد.
            </p>

            <a href="/auth">
                🔗 إعادة ربط YouTube
            </a>

            </html>
            """,
            status_code=400
        )

    if state != saved_state:
        return HTMLResponse(
            """
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ OAuth State غير صحيح</h2>

            <p>
            أعد عملية الربط من البداية.
            </p>

            <a href="/auth">
                🔗 إعادة ربط YouTube
            </a>

            </html>
            """,
            status_code=400
        )

    try:

        finish_authorization(
            code,
            state,
            code_verifier
        )

        request.session.pop("oauth_state", None)
        request.session.pop("code_verifier", None)

    except Exception as e:

        print("OAuth ERROR:", repr(e))

        return HTMLResponse(
            """
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ فشل ربط YouTube</h2>

            <p>
            حدث خطأ أثناء حفظ صلاحية YouTube.
            </p>

            <a href="/auth">
                🔗 المحاولة مرة أخرى
            </a>

            </html>
            """,
            status_code=500
        )

    return HTMLResponse("""
    <html lang="ar" dir="rtl">
    <meta charset="utf-8">

    <style>
        body {
            font-family: Arial;
            max-width: 800px;
            margin: 50px auto;
            text-align: center;
        }

        a {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 20px;
            background: #222;
            color: white;
            text-decoration: none;
            border-radius: 8px;
        }
    </style>

    <h2>✅ تم ربط حساب YouTube بنجاح</h2>

    <p>
        تم حفظ صلاحية الوصول إلى قناة YouTube.
    </p>

    <a href="/">
        العودة إلى الوكيل
    </a>

    </html>
    """)


# =========================
# Autopilot
# =========================

def autopilot_loop():

    while True:

        try:
            autopilot_once()

        except Exception as e:
            print("Autopilot ERROR:", repr(e))

        time.sleep(3600)


threading.Thread(
    target=autopilot_loop,
    daemon=True
).start()


# =========================
# Setup
# =========================

@app.get("/setup", response_class=HTMLResponse)
def setup():

    return """
    <html lang='ar' dir='rtl'>
    <meta charset='utf-8'>

    <style>
        body {
            font-family: Arial;
            max-width: 800px;
            margin: 40px auto;
        }

        input, button {
            padding: 10px;
            margin: 5px;
        }

        a {
            display: inline-block;
            margin: 8px;
        }
    </style>

    <h1>إعداد الوكيل</h1>

    <p>
        ضع OPENAI_API_KEY في Environment Variables.
    </p>

    <p>
        ضع client_secret.json داخل Render Secret Files.
    </p>

    <p>
        بعد ذلك اضغط الزر التالي لربط قناة YouTube:
    </p>

    <a href="/auth">
        <button>🔗 ربط YouTube</button>
    </a>

    <br>

    <a href="/">
        العودة إلى Dashboard
    </a>

    </html>
    """


# =========================
# Dashboard
# =========================

@app.get("/", response_class=HTMLResponse)
def home():

    rows = jobs()

    tr = ""

    for j in rows:

        act = ""

        if j["status"] == "ready":

            act = f"""
            <form method='post' action='/upload/{j["id"]}'>
                <button>رفع Private</button>
            </form>
            """

        elif j["status"] == "uploaded_private":

            act = f"""
            <form method='post' action='/publish/{j["id"]}'>
                <button>نشر Public</button>
            </form>
            """

        tr += f"""
        <tr>
            <td>{j["id"]}</td>
            <td>{j["topic"]}</td>
            <td>{j["status"]}</td>
            <td>{j["title"] or ""}</td>
            <td>{act}</td>
        </tr>
        """

    ap = os.getenv(
        "AUTOPILOT",
        "false"
    )

    return f"""
    <!doctype html>
    <html lang='ar' dir='rtl'>

    <meta charset='utf-8'>

    <style>

        body {{
            font-family: Arial;
            max-width: 1200px;
            margin: 30px auto;
        }}

        input, button {{
            padding: 10px;
            margin: 4px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        td, th {{
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }}

    </style>

    <h1>
        🤖 YouTube AI Autonomous 24/7
    </h1>

    <p>
        Autopilot:
        <b>{ap}</b>
        —
        الحد اليومي:
        {os.getenv("DAILY_JOB_LIMIT", "2")}
    </p>

    <p>

        <a href="/auth">
            <button>
                🔗 ربط حساب YouTube
            </button>
        </a>

    </p>

    <form method='post' action='/create'>

        <input
            name='topic'
            required
            placeholder='اكتب موضوعاً أو اترك الوكيل يبحث بنفسه'
            style='width:60%'
        >

        <button>
            إنشاء
        </button>

    </form>


    <form method='post' action='/autopilot'>

        <button>
            تفعيل Autopilot
        </button>

    </form>


    <table>

        <tr>
            <th>ID</th>
            <th>الموضوع</th>
            <th>الحالة</th>
            <th>العنوان</th>
            <th>إجراء</th>
        </tr>

        {tr}

    </table>


    <p>

        <a href='/setup'>
            الإعداد
        </a>

    </p>

    </html>
    """


# =========================
# Create Job
# =========================

@app.post("/create")
def create(
    background_tasks: BackgroundTasks,
    topic: str = Form(...)
):

    jid = add_job(
        topic,
        os.getenv(
            "DEFAULT_LANGUAGE",
            "ar"
        )
    )

    if jid:

        background_tasks.add_task(
            run_job,
            jid
        )

    return RedirectResponse(
        "/",
        303
    )


# =========================
# Autopilot
# =========================

@app.post("/autopilot")
def autopilot():

    os.environ["AUTOPILOT"] = "true"

    return RedirectResponse(
        "/",
        303
    )


# =========================
# Upload
# =========================

@app.post("/upload/{jid}")
def upload(jid: int):

    upload_job(jid)

    return RedirectResponse(
        "/",
        303
    )


# =========================
# Publish
# =========================

@app.post("/publish/{jid}")
def publish(jid: int):

    publish_job(jid)

    return RedirectResponse(
        "/",
        303
    )
