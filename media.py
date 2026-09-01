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
# FONT
# ============================================================

def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "C:/Windows/Fonts/arial.ttf",
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
        candidate = (
            f"{current} {word}".strip()
        )

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
# BACKGROUND
# ============================================================

def make_background(index):
    """
    Creates a visible cinematic background instead of the
    black Image.new() used by the old version.
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

    c1, c2 = palettes[index % len(palettes)]

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        c1
    )

    pixels = image.load()

    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)

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
            pixels[x, y] = (r, g, b)

    # Soft blurred light circles
    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    od = ImageDraw.Draw(overlay)

    circles = [
        (120, 130, 230, (255, 255, 255, 22)),
        (1050, 180, 300, (255, 255, 255, 255)),
        (850, 650, 260, (255, 255, 255, 18)),
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
# CARD FRAME
# ============================================================

def draw_card(
    title,
    subtitle,
    index,
    total
):
    image = make_background(index)

    draw = ImageDraw.Draw(image)

    # Dark transparent area behind text
    panel = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    pd = ImageDraw.Draw(panel)

    pd.rounded_rectangle(
        (
            55,
            80,
            WIDTH - 55,
            HEIGHT - 80
        ),
        radius=35,
        fill=(0, 0, 0, 115),
        outline=(255, 255, 255, 35),
        width=2
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        panel
    ).convert("RGB")

    draw = ImageDraw.Draw(image)

    # Scene number
    number_font = get_font(28)

    draw.rounded_rectangle(
        (85, 105, 245, 155),
        radius=20,
        fill=ACCENT
    )

    draw.text(
        (110, 117),
        f"المشهد {index + 1}/{total}",
        font=number_font,
        fill=TEXT_COLOR
    )

    # Main title
    title_font = get_font(58)

    title = clean_text(title)

    title_text = wrap(
        title,
        28
    )

    draw.multiline_text(
        (85, 205),
        title_text,
        font=title_font,
        fill=TEXT_COLOR,
        spacing=18,
        align="right",
        anchor="ra"
    )

    # Subtitle
    subtitle = clean_text(subtitle)

    subtitle_font = get_font(34)

    subtitle_text = wrap(
        subtitle,
        55
    )

    draw.multiline_text(
        (85, 490),
        subtitle_text,
        font=subtitle_font,
        fill=MUTED,
        spacing=12,
        align="right",
        anchor="ra"
    )

    # Decorative timeline
    line_y = HEIGHT - 115

    draw.rounded_rectangle(
        (
            85,
            line_y,
            WIDTH - 85,
            line_y + 8
        ),
        radius=4,
        fill=(255, 255, 255, 55)
    )

    progress = (
        (index + 1)
        / max(1, total)
    )

    draw.rounded_rectangle(
        (
            85,
            line_y,
            int(
                85
                + (WIDTH - 170)
                * progress
            ),
            line_y + 8
        ),
        radius=4,
        fill=ACCENT
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
    Creates a short MP4 with smooth zoom/pan movement
    so the video is not a static image.
    """

    out_dir = Path(out_dir)

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
        FPS * duration,
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

        # Smooth zoom
        zoom = (
            1.00
            + 0.045 * progress
        )

        crop_w = int(
            WIDTH / zoom
        )

        crop_h = int(
            HEIGHT / zoom
        )

        # Gentle horizontal movement
        max_x = WIDTH - crop_w
        max_y = HEIGHT - crop_h

        x = int(
            max_x * progress
        )

        y = int(
            max_y
            * (
                0.5
                + 0.15
                * (
                    1
                    if scene_index % 2
                    else -1
                )
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

        generated.append(path)

    return generated


# ============================================================
# TTS
# ============================================================

async def tts(
    text,
    voice,
    out
):
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

def audio_duration(path):
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
                        "text": text
                        or title,
                        "visual": visual
                        or text
                        or title,
                    }
                )

    # Never allow zero scenes.
    if not result:
        paragraphs = [
            x.strip()
            for x in re.split(
                r"\n+",
                str(script or "")
            )
            if x.strip()
        ]

        for paragraph in paragraphs[:8]:
            result.append(
                {
                    "text": paragraph[:300],
                    "visual": paragraph[:180],
                }
            )

    # Final fallback
    if not result:
        result = [
            {
                "text": title,
                "visual": title
            }
        ]

    return result[:8]


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
            scene.get("text", "")
            + " "
            + scene.get("visual", "")
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

    minimum = 3.0

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
                minimum,
                value
            )
        )

    # Keep total close to audio duration.
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
    frames = create_motion_frames(
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

    frames_txt = (
        Path(scene_dir)
        / f"scene_{index}.txt"
    )

    # Use image2 instead of concat to avoid
    # malformed concat timing.
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

    draw = ImageDraw.Draw(
        image
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
    out = Path(
        outdir
    )

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Clean previous incomplete output
    # --------------------------------------------------------

    video = out / "video.mp4"
    audio = out / "voice.mp3"
    thumbnail = out / "thumbnail.jpg"
    scene_dir = out / "rendered_scenes"

    if video.exists():
        video.unlink()

    if audio.exists():
        audio.unlink()

    # --------------------------------------------------------
    # TTS
    # --------------------------------------------------------

    asyncio.run(
        tts(
            str(script or title),
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
        script,
        scenes
    )

    durations = calculate_durations(
        normalized,
        total_duration
    )

    # --------------------------------------------------------
    # Render every scene
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
    # Concatenate
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
    # Add voice
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

    except Exception as e:
        raise RuntimeError(
            f"ملف الفيديو النهائي غير صالح: {e}"
        )

    # --------------------------------------------------------
    # Thumbnail
    # --------------------------------------------------------

    make_thumbnail(
        title,
        thumbnail
    )

    return (
        str(video),
        str(thumbnail)
    )
