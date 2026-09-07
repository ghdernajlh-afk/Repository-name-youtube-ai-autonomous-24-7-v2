import asyncio
import html
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# CONFIG
# ============================================================

WIDTH = int(os.getenv("VIDEO_WIDTH", "1920"))
HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1080"))
FPS = int(os.getenv("VIDEO_FPS", "30"))

DEFAULT_VOICE = os.getenv(
    "VOICE",
    "ar-SA-HamedNeural"
)

FONT_SIZE_TITLE = int(
    os.getenv("FONT_SIZE_TITLE", "72")
)

FONT_SIZE_TEXT = int(
    os.getenv("FONT_SIZE_TEXT", "48")
)

SCENE_MIN_DURATION = float(
    os.getenv("SCENE_MIN_DURATION", "4")
)

SCENE_MAX_DURATION = float(
    os.getenv("SCENE_MAX_DURATION", "12")
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
# HELPERS
# ============================================================

def find_ffmpeg():
    """
    البحث عن ffmpeg.
    """

    candidates = [
        shutil.which("ffmpeg"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]

    for candidate in candidates:

        if candidate and Path(candidate).exists():

            return candidate

    return None


def find_ffprobe():
    """
    البحث عن ffprobe.
    """

    candidates = [
        shutil.which("ffprobe"),
        "/usr/bin/ffprobe",
        "/usr/local/bin/ffprobe",
    ]

    for candidate in candidates:

        if candidate and Path(candidate).exists():

            return candidate

    return None


def require_ffmpeg():

    ffmpeg = find_ffmpeg()

    if not ffmpeg:

        raise RuntimeError(
            "FFmpeg غير موجود في بيئة التشغيل."
        )

    return ffmpeg


def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = html.unescape(value)

    value = re.sub(
        r"<[^>]+>",
        "",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def safe_filename(name):

    name = clean_text(name)

    name = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        name
    )

    name = name.strip()

    if not name:
        name = "file"

    return name[:120]


def run_command(command, timeout=None):

    log(
        "Running command: "
        + " ".join(
            str(x) for x in command
        )
    )

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )

    if process.returncode != 0:

        error = (
            process.stderr[-4000:]
            if process.stderr
            else "Unknown FFmpeg error"
        )

        raise RuntimeError(
            f"Command failed:\n{error}"
        )

    return process


# ============================================================
# FONTS
# ============================================================

def find_font():

    env_font = os.getenv(
        "VIDEO_FONT",
        ""
    ).strip()

    if env_font:

        path = Path(env_font)

        if path.exists():

            return str(path)

    candidates = [

        # Linux / Render
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",

        # Arabic fonts if available
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",

        # Local project fonts
        "fonts/DejaVuSans.ttf",
        "fonts/NotoSansArabic-Regular.ttf",
        "fonts/NotoNaskhArabic-Regular.ttf",
    ]

    for font in candidates:

        if Path(font).exists():

            return font

    return None


def get_font(size):

    font_path = find_font()

    if font_path:

        try:

            return ImageFont.truetype(
                font_path,
                size
            )

        except Exception:

            pass

    return ImageFont.load_default()


# ============================================================
# ARABIC / RTL HELPERS
# ============================================================

def prepare_rtl_text(text):

    text = clean_text(text)

    if not text:
        return ""

    try:

        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = arabic_reshaper.reshape(
            text
        )

        return get_display(
            reshaped
        )

    except Exception:

        # المشروع يعمل حتى بدون المكتبات الإضافية
        return text


# ============================================================
# TEXT WRAPPING
# ============================================================

def wrap_text(
    draw,
    text,
    font,
    max_width
):

    text = clean_text(text)

    if not text:

        return []

    words = text.split()

    lines = []

    current = ""

    for word in words:

        candidate = (
            word
            if not current
            else current + " " + word
        )

        bbox = draw.textbbox(
            (0, 0),
            candidate,
            font=font
        )

        width = bbox[2] - bbox[0]

        if width <= max_width:

            current = candidate

        else:

            if current:

                lines.append(
                    current
                )

            current = word

    if current:

        lines.append(
            current
        )

    return lines


# ============================================================
# BACKGROUND
# ============================================================

def create_gradient_background(
    width,
    height,
    index=0
):

    image = Image.new(
        "RGB",
        (width, height),
        (12, 18, 32)
    )

    pixels = image.load()

    palettes = [

        (
            (11, 20, 40),
            (34, 90, 150),
        ),

        (
            (28, 12, 45),
            (80, 35, 110),
        ),

        (
            (8, 40, 45),
            (25, 105, 100),
        ),

        (
            (35, 18, 15),
            (120, 60, 25),
        ),

        (
            (15, 20, 30),
            (70, 75, 100),
        ),
    ]

    top, bottom = palettes[
        index % len(palettes)
    ]

    for y in range(height):

        ratio = y / max(
            height - 1,
            1
        )

        r = int(
            top[0]
            + (
                bottom[0]
                - top[0]
            )
            * ratio
        )

        g = int(
            top[1]
            + (
                bottom[1]
                - top[1]
            )
            * ratio
        )

        b = int(
            top[2]
            + (
                bottom[2]
                - top[2]
            )
            * ratio
        )

        for x in range(width):

            pixels[x, y] = (
                r,
                g,
                b,
            )

    return image


# ============================================================
# DRAW CARD
# ============================================================

def draw_card(
    title,
    text,
    output_path,
    index=0,
    is_thumbnail=False,
):

    width = WIDTH
    height = HEIGHT

    image = create_gradient_background(
        width,
        height,
        index
    )

    draw = ImageDraw.Draw(
        image
    )

    # --------------------------------------------------------
    # DARK OVERLAY
    # --------------------------------------------------------

    overlay = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )

    overlay_draw = ImageDraw.Draw(
        overlay
    )

    overlay_draw.rectangle(
        (
            0,
            0,
            width,
            height,
        ),
        fill=(
            0,
            0,
            0,
            70,
        ),
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(
        image
    )

    # --------------------------------------------------------
    # TOP LABEL
    # --------------------------------------------------------

    label = "FUTURE PULSE"

    label_font = get_font(
        28
    )

    draw.rounded_rectangle(
        (
            60,
            55,
            380,
            110,
        ),
        radius=18,
        fill=(
            0,
            0,
            0,
            150,
        ),
    )

    draw.text(
        (
            90,
            70,
        ),
        label,
        font=label_font,
        fill=(
            255,
            255,
            255,
        ),
    )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title_font = get_font(
        FONT_SIZE_TITLE
        if is_thumbnail
        else max(
            48,
            int(FONT_SIZE_TITLE * 0.75)
        )
    )

    body_font = get_font(
        FONT_SIZE_TEXT
    )

    max_text_width = int(
        width * 0.82
    )

    title = prepare_rtl_text(
        title
    )

    body = prepare_rtl_text(
        text
    )

    title_lines = wrap_text(
        draw,
        title,
        title_font,
        max_text_width
    )

    body_lines = wrap_text(
        draw,
        body,
        body_font,
        max_text_width
    )

    if is_thumbnail:

        title_lines = title_lines[:4]

        body_lines = []

    else:

        title_lines = title_lines[:3]

        body_lines = body_lines[:5]

    # --------------------------------------------------------
    # CALCULATE HEIGHT
    # --------------------------------------------------------

    title_line_height = int(
        title_font.size * 1.35
    )

    body_line_height = int(
        body_font.size * 1.45
    )

    title_height = (
        len(title_lines)
        * title_line_height
    )

    body_height = (
        len(body_lines)
        * body_line_height
    )

    total_height = (
        title_height
        + body_height
        + 80
    )

    start_y = max(
        150,
        int(
            (
                height
                - total_height
            )
            / 2
        ),
    )

    # --------------------------------------------------------
    # TEXT SHADOW
    # --------------------------------------------------------

    def draw_centered_line(
        line,
        y,
        font,
        color,
        shadow=True,
    ):

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        line_width = (
            bbox[2]
            - bbox[0]
        )

        x = (
            width
            - line_width
        ) // 2

        if shadow:

            draw.text(
                (
                    x + 3,
                    y + 4,
                ),
                line,
                font=font,
                fill=(
                    0,
                    0,
                    0,
                    190,
                ),
            )

        draw.text(
            (
                x,
                y,
            ),
            line,
            font=font,
            fill=color,
        )

    # --------------------------------------------------------
    # DRAW TITLE
    # --------------------------------------------------------

    current_y = start_y

    for line in title_lines:

        draw_centered_line(
            line,
            current_y,
            title_font,
            (
                255,
                255,
                255,
            ),
        )

        current_y += (
            title_line_height
        )

    current_y += 35

    # --------------------------------------------------------
    # DRAW BODY
    # --------------------------------------------------------

    for line in body_lines:

        draw_centered_line(
            line,
            current_y,
            body_font,
            (
                225,
                230,
                240,
            ),
        )

        current_y += (
            body_line_height
        )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    footer = "نبض المستقبل"

    footer_font = get_font(
        30
    )

    footer_rtl = prepare_rtl_text(
        footer
    )

    bbox = draw.textbbox(
        (0, 0),
        footer_rtl,
        font=footer_font
    )

    footer_width = (
        bbox[2]
        - bbox[0]
    )

    draw.text(
        (
            (
                width
                - footer_width
            )
            // 2,
            height - 80,
        ),
        footer_rtl,
        font=footer_font,
        fill=(
            220,
            220,
            220,
        ),
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    image.convert(
        "RGB"
    ).save(
        output_path,
        quality=95
    )

    return output_path


# ============================================================
# NARRATION
# ============================================================

async def edge_tts_async(
    text,
    voice,
    output_path,
):

    communicate = edge_tts.Communicate(
        text,
        voice,
    )

    await communicate.save(
        str(output_path)
    )


def generate_narration(
    text,
    voice,
    output_path,
):

    text = clean_text(
        text
    )

    if not text:

        raise RuntimeError(
            "نص التعليق الصوتي فارغ."
        )

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    attempts = 3

    for attempt in range(
        1,
        attempts + 1
    ):

        try:

            log(
                f"Starting Edge TTS "
                f"attempt {attempt}/{attempts} "
                f"with voice: {voice}"
            )

            if output_path.exists():

                output_path.unlink()

            asyncio.run(
                edge_tts_async(
                    text,
                    voice,
                    output_path,
                )
            )

            if (
                output_path.exists()
                and output_path.stat().st_size > 1000
            ):

                log(
                    f"Edge TTS completed successfully "
                    f"on attempt {attempt}."
                )

                return output_path

            raise RuntimeError(
                "Edge TTS created an empty audio file."
            )

        except Exception as error:

            log(
                f"Edge TTS attempt {attempt} failed: "
                f"{repr(error)}"
            )

            if attempt >= attempts:

                raise RuntimeError(
                    f"فشل Edge TTS بعد "
                    f"{attempts} محاولات: "
                    f"{error}"
                )

            time.sleep(
                attempt * 2
            )

    raise RuntimeError(
        "فشل توليد التعليق الصوتي."
    )


# ============================================================
# AUDIO DURATION
# ============================================================

def get_audio_duration(
    audio_path
):

    ffprobe = find_ffprobe()

    if ffprobe:

        try:

            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            duration = float(
                result.stdout.strip()
            )

            if duration > 0:

                return duration

        except Exception as error:

            log(
                f"FFprobe duration failed: "
                f"{repr(error)}"
            )

    # Fallback تقريبي
    size = Path(
        audio_path
    ).stat().st_size

    estimated = size / 16000

    return max(
        estimated,
        5.0
    )


# ============================================================
# SCENE NORMALIZATION
# ============================================================

def normalize_scenes(
    scenes,
    script,
):

    normalized = []

    if isinstance(
        scenes,
        list
    ):

        for index, scene in enumerate(
            scenes,
            start=1
        ):

            if isinstance(
                scene,
                dict
            ):

                text = (
                    scene.get("text")
                    or scene.get("narration")
                    or scene.get("description")
                    or scene.get("caption")
                    or ""
                )

                title = (
                    scene.get("title")
                    or scene.get("heading")
                    or ""
                )

            else:

                text = str(scene)

                title = ""

            text = clean_text(
                text
            )

            title = clean_text(
                title
            )

            if text or title:

                normalized.append(
                    {
                        "title": title,
                        "text": text,
                    }
                )

    if normalized:

        return normalized

    # --------------------------------------------------------
    # FALLBACK:
    # تقسيم النص إلى فقرات
    # --------------------------------------------------------

    script = clean_text(
        script
    )

    if not script:

        return [
            {
                "title": "فيديو جديد",
                "text": "",
            }
        ]

    sentences = re.split(
        r"(?<=[.!؟?])\s+",
        script
    )

    buffer = []

    for sentence in sentences:

        sentence = sentence.strip()

        if sentence:

            buffer.append(
                sentence
            )

    if not buffer:

        buffer = [script]

    group_size = max(
        1,
        math.ceil(
            len(buffer) / 8
        )
    )

    for start in range(
        0,
        len(buffer),
        group_size
    ):

        part = " ".join(
            buffer[
                start:
                start + group_size
            ]
        )

        normalized.append(
            {
                "title": "",
                "text": part,
            }
        )

    return normalized


# ============================================================
# PREPARE SCENES
# ============================================================

def prepare_scenes(
    title,
    script,
    scenes,
):

    prepared = normalize_scenes(
        scenes,
        script,
    )

    if not prepared:

        prepared = [
            {
                "title": title,
                "text": script,
            }
        ]

    # إعطاء عنوان رئيسي للمشهد الأول
    if prepared:

        if not prepared[0].get(
            "title"
        ):

            prepared[0][
                "title"
            ] = title

    return prepared


# ================================
