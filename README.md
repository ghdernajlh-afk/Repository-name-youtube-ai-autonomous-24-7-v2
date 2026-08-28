# YouTube AI Autonomous 24/7

وكيل YouTube ذاتي التشغيل مع لوحة تحكم ومعالج إعداد مرة واحدة.

## ماذا يفعل؟
- يجلب أفكاراً حديثة من RSS (Google News RSS) دون الحاجة إلى مفتاح بحث منفصل.
- يختار فكرة باستخدام نموذج OpenAI.
- يجري بحثاً نصياً عبر مصادر عامة، ثم يكتب سكربتاً أصلياً.
- يولد صوتاً عربياً عبر Edge TTS.
- يبني فيديو MP4 متعدد البطاقات النصية مع FFmpeg.
- ينشئ Thumbnail محلياً.
- يرفع الفيديو إلى YouTube كـ Private.
- ينتظر/يتابع حالة الرفع.
- يتيح لك زر Publish مستقل.
- يحتفظ بسجل jobs وقاعدة بيانات SQLite.
- يمكن تشغيله كخدمة 24/7 عبر Docker أو run script.
- يمنع التكرار عبر سجل المواضيع.
- يطبق حدّاً لعدد الوظائف اليومية.

## مهم
لا يوجد برنامج يمكنه الوصول إلى حساب YouTube أو OpenAI بدون تفويضك. هذه النسخة لا تطلب تعديل الكود:
كل ما تحتاجه هو تشغيل Setup Wizard وإدخال OpenAI API key ووضع ملف Google OAuth الذي تنزله من Google Cloud.

## تشغيل Windows
1. ثبّت Python 3.11+ وFFmpeg.
2. شغّل `setup.bat`.
3. شغّل `run.bat`.
4. افتح http://127.0.0.1:8000/setup
5. أكمل المعالج.
6. من Dashboard فعّل AutoPilot.
7. أول رفع سيطلب OAuth من Google.

## تشغيل macOS/Linux
1. ثبّت Python 3.11+ وFFmpeg.
2. `chmod +x setup.sh run.sh`
3. `./setup.sh`
4. `./run.sh`
5. افتح http://127.0.0.1:8000/setup

## YouTube OAuth
في Google Cloud:
- أنشئ مشروعاً.
- فعّل YouTube Data API v3.
- أنشئ OAuth Client من نوع Desktop App.
- ضع JSON في `credentials/client_secret.json`.

لا تضع كلمة مرور Google في البرنامج.

## سياسة التشغيل
الافتراضي:
- إنشاء المحتوى: ON
- الرفع: Private
- النشر العام: OFF

يمكنك تفعيل Auto-Publish من لوحة التحكم، لكن يفضل البدء بـ Private حتى تتأكد من جودة المحتوى.

## ملاحظة الحصص
YouTube لديه حصص منفصلة لبعض الطرق الحديثة مثل search.list وvideos.insert، لذلك الوكيل يحدّ من البحث والرفع ولا يرسل طلبات بلا حدود.
