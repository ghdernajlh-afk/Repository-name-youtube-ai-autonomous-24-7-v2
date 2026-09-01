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

        # Keep error useful but avoid gigantic logs.
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
# MOTION FRAMES
# ============================================================

def create_motion_frames(
    image,
    out_dir,
    scene_index,
    duration
):
    """
    Compatibility function.

    The actual renderer uses FFmpeg Ken Burns
    motion directly and does not generate
    thousands of JPEG frames.
    """

    out_dir = Path(
        out_dir
    )

    frame_dir = (
        out_dir
        / f"frames_{scene_index}"
    )

    frame_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    first_frame = (
        frame_dir
        / "000000.jpg"
    )

    image.save(
        first_frame,
        "JPEG",
        quality=92
    )

    return [first_frame]


# ============================================================
# TTS
# ============================================================

async def tts(
    text,
    voice,
    out
):
    text = clean_text(
        text
    )

    if not text:
        raise RuntimeError(
            "لا يوجد نص لإنشاء الصوت."
        )

    if not voice:
        raise RuntimeError(
            "صوت Edge TTS غير محدد."
        )

    log(
        f"Starting Edge TTS with voice: {voice}"
    )

    communicator = edge_tts.Communicate(
        text,
        voice
    )

    try:
        await asyncio.wait_for(
            communicator.save(
                str(out)
            ),
            timeout=TTS_TIMEOUT
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            "Edge TTS تجاوز المهلة "
            f"({TTS_TIMEOUT} ثانية)."
        ) from exc

    log(
        "Edge TTS completed."
    )


# ============================================================
# AUDIO DURATION
# ============================================================

def audio_duration(path):
    path = Path(path)

    if not path.exists():
        raise RuntimeError(
            f"ملف الصوت غير موجود: {path}"
        )

    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=FFPROBE_TIMEOUT,
        description="audio duration probe"
    )

    try:
        value = float(
            result.stdout.strip()
        )
    except Exception as exc:
        raise RuntimeError(
            "تعذر قراءة مدة ملف الصوت."
        ) from exc

    if value <= 0:
        raise RuntimeError(
            "مدة ملف الصوت غير صالحة."
        )

    return value


# ============================================================
# SCENES
# ============================================================

def normalize_scenes(
    title,
    script,
    scenes
):
    result = []

    if isinstance(
        scenes,
        list
    ):
        for scene in scenes:
            if not isinstance(
                scene,
                dict
            ):
                continue

            text = clean_text(
                scene.get(
                    "text",
                    ""
                )
            )

            visual = clean_text(
                scene.get(
                    "visual",
                    ""
                )
            )

            if text or visual:
                result.append(
                    {
                        "text": (
                            text
                            or title
                        ),
                        "visual": (
                            visual
                            or text
                            or title
                        ),
                    }
                )

    if not result:
        paragraphs = [
            x.strip()
            for x in re.split(
                r"\n+",
                str(script or "")
            )
            if x.strip()
        ]

        for paragraph in paragraphs:
            result.append(
                {
                    "text": paragraph[:500],
                    "visual": paragraph[:250],
                }
            )

    if not result:
        result = [
            {
                "text": title,
                "visual": title,
            }
        ]

    return result[
        :MAX_SCENES
    ]


# ============================================================
# DURATIONS
# ============================================================

def calculate_durations(
    scenes,
    total_duration
):
    if not scenes:
        return []

    weights = []

    for scene in scenes:
        text = clean_text(
            scene.get(
                "text",
                ""
            )
        )

        visual = clean_text(
            scene.get(
                "visual",
                ""
            )
        )

        weight = max(
            20,
            len(text)
            + len(visual) * 0.35
        )

        weights.append(
            weight
        )

    total_weight = sum(
        weights
    )

    durations = []

    for weight in weights:
        value = (
            total_duration
            * weight
            / max(
                1,
                total_weight
            )
        )

        durations.append(
            max(
                MIN_SCENE_DURATION,
                min(
                    MAX_SCENE_DURATION,
                    value
                )
            )
        )

    for _ in range(12):
        difference = (
            total_duration
            - sum(durations)
        )

        if abs(difference) < 0.05:
            break

        adjustable = []

        for i, duration in enumerate(
            durations
        ):
            if difference > 0:
                if duration < MAX_SCENE_DURATION:
                    adjustable.append(i)
            else:
                if duration > MIN_SCENE_DURATION:
                    adjustable.append(i)

        if not adjustable:
            break

        change = (
            difference
            / len(adjustable)
        )

        for i in adjustable:
            durations[i] = max(
                MIN_SCENE_DURATION,
                min(
                    MAX_SCENE_DURATION,
                    durations[i] + change
                )
            )

    return durations


# ============================================================
# RENDER SCENE
# ============================================================

def render_scene(
    image,
    scene_dir,
    index,
    duration
):
    scene_dir = Path(
        scene_dir
    )

    scene_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    image_path = (
        scene_dir
        / f"scene_source_{index}.jpg"
    )

    output = (
        scene_dir
        / f"scene_{index}.mp4"
    )

    image.save(
        image_path,
        "JPEG",
        quality=92
    )

    duration = max(
        1.0,
        float(duration)
    )

    zoom_expression = (
        "min(zoom+0.0007,1.10)"
    )

    x_expression = (
        "if(eq(on,1),"
        "(iw-iw/zoom)/2,"
        "iw/2-(iw/zoom/2))"
    )

    y_expression = (
        "if(eq(on,1),"
        "(ih-ih/zoom)/2,"
        "ih/2-(ih/zoom/2))"
    )

    filter_complex = (
        "scale="
        f"{WIDTH * 2}:"
        f"{HEIGHT * 2}:"
        "force_original_aspect_ratio=increase,"
        f"crop={WIDTH * 2}:{HEIGHT * 2},"
        "zoompan="
        f"z='{zoom_expression}':"
        f"x='{x_expression}':"
        f"y='{y_expression}':"
        "d=1:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={FPS},"
        "format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        filter_complex,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        VIDEO_PRESET,
        "-crf",
        VIDEO_CRF,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]

    run_command(
        cmd,
        timeout=FFMPEG_TIMEOUT,
        description=f"render scene {index + 1}"
    )

    if not output.exists():
        raise RuntimeError(
            f"FFmpeg لم ينشئ المشهد "
            f"{index + 1}."
        )

    return output


# ============================================================
# CONCAT
# ============================================================

def concat_scenes(
    scene_files,
    output
):
    output = Path(
        output
    )

    if not scene_files:
        raise RuntimeError(
            "لا توجد مشاهد للدمج."
        )

    concat_file = (
        output.parent
        / "scenes_concat.txt"
    )

    lines = []

    for scene in scene_files:
        path = Path(
            scene
        ).resolve()

        escaped = str(path).replace(
            "'",
            "'\\''"
        )

        lines.append(
            f"file '{escaped}'"
        )

    concat_file.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    silent_video = (
        output.parent
        / "silent_video.mp4"
    )

    if silent_video.exists():
        silent_video.unlink()

    # Keep the safe re-encode here.
    # We can optimize this later after stability
    # is confirmed.
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c:v",
        "libx264",
        "-preset",
        VIDEO_PRESET,
        "-crf",
        VIDEO_CRF,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(silent_video),
    ]

    run_command(
        cmd,
        timeout=FFMPEG_TIMEOUT,
        description="concatenate scenes"
    )

    if not silent_video.exists():
        raise RuntimeError(
            "فشل إنشاء الفيديو الصامت."
        )

    return silent_video


# ============================================================
# AUDIO
# ============================================================

def add_audio(
    video,
    audio,
    output
):
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]

    run_command(
        cmd,
        timeout=FFMPEG_TIMEOUT,
        description="add narration audio"
    )

    if not Path(output).exists():
        raise RuntimeError(
            "فشل إنشاء الفيديو مع الصوت."
        )


# ============================================================
# VALIDATION
# ============================================================

def validate_video(path):
    path = Path(path)

    if not path.exists():
        raise RuntimeError(
            f"الفيديو غير موجود: {path}"
        )

    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        timeout=FFPROBE_TIMEOUT,
        description="final video validation"
    )

    output = (
        result.stdout
        or ""
    )

    if "codec_type=video" not in output:
        raise RuntimeError(
            "الفيديو النهائي لا يحتوي "
            "على مسار فيديو صالح."
        )

    if "codec_type=audio" not in output:
        raise RuntimeError(
            "الفيديو النهائي لا يحتوي "
            "على مسار صوت صالح."
        )

    log(
        "Final video validation passed."
    )


# ============================================================
# THUMBNAIL
# ============================================================

def make_thumbnail(
    title,
    path
):
    image = make_background(
        0
    )

    overlay = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 105)
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")

    draw = ImageDraw.Draw(
        image
    )

    title_text, title_font = fit_text(
        draw,
        clean_text(title),
        max_width=1500,
        max_height=450,
        start_size=80,
        bold=True,
    )

    draw.multiline_text(
        (
            WIDTH // 2,
            HEIGHT // 2 - 40
        ),
        title_text,
        font=title_font,
        fill=TEXT_COLOR,
        spacing=25,
        anchor="mm",
        align="center"
    )

    brand_font = get_font(
        30,
        bold=True
    )

    draw.rounded_rectangle(
        (
            80,
            HEIGHT - 105,
            650,
            HEIGHT - 45
        ),
        radius=30,
        fill=(0, 0, 0, 120)
    )

    draw.text(
        (
            105,
            HEIGHT - 75
        ),
        BRAND_NAME,
        font=brand_font,
        fill=TEXT_COLOR,
        anchor="lm"
    )

    image.save(
        str(path),
        "JPEG",
        quality=96
    )


# ============================================================
# MAIN VIDEO GENERATOR
# ============================================================

def make_video(
    title,
    script,
    scenes,
    outdir,
    voice
):
    out = Path(
        outdir
    )

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    video = (
        out
        / "video.mp4"
    )

    audio = (
        out
        / "voice.mp3"
    )

    thumbnail = (
        out
        / "thumbnail.jpg"
    )

    scene_dir = (
        out
        / "rendered_scenes"
    )

    log(
        "=================================================="
    )

    log(
        f"Starting video generation: {title}"
    )

    log(
        f"Output directory: {out}"
    )

    log(
        f"Resolution: {WIDTH}x{HEIGHT}"
    )

    log(
        f"FPS: {FPS}"
    )

    # --------------------------------------------------------
    # Clean old output
    # --------------------------------------------------------

    for path in [
        video,
        audio,
        thumbnail,
    ]:
        if path.exists():
            try:
                path.unlink()
            except Exception as exc:
                log(
                    f"Warning: could not remove {path}: {exc}"
                )

    if scene_dir.exists():
        try:
            shutil.rmtree(
                scene_dir
            )
        except Exception as exc:
            raise RuntimeError(
                "تعذر تنظيف مجلد المشاهد القديم."
            ) from exc

    language = detect_language(
        script
    )

    final_script = clean_text(
        script or title
    )

    if not final_script:
        final_script = clean_text(
            title
        )

    if not final_script:
        raise RuntimeError(
            "لا يوجد نص لإنشاء الفيديو."
        )

    hashtags = generate_hashtags(
        title,
        final_script,
        language
    )

    log(
        f"Language: {language}"
    )

    log(
        f"Hashtags: {hashtags}"
    )

    # --------------------------------------------------------
    # TTS
    # --------------------------------------------------------

    log(
        "STEP 1/6: Generating narration..."
    )

    asyncio.run(
        tts(
            final_script,
            voice,
            audio
        )
    )

    if not audio.exists():
        raise RuntimeError(
            "فشل إنشاء ملف الصوت."
        )

    total_duration = audio_duration(
        audio
    )

    total_duration = max(
        8.0,
        total_duration
    )

    log(
        f"Narration duration: "
        f"{total_duration:.2f} seconds"
    )

    # --------------------------------------------------------
    # Scenes
    # --------------------------------------------------------

    log(
        "STEP 2/6: Preparing scenes..."
    )

    normalized = normalize_scenes(
        title,
        final_script,
        scenes
    )

    if not normalized:
        raise RuntimeError(
            "لم يتم العثور على مشاهد."
        )

    durations = calculate_durations(
        normalized,
        total_duration
    )

    total_scenes = len(
        normalized
    )

    log(
        f"Total scenes: {total_scenes}"
    )

    scene_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Render scenes
    # --------------------------------------------------------

    log(
        "STEP 3/6: Rendering scenes..."
    )

    scene_files = []

    for index, scene in enumerate(
        normalized
    ):
        visual = (
            scene.get("visual")
            or scene.get("text")
            or title
        )

        duration = durations[index]

        log(
            f"Scene {index + 1}/{total_scenes} "
            f"- duration {duration:.2f}s"
        )

        image = draw_card(
            title,
            visual,
            index,
            total_scenes
        )

        scene_file = render_scene(
            image,
            scene_dir,
            index,
            duration
        )

        if not scene_file.exists():
            raise RuntimeError(
                f"فشل إنشاء المشهد "
                f"{index + 1}."
            )

        scene_files.append(
            scene_file
        )

        log(
            f"Scene {index + 1}/{total_scenes} completed."
        )

    if not scene_files:
        raise RuntimeError(
            "لم يتم إنشاء أي مشهد للفيديو."
        )

    # --------------------------------------------------------
    # Concatenate
    # --------------------------------------------------------

    log(
        "STEP 4/6: Concatenating scenes..."
    )

    silent_video = concat_scenes(
        scene_files,
        video
    )

    if not silent_video.exists():
        raise RuntimeError(
            "فشل دمج مشاهد الفيديو."
        )

    log(
        "Scene concatenation completed."
    )

    # --------------------------------------------------------
    # Audio
    # --------------------------------------------------------

    log(
        "STEP 5/6: Adding narration..."
    )

    add_audio(
        silent_video,
        audio,
        video
    )

    if not video.exists():
        raise RuntimeError(
            "فشل إنشاء الفيديو النهائي."
        )

    log(
        "Narration added successfully."
    )

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    log(
        "STEP 6/6: Validating final video..."
    )

    validate_video(
        video
    )

    # --------------------------------------------------------
    # Thumbnail
    # --------------------------------------------------------

    log(
        "Creating thumbnail..."
    )

    make_thumbnail(
        title,
        thumbnail
    )

    if not thumbnail.exists():
        raise RuntimeError(
            "فشل إنشاء الصورة المصغرة."
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = (
        out
        / "metadata.txt"
    )

    metadata.write_text(
        (
            f"brand={BRAND_NAME}\n"
            f"language={language}\n"
            f"hashtags={hashtags}\n"
            f"title={clean_text(title)}\n"
            f"duration={total_duration:.2f}\n"
            f"resolution={WIDTH}x{HEIGHT}\n"
            f"fps={FPS}\n"
        ),
        encoding="utf-8"
    )

    log(
        "=================================================="
    )

    log(
        "Video generation completed successfully."
    )

    log(
        f"Video: {video}"
    )

    log(
        f"Thumbnail: {thumbnail}"
    )

    log(
        f"Duration: {total_duration:.2f}s"
    )

    log(
        "=================================================="
    )

    return (
        str(video),
        str(thumbnail)
    )
