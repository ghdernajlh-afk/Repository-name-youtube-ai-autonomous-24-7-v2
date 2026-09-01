import asyncio
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import edge_tts


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1280
HEIGHT = 720
FPS = 30

DEFAULT_BG = (18, 24, 38)
ACCENT = (55, 130, 255)
TEXT_COLOR = (255, 255, 255)
MUTED = (205, 215, 230)

# ============================================================
# BRANDING
# ============================================================

BRAND_NAME = "نبض المستقبل | Future Pulse 🚀"

WATERMARK_TEXT = BRAND_NAME

# حجم العلامة المائية
WATERMARK_FONT_SIZE = 24

# شفافية العلامة المائية
WATERMARK_ALPHA = 150

# مكان العلامة المائية
WATERMARK_MARGIN = 28

# ============================================================
# VIDEO SETTINGS
# ============================================================

MAX_SCENES = 8
MIN_SCENE_DURATION = 3.0

# سرعة حركة الخلفية
MOTION_ZOOM = 0.045

# ============================================================
# FONT
# ============================================================

def get_font(size):
    candidates = [
        # Arabic fonts first
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",

        # Common Linux fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",

        # Other possible fonts
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",

        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",

        # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]

    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    return ImageFont.load_default()


# ============================================================
# TEXT HELPERS
# ============================================================

def wrap(text, width=34):
    text = str(text or "").strip()

    if not text:
        return ""

    words = text.split()

    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()

        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    return "\n".join(lines)


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


# ============================================================
# LANGUAGE
# ============================================================

def detect_language(text):
    """
    Detect the main language.

    The project is configured to use one language only.
    DEFAULT_LANGUAGE can be set in Render.
    """

    configured = os.getenv(
        "DEFAULT_LANGUAGE",
        "ar"
    ).strip().lower()

    if configured:
        return configured

    return "ar"


# ============================================================
# HASHTAGS
# ============================================================

def generate_hashtags(
    title,
    script,
    language="ar"
):
    """
    Generate automatic hashtags.

    Hashtags are generated from the title and script.
    """

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
        "من",
        "في",
        "على",
        "إلى",
        "عن",
        "مع",
        "هذا",
        "هذه",
        "ذلك",
        "التي",
        "الذي",
        "هو",
        "هي",
        "و",
        "أو",
        "أن",
        "إن",
        "كان",
        "كانت",
        "ما",
        "ماذا",
        "كيف",
        "لماذا",
        "لقد",
        "قد",
        "بعد",
        "قبل",
        "بين",
        "هناك",
        "كل",
        "أي",
        "كما",
        "ثم",
        "لكن",
        "عندما",
        "حتى",
        "لذلك",
        "فقط",
    }

    stopwords_en = {
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "this",
        "that",
        "from",
        "how",
        "why",
        "what",
        "when",
        "where",
        "is",
        "are",
        "was",
        "were",
        "a",
        "an",
    }

    stopwords = (
        stopwords_ar
        if language.startswith("ar")
        else stopwords_en
    )

    unique = []

    for word in words:

        word = word.strip()

        if not word:
            continue

        if len(word) < 3:
            continue

        if word.lower() in stopwords:
            continue

        if word not in unique:
            unique.append(word)

        if len(unique) >= 6:
            break

    hashtags = []

    for word in unique:
        clean_word = re.sub(
            r"[^\w\u0600-\u06FF]",
            "",
            word,
            flags=re.UNICODE
        )

        if clean_word:
            hashtags.append(
                f"#{clean_word}"
            )

    # Always include branding.
    hashtags.append("#FuturePulse")

    if language.startswith("ar"):
        hashtags.append("#نبض_المستقبل")

    # Remove duplicates.
    result = []

    for tag in hashtags:
        if tag not in result:
            result.append(tag)

    return " ".join(result[:8])


# ============================================================
# BACKGROUND
# ============================================================

def make_background(index):
    """
    Create a visible cinematic background.

    This replaces the old plain/black background.
    """

    palettes = [
        ((12, 25, 48), (36, 75, 130)),
        ((20, 35, 30), (35, 105, 80)),
        ((45, 25, 55), (105, 50, 125)),
        ((45, 32, 18), (120, 75, 35)),
        ((18, 40, 50), (30, 110, 125)),
        ((35, 20, 28), (115, 45, 65)),
        ((20, 25, 45), (70, 65, 130)),
        ((25, 38, 22), (80, 105, 45)),
    ]

    c1, c2 = palettes[
        index % len(palettes)
    ]

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        c1
    )

    pixels = image.load()

    for y in range(HEIGHT):

        ratio = (
            y
            / max(
                1,
                HEIGHT - 1
            )
        )

        r = int(
            c1[0] * (1 - ratio)
            + c2[0] * ratio
        )

        g = int(
            c1[1] * (1 - ratio)
            + c2[1] * ratio
        )

        b = int(
            c1[2] * (1 - ratio)
            + c2[2] * ratio
        )

        for x in range(WIDTH):

            pixels[x, y] = (
                r,
                g,
                b
            )

    # --------------------------------------------------------
    # Soft cinematic lights
    # --------------------------------------------------------

    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    od = ImageDraw.Draw(
        overlay
    )

    circles = [
        (
            120,
            130,
            230,
            (255, 255, 255, 22)
        ),
        (
            1050,
            180,
            300,
            (255, 255, 255, 25)
        ),
        (
            850,
            650,
            260,
            (255, 255, 255, 18)
        ),
    ]

    for x, y, radius, color in circles:

        od.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius,
            ),
            fill=color
        )

    overlay = overlay.filter(
        ImageFilter.GaussianBlur(80)
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")

    return image


# ============================================================
# WATERMARK
# ============================================================

def add_watermark(
    image,
    text=WATERMARK_TEXT
):
    """
    Add Future Pulse watermark.
    """

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
        WATERMARK_FONT_SIZE
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

    # Background behind watermark.
    padding_x = 12
    padding_y = 8

    draw.rounded_rectangle(
        (
            x - padding_x,
            y - padding_y,
            x + text_width + padding_x,
            y + text_height + padding_y,
        ),
        radius=12,
        fill=(
            0,
            0,
            0,
            85
        )
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

    image = Image.alpha_composite(
        image,
        overlay
    )

    return image.convert(
        "RGB"
    )


# ============================================================
# CARD FRAME
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

    # --------------------------------------------------------
    # Main panel
    # --------------------------------------------------------

    panel = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    pd = ImageDraw.Draw(
        panel
    )

    pd.rounded_rectangle(
        (
            55,
            80,
            WIDTH - 55,
            HEIGHT - 80
        ),
        radius=35,
        fill=(
            0,
            0,
            0,
            115
        ),
        outline=(
            255,
            255,
            255,
            35
        ),
        width=2
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        panel
    ).convert("RGB")

    draw = ImageDraw.Draw(
        image
    )

    # --------------------------------------------------------
    # Scene number
    # --------------------------------------------------------

    number_font = get_font(
        28
    )

    draw.rounded_rectangle(
        (
            85,
            105,
            245,
            155
        ),
        radius=20,
        fill=ACCENT
    )

    scene_text = (
        f"المشهد {index + 1}/{total}"
    )

    draw.text(
        (
            110,
            117
        ),
        scene_text,
        font=number_font,
        fill=TEXT_COLOR
    )

    # --------------------------------------------------------
    # Main title
    # --------------------------------------------------------

    title_font = get_font(
        58
    )

    title = clean_text(
        title
    )

    title_text = wrap(
        title,
        28
    )

    draw.multiline_text(
        (
            85,
            205
        ),
        title_text,
        font=title_font,
        fill=TEXT_COLOR,
        spacing=18,
        align="right",
        anchor="ra"
    )

    # --------------------------------------------------------
    # Subtitle / visual description
    # --------------------------------------------------------

    subtitle = clean_text(
        subtitle
    )

    subtitle_font = get_font(
        34
    )

    subtitle_text = wrap(
        subtitle,
        55
    )

    draw.multiline_text(
        (
            85,
            490
        ),
        subtitle_text,
        font=subtitle_font,
        fill=MUTED,
        spacing=12,
        align="right",
        anchor="ra"
    )

    # --------------------------------------------------------
    # Timeline
    # --------------------------------------------------------

    line_y = HEIGHT - 115

    draw.rounded_rectangle(
        (
            85,
            line_y,
            WIDTH - 85,
            line_y + 8
        ),
        radius=4,
        fill=(
            255,
            255,
            255,
            55
        )
    )

    progress = (
        (index + 1)
        / max(
            1,
            total
        )
    )

    draw.rounded_rectangle(
        (
            85,
            line_y,
            int(
                85
                + (
                    WIDTH - 170
                )
                * progress
            ),
            line_y + 8
        ),
        radius=4,
        fill=ACCENT
    )

    # --------------------------------------------------------
    # Branding watermark
    # --------------------------------------------------------

    image = add_watermark(
        image
    )

    return image


# ============================================================
# KEN BURNS MOTION
# ============================================================

def create_motion_frames(
    image,
    out_dir,
    scene_index,
    duration
):
    """
    Create moving cinematic frames.
    """

    out_dir = Path(
        out_dir
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    frame_dir = (
        out_dir
        / f"frames_{scene_index}"
    )

    frame_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    total_frames = max(
        int(FPS * duration),
        FPS * 3
    )

    generated = []

    for frame_number in range(
        total_frames
    ):

        progress = (
            frame_number
            / max(
                1,
                total_frames - 1
            )
        )

        # Smooth zoom.
        zoom = (
            1.00
            + MOTION_ZOOM * progress
        )

        crop_w = int(
            WIDTH / zoom
        )

        crop_h = int(
            HEIGHT / zoom
        )

        max_x = max(
            0,
            WIDTH - crop_w
        )

        max_y = max(
            0,
            HEIGHT - crop_h
        )

        x = int(
            max_x * progress
        )

        direction = (
            1
            if scene_index % 2
            else -1
        )

        y = int(
            max_y
            * (
                0.5
                + 0.15
                * direction
                * progress
            )
        )

        x = max(
            0,
            min(
                x,
                max_x
            )
        )

        y = max(
            0,
            min(
                y,
                max_y
            )
        )

        frame = image.crop(
            (
                x,
                y,
                x + crop_w,
                y + crop_h
            )
        )

        frame = frame.resize(
            (
                WIDTH,
                HEIGHT
            ),
            Image.Resampling.LANCZOS
        )

        path = (
            frame_dir
            / f"{frame_number:06d}.jpg"
        )

        frame.save(
            path,
            "JPEG",
            quality=94
        )

        generated.append(
            path
        )

    return generated


# ============================================================
# TTS
# ============================================================

async def tts(
    text,
    voice,
    out
):
    """
    Generate one continuous voice track.

    The complete script is converted into one audio file,
    keeping the narration connected.
    """

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

    communicator = edge_tts.Communicate(
        text,
        voice
    )

    await communicator.save(
        str(out)
    )


# ============================================================
# AUDIO DURATION
# ============================================================

def audio_duration(
    path
):
    try:

        result = subprocess.run(
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
            capture_output=True,
            text=True,
            check=True,
        )

        value = float(
            result.stdout.strip()
        )

        if value > 0:
            return value

    except Exception:
        pass

    return 30.0


# ============================================================
# SAFE SCENES
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

    # --------------------------------------------------------
    # Fallback: split connected script into scenes.
    # --------------------------------------------------------

    if not result:

        paragraphs = [
            x.strip()
            for x in re.split(
                r"\n+",
                str(script or "")
            )
            if x.strip()
        ]

        for paragraph in paragraphs[:MAX_SCENES]:

            result.append(
                {
                    "text": paragraph[:300],
                    "visual": paragraph[:180],
                }
            )

    # --------------------------------------------------------
    # Final fallback.
    # --------------------------------------------------------

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
# SCENE DURATIONS
# ============================================================

def calculate_durations(
    scenes,
    total_duration
):
    weights = []

    for scene in scenes:

        text = (
            scene.get(
                "text",
                ""
            )
            + " "
            + scene.get(
                "visual",
                ""
            )
        )

        weight = max(
            1,
            len(text)
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
                value
            )
        )

    current = sum(
        durations
    )

    if current > 0:

        factor = (
            total_duration
            / current
        )

        durations = [
            max(
                2.5,
                x * factor
            )
            for x in durations
        ]

    return durations


# ============================================================
# BUILD SCENE VIDEOS
# ============================================================

def render_scene(
    image,
    scene_dir,
    index,
    duration
):
    create_motion_frames(
        image,
        scene_dir,
        index,
        max(
            3,
            int(
                duration + 1
            )
        )
    )

    pattern = (
        Path(scene_dir)
        / f"frames_{index}"
        / "%06d.jpg"
    )

    output = (
        Path(scene_dir)
        / f"scene_{index}.mp4"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(pattern),
        "-t",
        str(duration),
        "-vf",
        (
            f"scale={WIDTH}:{HEIGHT}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        ),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return output


# ============================================================
# CONCAT SCENES
# ============================================================

def concat_scenes(
    scene_files,
    output
):
    concat_file = (
        Path(output).parent
        / "scenes_concat.txt"
    )

    lines = []

    for scene in scene_files:

        lines.append(
            f"file '{Path(scene).resolve()}'"
        )

    concat_file.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    silent_video = (
        Path(output).parent
        / "silent_video.mp4"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(silent_video),
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return silent_video


# ============================================================
# ADD AUDIO
# ============================================================

def add_audio(
    video,
    audio,
    output
):
    cmd = [
        "ffmpeg",
        "-y",
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

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
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
        (0, 0, 0, 90)
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")

    draw = ImageDraw.Draw(
        image
    )

    title_font = get_font(
        58
    )

    title_text = wrap(
        clean_text(title),
        25
    )

    draw.multiline_text(
        (
            WIDTH // 2,
            HEIGHT // 2
        ),
        title_text,
        font=title_font,
        fill=TEXT_COLOR,
        spacing=18,
        anchor="mm",
        align="center"
    )

    # Branding on thumbnail.
    brand_font = get_font(
        28
    )

    bbox = draw.textbbox(
        (0, 0),
        BRAND_NAME,
        font=brand_font
    )

    brand_width = (
        bbox[2] - bbox[0]
    )

    draw.text(
        (
            WIDTH
            - brand_width
            - 30,
            HEIGHT - 55
        ),
        BRAND_NAME,
        font=brand_font,
        fill=TEXT_COLOR
    )

    image.save(
        str(path),
        "JPEG",
        quality=95
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
    """
    Main video generator.

    Features:
        - Visible cinematic backgrounds
        - Moving scenes
        - One continuous narration
        - Automatic branding
        - Automatic watermark
        - Automatic hashtags
        - YouTube-compatible MP4
        - Thumbnail generation
    """

    out = Path(
        outdir
    )

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Output files
    # --------------------------------------------------------

    video = out / "video.mp4"
    audio = out / "voice.mp3"
    thumbnail = out / "thumbnail.jpg"
    scene_dir = out / "rendered_scenes"

    # --------------------------------------------------------
    # Clean previous output
    # --------------------------------------------------------

    if video.exists():
        video.unlink()

    if audio.exists():
        audio.unlink()

    # --------------------------------------------------------
    # Language
    # --------------------------------------------------------

    language = detect_language(
        script
    )

    # --------------------------------------------------------
    # Clean script
    # --------------------------------------------------------

    final_script = clean_text(
        script or title
    )

    if not final_script:
        final_script = clean_text(
            title
        )

    # --------------------------------------------------------
    # Generate automatic hashtags.
    #
    # Worker can also use these if needed.
    # --------------------------------------------------------

    hashtags = generate_hashtags(
        title,
        final_script,
        language
    )

    print(
        f"[MEDIA] Language: {language}",
        flush=True
    )

    print(
        f"[MEDIA] Hashtags: {hashtags}",
        flush=True
    )

    # --------------------------------------------------------
    # TTS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Audio duration
    # --------------------------------------------------------

    total_duration = audio_duration(
        audio
    )

    total_duration = max(
        8.0,
        total_duration
    )

    # --------------------------------------------------------
    # Normalize scenes
    # --------------------------------------------------------

    normalized = normalize_scenes(
        title,
        final_script,
        scenes
    )

    durations = calculate_durations(
        normalized,
        total_duration
    )

    # --------------------------------------------------------
    # Render scenes
    # --------------------------------------------------------

    scene_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    scene_files = []

    total_scenes = len(
        normalized
    )

    for index, scene in enumerate(
        normalized
    ):

        image = draw_card(
            title,
            scene.get(
                "visual"
            )
            or scene.get(
                "text"
            )
            or title,
            index,
            total_scenes
        )

        scene_file = render_scene(
            image,
            scene_dir,
            index,
            durations[index]
        )

        if not scene_file.exists():

            raise RuntimeError(
                f"فشل إنشاء المشهد {index + 1}."
            )

        scene_files.append(
            scene_file
        )

    if not scene_files:

        raise RuntimeError(
            "لم يتم إنشاء أي مشهد للفيديو."
        )

    # --------------------------------------------------------
    # Concatenate scenes
    # --------------------------------------------------------

    silent_video = concat_scenes(
        scene_files,
        video
    )

    if not silent_video.exists():

        raise RuntimeError(
            "فشل دمج مشاهد الفيديو."
        )

    # --------------------------------------------------------
    # Add continuous voice
    # --------------------------------------------------------

    add_audio(
        silent_video,
        audio,
        video
    )

    if not video.exists():

        raise RuntimeError(
            "فشل إنشاء الفيديو النهائي."
        )

    # --------------------------------------------------------
    # Validate video
    # --------------------------------------------------------

    try:

        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height",
                "-of",
                "default=noprint_wrappers=1",
                str(video),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    except Exception as exc:

        raise RuntimeError(
            f"ملف الفيديو النهائي غير صالح: {exc}"
        )

    # --------------------------------------------------------
    # Thumbnail
    # --------------------------------------------------------

    make_thumbnail(
        title,
        thumbnail
    )

    if not thumbnail.exists():

        raise RuntimeError(
            "فشل إنشاء الصورة المصغرة."
        )

    # --------------------------------------------------------
    # Save metadata for worker / future use.
    # --------------------------------------------------------

    metadata = out / "metadata.txt"

    metadata.write_text(
        (
            f"brand={BRAND_NAME}\n"
            f"language={language}\n"
            f"hashtags={hashtags}\n"
            f"title={clean_text(title)}\n"
        ),
        encoding="utf-8"
    )

    print(
        "[MEDIA] Video generation completed successfully",
        flush=True
    )

    print(
        f"[MEDIA] Video: {video}",
        flush=True
    )

    print(
        f"[MEDIA] Thumbnail: {thumbnail}",
        flush=True
    )

    return (
        str(video),
        str(thumbnail)
    )
