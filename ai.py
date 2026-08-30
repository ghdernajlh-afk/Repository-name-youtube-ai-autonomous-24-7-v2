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

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash-lite"
)


# ============================================================
# HELPERS
# ============================================================

def clean_json(text):
    if not text:
        raise RuntimeError("Empty AI response.")

    text = text.strip()

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

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


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
مرحبًا بكم في قناة اليوم.

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

إذا أعجبكم الفيديو، تابعوا القناة للمزيد
من المواضيع التقنية والعلمية والمعلومات
المثيرة للاهتمام.

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
        "المتاحة وقت إنشاء الفيديو."
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
        "title": title[:100],
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
أنت مدير قناة YouTube عربية.

اختر فكرة واحدة فقط من المصادر التالية.

الشروط:
- اختر موضوعًا جذابًا ومفيدًا.
- لا تختار موضوعًا مكررًا.
- لا تختلق أخبارًا.
- اعتمد على المعلومات الموجودة.
- أعد JSON فقط.

المواضيع السابقة:
{recent}

المصادر:
{json.dumps(items[:40], ensure_ascii=False)}
"""

    try:

        result = ask_gemini(prompt)

        if result:
            return clean_json(result)

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
أنت منتج YouTube محترف.

الموضوع:
{topic}

اللغة:
{language}

المصادر:
{json.dumps(sources, ensure_ascii=False)[:16000]}

أنشئ محتوى أصليًا.

لا تنسخ النصوص من المصادر.

لا تقدم ادعاءً كحقيقة إذا لم تدعمه
المصادر.

أعد JSON فقط بالشكل التالي:

{{
  "title": "عنوان جذاب وغير مضلل",
  "description": "وصف الفيديو",
  "script": "سكربت عربي",
  "scenes": [
    {{
      "text": "جملة قصيرة",
      "visual": "وصف بصري"
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

            if (
                data.get("title")
                and data.get("script")
            ):
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
