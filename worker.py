import os
import json
import traceback
import threading
import time
from pathlib import Path

from db import *
from discovery import discover, source_text
from ai import choose, make_content
from media import make_video
from youtube import upload_private, publish


# ============================================================
# HELPERS
# ============================================================

def log(message):
    print(f"[WORKER] {message}", flush=True)


def safe_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


# ============================================================
# CREATE VIDEO JOB
# ============================================================

def run_job(job_id):

    log(f"Starting job {job_id}")

    try:

        j = get_job(job_id)

        if not j:
            raise RuntimeError(
                f"Job {job_id} غير موجود في قاعدة البيانات."
            )

        # ----------------------------------------------------
        # RESEARCH
        # ----------------------------------------------------

        update_job(
            job_id,
            status="researching",
            error=""
        )

        log(f"Job {job_id}: starting research")

        items = discover()

        log(
            f"Job {job_id}: discovered "
            f"{len(items)} sources"
        )

        if not items:
            raise RuntimeError(
                "لم يتم العثور على مصادر حديثة."
            )

        # ----------------------------------------------------
        # CHOOSE TOPIC
        # ----------------------------------------------------

        log(f"Job {job_id}: selecting topic")

        pick = choose(
            items,
            recent_topics(30)
        )

        if not pick or not pick.get("topic"):
            raise RuntimeError(
                "تعذر اختيار موضوع للفيديو."
            )

        topic = pick["topic"]

        log(
            f"Job {job_id}: selected topic: {topic}"
        )

        # ----------------------------------------------------
        # FETCH SOURCES
        # ----------------------------------------------------

        sources = []

        max_sources = safe_int(
            "MAX_SOURCE_FETCH",
            4
        )

        log(
            f"Job {job_id}: fetching "
            f"up to {max_sources} sources"
        )

        for index, x in enumerate(
            items[:max_sources],
            start=1
        ):

            link = x.get("link", "")

            if not link:
                continue

            log(
                f"Job {job_id}: source "
                f"{index}/{max_sources}"
            )

            started = time.time()

            try:

                txt = source_text(link)

                elapsed = round(
                    time.time() - started,
                    2
                )

                if txt:

                    sources.append(
                        {
                            "title": x.get(
                                "title",
                                ""
                            ),
                            "url": link,
                            "text": txt[:2500],
                        }
                    )

                    log(
                        f"Job {job_id}: source "
                        f"{index} OK "
                        f"({elapsed}s)"
                    )

                else:

                    log(
                        f"Job {job_id}: source "
                        f"{index} empty "
                        f"({elapsed}s)"
                    )

            except Exception as source_error:

                log(
                    f"Job {job_id}: source "
                    f"{index} failed: "
                    f"{repr(source_error)}"
                )

            # لا نسمح لمصدر واحد بإيقاف العملية
            continue

        # ----------------------------------------------------
        # FALLBACK TO RSS SUMMARIES
        # ----------------------------------------------------

        minimum_sources = safe_int(
            "MIN_SOURCE_COUNT",
            2
        )

        if len(sources) < minimum_sources:

            log(
                f"Job {job_id}: only "
                f"{len(sources)} full sources. "
                f"Using RSS summaries."
            )

            sources = []

            for x in items[:4]:

                summary = x.get(
                    "summary",
                    ""
                )

                if summary:

                    sources.append(
                        {
                            "title": x.get(
                                "title",
                                ""
                            ),
                            "url": x.get(
                                "link",
                                ""
                            ),
                            "text": summary[:2500],
                        }
                    )

        if not sources:
            raise RuntimeError(
                "تعذر الحصول على أي محتوى من المصادر."
            )

        log(
            f"Job {job_id}: using "
            f"{len(sources)} sources"
        )

        # ----------------------------------------------------
        # WRITING
        # ----------------------------------------------------

        update_job(
            job_id,
            status="writing"
        )

        log(
            f"Job {job_id}: starting AI writing"
        )

        c = make_content(
            topic,
            sources,
            j["language"]
        )

        if not c:
            raise RuntimeError(
                "لم يتم إنشاء محتوى الفيديو."
            )

        title = c.get("title", topic)

        script = c.get("script", "")

        scenes = c.get("scenes", [])

        description = c.get(
            "description",
            ""
        )

        if not script:
            raise RuntimeError(
                "النص الناتج للفيديو فارغ."
            )

        log(
            f"Job {job_id}: AI content ready"
        )

        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        update_job(
            job_id,
            status="generating"
        )

        log(
            f"Job {job_id}: generating video"
        )

        out = (
            Path("data/output")
            / str(job_id)
        )

        out.mkdir(
            parents=True,
            exist_ok=True
        )

        video, thumb = make_video(
            title,
            script,
            scenes,
            out,
            os.getenv(
                "VOICE",
                "ar-SA-HamedNeural"
            )
        )

        if not video:
            raise RuntimeError(
                "لم يتم إنشاء ملف الفيديو."
            )

        log(
            f"Job {job_id}: video generated"
        )

        # ----------------------------------------------------
        # READY
        # ----------------------------------------------------

        update_job(
            job_id,
            title=title,
            description=description,
            script=script,
            video_path=str(video),
            thumbnail_path=str(thumb)
            if thumb else "",
            sources=json.dumps(
                sources,
                ensure_ascii=False
            ),
            status="ready",
            error=""
        )

        log(
            f"Job {job_id}: READY"
        )

        return True

    except Exception as e:

        error_text = str(e)

        log(
            f"Job {job_id}: ERROR "
            f"{error_text}"
        )

        traceback.print_exc()

        try:

            update_job(
                job_id,
                status="error",
                error=error_text
            )

        except Exception:

            traceback.print_exc()

        return False


# ============================================================
# UPLOAD PRIVATE
# ============================================================

def upload_job(job_id):

    log(
        f"Uploading job {job_id} as PRIVATE"
    )

    try:

        j = get_job(job_id)

        if not j:
            raise RuntimeError(
                f"Job {job_id} غير موجود."
            )

        vid = upload_private(
            j["video_path"],
            j["title"],
            j["description"],
            j["thumbnail_path"]
        )

        update_job(
            job_id,
            youtube_id=vid,
            status="uploaded_private",
            error=""
        )

        log(
            f"Job {job_id}: uploaded "
            f"video {vid}"
        )

        return vid

    except Exception as e:

        log(
            f"Upload ERROR job {job_id}: "
            f"{repr(e)}"
        )

        traceback.print_exc()

        try:

            update_job(
                job_id,
                status="error",
                error=str(e)
            )

        except Exception:

            traceback.print_exc()

        raise


# ============================================================
# PUBLISH PUBLIC
# ============================================================

def publish_job(job_id):

    log(
        f"Publishing job {job_id}"
    )

    try:

        j = get_job(job_id)

        if not j:
            raise RuntimeError(
                f"Job {job_id} غير موجود."
            )

        if not j["youtube_id"]:
            raise RuntimeError(
                "لا يوجد YouTube video ID."
            )

        publish(
            j["youtube_id"]
        )

        from datetime import datetime, timezone

        update_job(
            job_id,
            status="published",
            published_at=datetime.now(
                timezone.utc
            ).isoformat(),
            error=""
        )

        log(
            f"Job {job_id}: PUBLISHED"
        )

    except Exception as e:

        log(
            f"Publish ERROR job {job_id}: "
            f"{repr(e)}"
        )

        traceback.print_exc()

        try:

            update_job(
                job_id,
                status="error",
                error=str(e)
            )

        except Exception:

            traceback.print_exc()

        raise


# ============================================================
# AUTOPILOT
# ============================================================

def autopilot_once():

    if (
        os.getenv(
            "AUTOPILOT",
            "false"
        ).lower()
        != "true"
    ):
        return None

    limit = safe_int(
        "DAILY_JOB_LIMIT",
        2
    )

    if jobs_today() >= limit:

        log(
            "Autopilot: daily limit reached"
        )

        return None

    log(
        "Autopilot: discovering sources"
    )

    try:

        items = discover()

        if not items:

            log(
                "Autopilot: no sources"
            )

            return None

        pick = choose(
            items,
            recent_topics(30)
        )

        if not pick or not pick.get("topic"):

            log(
                "Autopilot: no topic selected"
            )

            return None

        jid = add_job(
            pick["topic"],
            os.getenv(
                "DEFAULT_LANGUAGE",
                "ar"
            )
        )

        if jid:

            log(
                f"Autopilot: created job {jid}"
            )

            threading.Thread(
                target=run_job,
                args=(jid,),
                daemon=True
            ).start()

        return jid

    except Exception as e:

        log(
            f"Autopilot ERROR: {repr(e)}"
        )

        traceback.print_exc()

        return None
