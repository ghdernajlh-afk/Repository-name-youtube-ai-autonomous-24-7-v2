import os
import subprocess
import json
import math
from pathlib import Path
import async_timeout
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================

DEFAULT_VOICE = os.getenv("VOICE", "ar-SA-HamedNeural")
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1280"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "720"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "20"))

SCENE_MIN_DURATION = 3.0
SCENE_MAX_DURATION = 15.0


def log(msg):
    print(f"[MEDIA] {msg}", flush=True)


def require_ffmpeg():
    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")
    try:
        subprocess.run([ffmpeg_bin, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return ffmpeg_bin
    except Exception:
        raise RuntimeError("FFmpeg is not available in system environment PATH.")


def run_command(cmd):
    log(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed:\n{result.stderr}")
    return result.stdout


# ============================================================
# TEXT PROCESSING & RENDERING
# ============================================================

def reshape_arabic(text: str) -> str:
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        log(f"Arabic reshape warning: {e}")
        return text


def get_font(size: int):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "arial.ttf"
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_card(title: str, text: str, output_path: Path, index: int = 0, is_thumbnail: bool = False):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 24, 33))
    draw = ImageDraw.Draw(img)

    title_reshaped = reshape_arabic(title)
    text_reshaped = reshape_arabic(text)

    font_title = get_font(48 if not is_thumbnail else 56)
    font_text = get_font(32)

    # رسم العنوان
    draw.text((VIDEO_WIDTH // 2, VIDEO_HEIGHT // 3), title_reshaped, fill=(255, 255, 255), font=font_title, anchor="mm")

    # رسم النص الفرعي إن وجد
    if text_reshaped and not is_thumbnail:
        draw.text((VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2 + 50), text_reshaped, fill=(200, 210, 225), font=font_text, anchor="mm")

    img.save(output_path)


# ============================================================
# NARRATION & AUDIO
# ============================================================

async def _tts_to_file(text: str, voice: str, output_path: Path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def generate_narration(text: str, voice: str, output_path: Path):
    try:
        asyncio.run(_tts_to_file(text, voice, output_path))
    except Exception as e:
        log(f"TTS Generation Error: {e}")
        raise


def get_audio_duration(audio_path: Path) -> float:
    ffmpeg = require_ffmpeg()
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path.absolute())
    ]
    try:
        out = run_command(cmd)
        return float(out.strip())
    except Exception:
        return SCENE_MIN_DURATION


def prepare_scenes(title: str, script: str, scenes: list) -> list:
    if scenes and isinstance(scenes, list):
        return scenes
    
    # تحضير مشاهد افتراضية من النص
    lines = [line.strip() for line in script.split(".") if line.strip()]
    if not lines:
        lines = [title]
        
    prepared = []
    for idx, line in enumerate(lines):
        prepared.append({
            "title": f"المشهد {idx + 1}" if len(lines) > 1 else title,
            "text": line
        })
    return prepared


# ============================================================
# MAKE VIDEO (MATCHING WORKER.PY REQUIREMENT)
# ============================================================

def make_video(
    title: str,
    script: str = "",
    scenes: list = None,
    output_dir = "output",
    voice: str = DEFAULT_VOICE,
    **kwargs
):
    """
    إنشاء الفيديو والصورة المصغرة وترجيع (video_path, thumbnail_path)
    مع ضبط المسارات بدقة لمنع خطأ البحث في مجلد باسم الصوت.
    """
    ffmpeg = require_ffmpeg()
    
    # تحويل مسار المخرج إلى Path بشكل مطلق وصحيح
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    prepared_scenes = prepare_scenes(title, script, scenes or [])
    video_clips = []

    log(f"Processing {len(prepared_scenes)} scenes in folder: {output_path}")

    # 1. إنشاء الصورة المصغرة (Thumbnail)
    thumb_path = output_path / "thumbnail.png"
    try:
        draw_card(title, "", thumb_path, index=0, is_thumbnail=True)
    except Exception as e:
        log(f"Thumbnail generation warning: {e}")
        thumb_path = None

    # 2. إنتاج المشاهد
    for idx, scene in enumerate(prepared_scenes):
        scene_title = scene.get("title", "")
        scene_text = scene.get("text", "")
        
        img_path = output_path / f"scene_{idx}.png"
        draw_card(scene_title, scene_text, img_path, index=idx)

        audio_path = output_path / f"scene_{idx}.mp3"
        narration_text = f"{scene_title}. {scene_text}".strip()
        
        try:
            generate_narration(narration_text, voice, audio_path)
            duration = get_audio_duration(audio_path)
        except Exception as e:
            log(f"Narration warning for scene {idx}: {e}")
            duration = SCENE_MIN_DURATION

        duration = max(SCENE_MIN_DURATION, min(duration, SCENE_MAX_DURATION))

        clip_path = output_path / f"clip_{idx}.mp4"
        cmd = [
            ffmpeg, "-y",
            "-loop", "1", "-i", str(img_path.absolute()),
            "-i", str(audio_path.absolute()),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-r", str(VIDEO_FPS),
            "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-t", str(duration),
            str(clip_path.absolute())
        ]
        run_command(cmd)
        video_clips.append(clip_path)

    # 3. دمج المشاهد
    concat_list = output_path / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for clip in video_clips:
            f.write(f"file '{clip.absolute()}'\n")

    final_video_path = output_path / "final_output.mp4"
    concat_cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list.absolute()),
        "-c", "copy",
        str(final_video_path.absolute())
    ]
    run_command(concat_cmd)

    log(f"Video generated successfully: {final_video_path}")

    return str(final_video_path.absolute()), str(thumb_path.absolute()) if thumb_path else ""
