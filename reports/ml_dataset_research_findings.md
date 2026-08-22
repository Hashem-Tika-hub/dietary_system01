# نتائج بحث مختصرة: متطلبات بيانات نموذج توصية غذائي شخصي

## مبادئ موثقة

1. **التصفية التعاونية** تعتمد على بيانات تفاعل المستخدم–العنصر، ويمكن أن تكون هذه البيانات صريحة مثل التقييم أو الإعجاب، أو ضمنية مثل النقر والمشاهدة. التفاعل الضمني قد يكون مشوشًا؛ لذلك لا يكفي سجل الاستهلاك وحده للدلالة على التفضيل. [1]
2. **التغذية الراجعة الصريحة** مناسبة لتعلم التفضيلات، لكن نظام التوصية يحتاج أيضًا معالجة مشكلة البدء البارد للمستخدمين أو العناصر الجديدة؛ ومن المناسب الإبقاء على Content-Based Filtering كبديل أولي. [1] [2]
3. يمثل **Collaborative Filtering القائم على الجيران** نموذجًا صالحًا كبداية، بينما تصبح Matrix Factorization أو النماذج العميقة أنسب عند زيادة حجم البيانات وكثافتها وتنوعها. [1]
4. تتطلب التوصية الغذائية الشخصية بيانات عالية الجودة وسياقًا فرديًا، كما أن الشفافية والخصوصية والتحقق الخبروي عناصر أساسية عند الاقتراب من حالات صحية. [3]
5. يقدم العمل البحثي PROTEIN AI Advisor مثالًا على قيمة الوجبات المعتمدة من خبراء في بناء إطار توصية غذائي قائم على المعرفة؛ وهو يدعم قرار اعتماد مسار expert-validated labels بدل اختراع تسميات من قواعد داخلية. [4]

## أثر ذلك على المشروع

- بيانات `synthetic_users.csv` مفيدة للاختبار الوظيفي فقط، وليست دليلًا على تعميم نموذج شخصي على مستخدمين حقيقيين.
- بيانات الأطعمة الحالية تصلح كتالوجًا للمحتوى والقيود والمغذيات، لا كبيانات تدريب Supervised Learning لأن كل صف لا يملك label خبيرًا يحدد ملاءمته لشخص محدد.
- المسار الآمن الحالي هو: **قيود صلبة → Content-Based Filtering → Collaborative Filtering من تفاعلات صريحة حقيقية عند الجاهزية**.
- أي تدريب Supervised يقتضي جدول أمثلة مستقلًا يربط خصائص مستخدم مجهول الهوية بوجبة أو خطة موصى بها من مختص، أو بنتيجة قبول/التزام لاحقة محددة زمنيًا.

## المراجع

[1] [Dive into Deep Learning — Recommender Systems Overview](https://d2l.ai/chapter_recommender-systems/recsys-intro.html)

[2] [Google Machine Learning — Collaborative Filtering](https://developers.google.com/machine-learning/recommendation/collaborative/basics)

[3] [Artificial intelligence in personalized nutrition and food manufacturing: a comprehensive review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12325300/)

[4] [PROTEIN AI Advisor: A Knowledge-Based Recommendation Framework Using Expert-Validated Meals for Healthy Diets](https://www.mdpi.com/2072-6643/14/20/4435)
