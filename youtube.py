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

SECRET = Path("credentials/client_secret.json")
TOKEN = Path("credentials/token.json")


def get_flow():
    if not SECRET.exists():
        raise RuntimeError("ضع client_secret.json داخل credentials/")

    redirect_uri = os.getenv(
        "OAUTH_REDIRECT_URI",
        "http://localhost:8000/oauth2callback"
    )

    flow = Flow.from_client_secrets_file(
        str(SECRET),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def authorization_url():
    flow = get_flow()

    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return url, state


def finish_authorization(code, state):
    flow = get_flow()

    flow.fetch_token(code=code)

    creds = flow.credentials

    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")

    return creds


def service():
    if not TOKEN.exists():
        raise RuntimeError(
            "YouTube غير مربوط بعد. افتح /auth لبدء ربط حساب YouTube."
        )

    creds = Credentials.from_authorized_user_file(
        str(TOKEN),
        SCOPES
    )

    if not creds.valid:
        raise RuntimeError(
            "انتهت صلاحية YouTube OAuth. افتح /auth لإعادة الربط."
        )

    return build("youtube", "v3", credentials=creds)


def upload_private(path, title, description, thumbnail=None):
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

    req = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None

    while response is None:
        status, response = req.next_chunk()

    vid = response["id"]

    if thumbnail and Path(thumbnail).exists():
        yt.thumbnails().set(
            videoId=vid,
            media_body=MediaFileUpload(
                thumbnail,
                mimetype="image/jpeg"
            )
        ).execute()

    return vid


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

    r = yt.videos().list(
        part="status,processingDetails",
        id=video_id
    ).execute()

    return r.get("items", [{}])[0]
