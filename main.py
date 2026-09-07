import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import edge_tts


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1920
HEIGHT = 1080
FPS = 30

# Target only. Actual duration follows the generated narration.
TARGET_VIDEO_DURATION = 600.0

DEFAULT_BG = (10, 16, 30)
ACCENT = (55, 130, 255)
TEXT_COLOR = (255, 255, 255)
MUTED = (205, 215, 230)

BRAND_NAME = "نبض المستقبل | Future Pulse 🚀"
WATERMARK_TEXT = BRAND_NAME

WATERMARK_FONT_SIZE = 28
WATERMARK_ALPHA = 165
WATERMARK_MARGIN = 42

MAX_SCENES = 60
MIN_SCENE_DURATION = 5.0
MAX_SCENE_DURATION = 18.0

MOTION_ZOOM = 0.065

# Safety timeouts.
TTS_TIMEOUT = int(os.getenv("TTS_TIMEOUT", "180"))

# Number of automatic Edge TTS retries.
TTS_RETRIES = int(os.getenv("TTS_RETRIES", "3"))

FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "900"))
FFPROBE_TIMEOUT = int(os.getenv("FFPROBE_TIMEOUT", "60"))

VIDEO_PRESET = os.getenv(
    "VIDEO_PRESET",
    "veryfast"
)

VIDEO_CRF = os.getenv(
    "VIDEO_CRF",
    "21"
)


# ============================================================
# LOGGING
# ============================================================

def log(message):
    print(
        f"[MEDIA] {message}",
        flush=True
    )


# ============================================================
# COMMAND EXECUTION
# ============================================================

def run_command(
    cmd,
    timeout=None,
    description="command"
):
    if timeout is None:
        timeout = FFMPEG_TIMEOUT

    log(
        f"Running {description}..."
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{description} timed out after "
            f"{timeout} seconds."
        ) from exc

    if result.returncode != 0:
        stderr = (
            result.stderr
            or result.stdout
            or "Unknown command error."
        )

        stderr = stderr[-6000:]

        raise RuntimeError(
            f"{description} failed "
            f"(exit code {result.returncode}):\n"
            f"{stderr}"
        )

    return result


# ============================================================
# FONT
# ============================================================

def get_font(size, bold=False):
    candidates = []

    if bold:
        candidates += [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]

    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(
                    path,
                    size
                )
            except Exception:
                pass

    return ImageFont.load_default()


# ============================================================
# TEXT
# ============================================================

def clean_text(text):
    text = str(text or "")

    text = re.sub(
        r"https?://\S+",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def wrap(text, width=42):
    text = clean_text(text)

    if not text:
        return ""

    words = text.split()

    lines = []
    current = ""

    for word in words:
        candidate = (
            f"{current} {word}".strip()
        )

        if (
            len(candidate) > width
            and current
        ):
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    return "\n".join(lines)


def fit_text(
    draw,
    text,
    max_width,
    max_height,
    start_size,
    bold=False,
):
    text = clean_text(text)

    if not text:
        return (
            "",
            get_font(
                start_size,
                bold
            )
        )

    size = start_size

    while size >= 24:
        font = get_font(
            size,
            bold
        )

        wrapped = wrap(
            text,
            max(
                12,
                int(
                    max_width
                    / max(1, size * 0.55)
                )
            )
        )

        bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=font,
            spacing=int(size * 0.25),
            align="center",
        )

        width = (
            bbox[2] - bbox[0]
        )

        height = (
            bbox[3] - bbox[1]
        )

        if (
            width <= max_width
            and height <= max_height
        ):
            return (
                wrapped,
                font
            )

        size -= 2

    return (
        wrap(text, 24),
        get_font(24, bold)
    )


# ============================================================
# LANGUAGE
# ============================================================

def detect_language(text):
    configured = os.getenv(
        "DEFAULT_LANGUAGE",
        "ar"
    ).strip().lower()

    return configured or "ar"


# ============================================================
# HASHTAGS
# ============================================================

def generate_hashtags(
    title,
    script,
    language="ar"
):
    text = clean_text(
        f"{title} {script}"
    )

    if not text:
        return "#FuturePulse"

    words = re.findall(
        r"[\w\u0600-\u06FF]+",
        text,
        flags=re.UNICODE
    )

    stopwords_ar = {
        "من", "في", "على", "إلى", "عن",
        "مع", "هذا", "هذه", "ذلك", "التي",
        "الذي", "هو", "هي", "و", "أو",
        "أن", "إن", "كان", "كانت", "ما",
        "ماذا", "كيف", "لماذا", "لقد",
        "قد", "بعد", "قبل", "بين",
        "هناك", "كل", "أي", "كما",
        "ثم", "لكن", "عندما", "حتى",
        "لذلك", "فقط",
    }

    stopwords_en = {
        "the", "and", "or", "of", "to",
        "in", "on", "for", "with", "this",
        "that", "from", "how", "why",
        "what", "when", "where", "is",
        "are", "was", "were", "a", "an",
    }

    stopwords = (
        stopwords_ar
        if language.startswith("ar")
        else stopwords_en
    )

    unique = []

    for word in words:
        word = word.strip()

        if len(word) < 3:
            continue

        if word.lower() in stopwords:
            continue

        if word not in unique:
            unique.append(word)

        if len(unique) >= 6:
            break

    tags = []

    for word in unique:
        word = re.sub(
            r"[^\w\u0600-\u06FF]",
            "",
            word,
            flags=re.UNICODE
        )

        if word:
            tags.append(
                f"#{word}"
            )

    tags.append(
        "#FuturePulse"
    )

    if language.startswith("ar"):
        tags.append(
            "#نبض_المستقبل"
        )

    result = []

    for tag in tags:
        if tag not in result:
            result.append(tag)

    return " ".join(
        result[:8]
    )


# ============================================================
# BACKGROUND
# ============================================================

def make_background(index):
    palettes = [
        ((8, 18, 42), (25, 75, 145)),
        ((8, 30, 25), (20, 110, 90)),
        ((35, 12, 50), (105, 35, 135)),
        ((48, 25, 8), (145, 75, 25)),
        ((5, 35, 48), (15, 115, 135)),
        ((45, 10, 25), (125, 35, 70)),
        ((15, 18, 48), (70, 55, 150)),
        ((20, 40, 10), (80, 120, 35)),
    ]

    c1, c2 = palettes[
        index % len(palettes)
    ]

    small = Image.new(
        "RGB",
        (1, HEIGHT),
        c1
    )

    pixels = small.load()

    for y in range(HEIGHT):
        ratio = (
            y / max(
                1,
                HEIGHT - 1
            )
        )

        pixels[0, y] = (
            int(
                c1[0] * (1 - ratio)
                + c2[0] * ratio
            ),
            int(
                c1[1] * (1 - ratio)
                + c2[1] * ratio
            ),
            int(
                c1[2] * (1 - ratio)
                + c2[2] * ratio
            ),
        )

    image = small.resize(
        (WIDTH, HEIGHT)
    )

    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        overlay
    )

    positions = [
        (
            260 + (index * 83) % 500,
            170,
            300,
            (70, 150, 255, 40),
        ),
        (
            1500 - (index * 61) % 400,
            250,
            360,
            (150, 80, 255, 35),
        ),
        (
            950,
            900,
            420,
            (50, 200, 180, 28),
        ),
    ]

    for x, y, radius, color in positions:
        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius,
            ),
            fill=color
        )

    for n in range(10):
        x = (
            100
            + (
                (
                    index * 137
                    + n * 277
                )
                % (WIDTH - 200)
            )
        )

        y = (
            80
            + (
                (
                    index * 71
                    + n * 149
                )
                % (HEIGHT - 160)
            )
        )

        radius = 2 + (n % 4)

        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius,
            ),
            fill=(255, 255, 255, 45)
        )

    overlay = overlay.filter(
        ImageFilter.GaussianBlur(55)
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    )

    return image.convert("RGB")


# ============================================================
# WATERMARK
# ============================================================

def add_watermark(
    image,
    text=WATERMARK_TEXT
):
    image = image.convert(
        "RGBA"
    )

    overlay = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        overlay
    )

    font = get_font(
        WATERMARK_FONT_SIZE,
        bold=False
    )

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = (
        bbox[2] - bbox[0]
    )

    text_height = (
        bbox[3] - bbox[1]
    )

    x = (
        WIDTH
        - text_width
        - WATERMARK_MARGIN
    )

    y = (
        HEIGHT
        - text_height
        - WATERMARK_MARGIN
    )

    draw.rounded_rectangle(
        (
            x - 16,
            y - 10,
            x + text_width + 16,
            y + text_height + 10,
        ),
        radius=15,
        fill=(0, 0, 0, 95)
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=(
            255,
            255,
            255,
            WATERMARK_ALPHA
        )
    )

    return Image.alpha_composite(
        image,
        overlay
    ).convert("RGB")


# ============================================================
# SCENE CARD
# ============================================================

def draw_card(
    title,
    subtitle,
    index,
    total
):
    image = make_background(
        index
    )

    overlay = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        overlay
    )

    left = 110
    top = 100
    right = WIDTH - 110
    bottom = HEIGHT - 105

    draw.rounded_rectangle(
        (
            left,
            top,
            right,
            bottom,
        ),
        radius=45,
        fill=(0, 0, 0, 125),
        outline=(255, 255, 255, 45),
        width=2,
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")

    draw = ImageDraw.Draw(
        image
    )

    badge_font = get_font(
        27,
        bold=True
    )

    badge_text = (
        f"المشهد {index + 1} / {total}"
    )

    badge_bbox = draw.textbbox(
        (0, 0),
        badge_text,
        font=badge_font
    )

    badge_width = (
        badge_bbox[2]
        - badge_bbox[0]
        + 55
    )

    badge_height = 58

    badge_x = (
        WIDTH
        - 150
        - badge_width
    )

    badge_y = 145

    draw.rounded_rectangle(
        (
            badge_x,
            badge_y,
            badge_x + badge_width,
            badge_y + badge_height,
        ),
        radius=29,
        fill=ACCENT
    )

    draw.text(
        (
            badge_x + badge_width / 2,
            badge_y + badge_height / 2,
        ),
        badge_text,
        font=badge_font,
        fill=TEXT_COLOR,
        anchor="mm"
    )

    title_text, title_font = fit_text(
        draw,
        clean_text(title),
        max_width=WIDTH - 360,
        max_height=300,
        start_size=72,
        bold=True,
    )

    draw.multiline_text(
        (
            WIDTH // 2,
            310
        ),
        title_text,
        font=title_font,
        fill=TEXT_COLOR,
        spacing=22,
        align="center",
        anchor="mm"
    )

    subtitle_text, subtitle_font = fit_text(
        draw,
        clean_text(subtitle),
        max_width=WIDTH - 420,
        max_height=250,
        start_size=38,
        bold=False,
    )

    draw.multiline_text(
        (
            WIDTH // 2,
            620
        ),
        subtitle_text,
        font=subtitle_font,
        fill=MUTED,
        spacing=15,
        align="center",
        anchor="mm"
    )

    line_y = HEIGHT - 180
    line_left = 180
    line_right = WIDTH - 180

    draw.rounded_rectangle(
        (
            line_left,
            line_y,
            line_right,
            line_y + 10,
        ),
        radius=5,
        fill=(255, 255, 255, 55)
    )

    progress = (
        (index + 1)
        / max(1, total)
    )

    progress_right = int(
        line_left
        + (
            line_right - line_left
        ) * progress
    )

    draw.rounded_rectangle(
        (
            line_left,
            line_y,
            progress_right,
            line_y + 10,
        ),
        radius=5,
        fill=ACCENT
    )

    return add_watermark(
        image
)
    # ============================================================
# CREATE JOB
# ============================================================

@app.post("/create")
def create(
    topic: str = Form(...),
):

    print(
        f"[CREATE] Request received. Topic: {topic}",
        flush=True
    )

    jid = add_job(
        topic,
        os.getenv(
            "DEFAULT_LANGUAGE",
            "ar"
        ),
    )

    if not jid:

        print(
            "[CREATE] Job was not created "
            "(possibly duplicate topic)",
            flush=True
        )

        return RedirectResponse(
            "/",
            status_code=303,
        )

    print(
        f"[CREATE] Created job {jid}",
        flush=True
    )

    # مهم:
    # لا نستخدم FastAPI BackgroundTasks هنا.
    # نشغل العامل في Thread مباشر مثل Autopilot.
    thread = threading.Thread(
        target=run_job,
        args=(jid,),
        daemon=True,
        name=f"youtube-worker-{jid}",
    )

    thread.start()

    print(
        f"[CREATE] Started worker thread for job {jid}",
        flush=True
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

    print(
        "[AUTOPILOT] Enabled from Dashboard",
        flush=True
    )

    # تشغيل أول عملية فورًا بدل الانتظار ساعة
    threading.Thread(
        target=autopilot_once,
        daemon=True,
        name="autopilot-now",
    ).start()

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
