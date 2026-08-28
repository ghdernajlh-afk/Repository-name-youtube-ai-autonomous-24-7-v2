import os, json, re
from openai import OpenAI

def cli():
    k=os.getenv("OPENAI_API_KEY")
    if not k: raise RuntimeError("OPENAI_API_KEY غير موجود. افتح /setup.")
    return OpenAI(api_key=k)

def choose(items, recent):
    compact=json.dumps(items[:50],ensure_ascii=False)
    prompt=f"""أنت مدير قناة YouTube عربية متنوعة.
اختر فكرة واحدة فقط من القائمة تصلح لفيديو أصلي، مفيد، جذاب، ويمكن التحقق منه.
تجنب تكرار المواضيع التالية: {recent}
لا تختلق خبراً. أعد JSON فقط: {{"topic":"...","reason":"..."}}.
القائمة:
{compact}"""
    r=cli().responses.create(model=os.getenv("OPENAI_MODEL","gpt-5.6-luna"),input=prompt)
    return json.loads(re.sub(r"^```json|```$","",r.output_text.strip()).strip())

def make_content(topic, sources, language="ar"):
    src=json.dumps(sources,ensure_ascii=False)[:18000]
    prompt=f"""أنت منتج ومحرر YouTube.
الموضوع: {topic}
اللغة: {language}
المصادر المتاحة: {src}

اكتب محتوى أصلياً لا ينسخ النصوص. لا تقدم ادعاءً كحقيقة إن لم تدعمه المصادر.
أعد JSON فقط بالمفاتيح:
title: عنوان جذاب وغير مضلل
description: وصف منظم مع تنبيه أن التفاصيل قد تتغير عند الحاجة
script: سكربت 5-7 دقائق، مقدمة قوية، فقرات واضحة، خاتمة
scenes: قائمة 6 عناصر، كل عنصر {{"text":"جملة قصيرة على الشاشة","visual":"وصف بصري بسيط"}}
tags: قائمة كلمات مفتاحية
"""
    r=cli().responses.create(model=os.getenv("OPENAI_MODEL","gpt-5.6-luna"),input=prompt)
    return json.loads(re.sub(r"^```json|```$","",r.output_text.strip()).strip())
