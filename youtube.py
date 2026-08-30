import json
import os
import secrets
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
# FILE PATHS
# ============================================================

SECRET = Path(
    "/etc/secrets/client_secret.json"
)

TOKEN = Path(
    "credentials/token.json"
)

OAUTH_PENDING = Path(
    "credentials/oauth_pending.json"
)


# ============================================================
# DEFAULT OAUTH REDIRECT URI
# ============================================================

DEFAULT_REDIRECT_URI = (
    "https://youtube-ai-agent-yich.onrender.com/oauth2callback"
)


# ============================================================
# REDIRECT URI
# ============================================================

def get_redirect_uri():

    return os.getenv(
        "OAUTH_REDIRECT_URI",
        DEFAULT_REDIRECT_URI
    ).strip()


# ============================================================
# CREATE GOOGLE OAUTH FLOW
# ============================================================

def get_flow(
    code_verifier=None
):

    if not SECRET.exists():

        raise RuntimeError(
            "client_secret.json غير موجود في "
            "/etc/secrets/client_secret.json"
        )

    flow = Flow.from_client_secrets_file(
        str(SECRET),
        scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
    )

    if code_verifier:

        flow.oauth2session._client.code_verifier = (
            code_verifier
        )

    return flow


# ============================================================
# START OAUTH
# ============================================================

def authorization_url():

    flow = get_flow()

    # --------------------------------------------------------
    # إنشاء PKCE code verifier يدويًا
    # --------------------------------------------------------

    code_verifier = secrets.token_urlsafe(
        64
    )

    flow.oauth2session._client.code_verifier = (
        code_verifier
    )

    # --------------------------------------------------------
    # إنشاء Google Authorization URL
    # --------------------------------------------------------

    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge_method="S256",
    )

    if not url:

        raise RuntimeError(
            "تعذر إنشاء رابط Google OAuth."
        )

    if not state:

        raise RuntimeError(
            "تعذر إنشاء OAuth state."
        )

    # --------------------------------------------------------
    # حفظ بيانات OAuth على الخادم
    # --------------------------------------------------------

    OAUTH_PENDING.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OAUTH_PENDING.write_text(
        json.dumps(
            {
                "state": state,
                "code_verifier": code_verifier,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # مهم:
    # نعيد 3 قيم فقط لأن main.py يستقبل 3 قيم.
    # --------------------------------------------------------

    return (
        url,
        state,
        code_verifier,
    )


# ============================================================
# LOAD PENDING OAUTH
# ============================================================

def load_pending():

    if not OAUTH_PENDING.exists():

        return None

    try:

        data = json.loads(
            OAUTH_PENDING.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return None

    if not data.get("state"):

        return None

    if not data.get("code_verifier"):

        return None

    return data


# ============================================================
# CLEAR PENDING OAUTH
# ============================================================

def clear_pending():

    try:

        OAUTH_PENDING.unlink()

    except FileNotFoundError:

        pass


# ============================================================
# FINISH OAUTH
# ============================================================

def finish_authorization(
    code,
    state,
    code_verifier=None,
):

    if not code:

        raise RuntimeError(
            "لم يتم استلام authorization code من Google."
        )

    if not state:

        raise RuntimeError(
            "لم يتم استلام OAuth state من Google."
        )

    # --------------------------------------------------------
    # تحميل بيانات OAuth المحفوظة على الخادم
    # --------------------------------------------------------

    pending = load_pending()

    if pending:

        saved_state = pending.get(
            "state"
        )

        saved_verifier = pending.get(
            "code_verifier"
        )

        # ----------------------------------------------------
        # التحقق من state
        # ----------------------------------------------------

        if saved_state != state:

            clear_pending()

            raise RuntimeError(
                "OAuth state غير صحيح. "
                "ابدأ عملية الربط من /auth مرة أخرى."
            )

        # ----------------------------------------------------
        # نستخدم verifier المحفوظ على الخادم
        # ----------------------------------------------------

        code_verifier = saved_verifier

    # --------------------------------------------------------
    # إذا لم يوجد verifier نستخدم القيمة القادمة من Session
    # --------------------------------------------------------

    if not code_verifier:

        raise RuntimeError(
            "OAuth code_verifier مفقود. "
            "ابدأ عملية الربط من /auth مرة أخرى."
        )

    # --------------------------------------------------------
    # إنشاء Flow مع نفس code verifier
    # --------------------------------------------------------

    flow = get_flow(
        code_verifier=code_verifier
    )

    # --------------------------------------------------------
    # استبدال authorization code بالتوكن
    #
    # مهم جدًا:
    # نرسل code_verifier صراحةً إلى Google.
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
            "Google لم تُرجع بيانات Credentials."
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

    # --------------------------------------------------------
    # حذف بيانات OAuth المؤقتة
    # --------------------------------------------------------

    clear_pending()

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
    # قراءة Credentials
    # --------------------------------------------------------

    creds = Credentials.from_authorized_user_file(
        str(TOKEN),
        SCOPES,
    )

    # --------------------------------------------------------
    # إذا كان التوكن منتهيًا
    # نحاول تجديده باستخدام refresh token.
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
# UPLOAD PRIVATE VIDEO
# ============================================================

def upload_private(
    path,
    title,
    description,
    thumbnail=None,
):

    yt = service()

    # --------------------------------------------------------
    # Video metadata
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
    # Video file
    # --------------------------------------------------------

    media = MediaFileUpload(
        path,
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    # --------------------------------------------------------
    # Upload request
    # --------------------------------------------------------

    request = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    # --------------------------------------------------------
    # Resumable upload
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
            "YouTube لم تُرجع video ID."
        )

    # --------------------------------------------------------
    # Upload thumbnail if provided
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
# PUBLISH VIDEO
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
# CHECK VIDEO PROCESSING STATUS
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
