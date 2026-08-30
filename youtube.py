import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

SECRET = Path("/etc/secrets/client_secret.json")
TOKEN = Path("credentials/token.json")
OAUTH_PENDING = Path("credentials/oauth_pending.json")

DEFAULT_REDIRECT_URI = (
    "https://youtube-ai-agent-yich.onrender.com/oauth2callback"
)


def get_redirect_uri():
    return os.getenv(
        "OAUTH_REDIRECT_URI",
        DEFAULT_REDIRECT_URI
    ).strip()


def get_flow(code_verifier=None):
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
        flow.oauth2session._client.code_verifier = code_verifier

    return flow


def authorization_url():
    flow = get_flow()

    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    code_verifier = flow.oauth2session._client.code_verifier

    if not code_verifier:
        raise RuntimeError(
            "تعذر إنشاء OAuth code_verifier."
        )

    # نحفظ بيانات OAuth على الخادم بدل الاعتماد
    # على Cookie الخاصة بالمتصفح.
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
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return url, state, code_verifier


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


def clear_pending():
    try:
        OAUTH_PENDING.unlink()
    except FileNotFoundError:
        pass


def finish_authorization(
    code,
    state,
    code_verifier=None
):
    if not code:
        raise RuntimeError(
            "لم يتم استلام authorization code من Google."
        )

    if not state:
        raise RuntimeError(
            "لم يتم استلام OAuth state من Google."
        )

    pending = load_pending()

    if pending:

        if state != pending["state"]:
            clear_pending()

            raise RuntimeError(
                "OAuth state غير صحيح. "
                "ابدأ الربط من /auth مرة أخرى."
            )

        code_verifier = pending["code_verifier"]

    if not code_verifier:
        raise RuntimeError(
            "OAuth code_verifier مفقود. "
            "ابدأ الربط من /auth مرة أخرى."
        )

    flow = get_flow(
        code_verifier=code_verifier
    )

    flow.fetch_token(
        code=code,
        include_client_id=True,
    )

    creds = flow.credentials

    TOKEN.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    TOKEN.write_text(
        creds.to_json(),
        encoding="utf-8"
    )

    clear_pending()

    return creds


def service():

    if not TOKEN.exists():
        raise RuntimeError(
            "YouTube غير مربوط بعد. "
            "افتح /auth لبدء ربط الحساب."
        )

    creds = Credentials.from_authorized_user_file(
        str(TOKEN),
        SCOPES
    )

    if not creds.valid:

        if creds.expired and creds.refresh_token:

            from google.auth.transport.requests import Request

            creds.refresh(
                Request()
            )

            TOKEN.write_text(
                creds.to_json(),
                encoding="utf-8"
            )

        else:
            raise RuntimeError(
                "انتهت صلاحية YouTube OAuth. "
                "افتح /auth لإعادة الربط."
            )

    return build(
        "youtube",
        "v3",
        credentials=creds
    )


def upload_private(
    path,
    title,
    description,
    thumbnail=None
):

    yt = service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "private"
        },
    }

    media = MediaFileUpload(
        path,
        chunksize=8 * 1024 * 1024,
        resumable=True
    )

    request = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None

    while response is None:

        status, response = request.next_chunk()

    video_id = response["id"]

    if thumbnail and Path(thumbnail).exists():

        yt.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(
                thumbnail,
                mimetype="image/jpeg"
            )
        ).execute()

    return video_id


def publish(video_id):

    yt = service()

    return yt.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": {
                "privacyStatus": "public"
            }
        }
    ).execute()


def processing(video_id):

    yt = service()

    response = yt.videos().list(
        part="status,processingDetails",
        id=video_id
    ).execute()

    items = response.get(
        "items",
        []
    )

    if not items:
        return {}

    return items[0]
