# 📦 دليل المتطلبات والإعداد (Requirements & Setup Guide)
### Meta Business Suite Inbox Auto-Responder & Unread Restorer

هذا الملف يحتوي على كافة المتطلبات البرمجية والبيئية لتشغيل الاسكريبت بنجاح على نظامك (Linux / Windows / macOS).

---

## 1. المتطلبات الأساسية للنظام (System Requirements)

| المتطلب | الإصدار الأدنى | الوصف |
|---------|----------------|-------|
| **Python** | 3.9 أو أحدث | لغة البرمجة الأساسية لتشغيل الاسكريبت والربط مع المتصفح. |
| **Google Chrome** | أي إصدار حديث | المتصفح الذي يعمل عليه حساب Meta Business Suite. |
| **Playwright** | 1.40.0+ | المكتبة المسؤولة عن الاتصال بـ Chrome عبر بروتوكول CDP. |
| **Git** | أي إصدار | لإدارة ومزامنة كود المشروع مع GitHub. |

---

## 2. تثبيت حزم بايثون (Python Packages)

المكتبة الوحيدة المطلوبة هي **Playwright**.

### للتثبيت على نظام Linux:
```bash
pip install playwright --break-system-packages
```
أو عبر ملف `requirements.txt`:
```bash
pip install -r requirements.txt --break-system-packages
```

### للتثبيت على نظام Windows / macOS:
```bash
pip install playwright
```
أو:
```bash
pip install -r requirements.txt
```

> **ملاحظة هامة:** لا داعي لتنزيل متصفحات إضافية لـ Playwright عبر `playwright install`؛ لأن الاسكريبت يتصل مباشرة بمتصفح Chrome المثبت لديك على الجهاز.

---

## 3. إعداد Google Chrome للتحكم عن بعد (Remote Debugging Port 9222)

لكي يتمكن اسكريبت بايثون من الاتصال بالمتصفح وحقن واجهة التحكم (HUD) والأتمتة، يجب تشغيل Chrome مع تفعيل المنفذ `9222`:

### أ) على نظام لينكس (Linux):
أغلق جميع نوافذ Chrome تماماً أولاً، ثم نفّذ:
```bash
google-chrome --remote-debugging-port=9222
```

### ب) على نظام ويندوز (Windows CMD / PowerShell):
أغلق جميع نوافذ Chrome تماماً، ثم نفّذ:
```cmd
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-dev-profile"
```

### ج) على نظام ماك (macOS):
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

---

## 4. التحقق من جاهزية الاتصال (Verification)

للتأكد من أن Chrome يعمل بمنفذ التحكم وجاهز للاتصال، يمكنك فحص الرابط التالي في المتصفح أو عبر Terminal:
```bash
curl http://localhost:9222/json/version
```
إذا أعاد بيانات JSON تحتوي على إصدار Chrome ومعرّف WebSocket، فهذا يعني أن المتصفح جاهز 100%.

---

## 5. التشغيل واستخدام كود Tampermonkey (اختياري)

إذا كنت ترغب في تشغيل الاسكريبت كـ **UserScript** مباشر داخل المتصفح بدون تشغيل بايثون:
1. ثبّت إضافة **Tampermonkey** في متصفحك من متجر Chrome.
2. أنشئ اسكريبت جديد في الإضافة.
3. انسخ والصق محتوى ملف [`meta_inbox_userscript.user.js`](./meta_inbox_userscript.user.js).
4. احفظ الاسكريبت، وافتح صفحة Meta Business Suite وسيعمل مباشرة مع الواجهة الزجاجية المتحركة!

---

## 6. استكشاف الأخطاء الشائعة (Troubleshooting)

- **خطأ: `Connection Refused` أو تعذر الاتصال بالمتصفح:**
  - تأكد من إغلاق كافة عمليات Chrome في الخلفية قبل تشغيله بأمر `--remote-debugging-port=9222`.
- **الواجهة لم تظهر على الصفحة:**
  - تأكد من أن التبويب المفتوح هو `https://business.facebook.com/latest/inbox/*`.
  - اضغط `Ctrl + F5` لتحديث الصفحة وسيعيد الاسكريبت حقن الواجهة تلقائياً.
- **إيقاف الطوارئ السريع:**
  - يمكنك إيقاف الأتمتة فوراً بالضغط على مفتاح **[Escape]** داخل المتصفح، أو **[Ctrl + C]** في الطرفية.
