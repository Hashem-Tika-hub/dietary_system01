# دليل نشر الإصدار الثاني في بيئة إنتاج باستخدام Docker

## 1. الهدف وحدود هذا الإعداد

يوفر هذا الدليل طريقة تشغيل الإصدار الثاني من نظام توصية الوجبات على خادم Linux حقيقي باستخدام Docker. يتكون النشر من ثلاث خدمات: **PostgreSQL** لحفظ بيانات الإصدار الثاني، و**FastAPI** لتشغيل API ومحرك التوصية، و**Caddy** لعكس الطلبات وتوفير HTTPS. لا يعيد هذا الإعداد استخدام قاعدة بيانات الإصدار الأول؛ إذ يبقي V1 وV2 منفصلين كي يمكن مقارنة النتائج دون اختلاط الحسابات أو الخطط أو التفاعلات.

> لا يحتوي APK على قاعدة البيانات أو خوارزميات Python وحدها. يجب نشر API V2 أولًا، ثم بناء APK بعنوان V2 باستخدام `API_BASE_URL`.

| العنصر | مسؤولية الإنتاج |
|---|---|
| `postgres` | قاعدة بيانات PostgreSQL خاصة بالإصدار الثاني، ولا تعرض منفذًا إلى الإنترنت. |
| `api` | FastAPI ومحرك التوصية والنماذج المدربة؛ يطبق Alembic قبل التشغيل. |
| `caddy` | المنفذ العام 80 و443، وشهادات HTTPS وعكس الطلبات إلى API. |
| Docker volume | حفظ بيانات PostgreSQL وشهادات Caddy عند إعادة تشغيل الحاويات. |
| `.env.production` | الأسرار وإعدادات النطاق وكلمة مرور قاعدة البيانات؛ لا يدخل GitHub. |

---

## 2. متطلبات الخادم والشبكة

اختر خادم Ubuntu حديثًا ذو عنوان IP عام ثابت. يحتاج النشر إلى صلاحية SSH ومجال فرعي مخصص، مثل `api-v2.example.com`. قبل تشغيل Caddy، أنشئ سجل DNS من النوع `A` يربط النطاق بعنوان IP العام للخادم. يجب أن تكون المنافذ `80/TCP` و`443/TCP` متاحة من الإنترنت حتى يتمكن Caddy من إصدار وتجديد شهادة HTTPS تلقائيًا.

| المتطلب | الحد العملي للمشروع | السبب |
|---|---|---|
| نظام التشغيل | Ubuntu Server حديث أو Linux متوافق مع Docker | تشغيل Docker Compose وCaddy. |
| الذاكرة | 2 GB كحد أدنى، و4 GB أفضل | تحميل pandas وscikit-learn ونماذج التوصية. |
| المنافذ العامة | 80 و443 فقط | وصول HTTPS وإصدار الشهادة. |
| قاعدة البيانات | PostgreSQL داخل Docker volume منفصل | فصل بيانات V2 عن V1 وإتاحة النسخ الاحتياطي. |
| اسم النطاق | نطاق فرعي مستقل لـV2 | منع خلط APK الجديد بخادم V1. |

على الخادم، استخدم مستخدمًا غير جذري مع مفاتيح SSH، ثم ثبّت Docker Engine وDocker Compose Plugin باتباع [الدليل الرسمي لـDocker على Ubuntu][1]. لا تفتح منفذ PostgreSQL `5432` للعامة؛ فخدمة API هي العميل الوحيد لقاعدة البيانات داخل شبكة Docker الخاصة.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
# أكمل تثبيت Docker Engine وDocker Compose Plugin وفق الدليل الرسمي.
docker --version
docker compose version
```

بعد تثبيت Docker، اضبط الجدار الناري وفق بيئة الخادم لديك بحيث يسمح فقط بـSSH ومنفذي HTTP وHTTPS. لا تستخدم كلمات مرور افتراضية ولا تشغل API بوضع `--reload` في الإنتاج.

---

## 3. الملفات المضافة للمستودع

أضيفت ملفات التشغيل التالية إلى جذر المشروع. لا تحفظ هذه الملفات أسرارًا حقيقية.

| الملف | الاستخدام |
|---|---|
| `Dockerfile` | بناء صورة Python 3.12 للإنتاج وتشغيل API بمستخدم غير جذري. |
| `docker-compose.production.yml` | تعريف PostgreSQL وAPI وCaddy والشبكات والـvolumes. |
| `docker/entrypoint.sh` | تطبيق `alembic upgrade head` قبل بدء Uvicorn. |
| `docker/Caddyfile` | HTTPS تلقائي وعكس الطلبات من النطاق إلى خدمة API. |
| `.dockerignore` | منع الأسرار وSQLite المحلية وملفات التطوير من دخول image. |
| `.env.production.example` | قالب المتغيرات اللازمة؛ ينسخ على الخادم فقط. |
| `app/lib/core/constants.dart` | يسمح بحقن عنوان V2 وقت بناء APK بـ`--dart-define`. |

التشغيل في الحاوية يقرأ أصول النماذج الموجودة في `models/` وكتالوج الطعام المنظف في `data/`. لا ينسخ قاعدة SQLite المحلية إلى الصورة؛ فالخدمة في الإنتاج تستخدم PostgreSQL فقط.

---

## 4. تجهيز ملفات الإنتاج على الخادم

انسخ المستودع إلى الخادم ثم انتقل إلى فرع الإصدار الثاني. يفضّل تثبيت commit محدد عند العرض الأكاديمي حتى تكون النتيجة قابلة لإعادة الإنتاج.

```bash
git clone https://github.com/Hashem-Tika-hub/dietary_system01.git
cd dietary_system01
git checkout feat/feedback-cf-swagger-performance
# اختياري بعد مراجعة آخر commit:
git log -1 --oneline
```

أنشئ ملف الأسرار المحلي من القالب واضبط أذوناته. استخدم قيم hex مولدة عشوائيًا؛ فهي آمنة كذلك داخل URL الخاص بقاعدة البيانات ولا تسبب مشكلة مع رموز مثل `@` أو `:`.

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32   # استخدم الناتج لكلمة POSTGRES_PASSWORD
openssl rand -hex 32   # استخدم الناتج لـSECRET_KEY
nano .env.production
```

مثال توضيحي لملف `.env.production`، مع استبدال القيم بالكامل وعدم رفعه إلى GitHub:

```dotenv
APP_VERSION=v2.0.0
API_DOMAIN=api-v2.example.com
POSTGRES_DB=dietary_v2
POSTGRES_USER=dietary_v2
POSTGRES_PASSWORD=<HEX_LONG_RANDOM_VALUE>
SECRET_KEY=<HEX_LONG_RANDOM_VALUE>
USDA_API_KEY=<OPTIONAL_SERVER_ONLY_KEY>
ALLOWED_ORIGINS=https://api-v2.example.com
```

| متغير البيئة | ملاحظة أمنية |
|---|---|
| `POSTGRES_PASSWORD` | كلمة مرور قاعدة البيانات ولا تدخل APK أو Git. |
| `SECRET_KEY` | مفتاح توقيع JWT؛ تغييره يبطل الجلسات الحالية. |
| `USDA_API_KEY` | يستخدم في عمليات الاستيراد على الخادم فقط؛ لا يرسل للعميل. |
| `API_DOMAIN` | يجب أن يطابق نطاق DNS الذي يشير إلى عنوان الخادم. |
| `ALLOWED_ORIGINS` | يخص تطبيقات الويب وSwagger؛ Flutter native لا يعتمد على CORS. |

---

## 5. بدء الخدمات وترحيل قاعدة البيانات

يمرر الخيار `--env-file` متغيرات قاعدة البيانات إلى Docker Compose، بينما يقرأ API الملف نفسه عبر `env_file`. لا تشغل `alembic upgrade head` يدويًا داخل API في كل مرة؛ تنفذ `docker/entrypoint.sh` هذا الأمر قبل تشغيل الخدمة، ويتوقف التطبيق إن فشل الترحيل بدل العمل على مخطط قديم.

```bash
docker compose \
  --env-file .env.production \
  -f docker-compose.production.yml \
  up -d --build
```

راقب بدء الخدمات حتى تنجح ترحيلات Alembic وتصبح حالة API سليمة:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs -f api
docker compose --env-file .env.production -f docker-compose.production.yml logs -f caddy
```

تحقق بعد اكتمال DNS وHTTPS:

```bash
curl -fsS https://api-v2.example.com/health
curl -I https://api-v2.example.com/docs
```

الاستجابة المتوقعة لمسار الصحة تشمل `api: ok` وبيان حالة النماذج. إذا قالت API إن قاعدة البيانات غير جاهزة، راجع `docker compose ... logs api` ولا تعدل الجداول يدويًا. إدارة المخطط في المشروع مخصصة لـAlembic، وتؤكد وثائق المشروع وجوب تشغيل `alembic upgrade head` قبل بدء API [2].

---

## 6. بناء APK متصل بالإصدار الثاني

أصبح عنوان API في Flutter قابلًا للضبط وقت البناء. يظل العنوان السابق قيمة افتراضية للتوافق، لكن APK V2 يجب بناؤه مع عنوان النطاق الجديد. نفذ الأمر من مجلد `app/` على جهاز التطوير:

```bash
cd app
flutter clean
flutter pub get
flutter build apk --release \
  --build-name=2.0.0 \
  --build-number=2 \
  --dart-define=API_BASE_URL=https://api-v2.example.com
```

ينتج الملف عادةً في:

```text
app/build/app/outputs/flutter-apk/app-release.apk
```

لا تستخدم `http://` في APK الإنتاج، ولا تستخدم `localhost` أو IP خاص بالشبكة المحلية. اختبر النطاق من متصفح الهاتف أولًا عبر `https://api-v2.example.com/docs`، ثم ثبّت APK. يوفر Flutter توثيقًا رسميًا لبناء وإصدار APK لتطبيقات Android [3].

---

## 7. مقارنة V1 وV2 دون خلط البيانات

لإجراء مقارنة عادلة، أبقِ APK V1 مرتبطًا بخادم V1 أو بالعنوان الافتراضي السابق، وابنِ APK V2 باستخدام `--dart-define` المشار إليه أعلاه. لا تجعل الإصدارين يتصلان بقاعدة PostgreSQL نفسها، ولا تعيد استخدام `POSTGRES_DB` الخاص بـV1.

| عنصر المقارنة | V1 | V2 |
|---|---|---|
| عنوان API | رابط V1 الحالي | `https://api-v2.example.com` |
| قاعدة البيانات | قاعدة V1 الحالية | `dietary_v2` داخل Docker volume منفصل |
| APK | build-number قديم | `build-number=2` و`API_BASE_URL` جديد |
| التحقق من الملف | الحدود السابقة | تحقق API وقاعدة البيانات، بما في ذلك تحديث الوزن/الطول الجزئي |
| التوصيات | السلوك السابق | التفاعل الصريح وCF المشروط والتنويع والتفسير بحسب الإصدار V2 |

يمكن اختبار الفرق من Swagger أو من التطبيق عبر السيناريوهات نفسها: مستخدم جديد، حساسية متعددة، إدخال عمر مفرط، محاولة تحديث وزن غير متسق مع الطول، وخطة أسبوعية. احفظ لقطات شاشة واستجابات JSON من كلا الإصدارين لاستخدامها في تقرير التخرج.

---

## 8. النسخ الاحتياطي والتحديث والرجوع

أنشئ نسخًا احتياطية دورية من قاعدة V2 قبل كل تحديث فيه ترحيل جديد. مثال لنسخة محلية على الخادم:

```bash
mkdir -p backups
docker compose --env-file .env.production -f docker-compose.production.yml \
  exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "backups/dietary_v2_$(date +%F_%H%M).sql"
```

عند تحديث الشفرة، راجع التغييرات ثم أعد بناء الحاوية. لا تنفذ تحديثًا عشوائيًا من `main` أثناء العرض أو التقييم؛ استخدم branch أو tag أو commit محددًا.

```bash
git fetch origin
git checkout feat/feedback-cf-swagger-performance
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

الرجوع في الشفرة لا يعني دائمًا أن الرجوع في قاعدة البيانات آمن؛ فبعض الترحيلات قد تحتاج خطة استعادة. قبل أي downgrade، خذ نسخة احتياطية واختبر الاسترجاع في بيئة منفصلة. لا تستخدم `alembic stamp head` لتجاوز ترحيل غير معروف في الإنتاج [2].

---

## 9. قائمة تحقق قبل مشاركة APK V2

| التحقق | المطلوب |
|---|---|
| DNS | `api-v2` يشير إلى عنوان الخادم العام. |
| HTTPS | فتح `/docs` من الهاتف بلا تحذير شهادة. |
| API | `/health` يستجيب بنجاح بعد ترحيلات Alembic. |
| قاعدة البيانات | منفصلة عن V1 ولا يوجد منفذ 5432 مكشوف للعامة. |
| الأسرار | `.env.production` غير متعقب وأذوناته `600`. |
| APK | بني باستخدام `--dart-define=API_BASE_URL=https://api-v2...`. |
| الاختبار | التسجيل وتسجيل الدخول والملف والتوصية والخطة تعمل من هاتف حقيقي. |
| النسخ الاحتياطي | نسخة PostgreSQL محفوظة قبل تحديثات المخطط. |

---

## المراجع

[1] [Docker Docs — Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) — التثبيت الرسمي لـDocker Engine وCompose Plugin على Ubuntu.

[2] [وثيقة ترحيلات قاعدة بيانات المشروع](database-migrations.md) — سياسة Alembic الخاصة بالمشروع وخطوات الترحيل الآمن.

[3] [Flutter Docs — Build and release an Android app](https://docs.flutter.dev/deployment/android) — الدليل الرسمي لبناء وإصدار APK على Android.
