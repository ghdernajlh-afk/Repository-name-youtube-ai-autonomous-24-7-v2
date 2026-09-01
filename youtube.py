import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from db import setting, set_setting


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


# ============================================================
# DATABASE KEY
# ============================================================

YOUTUBE_CREDENTIALS_KEY = "youtube_credentials"


# ============================================================
# REDIRECT URI
# ============================================================

DEFAULT_REDIRECT_URI = (
    "https://youtube-ai-agent-yich.onrender.com/oauth2callback"
)


def get_redirect_uri():
    """
    Return the OAuth redirect URI.

    OAUTH_REDIRECT_URI can be configured in Render.
    """

    value = os.getenv(
        "OAUTH_REDIRECT_URI",
        DEFAULT_REDIRECT_URI,
    )

    value = value.strip()

    if not value:
        raise RuntimeError(
            "OAUTH_REDIRECT_URI فارغ."
        )

    return value


# ============================================================
# CLIENT SECRET CHECK
# ============================================================

def check_secret():
    """
    Make sure Google client_secret.json exists.
    """

    if not SECRET.exists():
        raise RuntimeError(
            "client_secret.json غير موجود في "
            "/etc/secrets/client_secret.json"
        )


# ============================================================
# CREATE OAUTH FLOW
# ============================================================

def get_flow(code_verifier=None):
    """
    Create a Google OAuth Flow.

    When code_verifier is supplied, the exact verifier from
    the authorization session is used.
    """

    check_secret()

    if code_verifier:

        flow = Flow.from_client_secrets_file(
            str(SECRET),
            scopes=SCOPES,
            redirect_uri=get_redirect_uri(),
            code_verifier=code_verifier,
        )

    else:

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
    """
    Start Google OAuth authorization.

    Returns:
        url
        state
        code_verifier
    """

    flow = get_flow()

    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

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
# SAVE CREDENTIALS TO DATABASE
# ============================================================

def save_credentials(creds):
    """
    Save Google OAuth credentials in the database.

    The credentials are stored as JSON in the settings table.
    """

    if not creds:
        raise RuntimeError(
            "لا توجد Credentials لحفظها."
        )

    data = creds.to_json()

    if not data:
        raise RuntimeError(
            "تعذر تحويل YouTube Credentials إلى JSON."
        )

    try:
        # Validate JSON before storing it.
        json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "بيانات YouTube Credentials غير صالحة."
        ) from exc

    set_setting(
        YOUTUBE_CREDENTIALS_KEY,
        data,
    )


# ============================================================
# LOAD CREDENTIALS FROM DATABASE
# ============================================================

def load_credentials():
    """
    Load YouTube OAuth credentials from the database.

    Returns:
        Credentials object
        or None when no credentials exist.
    """

    raw = setting(
        YOUTUBE_CREDENTIALS_KEY,
        None,
    )

    if not raw:
        return None

    try:

        info = json.loads(raw)

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "بيانات YouTube OAuth المخزنة في قاعدة البيانات "
            "غير صالحة."
        ) from exc

    if not isinstance(info, dict):
        raise RuntimeError(
            "صيغة YouTube OAuth المخزنة غير صحيحة."
        )

    try:

        creds = Credentials.from_authorized_user_info(
            info,
            SCOPES,
        )

    except Exception as exc:

        raise RuntimeError(
            "تعذر تحميل YouTube OAuth من قاعدة البيانات: "
            f"{exc}"
        ) from exc

    return creds


# ============================================================
# FINISH AUTHORIZATION
# ============================================================

def finish_authorization(
    code,
    state,
    code_verifier,
):
    """
    Complete Google OAuth authorization.

    The credentials are stored in Neon/PostgreSQL through db.py
    when DATABASE_URL is configured.
    """

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
    # Create Flow using the exact verifier generated during
    # authorization_url().
    # --------------------------------------------------------

    flow = get_flow(
        code_verifier=code_verifier,
    )

    # --------------------------------------------------------
    # Exchange authorization code for credentials.
    # --------------------------------------------------------

    flow.fetch_token(
        code=code,
        include_client_id=True,
        code_verifier=code_verifier,
    )

    creds = flow.credentials

    if not creds:
        raise RuntimeError(
            "Google لم تُرجع Credentials."
        )

    # --------------------------------------------------------
    # Make sure we received a refresh token.
    #
    # Without a refresh token, the autonomous worker may not
    # be able to continue after the access token expires.
    # --------------------------------------------------------

    if not creds.refresh_token:

        raise RuntimeError(
            "Google لم تُرجع Refresh Token. "
            "أعد محاولة ربط YouTube مع prompt=consent."
        )

    # --------------------------------------------------------
    # Save credentials to Neon/SQLite through db.py.
    # --------------------------------------------------------

    save_credentials(
        creds
    )

    return creds


# ============================================================
# REFRESH CREDENTIALS
# ============================================================

def refresh_credentials(creds):
    """
    Refresh expired credentials.

    Returns:
        refreshed Credentials
    """

    if not creds:
        raise RuntimeError(
            "YouTube Credentials مفقودة."
        )

    if not creds.refresh_token:
        raise RuntimeError(
            "لا يوجد Refresh Token لتجديد YouTube OAuth."
        )

    from google.auth.transport.requests import Request

    try:

        creds.refresh(
            Request()
        )

    except Exception as exc:

        raise RuntimeError(
            "فشل تجديد YouTube OAuth. "
            "قد تحتاج إلى إعادة ربط الحساب من /auth. "
            f"التفاصيل: {exc}"
        ) from exc

    if not creds.valid:
        raise RuntimeError(
            "تم تجديد YouTube OAuth ولكن Credentials "
            "ما زالت غير صالحة."
        )

    save_credentials(
        creds
    )

    return creds


# ============================================================
# YOUTUBE SERVICE
# ============================================================

def service():
    """
    Create an authenticated YouTube API service.

    OAuth credentials are loaded from the database instead of
    relying on credentials/token.json.
    """

    creds = load_credentials()

    if not creds:

        raise RuntimeError(
            "YouTube غير مربوط بعد. "
            "افتح /auth لبدء ربط الحساب."
        )

    # --------------------------------------------------------
    # Refresh expired access token.
    # --------------------------------------------------------

    if not creds.valid:

        if (
            creds.expired
            and creds.refresh_token
        ):

            creds = refresh_credentials(
                creds
            )

        else:

            raise RuntimeError(
                "انتهت صلاحية YouTube OAuth "
                "ولا يوجد Refresh Token صالح. "
                "افتح /auth لإعادة الربط."
            )

    # --------------------------------------------------------
    # Build YouTube API service.
    # --------------------------------------------------------

    try:

        return build(
            "youtube",
            "v3",
            credentials=creds,
            cache_discovery=False,
        )

    except Exception as exc:

        raise RuntimeError(
            "تعذر إنشاء YouTube API service: "
            f"{exc}"
        ) from exc


# ============================================================
# CHECK VIDEO FILE
# ============================================================

def check_video_file(path):
    """
    Validate that the video file exists.
    """

    if not path:
        raise RuntimeError(
            "مسار الفيديو مفقود."
        )

    video_path = Path(path)

    if not video_path.exists():
        raise RuntimeError(
            f"ملف الفيديو غير موجود: {video_path}"
        )

    if not video_path.is_file():
        raise RuntimeError(
            f"مسار الفيديو ليس ملفًا: {video_path}"
        )

    if video_path.stat().st_size <= 0:
        raise RuntimeError(
            f"ملف الفيديو فارغ: {video_path}"
        )

    return video_path


# ============================================================
# UPLOAD PRIVATE
# ============================================================

def upload_private(
    path,
    title,
    description,
    thumbnail=None,
):
    """
    Upload a video as PRIVATE.

    Thumbnail upload is optional.

    If YouTube refuses the custom thumbnail because the account
    does not have thumbnail permissions, the video upload itself
    still succeeds.
    """

    # --------------------------------------------------------
    # Validate video.
    # --------------------------------------------------------

    video_path = check_video_file(
        path
    )

    # --------------------------------------------------------
    # YouTube service.
    # --------------------------------------------------------

    yt = service()

    # --------------------------------------------------------
    # Video metadata.
    # --------------------------------------------------------

    body = {
        "snippet": {
            "title": title or "YouTube AI Video",
            "description": description or "",
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "private",
        },
    }

    # --------------------------------------------------------
    # Video media.
    # --------------------------------------------------------

    media = MediaFileUpload(
        str(video_path),
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    # --------------------------------------------------------
    # Create upload request.
    # --------------------------------------------------------

    request = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    # --------------------------------------------------------
    # Resumable upload.
    # --------------------------------------------------------

    while response is None:

        status, response = (
            request.next_chunk()
        )

        if status:

            try:

                progress = int(
                    status.progress() * 100
                )

                print(
                    f"[YOUTUBE] Upload progress: {progress}%",
                    flush=True,
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # Validate response.
    # --------------------------------------------------------

    if not response:

        raise RuntimeError(
            "فشل رفع الفيديو إلى YouTube."
        )

    video_id = response.get(
        "id"
    )

    if not video_id:

        raise RuntimeError(
            "لم يتم الحصول على video_id من YouTube."
        )

    print(
        f"[YOUTUBE] Video uploaded privately: {video_id}",
        flush=True,
    )

    # --------------------------------------------------------
    # Optional thumbnail.
    #
    # IMPORTANT:
    # Thumbnail permission errors must NOT turn a successful
    # video upload into a failed job.
    # --------------------------------------------------------

    if thumbnail:

        thumbnail_path = Path(
            thumbnail
        )

        if thumbnail_path.exists() and thumbnail_path.is_file():

            try:

                yt.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(
                        str(thumbnail_path),
                        mimetype="image/jpeg",
                    ),
                ).execute()

                print(
                    f"[YOUTUBE] Thumbnail uploaded for {video_id}",
                    flush=True,
                )

            except Exception as exc:

                print(
                    "[YOUTUBE] Thumbnail upload skipped: "
                    f"{repr(exc)}",
                    flush=True,
                )

        else:

            print(
                "[YOUTUBE] Thumbnail file not found; "
                "continuing without thumbnail.",
                flush=True,
            )

    return video_id


# ============================================================
# PUBLISH
# ============================================================

def publish(
    video_id,
):
    """
    Change a previously uploaded video from private to public.
    """

    if not video_id:

        raise RuntimeError(
            "video_id مفقود."
        )

    yt = service()

    try:

        response = yt.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {
                    "privacyStatus": "public",
                },
            },
        ).execute()

    except Exception as exc:

        raise RuntimeError(
            "فشل نشر الفيديو على YouTube: "
            f"{exc}"
        ) from exc

    return response


# ============================================================
# PROCESSING STATUS
# ============================================================

def processing(
    video_id,
):
    """
    Return YouTube processing information for a video.
    """

    if not video_id:
        return {}

    yt = service()

    try:

        response = yt.videos().list(
            part="status,processingDetails",
            id=video_id,
        ).execute()

    except Exception as exc:

        raise RuntimeError(
            "فشل الحصول على حالة معالجة الفيديو: "
            f"{exc}"
        ) from exc

    items = response.get(
        "items",
        [],
    )

    if not items:
        return {}

    return items[0]


# ============================================================
# YOUTUBE CONNECTION STATUS
# ============================================================

def is_connected():
    """
    Return True if YouTube credentials exist in the database.
    """

    return setting(
        YOUTUBE_CREDENTIALS_KEY,
        None,
    ) is not None


# ============================================================
# GET CHANNEL INFORMATION
# ============================================================

def channel():
    """
    Return the authenticated YouTube channel information.

    Useful for verifying that the OAuth account is connected
    to a YouTube channel.
    """

    yt = service()

    try:

        response = yt.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True,
        ).execute()

    except Exception as exc:

        raise RuntimeError(
            "فشل الحصول على معلومات قناة YouTube: "
            f"{exc}"
        ) from exc

    items = response.get(
        "items",
        [],
    )

    if not items:

        raise RuntimeError(
            "تمت مصادقة Google لكن لم يتم العثور "
            "على قناة YouTube."
        )

    return items[0]
