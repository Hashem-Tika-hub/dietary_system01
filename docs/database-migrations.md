# إدارة ترحيلات قاعدة البيانات

يستخدم المشروع الآن **Alembic** لإدارة مخطط قاعدة البيانات. لا ينشئ الخادم الجداول ولا يعدلها عند بدء التشغيل؛ يجب تطبيق الترحيلات صراحة قبل تشغيل الـAPI.

## بيئة جديدة أو قاعدة بيانات فارغة

بعد ضبط `DATABASE_URL` عند الحاجة، نفّذ:

```bash
alembic upgrade head
python run_api.py
```

ينشئ الأمر جداول `users` و`meal_logs` و`weekly_plans` وجدول `alembic_version` الذي يسجل آخر revision مطبق.

## قاعدة بيانات محلية موجودة مسبقًا

لا تشغّل `alembic stamp head` تلقائيًا على قاعدة إنتاج أو قاعدة لا تعرف مخططها. أولًا أنشئ نسخة احتياطية، ثم تحقق أن الجداول والأعمدة تطابق revision الأول (`786a3450d5e4`). بعد ذلك فقط يمكن تسجيلها كقاعدة مُدارة دون إعادة إنشاء الجداول:

```bash
cp data/dietary.db data/backups/dietary-before-alembic.db
alembic stamp 786a3450d5e4
alembic current
```

إذا اختلف المخطط، أنشئ migration مناسبًا أو انقل البيانات في بيئة اختبار؛ لا تعدل الجداول يدويًا وقت تشغيل التطبيق.

## أوامر المطور اليومية

```bash
# تطبيق جميع الترحيلات
alembic upgrade head

# عرض الإصدار الحالي
alembic current

# إنشاء revision بعد تعديل SQLAlchemy models
alembic revision --autogenerate -m "describe schema change"

# مراجعة SQL المولد ثم تطبيقه
alembic upgrade head

# الرجوع Revision واحدة محليًا فقط عند الحاجة
alembic downgrade -1

# تشغيل اختبارات الترحيلات
pytest api/tests/test_database_migrations.py -q
```

## قواعد مهمة

كل تغيير للمخطط يجب أن يكون في revision جديد قابل للمراجعة. لا تعدّل revision طُبّق في بيئة مشتركة. أبقِ `DATABASE_URL` في متغيرات البيئة أو منصة النشر، ولا تضع بيانات الاتصال أو المفاتيح في `alembic.ini` أو المستودع.
