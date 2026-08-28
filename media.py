import asyncio, subprocess, os, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import edge_tts

def get_font(size):
    candidates=[
      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
      "C:/Windows/Fonts/arial.ttf",
      "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def wrap(text,width=34):
    words=text.split(); lines=[]; cur=""
    for w in words:
        if len(cur)+len(w)+1>width:
            lines.append(cur); cur=w
        else: cur=(cur+" "+w).strip()
    if cur:lines.append(cur)
    return "\n".join(lines)

def card(title, subtitle, path, w=1280,h=720):
    im=Image.new("RGB",(w,h))
    d=ImageDraw.Draw(im)
    f1=get_font(62); f2=get_font(34)
    d.multiline_text((70,160),wrap(title,28),font=f1,fill="white",spacing=18)
    d.multiline_text((70,500),wrap(subtitle,55),font=f2,fill="white",spacing=12)
    im.save(path,quality=95)

async def tts(text, voice, out):
    await edge_tts.Communicate(text,voice).save(str(out))

def make_video(title,script,scenes,outdir,voice):
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    audio=out/"voice.mp3"
    asyncio.run(tts(script,voice,audio))
    scene_dir=out/"scenes"; scene_dir.mkdir(exist_ok=True)
    imgs=[]
    for i,s in enumerate(scenes[:8]):
        p=scene_dir/f"{i}.png"
        card(title,s.get("text",""),p)
        imgs.append(p)
    # create one concat file with equal-duration stills; audio determines final length
    concat=out/"concat.txt"
    duration=max(5, int(max(1,len(script))/120))
    concat.write_text("\n".join(f"file '{p.resolve()}'\nduration {duration}" for p in imgs)+f"\nfile '{imgs[-1].resolve()}'",encoding="utf8")
    video=out/"video.mp4"
    cmd=["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-i",str(audio),
         "-vf","format=yuv420p","-c:v","libx264","-c:a","aac","-b:a","160k",
         "-shortest",str(video)]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    thumb=out/"thumbnail.jpg"; card(title,"",thumb)
    return str(video),str(thumb)
