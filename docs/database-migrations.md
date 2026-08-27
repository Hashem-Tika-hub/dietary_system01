# ترحيلات قاعدة البيانات وتهيئة الكتالوج

يستخدم المشروع **Alembic** لإدارة مخطط قاعدة البيانات. لا ينشئ الخادم الجداول أو يغيرها تلقائيًا عند بدء API؛ يجب تطبيق الترحيلات بوضوح. يدعم المشروع محركين فقط: **SQLite** للتطوير والاختبارات المحلية، و**PostgreSQL** لقاعدة التشغيل الإنتاجية متعددة المستخدمين.

> الترحيل ينشئ المخطط فقط. لمزامنة كتالوج الطعام في قاعدة تشغيل جديدة، شغّل أداة التهيئة بعد نجاح Alembic. لا تنسخ نسخة SQLite المرجعية إلى قاعدة تشغيل؛ الأداة تنقل جداول الكتالوج فقط إلى `DATABASE_URL`.

## قاعدة جديدة أو فارغة

بعد ضبط `DATABASE_URL` عند الحاجة، طبّق المخطط ثم حمّل نسخة الكتالوج المرجعية.

```bash
alembic upgrade head
python scripts/seed_runtime_catalog.py
python run_api.py
```

ينشئ Alembic جداول التشغيل (`users` و`meal_logs` و`weekly_plans` و`user_food_feedback`) وجداول كتالوج الطعام والحساسية و`alembic_version`. تستورد أداة التهيئة من `data/catalog/food_catalog_reference.sqlite3` جداول الطعام والمغذيات والحصص والمصادر والحساسيات فقط. لا تحتوي النسخة المرجعية على بيانات مستخدم، ولا تضيفها الأداة أو تحذفها.

في Railway، يضبط هذا التسلسل في **Pre-deploy Command** قبل بدء FastAPI. راجع [دليل Railway للنشر](production_railway_deployment_ar.md) لإعداد قاعدة PostgreSQL ومتغيرات البيئة وأمر البدء.

| البيئة | `DATABASE_URL` | الاستخدام |
|---|---|---|
| تطوير محلي | `sqlite:///./data/dietary.db` أو القيمة الافتراضية | تطوير واختبارات محلية. |
| اختبار PostgreSQL | `postgresql+psycopg://...` | ترحيلات وتكامل ضد قاعدة مؤقتة قابلة للرمي. |
| إنتاج Railway | مرجع Railway إلى خدمة PostgreSQL | قاعدة تشغيل API، غير متعقبة في Git. |

## قاعدة موجودة مسبقًا

لا تشغّل `alembic stamp head` تلقائيًا على قاعدة إنتاج أو قاعدة مجهولة المخطط. أنشئ نسخة احتياطية، ثم تحقق يدويًا من تطابق الجداول والأعمدة مع الإصدار التاريخي قبل تسجيلها كقاعدة مُدارة. إذا اختلف المخطط، أنشئ migration مناسبًا أو انقل البيانات في بيئة اختبار؛ لا تعدّل الجداول يدويًا أثناء تشغيل التطبيق.

```bash
# مثال SQLite محلي فقط؛ لا تستخدمه لبيانات إنتاج PostgreSQL.
cp data/dietary.db data/backups/dietary-before-alembic.db
alembic stamp 786a3450d5e4
alembic current
```

## أوامر المطور اليومية

```bash
# تطبيق جميع الترحيلات
alembic upgrade head

# مزامنة كتالوج Git المرجعي مع قاعدة التشغيل المحددة في DATABASE_URL
python scripts/seed_runtime_catalog.py

# عرض الإصدار الحالي
alembic current

# إنشاء revision بعد تعديل SQLAlchemy models
alembic revision --autogenerate -m "describe schema change"

# مراجعة SQL المولد ثم تطبيقه
alembic upgrade head

# الرجوع Revision واحدة محليًا فقط عند الحاجة
alembic downgrade -1

# اختبارات SQLite ونسخة الكتالوج المرجعية
pytest -q api/tests

# اختبار PostgreSQL اختياري محليًا؛ يتطلب قاعدة مؤقتة قابلة للحذف
POSTGRES_INTEGRATION_DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/dietary_test' \
  pytest -q api/tests/test_postgresql_schema_integration.py
```

## قواعد مهمة

كل تغيير للمخطط يكون في revision جديد قابل للمراجعة؛ لا تعدّل revision طُبق في بيئة مشتركة. أبقِ `DATABASE_URL` في متغيرات البيئة أو إعدادات Railway، ولا تضع بيانات الاتصال أو المفاتيح في `alembic.ini` أو المستودع. لا ترفع `.env` أو قاعدة تشغيل SQLite أو نسخة PostgreSQL أو نسخ المستخدمين الاحتياطية إلى Git. الاستثناء المقصود هو `data/catalog/food_catalog_reference.sqlite3`، وهو ملف كتالوج فقط للمراجعة وإعادة التهيئة.
