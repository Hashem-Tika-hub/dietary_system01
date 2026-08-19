# دليل Swagger ودمج Dietary Recommendation API

يقدّم المشروع توثيقًا تفاعليًا تلقائيًا عبر **Swagger UI** على المسار `/docs`، وتوثيقًا بديلًا للقراءة عبر `/redoc`، ومخططًا قياسيًا قابلًا للاستيراد عبر `/openapi.json`.

> استخدم Swagger في بيئة التطوير فقط مع عنوان خادم موثوق. لا تشارك رمز JWT أو ملف `.env` في لقطات الشاشة أو المستندات العامة.

## مسارات التوثيق

| الغرض | المسار |
|---|---|
| Swagger UI التفاعلي | `/docs` |
| ReDoc | `/redoc` |
| مخطط OpenAPI | `/openapi.json` |
| فحص الخدمة | `/health` |

## تسلسل الدمج الأساسي

ابدأ بإنشاء حساب عبر `POST /auth/register` أو سجّل دخولًا عبر `POST /auth/login`. ستستلم `access_token`. داخل Swagger اختر زر **Authorize** وأدخل:

```text
Bearer <access_token>
```

بعد المصادقة، حدّث ملف المستخدم من `PUT /users/profile`، ثم استخدم `GET /users/nutrition-targets` لعرض أهداف السعرات والمغذيات. بعد ذلك يمكن طلب وجبة عبر `POST /recommendations/meal` أو إنشاء خطة أسبوعية من `POST /recommendations/weekly`.

## مثال: طلب توصية لوجبة

```json
{
  "meal": "lunch",
  "top_k": 5
}
```

تحتوي الاستجابة على `ranking_basis` و`content_weight` و`collaborative_weight`. حاليًا يجب أن يكون `ranking_basis` مساويًا لـ`content_based` حتى تتوفر تفاعلات صريحة وحقيقية كافية. هذا يوضّح للواجهة الأمامية كيف اتخذ النظام قرار الترتيب بدل إخفاء حالة النموذج.

## إدارة سجل الوجبات

| العملية | endpoint |
|---|---|
| إضافة سجل | `POST /users/meal-logs` |
| عرض السجل | `GET /users/meal-logs` |
| عرض سجل واحد | `GET /users/meal-logs/{log_id}` |
| تحديث سجل | `PATCH /users/meal-logs/{log_id}` |
| حذف سجل | `DELETE /users/meal-logs/{log_id}` |
| ملخص الاستهلاك | `GET /users/meal-logs/summary` |

سجل الوجبة يصف ما تناوله المستخدم، لكنه لا يُفسّر تلقائيًا كتقييم إيجابي أو سلبي. لتغذية نموذج Collaborative Filtering، استخدم `POST /users/food-feedback` مع أحد الأحداث `like` أو `dislike` أو `save` أو `not_interested`. تعرض `GET /users/food-feedback/readiness` سبب بقاء النموذج في وضع cold start أو انتقاله إلى الوضع الجاهز.

## تفسير القيود

تُطبَّق الحساسية وملاءمة الوجبة والقيود الصحية كمرشحات صلبة قبل الترتيب. لا يمكن لدرجة نموذج تعلم الآلة تجاوز عنصر مرفوض بقاعدة أمان. يجب أن تعرض الواجهة أي رسالة تفيد بعدم وجود مرشحات آمنة، بدل عرض بديل غير مناسب.

## شروط تفعيل Collaborative Filtering

لا تصبح الدرجة التعاونية فعالة لمجرد وجود سجل وجبات. يشترط النموذج الحالي حدًا أدنى محافظًا: **10 تفاعلات صريحة** موزعة على **3 مستخدمين** و**3 أطعمة** على الأقل، مع وجود تفاعلين صريحين على الأقل للمستخدم الطالب. قبل ذلك، تظل `ranking_basis` مساوية لـ`content_based`.
