import os
import sqlite3
from pathlib import Path


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

SQLITE_DB = Path("data/agent.db")
SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATABASE TYPE
# ============================================================

USE_POSTGRES = bool(DATABASE_URL)


# ============================================================
# CONNECTION
# ============================================================

def conn():
    """
    Return a database connection.

    If DATABASE_URL exists:
        use Neon PostgreSQL.

    Otherwise:
        use local SQLite as a safe fallback.
    """

    if USE_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row

            connection = psycopg.connect(
                DATABASE_URL,
                row_factory=dict_row,
                connect_timeout=15,
            )

            return connection

        except Exception as exc:
            raise RuntimeError(
                "تعذر الاتصال بقاعدة بيانات Neon PostgreSQL: "
                f"{exc}"
            ) from exc

    connection = sqlite3.connect(
        SQLITE_DB,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# DATABASE PLACEHOLDER
# ============================================================

def placeholder():
    """
    PostgreSQL uses %s.
    SQLite uses ?.
    """

    return "%s" if USE_POSTGRES else "?"


# ============================================================
# INIT DATABASE
# ============================================================

def init():
    """
    Create all required tables if they do not exist.
    """

    if USE_POSTGRES:

        with conn() as c:

            c.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            c.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id BIGSERIAL PRIMARY KEY,
                    topic TEXT UNIQUE NOT NULL,
                    language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    script TEXT,
                    video_path TEXT,
                    thumbnail_path TEXT,
                    youtube_id TEXT,
                    sources TEXT,
                    error TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMPTZ
                )
                """
            )

            c.commit()

        return

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    with conn() as c:

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE NOT NULL,
                language TEXT NOT NULL,
                status TEXT NOT NULL,
                title TEXT,
                description TEXT,
                script TEXT,
                video_path TEXT,
                thumbnail_path TEXT,
                youtube_id TEXT,
                sources TEXT,
                error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                published_at DATETIME
            )
            """
        )

        c.commit()


# ============================================================
# SETTINGS
# ============================================================

def setting(k, default=None):
    """
    Get a setting value.
    """

    ph = placeholder()

    with conn() as c:

        row = c.execute(
            f"SELECT value FROM settings WHERE key={ph}",
            (k,),
        ).fetchone()

        if not row:
            return default

        return row["value"]


# ============================================================
# SET SETTING
# ============================================================

def set_setting(k, v):
    """
    Insert or update a setting.
    """

    if USE_POSTGRES:

        with conn() as c:

            c.execute(
                """
                INSERT INTO settings(key, value)
                VALUES (%s, %s)
                ON CONFLICT(key)
                DO UPDATE SET value = EXCLUDED.value
                """,
                (k, str(v)),
            )

            c.commit()

        return

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    with conn() as c:

        c.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            (k, str(v)),
        )

        c.commit()


# ============================================================
# ADD JOB
# ============================================================

def add_job(topic, language):
    """
    Add a new queued job.

    Returns:
        job id

    Returns None if the topic already exists.
    """

    if USE_POSTGRES:

        with conn() as c:

            row = c.execute(
                """
                INSERT INTO jobs(
                    topic,
                    language,
                    status
                )
                VALUES (%s, %s, %s)
                ON CONFLICT(topic)
                DO NOTHING
                RETURNING id
                """,
                (
                    topic,
                    language,
                    "queued",
                ),
            ).fetchone()

            c.commit()

            if not row:
                return None

            return row["id"]

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    try:

        with conn() as c:

            row = c.execute(
                """
                INSERT INTO jobs(
                    topic,
                    language,
                    status
                )
                VALUES (?, ?, ?)
                """,
                (
                    topic,
                    language,
                    "queued",
                ),
            )

            c.commit()

            return row.lastrowid

    except sqlite3.IntegrityError:
        return None


# ============================================================
# UPDATE JOB
# ============================================================

def update_job(i, **kw):
    """
    Update allowed job fields.
    """

    allowed = {
        "status",
        "title",
        "description",
        "script",
        "video_path",
        "thumbnail_path",
        "youtube_id",
        "sources",
        "error",
        "published_at",
    }

    kw = {
        key: value
        for key, value in kw.items()
        if key in allowed
    }

    if not kw:
        return

    if USE_POSTGRES:

        assignments = ", ".join(
            f"{key} = %s"
            for key in kw
        )

        values = list(kw.values())
        values.append(i)

        with conn() as c:

            c.execute(
                f"""
                UPDATE jobs
                SET {assignments}
                WHERE id = %s
                """,
                tuple(values),
            )

            c.commit()

        return

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    assignments = ", ".join(
        f"{key} = ?"
        for key in kw
    )

    values = list(kw.values())
    values.append(i)

    with conn() as c:

        c.execute(
            f"""
            UPDATE jobs
            SET {assignments}
            WHERE id = ?
            """,
            tuple(values),
        )

        c.commit()


# ============================================================
# GET JOB
# ============================================================

def get_job(i):
    """
    Return one job as a dictionary.
    """

    ph = placeholder()

    with conn() as c:

        row = c.execute(
            f"""
            SELECT *
            FROM jobs
            WHERE id = {ph}
            """,
            (i,),
        ).fetchone()

        if not row:
            return None

        return dict(row)


# ============================================================
# ALL JOBS
# ============================================================

def jobs(limit=100):
    """
    Return latest jobs.
    """

    ph = placeholder()

    with conn() as c:

        rows = c.execute(
            f"""
            SELECT *
            FROM jobs
            ORDER BY id DESC
            LIMIT {ph}
            """,
            (limit,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


# ============================================================
# RECENT TOPICS
# ============================================================

def recent_topics(limit=30):
    """
    Return recent job topics.
    """

    ph = placeholder()

    with conn() as c:

        rows = c.execute(
            f"""
            SELECT topic
            FROM jobs
            ORDER BY id DESC
            LIMIT {ph}
            """,
            (limit,),
        ).fetchall()

        return [
            row["topic"]
            for row in rows
        ]


# ============================================================
# JOBS TODAY
# ============================================================

def jobs_today():
    """
    Count jobs created today.

    PostgreSQL:
        CURRENT_DATE

    SQLite:
        date('now')
    """

    with conn() as c:

        if USE_POSTGRES:

            row = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM jobs
                WHERE created_at::date = CURRENT_DATE
                """
            ).fetchone()

        else:

            row = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM jobs
                WHERE date(created_at) = date('now')
                """
            ).fetchone()

        return row["n"]
