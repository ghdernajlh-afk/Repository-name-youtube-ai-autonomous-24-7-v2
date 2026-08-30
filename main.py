import os
import threading
import time
from html import escape

from fastapi import (
    FastAPI,
    Form,
    BackgroundTasks,
    Request,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)
from starlette.middleware.sessions import SessionMiddleware

from dotenv import load_dotenv

from db import (
    init,
    jobs,
    add_job,
)

from worker import (
    run_job,
    upload_job,
    publish_job,
    autopilot_once,
)

from youtube import (
    authorization_url,
    finish_authorization,
)


load_dotenv()


# ============================================================
# DATABASE
# ============================================================

init()


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="YouTube AI Autonomous 24/7"
)


# ============================================================
# SESSION
# ============================================================

SESSION_SECRET = os.getenv(
    "OAUTH_SESSION_SECRET"
)

if not SESSION_SECRET:
    raise RuntimeError(
        "OAUTH_SESSION_SECRET is missing. "
        "Add it in Render Environment Variables."
    )


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=True,
    same_site="lax",
)


# ============================================================
# YOUTUBE AUTH
# ============================================================

@app.get("/auth")
def auth(request: Request):

    try:

        result = authorization_url()

        # youtube.py الجديد يعيد 3 قيم
        # url, state, code_verifier
        if len(result) != 3:
            raise RuntimeError(
                "authorization_url() returned an "
                "unexpected number of values."
            )

        url, state, code_verifier = result

        # نحتفظ بها أيضًا في Session
        # للتوافق مع المتصفح.
        request.session["oauth_state"] = state
        request.session["code_verifier"] = code_verifier

        return RedirectResponse(
            url=url,
            status_code=302,
        )

    except Exception as e:

        print(
            "AUTH START ERROR:",
            repr(e)
        )

        return HTMLResponse(
            f"""
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ فشل بدء ربط YouTube</h2>

            <p>
            {escape(str(e))}
            </p>

            <p>
            تأكد من وجود client_secret.json
            وإعدادات OAuth في Render.
            </p>

            <a href="/">
                العودة إلى Dashboard
            </a>

            </html>
            """,
            status_code=500,
        )


# ============================================================
# OAUTH CALLBACK
# ============================================================

@app.get("/oauth2callback")
def oauth2callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):

    # --------------------------------------------------------
    # Google returned an OAuth error
    # --------------------------------------------------------

    if error:

        print(
            "GOOGLE OAUTH ERROR:",
            error
        )

        return HTMLResponse(
            f"""
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ ألغيت عملية ربط YouTube</h2>

            <p>
            Google OAuth:
            {escape(error)}
            </p>

            <a href="/auth">
                🔗 إعادة المحاولة
            </a>

            </html>
            """,
            status_code=400,
        )


    # --------------------------------------------------------
    # Get values from browser session
    # --------------------------------------------------------

    saved_state = request.session.get(
        "oauth_state"
    )

    code_verifier = request.session.get(
        "code_verifier"
    )


    # --------------------------------------------------------
    # Important:
    # youtube.py also stores the pending OAuth data
    # on the server. Therefore, the browser Session
    # is not the only source.
    # --------------------------------------------------------

    if not state:

        return HTMLResponse(
            """
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ لم يتم استلام OAuth State</h2>

            <p>
            ابدأ عملية الربط من جديد.
            </p>

            <a href="/auth">
                🔗 إعادة ربط YouTube
            </a>

            </html>
            """,
            status_code=400,
        )


    if not code:

        return HTMLResponse(
            """
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ لم يتم استلام رمز Google</h2>

            <p>
            ابدأ عملية الربط من جديد.
            </p>

            <a href="/auth">
                🔗 إعادة المحاولة
            </a>

            </html>
            """,
            status_code=400,
        )


    # --------------------------------------------------------
    # If browser session exists, verify it.
    #
    # If it does not exist, youtube.py can still validate
    # the pending OAuth transaction saved on the server.
    # --------------------------------------------------------

    if saved_state and saved_state != state:

        print(
            "OAUTH SESSION STATE MISMATCH"
        )

        return HTMLResponse(
            """
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ OAuth State غير صحيح</h2>

            <p>
            أعد عملية الربط من /auth.
            </p>

            <a href="/auth">
                🔗 إعادة ربط YouTube
            </a>

            </html>
            """,
            status_code=400,
        )


    # --------------------------------------------------------
    # Finish OAuth
    # --------------------------------------------------------

    try:

        finish_authorization(
            code=code,
            state=state,
            code_verifier=code_verifier,
        )

        # Clear browser session
        request.session.pop(
            "oauth_state",
            None
        )

        request.session.pop(
            "code_verifier",
            None
        )

        return HTMLResponse(
            """
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <head>
                <title>YouTube Connected</title>
            </head>

            <body>

            <h2>✅ تم ربط YouTube بنجاح</h2>

            <p>
            تم حفظ صلاحيات الحساب بنجاح.
            </p>

            <p>
            أصبح الوكيل قادرًا على استخدام قناة YouTube.
            </p>

            <br>

            <a href="/">
                🏠 العودة إلى Dashboard
            </a>

            </body>
            </html>
            """
        )

    except Exception as e:

        print(
            "OAUTH CALLBACK ERROR:",
            repr(e)
        )

        return HTMLResponse(
            f"""
            <!doctype html>
            <html lang="ar" dir="rtl">
            <meta charset="utf-8">

            <h2>❌ فشل ربط YouTube</h2>

            <p>
            حدث خطأ أثناء إكمال المصادقة.
            </p>

            <p>
            {escape(str(e))}
            </p>

            <br>

            <a href="/auth">
                🔗 إعادة المحاولة
            </a>

            </html>
            """,
            status_code=500,
        )


# ============================================================
# AUTOPILOT
# ============================================================

def autopilot_loop():

    while True:

        try:

            autopilot_once()

        except Exception as e:

            print(
                "Autopilot ERROR:",
                repr(e)
            )

        time.sleep(3600)


threading.Thread(
    target=autopilot_loop,
    daemon=True,
).start()


# ============================================================
# SETUP
# ============================================================

@app.get(
    "/setup",
    response_class=HTMLResponse,
)
def setup():

    return """
    <!doctype html>

    <html lang="ar" dir="rtl">

    <meta charset="utf-8">

    <style>

        body {
            font-family: Arial;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
        }

        button {
            padding: 12px 20px;
            cursor: pointer;
        }

        a {
            text-decoration: none;
        }

    </style>

    <h1>⚙️ إعداد الوكيل</h1>

    <h3>المتطلبات</h3>

    <p>
    يجب إضافة OPENAI_API_KEY في
    Render → Environment Variables.
    </p>

    <p>
    يجب إضافة OAUTH_SESSION_SECRET في
    Render → Environment Variables.
    </p>

    <p>
    يجب إضافة client_secret.json في:
    </p>

    <pre>/etc/secrets/client_secret.json</pre>

    <p>
    ويجب أن يكون OAUTH_REDIRECT_URI:
    </p>

    <pre>
https://youtube-ai-agent-yich.onrender.com/oauth2callback
    </pre>

    <br>

    <a href="/auth">
        <button>
            🔗 ربط قناة YouTube
        </button>
    </a>

    <br><br>

    <a href="/">
        العودة إلى Dashboard
    </a>

    </html>
    """


# ============================================================
# DASHBOARD
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():

    rows = jobs()

    tr = ""

    for j in rows:

        action = ""

        if j["status"] == "ready":

            action = f"""
            <form
                method="post"
                action="/upload/{j['id']}"
            >

                <button>
                    رفع Private
                </button>

            </form>
            """

        elif j["status"] == "uploaded_private":

            action = f"""
            <form
                method="post"
                action="/publish/{j['id']}"
            >

                <button>
                    نشر Public
                </button>

            </form>
            """

        tr += f"""
        <tr>

            <td>
                {j["id"]}
            </td>

            <td>
                {escape(str(j["topic"] or ""))}
            </td>

            <td>
                {escape(str(j["status"] or ""))}
            </td>

            <td>
                {escape(str(j["title"] or ""))}
            </td>

            <td>
                {action}
            </td>

        </tr>
        """


    autopilot_status = os.getenv(
        "AUTOPILOT",
        "false"
    )

    daily_limit = os.getenv(
        "DAILY_JOB_LIMIT",
        "2"
    )


    return f"""
    <!doctype html>

    <html lang="ar" dir="rtl">

    <meta charset="utf-8">

    <style>

        body {{
            font-family: Arial;
            max-width: 1200px;
            margin: 30px auto;
            padding: 20px;
        }}

        input,
        button {{
            padding: 10px;
            margin: 4px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: right;
        }}

        a {{
            text-decoration: none;
        }}

    </style>

    <h1>
        🤖 YouTube AI Autonomous 24/7
    </h1>

    <p>
        Autopilot:
        <b>{escape(str(autopilot_status))}</b>
    </p>

    <p>
        الحد اليومي:
        <b>{escape(str(daily_limit))}</b>
    </p>

    <p>

        <a href="/auth">

            <button>
                🔗 ربط حساب YouTube
            </button>

        </a>

    </p>

    <hr>

    <h3>
        إنشاء فيديو
    </h3>

    <form
        method="post"
        action="/create"
    >

        <input
            name="topic"
            required
            placeholder="اكتب موضوع الفيديو"
            style="width:60%;"
        >

        <button>
            إنشاء
        </button>

    </form>

    <br>

    <form
        method="post"
        action="/autopilot"
    >

        <button>
            🤖 تفعيل Autopilot
        </button>

    </form>

    <br>

    <table>

        <tr>

            <th>
                ID
            </th>

            <th>
                الموضوع
            </th>

            <th>
                الحالة
            </th>

            <th>
                العنوان
            </th>

            <th>
                الإجراء
            </th>

        </tr>

        {tr}

    </table>

    <br>

    <a href="/setup">
        ⚙️ الإعداد
    </a>

    </html>
    """


# ============================================================
# CREATE JOB
# ============================================================

@app.post("/create")
def create(
    background_tasks: BackgroundTasks,
    topic: str = Form(...),
):

    jid = add_job(
        topic,
        os.getenv(
            "DEFAULT_LANGUAGE",
            "ar"
        ),
    )

    if jid:

        background_tasks.add_task(
            run_job,
            jid,
        )

    return RedirectResponse(
        "/",
        status_code=303,
    )


# ============================================================
# AUTOPILOT BUTTON
# ============================================================

@app.post("/autopilot")
def enable_autopilot():

    os.environ["AUTOPILOT"] = "true"

    return RedirectResponse(
        "/",
        status_code=303,
    )


# ============================================================
# UPLOAD
# ============================================================

@app.post("/upload/{jid}")
def upload(jid: int):

    upload_job(jid)

    return RedirectResponse(
        "/",
        status_code=303,
    )


# ============================================================
# PUBLISH
# ============================================================

@app.post("/publish/{jid}")
def publish(jid: int):

    publish_job(jid)

    return RedirectResponse(
        "/",
        status_code=303,
    )
