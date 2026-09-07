import os
import shutil
import asyncio
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# Dynamic Root Setup
BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media_tmp"
MEDIA_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 30

def log(msg: str):
    print(f"[MEDIA] {msg}", flush=True)

def find_font():
    """البحث عن خط يدعم اللغة العربية بشكل تلقائي"""
    custom_font = BASE_DIR / "fonts" / "Cairo-Bold.ttf"
    if custom_font.exists():
        return str(custom_font)

    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in system_fonts:
        if os.path.exists(path):
            return path
    return None

FONT_PATH = find_font()

def get_font(size: int):
    if FONT_PATH:
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()

def reshape_arabic(text: str) -> str:
    """إصلاح تشكيل وتوصيل اتجاه اللغة العربية بشكل مضمون 100%"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        return bidi_text
    except Exception as e:
        log(f"Arabic reshape warning: {e}")
        return text

def draw_card(title: str, text: str, output_path: Path, is_thumbnail: bool = False):
    """رسم الصورة بخلفية ملونة وإطار واضح لمنع ظهور الشاشة السوداء"""
    bg_color = (15, 23, 42) if is_thumbnail else (24, 32, 48)
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=bg_color)
    draw = ImageDraw.Draw(img)

    title_reshaped = reshape_arabic(title)
    text_reshaped = reshape_arabic(text)

    font_title = get_font(48 if is_thumbnail else 40)
    font_text = get_font(28)

    # رسم بطاقة خلفية أنيقة لتوضيح النصوص
    margin = 50
    card_box = [margin, margin, VIDEO_WIDTH - margin, VIDEO_HEIGHT - margin]
    draw.rounded_rectangle(card_box, radius=20, fill=(35, 45, 66), outline=(70, 90, 120), width=3)

    # رسم العنوان في المنتصف
    if title_reshaped:
        draw.text(
            (VIDEO_WIDTH // 2, VIDEO_HEIGHT // 3),
            title_reshaped,
            fill=(255, 255, 255),
            font=font_title,
            anchor="mm"
        )

    # رسم النص الفرعي إن وجد
    if text_reshaped and not is_thumbnail:
        draw.text(
            (VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2 + 50),
            text_reshaped,
            fill=(210, 225, 245),
            font=font_text,
            anchor="mm"
        )

    img.save(output_path, format="PNG")

def get_audio_duration(audio_path: Path) -> float:
    """استخراج مدة الملف الصوتي باستخدام ffprobe"""
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path.absolute())
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        log(f"Error getting audio duration: {e}")
        return 10.0

async def text_to_speech_edge(text: str, output_path: Path, voice: str = "ar-EG-SalmaNeural"):
    """توليد الصوت باستخدام edge-tts"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path.absolute()))

async def make_video(job_id: str, title: str, script_items: list) -> tuple[Path, Path]:
    """إنشاء أجزاء الفيديو وتجميعها بملف واحد وإعداد الصورة المصغرة"""
    job_dir = MEDIA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    clip_paths = []

    for idx, item in enumerate(script_items):
        sec_title = item.get("title", f"الجزء {idx+1}")
        sec_text = item.get("text", "")
        
        img_path = job_dir / f"img_{idx}.png"
        audio_path = job_dir / f"audio_{idx}.mp3"
        clip_path = job_dir / f"clip_{idx}.mp4"

        # 1. إنشاء الصورة
        draw_card(sec_title, sec_text, img_path)

        # 2. إنشاء الصوت
        tts_text = f"{sec_title}. {sec_text}"
        await text_to_speech_edge(tts_text, audio_path)

        duration = get_audio_duration(audio_path) + 0.5

        # 3. دمج الصوت والصورة إلى مقطع فيديو متوافق كلياً مع yuv420p لمنع السواد
        cmd = [
            ffmpeg, "-y",
            "-loop", "1", "-i", str(img_path.absolute()),
            "-i", str(audio_path.absolute()),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-r", str(VIDEO_FPS),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-t", str(duration),
            str(clip_path.absolute())
        ]
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            log(f"FFmpeg Clip Error: {stderr.decode()}")
            raise RuntimeError("فشل في إنشاء مقطع الفيديو")

        clip_paths.append(clip_path)

    # 4. تجميع كافة المقاطع
    concat_file = job_dir / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for c in clip_paths:
            f.write(f"file '{c.absolute()}'\n")

    final_video_path = job_dir / "final_video.mp4"
    concat_cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file.absolute()),
        "-c", "copy",
        str(final_video_path.absolute())
    ]
    
    proc = await asyncio.create_subprocess_exec(*concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        log(f"FFmpeg Concat Error: {stderr.decode()}")
        raise RuntimeError("فشل في تجميع مقاطع الفيديو")

    # 5. إنشاء الصورة المصغرة (Thumbnail)
    thumb_path = job_dir / "thumbnail.png"
    draw_card(title, "فيديو جديد", thumb_path, is_thumbnail=True)

    return final_video_path, thumb_path
    
