import os
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# ============================================================
# YOUTUBE API SCOPES
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


# ============================================================
# FILES
# ============================================================

SECRET = Path(
    "/etc/secrets/client_secret.json"
)

TOKEN = Path(
    "credentials/token.json"
)


# ============================================================
# REDIRECT URI
# ============================================================

DEFAULT_REDIRECT_URI = (
    "https://youtube-ai-agent-yich.onrender.com/oauth2callback"
)


def get_redirect_uri():

    value = os.getenv(
        "OAUTH_REDIRECT_URI",
        DEFAULT_REDIRECT_URI
    )

    value = value.strip()

    if not value:
        raise RuntimeError(
            "OAUTH_REDIRECT_URI فارغ."
        )

    return value


# ============================================================
# CREATE OAUTH FLOW
# ============================================================

def get_flow(
    code_verifier=None
):

    if not SECRET.exists():

        raise RuntimeError(
            "client_secret.json غير موجود في "
            "/etc/secrets/client_secret.json"
        )

    # --------------------------------------------------------
    # إذا كان لدينا verifier من Session
    # نضعه عند إنشاء Flow.
    # --------------------------------------------------------

    if code_verifier:

        flow = Flow.from_client_secrets_file(
            str(SECRET),
            scopes=SCOPES,
            redirect_uri=get_redirect_uri(),
            code_verifier=code_verifier,
        )

    else:

        # ----------------------------------------------------
        # Google library تنشئ verifier جديدًا لهذه العملية.
        # ----------------------------------------------------

        flow = Flow.from_client_secrets_file(
            str(SECRET),
            scopes=SCOPES,
            redirect_uri=get_redirect_uri(),
            autogenerate_code_verifier=True,
        )

    return flow


# ============================================================
# START AUTHORIZATION
# ============================================================

def authorization_url():

    # --------------------------------------------------------
    # إنشاء Flow جديد.
    # هذا الـ Flow هو الذي سينشئ code_verifier.
    # --------------------------------------------------------

    flow = get_flow()

    # --------------------------------------------------------
    # إنشاء رابط Google OAuth
    # --------------------------------------------------------

    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    # --------------------------------------------------------
    # الحصول على نفس verifier الذي استُخدم
    # لإنشاء code_challenge.
    # --------------------------------------------------------

    code_verifier = flow.code_verifier

    if not code_verifier:

        raise RuntimeError(
            "تعذر إنشاء OAuth code_verifier."
        )

    if not state:

        raise RuntimeError(
            "تعذر إنشاء OAuth state."
        )

    return (
        url,
        state,
        code_verifier,
    )


# ============================================================
# FINISH AUTHORIZATION
# ============================================================

def finish_authorization(
    code,
    state,
    code_verifier,
):

    # --------------------------------------------------------
    # التحقق من البيانات
    # --------------------------------------------------------

    if not code:

        raise RuntimeError(
            "لم يتم استلام authorization code من Google."
        )

    if not state:

        raise RuntimeError(
            "لم يتم استلام OAuth state من Google."
        )

    if not code_verifier:

        raise RuntimeError(
            "OAuth code_verifier مفقود."
        )

    # --------------------------------------------------------
    # إنشاء Flow باستخدام نفس verifier بالضبط
    # الذي تم استخدامه في authorization_url().
    # --------------------------------------------------------

    flow = get_flow(
        code_verifier=code_verifier
    )

    # --------------------------------------------------------
    # استبدال authorization code بالتوكن.
    #
    # code_verifier هنا يُرسل صراحةً إلى Google.
    # --------------------------------------------------------

    flow.fetch_token(
        code=code,
        include_client_id=True,
        code_verifier=code_verifier,
    )

    # --------------------------------------------------------
    # الحصول على Credentials
    # --------------------------------------------------------

    creds = flow.credentials

    if not creds:

        raise RuntimeError(
            "Google لم تُرجع Credentials."
        )

    # --------------------------------------------------------
    # حفظ التوكن
    # --------------------------------------------------------

    TOKEN.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    TOKEN.write_text(
        creds.to_json(),
        encoding="utf-8",
    )

    return creds


# ============================================================
# YOUTUBE SERVICE
# ============================================================

def service():

    if not TOKEN.exists():

        raise RuntimeError(
            "YouTube غير مربوط بعد. "
            "افتح /auth لبدء ربط الحساب."
        )

    # --------------------------------------------------------
    # تحميل Credentials
    # --------------------------------------------------------

    creds = Credentials.from_authorized_user_file(
        str(TOKEN),
        SCOPES,
    )

    # --------------------------------------------------------
    # تجديد Access Token إذا كان منتهيًا
    # --------------------------------------------------------

    if not creds.valid:

        if (
            creds.expired
            and creds.refresh_token
        ):

            from google.auth.transport.requests import (
                Request
            )

            creds.refresh(
                Request()
            )

            TOKEN.write_text(
                creds.to_json(),
                encoding="utf-8",
            )

        else:

            raise RuntimeError(
                "انتهت صلاحية YouTube OAuth. "
                "افتح /auth لإعادة الربط."
            )

    # --------------------------------------------------------
    # إنشاء YouTube API service
    # --------------------------------------------------------

    return build(
        "youtube",
        "v3",
        credentials=creds,
    )


# ============================================================
# UPLOAD PRIVATE
# ============================================================

def upload_private(
    path,
    title,
    description,
    thumbnail=None,
):

    yt = service()

    # --------------------------------------------------------
    # بيانات الفيديو
    # --------------------------------------------------------

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "private",
        },
    }

    # --------------------------------------------------------
    # ملف الفيديو
    # --------------------------------------------------------

    media = MediaFileUpload(
        path,
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    # --------------------------------------------------------
    # إنشاء طلب الرفع
    # --------------------------------------------------------

    request = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    # --------------------------------------------------------
    # رفع الفيديو
    # --------------------------------------------------------

    while response is None:

        status, response = (
            request.next_chunk()
        )

    if not response:

        raise RuntimeError(
            "فشل رفع الفيديو إلى YouTube."
        )

    video_id = response.get(
        "id"
    )

    if not video_id:

        raise RuntimeError(
            "لم يتم الحصول على video_id."
        )

    # --------------------------------------------------------
    # الصورة المصغرة
    # --------------------------------------------------------

    if (
        thumbnail
        and Path(thumbnail).exists()
    ):

        yt.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(
                thumbnail,
                mimetype="image/jpeg",
            ),
        ).execute()

    return video_id


# ============================================================
# PUBLISH
# ============================================================

def publish(
    video_id
):

    if not video_id:

        raise RuntimeError(
            "video_id مفقود."
        )

    yt = service()

    return yt.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": {
                "privacyStatus": "public",
            },
        },
    ).execute()


# ============================================================
# PROCESSING STATUS
# ============================================================

def processing(
    video_id
):

    if not video_id:

        return {}

    yt = service()

    response = yt.videos().list(
        part="status,processingDetails",
        id=video_id,
    ).execute()

    items = response.get(
        "items",
        []
    )

    if not items:

        return {}

    return items[0]
