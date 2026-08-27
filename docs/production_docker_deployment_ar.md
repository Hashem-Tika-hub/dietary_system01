# دليل نشر نظام التوصية الغذائي في بيئة إنتاج باستخدام Docker

## 1. الهدف وحدود البيانات

يشرح هذا الدليل تشغيل API نظام التوصية الغذائي على خادم Linux باستخدام Docker Compose. يتكون النشر من **PostgreSQL** لحفظ البيانات التشغيلية، و**FastAPI** لتقديم الـ API ومحرك التوصية، و**Caddy** لعكس الطلبات وتوفير HTTPS. تستخدم بيئة الإنتاج قاعدة مستقلة عن أي نسخة قديمة للتطبيق، فلا تختلط الحسابات أو الخطط أو التفاعلات بين الإصدارات.

| الأصل | الاستخدام المسموح |
|---|---|
| PostgreSQL داخل Docker volume | قاعدة الإنتاج القابلة للكتابة: الحسابات، سجلات الوجبات، الخطط الأسبوعية، والتغذية الراجعة الصريحة. |
| `data/catalog/food_catalog_reference.sqlite3` داخل Git | **نسخة مرجعية للكتالوج فقط** للمراجعة اليدوية وإعادة تهيئة قاعدة تشغيل جديدة. لا تحوي جداول أو بيانات مستخدمين، وليست قاعدة API تشغيلية. |
| SQLite المحلية `data/dietary.db` | تطوير واختبارات محلية فقط. لا تنسخ إلى صورة Docker ولا تنشر إلى الإنتاج. |
| `.env.production` | أسرار الخادم والنطاق وكلمة مرور PostgreSQL. يبقى خارج GitHub دائمًا. |

> لا يعني وجود كتالوج مرجعي أن بيانات الحساسية مكتملة أو أن الطعام معتمد حلالًا. الأدلة الناقصة لا تعد آمنة لمستخدم صرّح بحساسية، كما أن سياسة الاستبعاد الحالية لا تساوي شهادة حلال.

## 2. تصميم الخدمات

| الخدمة | المسؤولية | التعرض للشبكة |
|---|---|---|
| `postgres` | PostgreSQL 16 لتشغيل النظام متعدد المستخدمين. | شبكة Docker الداخلية فقط؛ لا يُنشر المنفذ `5432`. |
| `api` | FastAPI وAlembic ومزامنة الكتالوج ومحرك التوصية. | منفذ داخلي `8000`. |
| `caddy` | HTTPS والواجهة العامة لعكس الطلبات إلى API. | المنفذان العامان `80` و`443` فقط. |

تُطبق حاوية API `alembic upgrade head` أولًا، ثم تشغّل `scripts/seed_runtime_catalog.py` لمزامنة **جداول الكتالوج فقط** من النسخة المرجعية إلى PostgreSQL. لذلك تكون قاعدة جديدة جاهزة لطلبات الطعام والتوصية بعد بدء الخدمات، من دون إدخال بيانات مستخدم في Git أو في ملف SQLite المرجعي.

## 3. متطلبات الخادم

استخدم خادم Ubuntu حديثًا مع Docker Engine وDocker Compose Plugin ومفتاح SSH ومجال فرعي مثل `api-v2.example.com`. قبل البدء، أنشئ سجل DNS من النوع `A` يشير إلى عنوان الخادم العام، وافتح `80/TCP` و`443/TCP` فقط إضافة إلى SSH وفق سياسة المؤسسة. لا تفتح PostgreSQL للعامة.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
docker --version
docker compose version
```

اتبع [دليل Docker الرسمي لتثبيت Docker Engine على Ubuntu][1] عند الحاجة. لا تشغّل Uvicorn بوضع `--reload` في الإنتاج، ولا تستخدم كلمات مرور أو مفاتيح افتراضية.

## 4. تجهيز إصدار قابل لإعادة الإنتاج

انسخ المستودع وثبّت commit مدمجًا معروفًا عند العرض الأكاديمي أو النشر الفعلي.

```bash
git clone https://github.com/Hashem-Tika-hub/dietary_system01.git
cd dietary_system01
git checkout main
git pull --ff-only
git log -1 --oneline
```

أنشئ ملف الأسرار المحلي من القالب، واضبط أذوناته، ثم استبدل كل قيمة مكانية. يولّد أمر `openssl rand -hex 32` قيمة مناسبة لكل من كلمة مرور PostgreSQL و`SECRET_KEY` لأن صيغة hex لا تحتاج ترميزًا إضافيًا داخل رابط الاتصال.

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
nano .env.production
```

| المتغير | الغرض |
|---|---|
| `POSTGRES_DB` | اسم قاعدة PostgreSQL التشغيلية، مثل `dietary_v2`. |
| `POSTGRES_USER` | مستخدم قاعدة مستقل للإصدار. |
| `POSTGRES_PASSWORD` | كلمة مرور طويلة عشوائية لا تدخل Git أو تطبيق Flutter. |
| `SECRET_KEY` | مفتاح توقيع JWT؛ تدويره يُبطل الجلسات الحالية. |
| `API_DOMAIN` | النطاق العام الذي يشير DNS الخاص به إلى الخادم. |
| `ALLOWED_ORIGINS` | أصول متصفح موثوقة فقط؛ Flutter native لا يعتمد على CORS. |

مثال **توضيحي فقط** بلا قيم حقيقية:

```dotenv
APP_VERSION=v2.0.0
API_DOMAIN=api-v2.example.com
POSTGRES_DB=dietary_v2
POSTGRES_USER=dietary_v2
POSTGRES_PASSWORD=<LONG_RANDOM_HEX_VALUE>
SECRET_KEY=<LONG_RANDOM_HEX_VALUE>
ALLOWED_ORIGINS=https://api-v2.example.com
```

## 5. التحقق والبدء

يفرض ملف Compose وجود متغيرات PostgreSQL الأساسية والنطاق. تحقق من سلامة التوسيع قبل إنشاء أي حاوية، ثم ابدأ الخدمات.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml config -q
docker compose \
  --env-file .env.production \
  -f docker-compose.production.yml \
  up -d --build
```

راقب الحالة والسجلات. يجب أن يحتوي سجل API في أول بدء أو بعد تحديث الكتالوج على `Runtime catalog synchronized`، بعد نجاح ترحيلات Alembic. لا تعدّل الجداول يدويًا؛ Alembic هو مالك المخطط.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs -f api
curl -fsS https://api-v2.example.com/health
curl -I https://api-v2.example.com/docs
```

إذا أخفقت الترحيلات أو المزامنة، لا تبدأ API في حالة مخطط جزئية. راجع السجل، صحّح سبب الفشل، ثم أعد تشغيل الخدمات. للحصول على سياسة الترحيلات، راجع [وثيقة ترحيلات قاعدة بيانات المشروع][2].

## 6. النسخ الاحتياطي والتحديث والاسترجاع

أنشئ نسخة PostgreSQL احتياطية قبل أي تحديث قد يتضمن ترحيلًا، واحفظها في تخزين آمن خارج الخادم عند الإمكان. لا تحفظ ملفات النسخ في Git.

```bash
mkdir -p backups
docker compose --env-file .env.production -f docker-compose.production.yml \
  exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "backups/dietary_v2_$(date +%F_%H%M).sql"
```

عند التحديث، ثبّت commit أو tag معروفًا، خذ نسخة احتياطية، ثم أعد بناء الحاويات. الرجوع في الشفرة لا يجعل الرجوع في مخطط قاعدة البيانات آمنًا تلقائيًا؛ اختبر الاستعادة في بيئة منفصلة قبل أي عملية downgrade.

```bash
git fetch origin
git checkout main
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

## 7. بناء APK متصل ببيئة الإنتاج

لا يحتوي APK وحده قاعدة البيانات أو خوارزميات Python. يجب نشر API أولًا، ثم بناء التطبيق بعنوان HTTPS العام.

```bash
cd app
flutter pub get
flutter build apk --release \
  --build-name=2.0.0 \
  --build-number=2 \
  --dart-define=API_BASE_URL=https://api-v2.example.com
```

اختبر `/docs` من الهاتف أولًا، ثم ثبّت APK. لا تستخدم `localhost` أو عنوان شبكة محلي أو `http://` في APK الإنتاج. توضح [وثائق Flutter الرسمية][3] خطوات بناء وإصدار APK.

## 8. قائمة تحقق قبل النشر

| التحقق | المطلوب |
|---|---|
| قاعدة البيانات | PostgreSQL منفصلة عن أي إصدار سابق، ولا يوجد منفذ `5432` مكشوف للعامة. |
| التهيئة | ظهرت ترحيلات Alembic ورسالة مزامنة الكتالوج في سجل API. |
| الخصوصية | `.env.production` بصلاحية `600` وغير متعقب؛ لا توجد SQLite تشغيلية أو بيانات مستخدم في Git. |
| API | `/health` و`/docs` يعملان عبر HTTPS. |
| النسخ الاحتياطي | نسخة PostgreSQL حديثة محفوظة قبل تحديث المخطط. |
| تطبيق الهاتف | APK بُني باستخدام `API_BASE_URL` الإنتاجي واختُبر بتسجيل مستخدم ووجبة وخطة. |

## المراجع

[1]: https://docs.docker.com/engine/install/ubuntu/ "Docker Docs — Install Docker Engine on Ubuntu"
[2]: database-migrations.md "وثيقة ترحيلات قاعدة بيانات المشروع"
[3]: https://docs.flutter.dev/deployment/android "Flutter Docs — Build and release an Android app"
