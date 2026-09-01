import os
import json
import re
import random

try:
    from google import genai
except Exception:
    genai = None


# ============================================================
# CONFIG
# ============================================================

# يمكن تغيير النموذج من Render Environment Variables
# بدون تعديل الكود.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
).strip()


# ============================================================
# HELPERS
# ============================================================

def clean_json(text):
    if not text:
        raise RuntimeError("Empty AI response.")

    text = text.strip()

    # إزالة Markdown code fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    # استخراج JSON من أي نص إضافي
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Invalid JSON returned by Gemini: {e}"
        ) from e


def gemini_client():
    key = os.getenv(
        "GEMINI_API_KEY",
        ""
    ).strip()

    if not key:
        return None

    if genai is None:
        raise RuntimeError(
            "google-genai package is not installed."
        )

    return genai.Client(
        api_key=key
    )


def ask_gemini(prompt):
    client = gemini_client()

    if client is None:
        return None

    if not GEMINI_MODEL:
        raise RuntimeError(
            "GEMINI_MODEL is empty."
        )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    text = getattr(
        response,
        "text",
        None
    )

    if not text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    return text


# ============================================================
# LOCAL FALLBACK
# ============================================================

def local_choose(items, recent):

    recent_text = " ".join(
        str(x).lower()
        for x in (recent or [])
    )

    candidates = []

    for item in items:

        title = str(
            item.get("title", "")
        ).strip()

        summary = str(
            item.get("summary", "")
        ).strip()

        if not title:
            continue

        combined = (
            title + " " + summary
        ).lower()

        if title.lower() in recent_text:
            continue

        score = 0

        keywords = [
            "ai",
            "artificial intelligence",
            "technology",
            "science",
            "space",
            "future",
            "discovery",
            "interesting",
            "research",
            "innovation",
            "ذكاء",
            "تقنية",
            "علوم",
            "فضاء",
            "اكتشاف",
            "ابتكار",
        ]

        for keyword in keywords:
            if keyword in combined:
                score += 2

        if len(summary) > 150:
            score += 1

        candidates.append(
            (
                score,
                item
            )
        )

    if not candidates:

        if not items:
            raise RuntimeError(
                "لا توجد مصادر لاختيار موضوع."
            )

        item = items[0]

    else:

        candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

        top = candidates[
            :min(5, len(candidates))
        ]

        item = random.choice(top)[1]

    title = str(
        item.get("title", "")
    ).strip()

    return {
        "topic": title,
        "reason": (
            "تم اختيار الموضوع من المصادر "
            "المتاحة."
        ),
    }


def local_content(
    topic,
    sources,
    language="ar"
):

    source_lines = []

    for source in sources[:4]:

        title = str(
            source.get("title", "")
        ).strip()

        text = str(
            source.get("text", "")
        ).strip()

        if title:
            source_lines.append(
                f"- {title}"
            )

        if text:

            sentences = re.split(
                r"(?<=[.!؟])\s+",
                text
            )

            for sentence in sentences[:3]:

                sentence = sentence.strip()

                if len(sentence) > 40:
                    source_lines.append(
                        f"  {sentence[:350]}"
                    )

    source_block = "\n".join(
        source_lines
    )

    if not source_block:
        source_block = (
            "لا توجد تفاصيل نصية كافية "
            "في المصادر."
        )

    script = f"""
مرحبًا بكم في قناة نبض المستقبل.

موضوعنا اليوم هو:
{topic}

سنستعرض في هذا الفيديو أهم المعلومات
المتاحة حول هذا الموضوع.

المصادر التي جمعها الوكيل:

{source_block}

سنحاول التمييز بين المعلومات الموجودة
في المصادر وبين أي استنتاجات غير مؤكدة.

لماذا يستحق هذا الموضوع الاهتمام؟

لأن التطورات في هذا المجال قد تؤثر
على التقنية والعلوم والمستقبل.

ماذا يمكن أن يحدث لاحقًا؟

يعتمد ذلك على التطورات والمعلومات الجديدة
التي ستظهر من المصادر الموثوقة.

وفي النهاية، هذه كانت أهم النقاط حول:
{topic}

إذا أعجبكم الفيديو، تابعوا قناة
نبض المستقبل | Future Pulse 🚀
للمزيد من المواضيع التقنية والعلمية
والمعلومات المثيرة للاهتمام.

شكرًا لكم على المشاهدة.
""".strip()

    scenes = [
        {
            "text": topic,
            "visual": "عنوان رئيسي للموضوع"
        },
        {
            "text": "ما الذي نعرفه؟",
            "visual": "عرض المعلومات الأساسية"
        },
        {
            "text": "أهم المصادر",
            "visual": "عرض المصادر والمعلومات"
        },
        {
            "text": "لماذا الموضوع مهم؟",
            "visual": "شرح أهمية الموضوع"
        },
        {
            "text": "ماذا نتوقع؟",
            "visual": "نظرة إلى المستقبل"
        },
        {
            "text": "الخلاصة",
            "visual": "تلخيص أهم النقاط"
        },
    ]

    description = (
        f"في هذا الفيديو نستعرض موضوع: {topic}\n\n"
        "تم إعداد المحتوى اعتمادًا على المصادر "
        "المتاحة وقت إنشاء الفيديو.\n\n"
        "© نبض المستقبل | Future Pulse 🚀"
    )

    tags = [
        "أخبار",
        "تقنية",
        "علوم",
        "ذكاء اصطناعي",
        "معلومات",
        "YouTube",
    ]

    return {
        "title": topic[:100],
        "description": description,
        "script": script,
        "scenes": scenes,
        "tags": tags,
    }


# ============================================================
# CHOOSE TOPIC
# ============================================================

def choose(items, recent):

    prompt = f"""
أنت مدير قناة YouTube عربية اسمها:
نبض المستقبل | Future Pulse 🚀

اختر فكرة واحدة فقط من المصادر التالية.

الشروط:
- اختر موضوعًا جذابًا ومفيدًا.
- اختر موضوعًا واحدًا فقط.
- لا تخلط بين عدة مواضيع.
- لا تختار موضوعًا مكررًا.
- لا تختلق أخبارًا أو معلومات.
- اعتمد على المعلومات الموجودة في المصادر.
- أعد JSON فقط.
- لا تضف أي نص خارج JSON.

المواضيع السابقة:
{json.dumps(recent or [], ensure_ascii=False)}

المصادر:
{json.dumps(items[:40], ensure_ascii=False)}
"""

    try:

        result = ask_gemini(prompt)

        if result:
            data = clean_json(result)

            if data.get("topic"):
                return data

    except Exception as e:

        print(
            f"[AI] Gemini choose failed: "
            f"{repr(e)}. Using local fallback.",
            flush=True
        )

    return local_choose(
        items,
        recent
    )


# ============================================================
# MAKE CONTENT
# ============================================================

def make_content(
    topic,
    sources,
    language="ar"
):

    prompt = f"""
أنت منتج YouTube محترف لقناة:

نبض المستقبل | Future Pulse 🚀

الموضوع الوحيد للفيديو:
{topic}

اللغة المطلوبة:
{language}

المصادر:
{json.dumps(sources, ensure_ascii=False)[:16000]}

أنشئ محتوى أصليًا ومترابطًا حول الموضوع
المحدد فقط.

قواعد مهمة جدًا:
- استخدم لغة واحدة فقط طوال الفيديو.
- إذا كانت اللغة ar فاكتب السيناريو بالعربية فقط.
- لا تخلط العربية والإنجليزية أو أي لغة أخرى
  داخل السيناريو.
- لا تنتقل إلى موضوع مختلف.
- اجعل جميع المشاهد مرتبطة بالموضوع الرئيسي.
- لا تنسخ النصوص من المصادر.
- لا تقدم ادعاءً كحقيقة إذا لم تدعمه المصادر.
- لا تختلق معلومات.
- اجعل المشاهد مناسبة لما يقال في السيناريو.
- أعد JSON فقط.
- لا تضف Markdown أو شرحًا خارج JSON.

أعد JSON بهذا الشكل:

{{
  "title": "عنوان جذاب وغير مضلل",
  "description": "وصف الفيديو",
  "script": "سكربت مترابط باللغة المطلوبة",
  "scenes": [
    {{
      "text": "جملة قصيرة مرتبطة بالموضوع",
      "visual": "وصف بصري واضح ومحدد للمشهد"
    }}
  ],
  "tags": [
    "كلمة1",
    "كلمة2"
  ]
}}
"""

    try:

        result = ask_gemini(prompt)

        if result:

            data = clean_json(
                result
            )

            title = str(
                data.get("title", "")
            ).strip()

            script = str(
                data.get("script", "")
            ).strip()

            scenes = data.get(
                "scenes",
                []
            )

            tags = data.get(
                "tags",
                []
            )

            description = str(
                data.get("description", "")
            ).strip()

            if title and script:

                # ضمان أن البيانات الأساسية صحيحة
                if not isinstance(scenes, list):
                    scenes = []

                if not isinstance(tags, list):
                    tags = []

                # تنظيف الوسوم
                clean_tags = []

                for tag in tags:
                    tag = str(tag).strip()

                    if tag and tag not in clean_tags:
                        clean_tags.append(tag)

                # حقوق القناة في الوصف
                copyright_line = (
                    "\n\n© نبض المستقبل | "
                    "Future Pulse 🚀"
                )

                if (
                    "نبض المستقبل" not in description
                    and "Future Pulse" not in description
                ):
                    description += copyright_line

                data["title"] = title[:100]
                data["description"] = description
                data["script"] = script
                data["scenes"] = scenes
                data["tags"] = clean_tags[:30]

                return data

    except Exception as e:

        print(
            f"[AI] Gemini content failed: "
            f"{repr(e)}. Using local fallback.",
            flush=True
        )

    return local_content(
        topic,
        sources,
        language
    )
