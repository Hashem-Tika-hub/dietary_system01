# نشر نظام التوصية الغذائي على Railway

## الهدف ونطاق النشر

يعتمد مسار النشر المعتمد للمشروع على **Railway** بدل إدارة خادم Docker خاص. ينشر Railway خدمة FastAPI من مستودع GitHub، ويضيف خدمة PostgreSQL مُدارة داخل المشروع نفسه. يحتفظ المستودع بملفات التطبيق والاختبارات وقاعدة الكتالوج المرجعية فقط، ولا يحتوي Docker Compose أو Caddy أو ملفات أسرار إنتاجية.

| المكوّن | المسؤولية |
|---|---|
| Railway API Service | تشغيل FastAPI ومحرك التوصية من المستودع. |
| Railway PostgreSQL Service | قاعدة التشغيل القابلة للكتابة للحسابات والوجبات والخطط والتغذية الراجعة. |
| `data/catalog/food_catalog_reference.sqlite3` | نسخة كتالوج مرجعية للمراجعة والتهيئة فقط؛ لا تحتوي بيانات مستخدم وليست قاعدة API تشغيلية. |
| Flutter APK | يتصل بعنوان HTTPS العام لخدمة API. |

> SQLite المحلية مخصصة للتطوير والاختبارات ونسخة الكتالوج المرجعية. الإنتاج يستخدم PostgreSQL فقط.

## 1. إنشاء خدمات Railway

أنشئ مشروعًا جديدًا في Railway، ثم أضف خدمة من مستودع GitHub `Hashem-Tika-hub/dietary_system01`. أضف بعد ذلك خدمة **PostgreSQL** من لوحة المشروع. توفر خدمة PostgreSQL متغير `DATABASE_URL` قابلًا لاستخدامه من خدمات المشروع نفسها [1].

أنشئ نطاقًا عامًا لخدمة API من قسم **Networking**؛ لا تجعل قاعدة PostgreSQL عامة، إذ تتصل API بها عبر الشبكة الداخلية للمشروع [1] [2].

## 2. متغيرات API في Railway

أضف المتغيرات الآتية من تبويب **Variables** لخدمة API. لا تضع قيمها في Git أو في APK. يمكن إنشاء متغير مرجعي بين خدمتين بصيغة Railway، مثل `DATABASE_URL=${{Postgres.DATABASE_URL}}` بعد استبدال `Postgres` باسم خدمة القاعدة لديك [2].

| المتغير | القيمة أو المصدر |
|---|---|
| `DATABASE_URL` | مرجع إلى `DATABASE_URL` لخدمة PostgreSQL في Railway. |
| `SECRET_KEY` | قيمة عشوائية قوية مولدة مرة واحدة لخدمة API. |
| `ALLOWED_ORIGINS` | نطاقات تطبيقات الويب الموثوقة فقط؛ Flutter native لا يحتاج CORS. |
| `USDA_API_KEY` | اختياري لعمليات الاستيراد الإدارية فقط، ولا يرسل لتطبيق الهاتف. |

اجعل `SECRET_KEY` متغيرًا مختومًا (**Sealed Variable**) إن كانت الميزة متاحة في حسابك؛ تحفظ Railway قيم المتغير المختوم للتشغيل من دون عرضه في الواجهة أو واجهة API [2].

## 3. إعداد أوامر النشر

من إعدادات خدمة API في Railway اضبط الأوامر التالية. تستخدم Railway أمر بدء للخدمة، وتدعم أمرًا قبل النشر لإجراء عمليات مثل ترحيل قاعدة البيانات [3].

| إعداد Railway | الأمر |
|---|---|
| **Pre-deploy Command** | `alembic upgrade head && python scripts/seed_runtime_catalog.py` |
| **Start Command** | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| **Healthcheck Path** | `/health` |

أمر ما قبل النشر ينشئ أو يحدّث مخطط PostgreSQL ثم ينسخ **جداول الكتالوج فقط** من النسخة المرجعية إلى قاعدة التشغيل. لا ينقل جداول المستخدمين أو بياناتهم. يفشل النشر بوضوح إذا أخفق الترحيل أو مزامنة الكتالوج بدل تشغيل API على قاعدة غير جاهزة.

## 4. نشر واختبار الخدمة

بعد حفظ المتغيرات والأوامر، نفذ نشرًا من Railway وتابع السجل. يجب أن تظهر ترحيلات Alembic ورسالة `Runtime catalog synchronized` قبل بدء Uvicorn. بعد نجاح الصحة، تحقق من API عبر النطاق العام:

```bash
curl -fsS https://YOUR_RAILWAY_DOMAIN/health
curl -I https://YOUR_RAILWAY_DOMAIN/docs
```

اختبر بعد ذلك التسجيل وتسجيل الدخول وملف المستخدم والوجبات والخطة الأسبوعية من Swagger أو تطبيق Flutter. لا تعتبر النشر مكتملًا قبل اختبار الاتصال من هاتف حقيقي عبر HTTPS.

## 5. بناء APK للإنتاج

استبدل `YOUR_RAILWAY_DOMAIN` بعنوان API العام في Railway عند إنشاء APK:

```bash
cd app
flutter pub get
flutter build apk --release \
  --build-name=2.0.0 \
  --build-number=2 \
  --dart-define=API_BASE_URL=https://YOUR_RAILWAY_DOMAIN
```

لا تستخدم `localhost` أو عنوان شبكة محلية أو `http://` في APK الإنتاجي.

## 6. النسخ الاحتياطي وحدود البيانات

فعّل النسخ الاحتياطي لقاعدة PostgreSQL واختبر الاستعادة في بيئة منفصلة قبل العرض النهائي. توصي وثائق Railway بالنسخ الاحتياطي الدوري ومراقبة صحة قواعد الإنتاج [1]. لا ترفع عمليات النسخ الاحتياطي أو `.env` أو بيانات مستخدم أو قواعد تشغيل قابلة للكتابة إلى Git.

يحفظ المشروع `data/catalog/food_catalog_reference.sqlite3` فقط بوصفه مصدر مراجعة للكتالوج. غياب أدلة حساسية مكتملة لا يعد دليلًا على أمان الطعام لمستخدم أعلن حساسية، وسياسة استبعاد مؤشرات الخنزير أو الكحول ليست اعتماد حلال رسميًا.

## المراجع

[1]: https://docs.railway.com/databases/postgresql "Railway Docs — PostgreSQL"
[2]: https://docs.railway.com/variables "Railway Docs — Using Variables"
[3]: https://docs.railway.com/config-as-code/reference "Railway Docs — Start and pre-deploy commands"
